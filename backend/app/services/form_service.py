"""Attaching form templates to cases, pre-filling bank data, and saving answers.

The key requirement from the brief: *"do not force investigators to re-enter data
already supplied by the bank"*. Every value carries its provenance
(:class:`FieldSource`) and the original bank value is retained even after an
investigator overwrites it.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.case import Case, CaseStatusHistory
from app.models.enums import (
    AuditAction,
    CaseFormStatus,
    CaseOutcome,
    CaseStatus,
    FieldSource,
    FieldType,
    ReportStatus,
)
from app.models.form import (
    CaseFieldValue,
    CaseFieldValueHistory,
    CaseForm,
    FormField,
    FormSection,
    FormTemplate,
)
from app.models.user import User
from app.services import audit_service
from app.utils.dates import format_date, utcnow
from app.utils.text import clean

#: Case columns an investigator must never silently overwrite from the form.
READONLY_PREFILL_SOURCES = {"case_number", "company_name", "case_type_name"}


async def find_active_template(
    session: AsyncSession, company_id: uuid.UUID, case_type_id: uuid.UUID
) -> FormTemplate | None:
    """Highest active version for this company + case type."""
    result = await session.execute(
        select(FormTemplate)
        .options(selectinload(FormTemplate.sections).selectinload(FormSection.fields))
        .where(
            FormTemplate.company_id == company_id,
            FormTemplate.case_type_id == case_type_id,
            FormTemplate.is_active.is_(True),
        )
        .order_by(FormTemplate.version.desc())
    )
    return result.scalars().first()


def case_attribute(case: Case, key: str) -> Any:
    """Resolve a ``prefill_from`` reference against the case graph."""
    if key in {"company_name", "company_short_name"}:
        return case.company.short_name if case.company else None
    if key == "company_code":
        return case.company.code if case.company else None
    if key in {"case_type_name", "case_type"}:
        return case.case_type.name if case.case_type else None
    if key == "assigned_to_name":
        return case.assigned_to.full_name if case.assigned_to else None
    if key.startswith("death_claim.") and case.death_claim is not None:
        return getattr(case.death_claim, key.split(".", 1)[1], None)
    return getattr(case, key, None)


def stringify(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, datetime):
        return format_date(value)
    if isinstance(value, date):
        return format_date(value)
    if isinstance(value, Decimal):
        normalised = value.normalize()
        return format(normalised, "f")
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


async def attach_template(
    session: AsyncSession,
    case: Case,
    *,
    actor: User | None,
    import_batch_id: uuid.UUID | None = None,
) -> CaseForm | None:
    """Attach the right template to a case and pre-fill everything we already know.

    Returns ``None`` when no template is configured for the company/case type —
    the case still works, it just has no structured form yet.
    """
    template = await find_active_template(session, case.company_id, case.case_type_id)
    if template is None:
        return None

    existing = await session.execute(
        select(CaseForm).where(CaseForm.case_id == case.id, CaseForm.template_id == template.id)
    )
    case_form = existing.scalar_one_or_none()
    if case_form is not None:
        return case_form

    case_form = CaseForm(
        case_id=case.id,
        template_id=template.id,
        template_version=template.version,
        status=CaseFormStatus.DRAFT,
    )
    session.add(case_form)
    await session.flush()

    prefilled = 0
    for section in template.sections:
        for field in section.fields:
            if not field.prefill_from:
                continue
            raw = case_attribute(case, field.prefill_from)
            text = stringify(raw)
            if text in (None, ""):
                continue
            source = field.source or FieldSource.BANK_SUPPLIED
            session.add(
                CaseFieldValue(
                    case_form_id=case_form.id,
                    field_id=field.id,
                    field_key=field.field_key,
                    value_text=text,
                    source=source,
                    # Client-supplied values are marked, not locked. Staff can
                    # correct a wrong policy number on the spot; the original
                    # is kept beside it and every edit is still audited, which
                    # is what the provenance is actually for.
                    is_locked=False,
                    original_value=text,
                    import_batch_id=import_batch_id or case.import_batch_id,
                    original_column=field.prefill_from,
                    imported_at=utcnow() if case.is_imported else None,
                )
            )
            prefilled += 1

    case_form.completion_percent = await _completion_percent(session, case_form, template)
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="FORM_ATTACHED",
        summary=f"{template.name} attached (v{template.version})",
        detail=(
            f"{prefilled} field(s) pre-filled from client-supplied data" if prefilled else None
        ),
        actor=actor,
        icon="file-text",
    )
    return case_form


async def get_case_form(
    session: AsyncSession, case: Case, *, create_if_missing: bool = True
) -> CaseForm | None:
    result = await session.execute(
        select(CaseForm)
        .options(
            selectinload(CaseForm.template)
            .selectinload(FormTemplate.sections)
            .selectinload(FormSection.fields),
            selectinload(CaseForm.values),
        )
        .where(CaseForm.case_id == case.id)
        .order_by(CaseForm.created_at.desc())
    )
    case_form = result.scalars().first()
    if case_form is None and create_if_missing:
        case_form = await attach_template(session, case, actor=None)
        if case_form is not None:
            await session.flush()
            return await get_case_form(session, case, create_if_missing=False)
    return case_form


def flatten_fields(template: FormTemplate) -> dict[str, FormField]:
    return {
        field.field_key: field
        for section in template.sections
        for field in section.fields
        if field.field_type != FieldType.HEADING
    }


#: Placeholder names that carry the case verdict. Every seeded template tags
#: its verdict field with one of these, so the case picks the answer up from
#: the form the investigator actually filled in.
OUTCOME_MAPPING = "outcome"
REPORT_STATUS_MAPPING = "report_status"


def outcome_fields(template: FormTemplate) -> list[FormField]:
    """The template's verdict fields, in the order they appear on screen."""
    return [
        field
        for section in template.sections
        for field in section.fields
        if field.document_mapping == OUTCOME_MAPPING
    ]


