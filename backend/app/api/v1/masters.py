"""Companies, case types, form templates and document templates."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, require_permissions
from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.documents import docx_renderer
from app.models.case import Case
from app.models.company import CaseType, Company
from app.models.document import DocumentTemplate
from app.models.enums import AuditAction, CaseCategory, DocumentTemplateStatus
from app.models.form import FormField, FormSection, FormTemplate
from app.models.user import User
from app.schemas.common import IdResponse, Message
from app.schemas.form import FormTemplateDetailOut, FormTemplateIn, FormTemplateOut
from app.schemas.misc import (
    CaseTypeIn,
    CaseTypeOut,
    CompanyIn,
    CompanyOut,
    DocumentTemplateOut,
)
from app.services import audit_service
from app.utils.files import (
    build_stored_name,
    relative_to_storage,
    resolve_storage_path,
    sha256_bytes,
    write_bytes,
)
from app.utils.text import safe_filename, slugify

router = APIRouter(tags=["Companies & Templates"])

ViewCompany = Annotated[User, Depends(require_permissions("company.view"))]
ManageCompany = Annotated[User, Depends(require_permissions("company.manage"))]
ViewTemplate = Annotated[User, Depends(require_permissions("template.view"))]
ManageTemplate = Annotated[User, Depends(require_permissions("template.manage"))]


# --------------------------------------------------------------------------- #
# Companies
# --------------------------------------------------------------------------- #
@router.get("/companies", response_model=list[CompanyOut])
async def list_companies(
    session: DbSession,
    user: ViewCompany,
    include_inactive: bool = Query(False),
) -> list[CompanyOut]:
    statement = select(Company).order_by(Company.short_name)
    if not include_inactive:
        statement = statement.where(Company.is_active.is_(True))
    companies = (await session.execute(statement)).scalars().all()

    case_counts = dict(
        (
            await session.execute(select(Case.company_id, func.count()).group_by(Case.company_id))
        ).all()
    )
    from app.models.enums import CLOSED_STATUSES

    open_counts = dict(
        (
            await session.execute(
                select(Case.company_id, func.count())
                .where(Case.status.notin_(list(CLOSED_STATUSES)))
                .group_by(Case.company_id)
            )
        ).all()
    )
    form_counts = dict(
        (
            await session.execute(
                select(FormTemplate.company_id, func.count()).group_by(FormTemplate.company_id)
            )
        ).all()
    )
    doc_counts = dict(
        (
            await session.execute(
                select(DocumentTemplate.company_id, func.count()).group_by(
                    DocumentTemplate.company_id
                )
            )
        ).all()
    )

    return [
        CompanyOut(
            **{
                key: getattr(company, key)
                for key in (
                    "id",
                    "code",
                    "name",
                    "short_name",
                    "company_type",
                    "import_aliases",
                    "address",
                    "city",
                    "state",
                    "pin_code",
                    "contact_person",
                    "email",
                    "phone",
                    "logo_path",
                    "default_tat_days",
                    "is_active",
                    "notes",
                )
            },
            total_cases=int(case_counts.get(company.id, 0)),
            open_cases=int(open_counts.get(company.id, 0)),
            form_template_count=int(form_counts.get(company.id, 0)),
            document_template_count=int(doc_counts.get(company.id, 0)),
        )
        for company in companies
    ]


@router.post("/companies", response_model=IdResponse, status_code=201)
async def create_company(
    payload: CompanyIn, request: Request, session: DbSession, user: ManageCompany
) -> IdResponse:
    existing = (
        await session.execute(
            select(Company).where(func.lower(Company.code) == payload.code.lower())
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(f"Company code {payload.code} is already in use.")
    company = Company(**payload.model_dump())
    session.add(company)
    await session.flush()
    await audit_service.record(
        session,
        action=AuditAction.COMPANY_CHANGED,
        module="Companies",
        actor=user,
        entity_type="Company",
        entity_id=company.id,
        entity_label=company.name,
        new_values=payload.model_dump(),
        request=request,
    )
    await session.commit()
    return IdResponse(id=company.id, message="Company created.")


@router.patch("/companies/{company_id}", response_model=Message)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyIn,
    request: Request,
    session: DbSession,
    user: ManageCompany,
) -> Message:
    company = await session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Company not found.")
    changes = payload.model_dump()
    before = {key: getattr(company, key) for key in changes}
    for key, value in changes.items():
        setattr(company, key, value)
    old_values, new_values = audit_service.diff(before, changes)
    await audit_service.record(
        session,
        action=AuditAction.COMPANY_CHANGED,
        module="Companies",
        actor=user,
        entity_type="Company",
        entity_id=company.id,
        entity_label=company.name,
        old_values=old_values,
        new_values=new_values,
        request=request,
    )
    await session.commit()
    return Message(message="Company updated.")


# --------------------------------------------------------------------------- #
# Case types
# --------------------------------------------------------------------------- #
@router.get("/case-types", response_model=list[CaseTypeOut])
async def list_case_types(
    session: DbSession,
    user: ViewCompany,
    category: CaseCategory | None = Query(None),
    include_inactive: bool = Query(False),
) -> list[CaseTypeOut]:
    statement = select(CaseType).order_by(CaseType.display_order, CaseType.name)
    if category:
        statement = statement.where(CaseType.category == category)
    if not include_inactive:
        statement = statement.where(CaseType.is_active.is_(True))
    rows = (await session.execute(statement)).scalars().all()
    counts = dict(
        (
            await session.execute(
                select(Case.case_type_id, func.count()).group_by(Case.case_type_id)
            )
        ).all()
    )
    return [
        CaseTypeOut(
            **{
                key: getattr(row, key)
                for key in (
                    "id",
                    "code",
                    "name",
                    "category",
                    "description",
                    "import_aliases",
                    "default_tat_days",
                    "display_order",
                    "is_active",
                )
            },
            total_cases=int(counts.get(row.id, 0)),
        )
        for row in rows
    ]


@router.post("/case-types", response_model=IdResponse, status_code=201)
async def create_case_type(
    payload: CaseTypeIn, session: DbSession, user: ManageCompany
) -> IdResponse:
    row = CaseType(**payload.model_dump())
    session.add(row)
    await session.commit()
    return IdResponse(id=row.id, message="Case type created.")


@router.patch("/case-types/{case_type_id}", response_model=Message)
async def update_case_type(
    case_type_id: uuid.UUID,
    payload: CaseTypeIn,
    session: DbSession,
    user: ManageCompany,
) -> Message:
    row = await session.get(CaseType, case_type_id)
    if row is None:
        raise NotFoundError("Case type not found.")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await session.commit()
    return Message(message="Case type updated.")


# --------------------------------------------------------------------------- #
# Form templates
# --------------------------------------------------------------------------- #
@router.get("/form-templates", response_model=list[FormTemplateOut])
async def list_form_templates(
    session: DbSession,
    user: ViewTemplate,
    company_id: uuid.UUID | None = Query(None),
    case_type_id: uuid.UUID | None = Query(None),
) -> list[FormTemplateOut]:
    statement = (
        select(FormTemplate)
        .options(
            selectinload(FormTemplate.company),
            selectinload(FormTemplate.case_type),
            selectinload(FormTemplate.sections).selectinload(FormSection.fields),
        )
        .order_by(FormTemplate.name, FormTemplate.version.desc())
    )
    if company_id:
        statement = statement.where(FormTemplate.company_id == company_id)
    if case_type_id:
        statement = statement.where(FormTemplate.case_type_id == case_type_id)
    rows = (await session.execute(statement)).unique().scalars().all()
    return [_template_summary(row) for row in rows]


def _template_summary(template: FormTemplate) -> FormTemplateOut:
    return FormTemplateOut(
        id=template.id,
        code=template.code,
        name=template.name,
        company_id=template.company_id,
        company_name=template.company.short_name if template.company else None,
        case_type_id=template.case_type_id,
        case_type_name=template.case_type.name if template.case_type else None,
        case_category=template.case_type.category if template.case_type else None,
        version=template.version,
        is_active=template.is_active,
        description=template.description,
        source_document=template.source_document,
        section_count=len(template.sections),
        field_count=sum(len(section.fields) for section in template.sections),
        created_at=template.created_at,
    )


@router.get("/form-templates/{template_id}", response_model=FormTemplateDetailOut)
async def get_form_template(
    template_id: uuid.UUID, session: DbSession, user: ViewTemplate
) -> FormTemplateDetailOut:
    result = await session.execute(
        select(FormTemplate)
        .options(
            selectinload(FormTemplate.company),
            selectinload(FormTemplate.case_type),
            selectinload(FormTemplate.sections).selectinload(FormSection.fields),
        )
        .where(FormTemplate.id == template_id)
    )
    template = result.unique().scalar_one_or_none()
    if template is None:
        raise NotFoundError("Form template not found.")
    summary = _template_summary(template)
    return FormTemplateDetailOut(**summary.model_dump(), sections=template.sections)


@router.post("/form-templates", response_model=IdResponse, status_code=201)
async def create_form_template(
    payload: FormTemplateIn,
    request: Request,
    session: DbSession,
    user: ManageTemplate,
) -> IdResponse:
    """Create the next version of a company's form layout.

    Existing versions are never mutated — completed cases keep rendering the
    version they were filled under.
    """
    latest = (
        await session.execute(
            select(func.max(FormTemplate.version)).where(
                FormTemplate.company_id == payload.company_id,
                FormTemplate.case_type_id == payload.case_type_id,
            )
        )
    ).scalar_one_or_none()
    version = int(latest or 0) + 1

    if payload.is_active:
        # Only one active version per company + case type.
        previous = (
            (
                await session.execute(
                    select(FormTemplate).where(
                        FormTemplate.company_id == payload.company_id,
                        FormTemplate.case_type_id == payload.case_type_id,
                        FormTemplate.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in previous:
            row.is_active = False

    template = FormTemplate(
        code=payload.code,
        name=payload.name,
        company_id=payload.company_id,
        case_type_id=payload.case_type_id,
        version=version,
        is_active=payload.is_active,
        description=payload.description,
    )
    session.add(template)
    await session.flush()

    for section_index, section_payload in enumerate(payload.sections):
        section = FormSection(
            template_id=template.id,
            key=section_payload.key,
            title=section_payload.title,
            description=section_payload.description,
            display_order=section_payload.display_order or section_index,
            is_repeatable=section_payload.is_repeatable,
            visible_when=section_payload.visible_when,
        )
        session.add(section)
        await session.flush()
        for field_index, field_payload in enumerate(section_payload.fields):
            session.add(
                FormField(
                    section_id=section.id,
                    **{
                        **field_payload.model_dump(),
                        "display_order": field_payload.display_order or field_index,
                    },
                )
            )

    await audit_service.record(
        session,
        action=AuditAction.TEMPLATE_CHANGED,
        module="Templates",
        actor=user,
        entity_type="FormTemplate",
        entity_id=template.id,
        entity_label=f"{template.name} v{version}",
        new_values={"version": version, "sections": len(payload.sections)},
        request=request,
    )
    await session.commit()
    return IdResponse(id=template.id, message=f"Form template v{version} created.")


@router.post("/form-templates/{template_id}/activate", response_model=Message)
async def activate_form_template(
    template_id: uuid.UUID,
    request: Request,
    session: DbSession,
    user: ManageTemplate,
) -> Message:
    template = await session.get(FormTemplate, template_id)
    if template is None:
        raise NotFoundError("Form template not found.")
    siblings = (
        (
            await session.execute(
                select(FormTemplate).where(
                    FormTemplate.company_id == template.company_id,
                    FormTemplate.case_type_id == template.case_type_id,
                )
            )
        )
        .scalars()
        .all()
    )
    for row in siblings:
        row.is_active = row.id == template.id
    await audit_service.record(
        session,
        action=AuditAction.TEMPLATE_CHANGED,
        module="Templates",
        actor=user,
        entity_type="FormTemplate",
        entity_id=template.id,
        entity_label=f"{template.name} v{template.version}",
        new_values={"is_active": True},
        request=request,
    )
    await session.commit()
    return Message(message=f"Version {template.version} is now the active template.")


# --------------------------------------------------------------------------- #
# Document templates
# --------------------------------------------------------------------------- #
@router.get("/document-templates", response_model=list[DocumentTemplateOut])
async def list_document_templates(
    session: DbSession,
    user: ViewTemplate,
    company_id: uuid.UUID | None = Query(None),
) -> list[DocumentTemplateOut]:
    statement = (
        select(DocumentTemplate)
        .options(
            selectinload(DocumentTemplate.company),
            selectinload(DocumentTemplate.case_type),
        )
        .order_by(DocumentTemplate.name, DocumentTemplate.version.desc())
    )
    if company_id:
        statement = statement.where(DocumentTemplate.company_id == company_id)
    rows = (await session.execute(statement)).scalars().all()
    return [
        DocumentTemplateOut(
            id=row.id,
            code=row.code,
            name=row.name,
            company_id=row.company_id,
            company_name=row.company.short_name if row.company else None,
            case_type_id=row.case_type_id,
            case_type_name=row.case_type.name if row.case_type else None,
            version=row.version,
            status=row.status,
            original_filename=row.original_filename,
            has_tagged_copy=bool(row.tagged_path),
            can_generate_docx=row.can_generate_docx,
            size_bytes=row.size_bytes,
            placeholder_count=len(row.placeholder_map or {}),
            notes=row.notes,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/document-templates", response_model=IdResponse, status_code=201)
async def upload_document_template(
    request: Request,
    session: DbSession,
    user: ManageTemplate,
    file: Annotated[UploadFile, File(description="The insurer's .docx form")],
    company_id: Annotated[uuid.UUID, Form()],
    case_type_id: Annotated[uuid.UUID, Form()],
    name: Annotated[str, Form()],
    notes: Annotated[str | None, Form()] = None,
) -> IdResponse:
    """Register a new version of a client's Word form.

    The uploaded file is kept forever as ``original``; if it already carries
    ``{{ placeholders }}`` it is usable for generation immediately, otherwise an
    administrator runs ``scripts/tag_templates.py`` to produce the tagged copy.
    """
    payload = await file.read()
    if not payload:
        raise ValidationError("The uploaded file is empty.")
    if len(payload) > settings.max_upload_bytes:
        raise ValidationError(f"Template is larger than the {settings.MAX_UPLOAD_MB} MB limit.")

    company = await session.get(Company, company_id)
    case_type = await session.get(CaseType, case_type_id)
    if company is None or case_type is None:
        raise ValidationError("Unknown company or case type.")

    filename = safe_filename(file.filename or "template.docx")
    is_docx = payload.startswith(b"PK\x03\x04")

    latest = (
        await session.execute(
            select(func.max(DocumentTemplate.version)).where(
                DocumentTemplate.company_id == company_id,
                DocumentTemplate.case_type_id == case_type_id,
            )
        )
    ).scalar_one_or_none()
    version = int(latest or 0) + 1

    stored_name = build_stored_name(
        ".docx" if is_docx else ".doc",
        prefix=f"{slugify(company.code, '_')}_{slugify(case_type.code, '_')}_v{version}",
    )
    original_path = write_bytes(settings.template_originals_dir, stored_name, payload)

    tagged_relative: str | None = None
    placeholders: dict[str, str] = {}
    if is_docx:
        found = docx_renderer.list_placeholders(original_path)
        if found:
            # The upload already is a tagged template — use it directly.
            tagged_path = write_bytes(settings.template_tagged_dir, stored_name, payload)
            tagged_relative = relative_to_storage(tagged_path)
            placeholders = dict.fromkeys(found, "")

    template = DocumentTemplate(
        code=f"{company.code}_{case_type.code}",
        name=name,
        company_id=company_id,
        case_type_id=case_type_id,
        version=version,
        status=(
            DocumentTemplateStatus.ACTIVE if is_docx else DocumentTemplateStatus.NEEDS_CONVERSION
        ),
        original_filename=filename,
        original_path=relative_to_storage(original_path),
        tagged_path=tagged_relative,
        checksum_sha256=sha256_bytes(payload),
        size_bytes=len(payload),
        placeholder_map=placeholders or None,
        notes=notes,
        uploaded_by_id=user.id,
    )
    session.add(template)
    await session.flush()

    await audit_service.record(
        session,
        action=AuditAction.TEMPLATE_CHANGED,
        module="Templates",
        actor=user,
        entity_type="DocumentTemplate",
        entity_id=template.id,
        entity_label=f"{name} v{version}",
        new_values={
            "filename": filename,
            "version": version,
            "status": template.status.value,
        },
        request=request,
    )
    await session.commit()

    message = f"Template version {version} uploaded."
    if not is_docx:
        message += " It is a legacy .doc file — re-save it as .docx to enable Word generation."
    elif not tagged_relative:
        message += " No placeholders were found; run scripts/tag_templates.py to tag it."
    return IdResponse(id=template.id, message=message)


@router.get("/document-templates/{template_id}/download")
async def download_document_template(
    template_id: uuid.UUID,
    session: DbSession,
    user: ViewTemplate,
    tagged: bool = Query(False, description="Download the tagged copy instead"),
) -> FileResponse:
    template = await session.get(DocumentTemplate, template_id)
    if template is None:
        raise NotFoundError("Document template not found.")
    relative = template.tagged_path if tagged else template.original_path
    if not relative:
        raise NotFoundError("No tagged copy exists for this template.")
    path = resolve_storage_path(relative)
    if not path.exists():
        raise NotFoundError("The template file is missing from storage.")
    return FileResponse(
        path,
        media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        filename=template.original_filename,
    )
