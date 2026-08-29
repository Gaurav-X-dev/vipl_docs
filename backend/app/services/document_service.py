"""Case evidence uploads and generation of the completed client document."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.documents import docx_renderer, pdf_renderer
from app.documents.context import build_context
from app.models.case import Case, CaseDocument
from app.models.document import DocumentTemplate, GeneratedDocument
from app.models.enums import (
    AuditAction,
    CaseStatus,
    DocumentCategory,
    DocumentTemplateStatus,
    GeneratedFormat,
)
from app.models.user import User
from app.services import audit_service, form_service, settings_service
from app.services.case_workflow import status_label
from app.utils.dates import format_date, utcnow
from app.utils.files import (
    build_stored_name,
    dated_subdir,
    relative_to_storage,
    resolve_storage_path,
    sha256_bytes,
    validate_evidence_upload,
    write_bytes,
)
from app.utils.text import safe_filename, slugify

#: Cases must be at least verified before the client form can be produced.
GENERATION_READY_STATUSES = {CaseStatus.VERIFIED, CaseStatus.COMPLETED}


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #
async def upload_evidence(
    session: AsyncSession,
    case: Case,
    *,
    filename: str,
    content_type: str,
    payload: bytes,
    category: DocumentCategory,
    description: str | None,
    geo_latitude: float | None,
    geo_longitude: float | None,
    actor: User,
    request: Request | None = None,
) -> CaseDocument:
    extension, resolved_type = validate_evidence_upload(filename, content_type, payload)

    display_name = safe_filename(filename)
    result = await session.execute(
        select(CaseDocument).where(
            CaseDocument.case_id == case.id,
            CaseDocument.display_name == display_name,
        )
    )
    version = len(list(result.scalars().all())) + 1

    stored_name = build_stored_name(extension, prefix=slugify(case.case_number, "_"))
    target_dir = dated_subdir(settings.case_documents_dir)
    path = write_bytes(target_dir, stored_name, payload)

    document = CaseDocument(
        case_id=case.id,
        uploaded_by_id=actor.id,
        category=category,
        display_name=display_name,
        stored_name=stored_name,
        relative_path=relative_to_storage(path),
        content_type=resolved_type,
        size_bytes=len(payload),
        checksum_sha256=sha256_bytes(payload),
        description=description,
        geo_latitude=geo_latitude,
        geo_longitude=geo_longitude,
        version=version,
    )
    session.add(document)

    await audit_service.record(
        session,
        action=AuditAction.DOCUMENT_UPLOADED,
        module="Cases",
        actor=actor,
        entity_type="CaseDocument",
        entity_id=case.id,
        entity_label=f"{case.case_number} / {display_name}",
        new_values={"filename": display_name, "size_bytes": len(payload)},
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="DOCUMENT_UPLOADED",
        summary=f"Evidence uploaded: {display_name}",
        detail=description,
        actor=actor,
        icon="paperclip",
    )
    return document


async def delete_evidence(
    session: AsyncSession,
    document: CaseDocument,
    *,
    actor: User,
    request: Request | None = None,
) -> None:
    await audit_service.record(
        session,
        action=AuditAction.DOCUMENT_DELETED,
        module="Cases",
        actor=actor,
        entity_type="CaseDocument",
        entity_id=document.id,
        entity_label=document.display_name,
        old_values={"filename": document.display_name},
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=document.case_id,
        event_type="DOCUMENT_DELETED",
        summary=f"Evidence removed: {document.display_name}",
        actor=actor,
        icon="trash",
    )
    # The row goes; the blob is left in place so an accidental delete is
    # recoverable from storage and the checksum trail stays meaningful.
    await session.delete(document)


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
async def active_template(
    session: AsyncSession, company_id: uuid.UUID, case_type_id: uuid.UUID
) -> DocumentTemplate | None:
    result = await session.execute(
        select(DocumentTemplate)
        .options(
            selectinload(DocumentTemplate.company),
            selectinload(DocumentTemplate.case_type),
        )
        .where(
            DocumentTemplate.company_id == company_id,
            DocumentTemplate.case_type_id == case_type_id,
            DocumentTemplate.status != DocumentTemplateStatus.INACTIVE,
        )
        .order_by(DocumentTemplate.version.desc())
    )
    return result.scalars().first()


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
async def generate_document(
    session: AsyncSession,
    case: Case,
    *,
    output_format: GeneratedFormat,
    actor: User,
    force: bool = False,
    request: Request | None = None,
) -> GeneratedDocument:
    """Produce the completed client form for a case.

    Picks the template by ``(company, case type)`` and pins the version onto the
    generated record, so re-running the same case later never silently switches
    to a newer revision of the insurer's form.
    """
    if case.status not in GENERATION_READY_STATUSES and not force:
        raise ConflictError(
            "The client form can only be generated once the case is verified or "
            f"completed. This case is {status_label(case.status)}.",
        )

    template = await active_template(session, case.company_id, case.case_type_id)
    case_form = await form_service.get_case_form(session, case, create_if_missing=False)
    settings_map = await settings_service.as_dict(session)
    context = build_context(
        case,
        case_form,
        settings_map=settings_map,
        form_values=form_service.document_context(case_form),
        generated_by=actor.full_name,
    )

    stem = "_".join(
        part
        for part in (
            slugify(case.life_assured_name or "", "_"),
            slugify(case.case_number, "_"),
        )
        if part
    )
    output_dir = dated_subdir(settings.generated_documents_dir)
    used_client_template = False

    if output_format == GeneratedFormat.DOCX:
        if template is None or not template.can_generate_docx:
            raise ValidationError(
                _no_docx_message(template, case),
            )
        stored_name = build_stored_name(".docx", prefix=stem)
        path = docx_renderer.render(
            resolve_storage_path(template.tagged_path),
            context,
            output_dir / stored_name,
        )
        used_client_template = True
    else:
        stored_name = build_stored_name(".pdf", prefix=stem)
        path = None
        # Prefer converting the client's own DOCX so their layout survives.
        if template is not None and template.can_generate_docx:
            interim = docx_renderer.render(
                resolve_storage_path(template.tagged_path),
                context,
                output_dir / f"{stem}_interim.docx",
            )
            converted = pdf_renderer.convert_docx(interim, output_dir)
            interim.unlink(missing_ok=True)
            if converted is not None:
                path = converted.rename(output_dir / stored_name)
                used_client_template = True
        if path is None:
            path = _render_fallback_pdf(case, context, output_dir / stored_name)

    payload = path.read_bytes()
    # The client files reports by the person they are about, so the subject's
    # name leads the filename and the case number follows it for uniqueness.
    subject = (case.life_assured_name or "").strip()
    display_name = (
        f"{subject} - {case.case_number} - {case.company.short_name} "
        f"{case.case_type.name}{path.suffix}"
        if subject
        else f"{case.case_number} - {case.company.short_name} {case.case_type.name}{path.suffix}"
    )

    document = GeneratedDocument(
        case_id=case.id,
        template_id=template.id if template else None,
        template_version=template.version if template else None,
        output_format=output_format,
        display_name=safe_filename(display_name),
        stored_name=path.name,
        relative_path=relative_to_storage(path),
        size_bytes=len(payload),
        checksum_sha256=sha256_bytes(payload),
        generated_by_id=actor.id,
        generated_at=utcnow(),
        used_client_template=used_client_template,
    )
    # Keep relationships available to the response serializer without an
    # implicit async lazy-load after commit.
    document.template = template
    document.generated_by = actor
    session.add(document)

    await audit_service.record(
        session,
        action=AuditAction.DOCUMENT_GENERATED,
        module="Documents",
        actor=actor,
        entity_type="GeneratedDocument",
        entity_id=case.id,
        entity_label=case.case_number,
        new_values={
            "format": output_format.value,
            "template": template.code if template else None,
            "template_version": template.version if template else None,
            "used_client_template": used_client_template,
        },
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="DOCUMENT_GENERATED",
        summary=f"{output_format.value} generated from {template.name if template else 'the built-in report layout'}",
        detail=f"Template version {template.version}" if template else None,
        actor=actor,
        icon="download",
    )
    return document


def _no_docx_message(template: DocumentTemplate | None, case: Case) -> str:
    if template is None:
        return (
            f"No document template is configured for {case.company.short_name} / "
            f"{case.case_type.name}. Upload the insurer's form under "
            "Administration → Document Templates, or download the PDF instead."
        )
    if template.status == DocumentTemplateStatus.NEEDS_CONVERSION:
        return (
            f"'{template.original_filename}' is a legacy binary .doc file, which "
            "cannot be filled programmatically. Re-save it as .docx and upload it "
            "as a new version, or download the PDF instead."
        )
    return (
        f"The template '{template.name}' has no tagged copy yet. Run "
        "scripts/tag_templates.py, or re-upload the template."
    )


def _render_fallback_pdf(case: Case, context: dict[str, Any], output_path: Path) -> Path:
    """Self-contained PDF used when the client's DOCX cannot be rendered."""
    header_rows = [
        ("Case number", case.case_number),
        ("Company", case.company.name),
        ("Case type", case.case_type.name),
        (
            "Policy / application no.",
            f"{case.policy_number or '-'} / {case.application_number or '-'}",
        ),
        ("KRN", case.krn_no or "-"),
        ("Life assured", case.life_assured_name),
        ("Address", case.address or "-"),
        (
            "City / State / PIN",
            f"{case.city or '-'} / {case.state or '-'} / {case.pin_code or '-'}",
        ),
        ("Contact", case.contact_number or "-"),
    ]

    sections: list[dict[str, Any]] = [
        {
            "title": "Investigation summary",
            "rows": [
                ("Investigating agency", context.get("agency_name")),
                ("Field investigator", context.get("field_investigator_name") or "-"),
                ("Case received", format_date(case.received_at)),
                ("Assigned on", format_date(case.assigned_at)),
                ("Report submitted", format_date(case.submitted_at)),
                ("Completed on", format_date(case.completed_at)),
                ("Turn around time", context.get("tat_days") or "-"),
                ("Outcome", context.get("outcome") or "-"),
                ("Report status", context.get("report_status") or "-"),
            ],
        }
    ]

    if case.death_claim is not None:
        death = case.death_claim
        sections.append(
            {
                "title": "Claim details",
                "rows": [
                    ("Claimant", death.claimant_name or "-"),
                    ("Relation with LA", death.claimant_relation or "-"),
                    ("Claimant contact", death.claimant_contact or "-"),
                    ("Date of death", format_date(death.date_of_death)),
                    ("Place of death", death.place_of_death or "-"),
                    ("Cause of death", death.cause_of_death or "-"),
                    ("Standard of living", death.standard_of_living or "-"),
                    (
                        "Death certificate verified",
                        "Yes" if death.death_certificate_verified else "No",
                    ),
                ],
            }
        )
        sections.append(
            {
                "title": "Key sensing of the case",
                "headers": ["Observation", "Status"],
                "table": [
                    ["Profile mismatch", death.profile_mismatch or "-"],
                    ["Medical non-disclosure", death.medical_non_disclosure or "-"],
                    ["Death before issuance", death.death_before_issuance or "-"],
                    ["Impersonation", death.impersonation or "-"],
                    ["Forged / tampered documents", death.forged_documents or "-"],
                    ["Nexus involvement", death.nexus_involvement or "-"],
                    ["Industry shopping", death.industry_shopping or "-"],
                    ["Other adverse findings", death.other_adverse_findings or "-"],
                    ["No adverse findings", death.no_adverse_findings or "-"],
                ],
            }
        )

    # Everything captured through the dynamic form, section by section.
    form_sections = context.get("__form_sections__")
    if isinstance(form_sections, list):
        sections.extend(form_sections)

    if case.outcome_reason:
        sections.append({"title": "Conclusion", "text": case.outcome_reason})

    return pdf_renderer.render_report(
        output_path,
        title=f"{case.company.short_name} — {case.case_type.name}",
        subtitle=(
            f"{context.get('agency_name', '')} · Case {case.case_number} · "
            f"Generated {format_date(utcnow())}"
        ),
        header_rows=header_rows,
        sections=sections,
        footer_note=(
            "This report was generated by the Investigation Management System. "
            "Contents are confidential and intended solely for the commissioning client."
        ),
    )