def _parse_outcome(raw: str | None) -> CaseOutcome | None:
    if not raw:
        return None
    token = str(raw).strip().upper().replace(" ", "_")
    for member in CaseOutcome:
        if token == member.value:
            return member
    return None


def _parse_report_status(raw: str | None) -> ReportStatus | None:
    if not raw:
        return None
    token = str(raw).strip().upper()
    for member in ReportStatus:
        if token == member.value:
            return member
    return None


def sync_case_verdict(
    case: Case, case_form: CaseForm, values: dict[str, str | None]
) -> bool:
    """Copy the form's verdict onto the case.

    A form asks "Report Overall Status" or "Investigation outcome"; the case
    carries the same answer as ``case.outcome`` for the dashboards, TAT tiles
    and status machine. Without this the investigator fills the form correctly
    and is still refused at submit, which is what used to happen.

    Where a template asks twice — a summary field near the top and a conclusion
    at the end — the later one wins, because that is the investigator's final
    word. Returns True when the case changed.
    """
    template = case_form.template
    if template is None:
        return False

    changed = False
    for section in template.sections:
        for field in section.fields:
            raw = values.get(field.field_key)
            if field.document_mapping == OUTCOME_MAPPING:
                parsed = _parse_outcome(raw)
                if parsed is not None and case.outcome != parsed:
                    case.outcome = parsed
                    changed = True
            elif field.document_mapping == REPORT_STATUS_MAPPING:
                parsed_status = _parse_report_status(raw)
                if parsed_status is not None and case.report_status != parsed_status:
                    case.report_status = parsed_status
                    changed = True
    return changed


def missing_outcome_hint(template: FormTemplate | None) -> str:
    """Name the field to fill, rather than telling the user to look elsewhere."""
    if template is None:
        return "Set the case outcome (Positive, Negative or Suspicious)."
    labels = [field.label for field in outcome_fields(template)]
    if not labels:
        return (
            "Set the case outcome (Positive, Negative or Suspicious) from the "
            "case header before submitting."
        )
    named = labels[-1]
    return (
        f'Choose Positive, Negative or Suspicious in "{named}" before '
        "submitting this report."
    )


async def _completion_percent(
    session: AsyncSession, case_form: CaseForm, template: FormTemplate
) -> int:
    fields = flatten_fields(template)
    if not fields:
        return 0
    result = await session.execute(
        select(CaseFieldValue.field_key, CaseFieldValue.value_text).where(
            CaseFieldValue.case_form_id == case_form.id
        )
    )
    filled = {key for key, value in result.all() if value not in (None, "")}
    relevant = set(fields)
    return int(round(100 * len(filled & relevant) / max(1, len(relevant))))


def missing_required(
    template: FormTemplate, values: dict[str, str | None]
) -> list[dict[str, str]]:
    """Required fields with no answer, in the order they appear on the form.

    The key travels with the label so the browser can take the user straight
    to the field instead of leaving them to hunt through a 200-field report
    for the one thing they missed.
    """
    missing: list[dict[str, str]] = []
    for section in template.sections:
        for field in section.fields:
            if not field.is_required or field.field_type == FieldType.HEADING:
                continue
            if not clean(values.get(field.field_key)):
                missing.append(
                    {
                        "field_key": field.field_key,
                        "label": field.label,
                        "section": section.title,
                    }
                )
    return missing


def _validate_value(field: FormField, raw: Any) -> tuple[str | None, Any]:
    """Coerce and validate one answer. Returns ``(text_value, json_value)``."""
    if field.field_type in {FieldType.TABLE, FieldType.MULTI_SELECT}:
        if raw in (None, ""):
            return None, None
        if not isinstance(raw, (list, dict)):
            raise ValidationError(f"{field.label}: expected a list of rows.")
        return None, raw

    text = clean(raw) if raw is not None else ""
    if text == "":
        return None, None

    rules = field.validation_rules or {}
    max_length = rules.get("max_length")
    if isinstance(max_length, int) and len(text) > max_length:
        raise ValidationError(f"{field.label}: must be at most {max_length} characters.")

    if field.field_type in {FieldType.NUMBER, FieldType.CURRENCY}:
        try:
            number = Decimal(text.replace(",", ""))
        except Exception as exc:  # noqa: BLE001 - normalising any decimal error
            raise ValidationError(f"{field.label}: must be a number.") from exc
        minimum, maximum = rules.get("min"), rules.get("max")
        if minimum is not None and number < Decimal(str(minimum)):
            raise ValidationError(f"{field.label}: must be at least {minimum}.")
        if maximum is not None and number > Decimal(str(maximum)):
            raise ValidationError(f"{field.label}: must be at most {maximum}.")
        return text, None

    if field.field_type in {FieldType.SELECT, FieldType.RADIO} and field.options:
        allowed = {str(opt.get("value") if isinstance(opt, dict) else opt) for opt in field.options}
        if text not in allowed:
            raise ValidationError(f"{field.label}: '{text}' is not one of the allowed options.")

    if field.field_type == FieldType.YES_NO_NA and text.upper() not in {
        "YES",
        "NO",
        "NA",
    }:
        raise ValidationError(f"{field.label}: must be YES, NO or NA.")

    return text, None