async def build_form_sections_for_pdf(session: AsyncSession, case: Case) -> list[dict[str, Any]]:
    """Render the dynamic form into PDF-ready section blocks."""
    case_form = await form_service.get_case_form(session, case, create_if_missing=False)
    if case_form is None or case_form.template is None:
        return []
    values = {row.field_key: row for row in case_form.values}
    blocks: list[dict[str, Any]] = []
    for section in case_form.template.sections:
        rows: list[tuple[str, Any]] = []
        for field in section.fields:
            row = values.get(field.field_key)
            if row is None:
                continue
            value = row.value_text
            if value in (None, "") and row.value_json is None:
                continue
            if row.value_json is not None:
                value = _flatten_table(row.value_json)
            rows.append((field.label, value))
        if rows:
            blocks.append({"title": section.title, "rows": rows})
    return blocks


def _flatten_table(value: Any) -> str:
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append("; ".join(f"{k}: {v}" for k, v in item.items() if v not in (None, "")))
            else:
                lines.append(str(item))
        return "\n".join(lines)
    return str(value)


async def get_evidence(session: AsyncSession, document_id: uuid.UUID) -> CaseDocument:
    document = await session.get(CaseDocument, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    return document


async def get_generated(session: AsyncSession, document_id: uuid.UUID) -> GeneratedDocument:
    result = await session.execute(
        select(GeneratedDocument)
        .options(selectinload(GeneratedDocument.template))
        .where(GeneratedDocument.id == document_id)
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError("Generated document not found.")
    return document