async def save_values(
    session: AsyncSession,
    case: Case,
    case_form: CaseForm,
    payload: dict[str, Any],
    *,
    actor: User,
    submit: bool = False,
    request: Request | None = None,
) -> tuple[int, list[str]]:
    """Write a partial form save. Returns ``(saved_count, missing_required)``."""
    template = case_form.template
    if template is None:
        raise NotFoundError("This case has no form template attached.")
    if case_form.status == CaseFormStatus.APPROVED:
        raise ConflictError("This form has been approved and can no longer be edited.")

    fields = flatten_fields(template)
    existing_result = await session.execute(
        select(CaseFieldValue).where(CaseFieldValue.case_form_id == case_form.id)
    )
    existing = {row.field_key: row for row in existing_result.scalars().all()}

    saved = 0
    for key, raw in payload.items():
        field = fields.get(key)
        if field is None:
            continue  # unknown keys are ignored rather than failing the whole save
        if field.is_readonly:
            continue

        text_value, json_value = _validate_value(field, raw)
        row = existing.get(key)
        if row is None:
            row = CaseFieldValue(
                case_form_id=case_form.id,
                field_id=field.id,
                field_key=key,
                source=field.source or FieldSource.INVESTIGATION,
            )
            session.add(row)
            existing[key] = row
        else:
            if row.value_text == text_value and row.value_json == json_value:
                continue
            session.add(
                CaseFieldValueHistory(
                    case_field_value_id=row.id,
                    field_key=key,
                    old_value=row.value_text,
                    new_value=text_value,
                    changed_by_id=actor.id,
                )
            )
            if row.source == FieldSource.BANK_SUPPLIED:
                # Correcting client-supplied data is allowed, but never
                # invisible: it also lands on the case timeline so the next
                # person can see the figure moved and who moved it.
                await audit_service.timeline(
                    session,
                    case_id=case.id,
                    event_type="IMPORTED_DATA_EDITED",
                    summary=f"Client-supplied field {key} corrected",
                    detail=(
                        f"{row.value_text or '(blank)'} -> "
                        f"{text_value or '(blank)'}"
                    ),
                    actor=actor,
                    icon="pencil",
                )
            # Bank-supplied values keep their original even after an edit.
            if row.source == FieldSource.BANK_SUPPLIED and row.original_value is None:
                row.original_value = row.value_text

        row.value_text = text_value
        row.value_json = json_value
        row.updated_by_id = actor.id
        saved += 1

    await session.flush()

    value_map = {key: row.value_text for key, row in existing.items()}
    missing = missing_required(template, value_map)
    case_form.completion_percent = await _completion_percent(session, case_form, template)

    # The form is where the verdict is actually recorded, so the case takes it
    # from there rather than asking the investigator for it a second time.
    if sync_case_verdict(case, case_form, value_map):
        await audit_service.timeline(
            session,
            case_id=case.id,
            event_type="OUTCOME_SET",
            summary=(
                f"Outcome recorded as {case.outcome.value.title()}"
                if case.outcome
                else "Report status recorded"
            ),
            actor=actor,
            icon="check",
        )

    if submit:
        if missing:
            first = missing[0]
            raise ValidationError(
                f"{len(missing)} required field(s) are still empty. "
                f"Start with \"{first['label']}\" in {first['section']}.",
                details={"missing": missing},
            )
        if case.outcome is None:
            raise ValidationError(
                missing_outcome_hint(template),
                details={
                    "fields": [f.field_key for f in outcome_fields(template)],
                },
            )
        case_form.status = CaseFormStatus.SUBMITTED
        case_form.submitted_at = utcnow()
        case_form.submitted_by_id = actor.id
    elif case_form.status in {CaseFormStatus.DRAFT, CaseFormStatus.CORRECTION_REQUIRED}:
        case_form.status = CaseFormStatus.IN_PROGRESS

    if case.status == CaseStatus.ASSIGNED and saved:
        # The first save is the investigator starting work. Record it like any
        # other status change — a move with no history row is a hole in the
        # case's own account of itself.
        case.status = CaseStatus.WIP
        if case.started_at is None:
            case.started_at = utcnow()
        session.add(
            CaseStatusHistory(
                case_id=case.id,
                previous_status=CaseStatus.ASSIGNED,
                new_status=CaseStatus.WIP,
                changed_by_id=actor.id,
                comment="Work started on the investigation form",
            )
        )
        await audit_service.timeline(
            session,
            case_id=case.id,
            event_type="CASE_STATUS_CHANGED",
            summary="Work in progress",
            detail="The investigator began filling the form.",
            actor=actor,
            icon="play",
        )

    await audit_service.record(
        session,
        action=AuditAction.FORM_SUBMITTED if submit else AuditAction.FORM_UPDATED,
        module="Cases",
        actor=actor,
        entity_type="CaseForm",
        entity_id=case_form.id,
        entity_label=case.case_number,
        new_values={"saved_fields": saved, "submitted": submit},
        request=request,
    )
    if submit:
        await audit_service.timeline(
            session,
            case_id=case.id,
            event_type="FORM_SUBMITTED",
            summary="Investigation form submitted for review",
            actor=actor,
            icon="send",
        )
    elif saved:
        await audit_service.timeline(
            session,
            case_id=case.id,
            event_type="FORM_UPDATED",
            summary=f"Investigation form updated ({saved} field(s))",
            actor=actor,
            icon="edit",
        )
    return saved, missing


def values_payload(case_form: CaseForm) -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for row in case_form.values:
        payload[row.field_key] = {
            "field_key": row.field_key,
            "value": row.value_text,
            "value_json": row.value_json,
            "source": row.source,
            "original_value": row.original_value,
            "original_column": row.original_column,
            "imported_at": row.imported_at,
            "was_edited": bool(
                row.original_value is not None and row.original_value != row.value_text
            ),
            "updated_at": row.updated_at,
        }
    return payload


def document_context(case_form: CaseForm | None) -> dict[str, Any]:
    """Field values keyed by their ``document_mapping`` placeholder name."""
    if case_form is None or case_form.template is None:
        return {}
    context: dict[str, Any] = {}
    by_key = {row.field_key: row for row in case_form.values}
    for section in case_form.template.sections:
        for field in section.fields:
            row = by_key.get(field.field_key)
            if row is None:
                continue
            value = row.value_json if row.value_json is not None else row.value_text
            context[field.field_key] = value
            if field.document_mapping:
                context[field.document_mapping] = value
    return context
