"""Daily Excel / CSV import: upload, validate, preview, commit, roll back.

The whole pipeline is transactional. A half-processed file never leaves cases
behind: either every accepted row becomes a case, or none does.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.imports import parser
from app.imports.mapping import (
    FIELD_LABELS,
    ResolvedMapping,
    duplicate_signature,
    extract_row,
    resolve_mapping,
)
from app.models.case import Case, CaseDocument, CaseNote
from app.models.company import CaseType, Company
from app.models.document import GeneratedDocument
from app.models.enums import (
    CATEGORY_LABELS,
    CLOSED_STATUSES,
    AuditAction,
    CaseCategory,
    CasePriority,
    CaseStatus,
    ImportBatchStatus,
    ImportRowStatus,
    NotificationType,
)
from app.models.form import CaseFieldValue, CaseForm
from app.models.hr import Employee
from app.models.importing import ImportBatch, ImportColumnMapping, ImportRow, ImportTemplate
from app.models.user import User
from app.schemas.case import CaseCreate
from app.services import audit_service, case_service, notification_service
from app.utils.dates import detect_month_first, start_of_day, utcnow
from app.utils.files import (
    build_stored_name,
    dated_subdir,
    relative_to_storage,
    sha256_bytes,
    validate_import_upload,
    write_bytes,
)
from app.utils.text import clean, normalise_key

#: Client status wording -> internal status.
STATUS_SYNONYMS: dict[str, CaseStatus] = {
    "": CaseStatus.IMPORTED,
    "new": CaseStatus.IMPORTED,
    "fresh": CaseStatus.IMPORTED,
    "pending": CaseStatus.UNASSIGNED,
    "unassigned": CaseStatus.UNASSIGNED,
    "notassigned": CaseStatus.UNASSIGNED,
    "assigned": CaseStatus.ASSIGNED,
    "allocated": CaseStatus.ASSIGNED,
    "accepted": CaseStatus.ACCEPTED,
    "wip": CaseStatus.WIP,
    "workinprogress": CaseStatus.WIP,
    "inprogress": CaseStatus.WIP,
    "fieldinvestigation": CaseStatus.FIELD_INVESTIGATION,
    "fieldvisit": CaseStatus.FIELD_INVESTIGATION,
    "documentspending": CaseStatus.DOCUMENTS_PENDING,
    "docpending": CaseStatus.DOCUMENTS_PENDING,
    "rip": CaseStatus.RIP,
    "reportinprogress": CaseStatus.RIP,
    "submitted": CaseStatus.REPORT_SUBMITTED,
    "reportsubmitted": CaseStatus.REPORT_SUBMITTED,
    "underreview": CaseStatus.UNDER_REVIEW,
    "review": CaseStatus.UNDER_REVIEW,
    "correctionrequired": CaseStatus.CORRECTION_REQUIRED,
    "rework": CaseStatus.CORRECTION_REQUIRED,
    "verified": CaseStatus.VERIFIED,
    "completed": CaseStatus.COMPLETED,
    "closed": CaseStatus.COMPLETED,
    "done": CaseStatus.COMPLETED,
    "rejected": CaseStatus.REJECTED,
    "repudiated": CaseStatus.REJECTED,
    "cancelled": CaseStatus.CANCELLED,
    "canceled": CaseStatus.CANCELLED,
}


# --------------------------------------------------------------------------- #
# Lookup caches
# --------------------------------------------------------------------------- #
class ResolverCache:
    """Loads companies, case types and staff once per import run."""

    def __init__(self) -> None:
        self.companies: dict[str, Company] = {}
        self.case_types: dict[str, CaseType] = {}
        #: (company key, label key) -> case type, for wording that means one
        #: thing to one insurer and something else to another.
        self.company_case_types: dict[tuple[str, str], CaseType] = {}
        self.users: dict[str, User] = {}

    async def load(self, session: AsyncSession) -> None:
        companies = (await session.execute(select(Company))).scalars().all()
        for company in companies:
            for token in {company.code, company.name, company.short_name, *company.alias_list}:
                if token:
                    self.companies[normalise_key(token)] = company

        case_types = (await session.execute(select(CaseType))).scalars().all()
        for case_type in case_types:
            for token in {case_type.code, case_type.name, *case_type.alias_list}:
                if not token:
                    continue
                # "PNB:Retail" scopes the wording to one insurer. PNB's sheet
                # says Retail where another company might mean something else
                # entirely, so these must not become global aliases.
                company_code, _, label = token.partition(":")
                if label:
                    self.company_case_types[
                        (normalise_key(company_code), normalise_key(label))
                    ] = case_type
                else:
                    self.case_types[normalise_key(token)] = case_type

        result = await session.execute(select(User).options(selectinload(User.employee)))
        for user in result.scalars().unique().all():
            for token in {user.full_name, user.email}:
                if token:
                    self.users.setdefault(normalise_key(token), user)
            employee: Employee | None = user.employee
            if employee is not None and employee.employee_code:
                self.users.setdefault(normalise_key(employee.employee_code), user)

    def company(self, raw: Any) -> Company | None:
        return self.companies.get(normalise_key(raw)) if clean(raw) else None

    def case_type(self, raw: Any, company: Company | None = None) -> CaseType | None:
        """Resolve the sheet's wording, preferring what it means to this insurer."""
        if not clean(raw):
            return None
        token = normalise_key(raw)

        if company is not None:
            for company_token in (company.code, company.short_name, company.name):
                if not company_token:
                    continue
                scoped = self.company_case_types.get((normalise_key(company_token), token))
                if scoped is not None:
                    return scoped

        return self.case_types.get(token)

    def user(self, raw: Any) -> User | None:
        return self.users.get(normalise_key(raw)) if clean(raw) else None


def map_status(raw: Any) -> CaseStatus | None:
    if not clean(raw):
        return None
    return STATUS_SYNONYMS.get(normalise_key(raw))


# --------------------------------------------------------------------------- #
# Template resolution
# --------------------------------------------------------------------------- #
async def get_template(session: AsyncSession, template_id: uuid.UUID | None) -> ImportTemplate:
    statement = select(ImportTemplate).options(
        selectinload(ImportTemplate.mappings), selectinload(ImportTemplate.company)
    )
    if template_id:
        statement = statement.where(ImportTemplate.id == template_id)
    else:
        statement = statement.where(
            ImportTemplate.is_default.is_(True), ImportTemplate.is_active.is_(True)
        )
    result = await session.execute(statement)
    template = result.scalars().first()
    if template is None:
        raise NotFoundError(
            "No import template is configured. Create one under "
            "Administration → Import Configuration."
        )
    return template


async def next_batch_number(session: AsyncSession) -> str:
    """``IMP-YYYY-00001``. Uses a date range rather than a dialect-specific
    ``EXTRACT`` so the same code runs on PostgreSQL and on the SQLite test-suite.
    """
    now = utcnow()
    year_start = datetime(now.year, 1, 1, tzinfo=UTC)
    year_end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    result = await session.execute(
        select(func.count())
        .select_from(ImportBatch)
        .where(
            ImportBatch.created_at >= year_start,
            ImportBatch.created_at < year_end,
        )
    )
    sequence = int(result.scalar_one() or 0) + 1
    return f"IMP-{now.year}-{sequence:05d}"


# --------------------------------------------------------------------------- #
# Upload + validation
# --------------------------------------------------------------------------- #
async def upload_and_validate(
    session: AsyncSession,
    *,
    filename: str,
    payload: bytes,
    template_id: uuid.UUID | None,
    company_id: uuid.UUID | None,
    actor: User,
    category: CaseCategory | None = None,
    mapping_overrides: dict[str, str | None] | None = None,
    request: Request | None = None,
) -> tuple[ImportBatch, ResolvedMapping, parser.ParsedSheet]:
    validate_import_upload(filename, payload)

    template = await get_template(session, template_id)
    sheet = parser.parse(
        payload,
        filename,
        header_row=template.header_row,
        sheet_name=template.sheet_name,
    )
    if not sheet.rows:
        raise ValidationError("The file contains a header row but no data rows.")

    # XLSX ZIP metadata (including creation timestamps) can change while the
    # workbook's cells remain identical. Fingerprint the parsed content so the
    # same daily sheet cannot bypass duplicate protection by being re-saved.
    canonical_content = json.dumps(
        {"headers": sheet.headers, "rows": sheet.rows},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    checksum = sha256_bytes(canonical_content)

    existing = await session.execute(
        select(ImportBatch).where(
            ImportBatch.checksum_sha256 == checksum,
            ImportBatch.status.in_(
                [
                    ImportBatchStatus.COMPLETED,
                    ImportBatchStatus.COMPLETED_WITH_ERRORS,
                ]
            ),
        )
    )
    previous = existing.scalars().first()
    if previous is not None:
        raise ConflictError(
            "This exact file has already been imported "
            f"as batch {previous.batch_number} on "
            f"{previous.committed_at:%d-%m-%Y}. Upload a different file, or roll "
            "the previous batch back first.",
            details={"batch_id": str(previous.id), "batch_number": previous.batch_number},
        )

    mapping = resolve_mapping(sheet.headers, template, mapping_overrides)

    stored_name = build_stored_name(f".{filename.rsplit('.', 1)[-1].lower()}", prefix="import")
    target_dir = dated_subdir(settings.import_files_dir)
    path = write_bytes(target_dir, stored_name, payload)

    batch = ImportBatch(
        batch_number=await next_batch_number(session),
        template_id=template.id,
        company_id=company_id or template.company_id,
        uploaded_by_id=actor.id,
        original_filename=filename[:255],
        stored_name=stored_name,
        relative_path=relative_to_storage(path),
        size_bytes=len(payload),
        checksum_sha256=checksum,
        status=ImportBatchStatus.VALIDATING,
        detected_headers=sheet.headers,
        applied_mapping=dict(mapping.header_to_field),
        total_rows=len(sheet.rows),
    )
    session.add(batch)
    await session.flush()

    await _validate_rows(session, batch, template, mapping, sheet, category)

    batch.status = ImportBatchStatus.VALIDATED
    batch.validated_at = utcnow()

    await audit_service.record(
        session,
        action=AuditAction.IMPORT_CREATED,
        module="Import",
        actor=actor,
        entity_type="ImportBatch",
        entity_id=batch.id,
        entity_label=batch.batch_number,
        new_values={
            "filename": batch.original_filename,
            "rows": batch.total_rows,
            "valid": batch.valid_rows,
            "errors": batch.error_rows,
            "duplicates": batch.duplicate_rows,
        },
        request=request,
    )
    return batch, mapping, sheet


async def _validate_rows(
    session: AsyncSession,
    batch: ImportBatch,
    template: ImportTemplate,
    mapping: ResolvedMapping,
    sheet: parser.ParsedSheet,
    category: CaseCategory | None = None,
) -> None:
    cache = ResolverCache()
    await cache.load(session)

    # Which order this file writes its dates in, decided once from every date
    # cell in it. Per-cell guessing reads 8/6/2026 as 8 June in an American
    # sheet and silently moves the case two months.
    column_types = {m.target_field: m.data_type for m in template.mappings}
    date_headers = [
        header
        for header, target in mapping.header_to_field.items()
        if target and column_types.get(target) == "date"
    ]
    month_first = detect_month_first(
        raw.get(header)
        for _, raw in parser.iter_rows(sheet)
        for header in date_headers
    )

    seen_in_file: dict[tuple[str, ...], int] = {}
    counts = {"valid": 0, "warning": 0, "error": 0, "duplicate": 0}

    for row_number, raw in parser.iter_rows(sheet):
        errors: list[str] = []
        warnings: list[str] = []
        parsed = extract_row(raw, mapping, template, month_first=month_first)

        if mapping.missing_required:
            errors.append(
                "The file is missing required columns: " + ", ".join(mapping.missing_required)
            )

        company = cache.company(parsed.get("company_code"))
        if company is None:
            errors.append(f"Unknown company '{clean(parsed.get('company_code')) or '(blank)'}'.")
        elif not company.is_active:
            errors.append(f"Company '{company.short_name}' is inactive.")

        case_type = cache.case_type(parsed.get("case_type_code"), company)
        if case_type is None:
            errors.append(
                f"Unknown case type '{clean(parsed.get('case_type_code')) or '(blank)'}'."
            )
        elif not case_type.is_active:
            errors.append(f"Case type '{case_type.name}' is inactive.")
        elif category is not None and case_type.category != category:
            errors.append(
                f"'{case_type.name}' is a {CATEGORY_LABELS[case_type.category]} case. "
                f"Import it from the {CATEGORY_LABELS[case_type.category]} screen."
            )

        name = clean(parsed.get("life_assured_name"))
        if not name:
            errors.append("Life Assured Name is required.")
        elif len(name) < 2:
            errors.append("Life Assured Name is too short.")

        if parsed.get("received_at") is None:
            errors.append("Date is required and could not be parsed.")

        if not clean(parsed.get("policy_number")) and not clean(parsed.get("application_number")):
            errors.append("Either Policy Number or Application Number is required.")

        pin = clean(parsed.get("pin_code"))
        if pin and not (pin.isdigit() and len(pin) == 6):
            warnings.append(f"Pin Code '{pin}' is not a 6-digit code; it was kept as-is.")

        assignee_raw = clean(parsed.get("assigned_to"))
        if assignee_raw and cache.user(assignee_raw) is None:
            warnings.append(
                f"'{assignee_raw}' did not match any staff member; the case will "
                "be imported unassigned."
            )

        status_raw = clean(parsed.get("status"))
        if status_raw:
            warnings.append(
                f"Status '{status_raw}' is kept as a note. The case starts as "
                "Imported so it can be assigned and worked."
            )

        duplicate_case: Case | None = None
        signature = duplicate_signature(parsed, template.duplicate_key_fields) or (
            duplicate_signature(parsed, template.fallback_duplicate_key_fields)
        )
        if signature is not None:
            if signature in seen_in_file:
                errors.append(f"Duplicate of row {seen_in_file[signature]} within this file.")
            else:
                seen_in_file[signature] = row_number

        if company is not None and not errors:
            duplicate_case = await case_service.find_duplicate(
                session,
                company_id=company.id,
                krn_no=clean(parsed.get("krn_no")) or None,
                policy_number=clean(parsed.get("policy_number")) or None,
                application_number=clean(parsed.get("application_number")) or None,
                life_assured_name=name or None,
            )

        if errors:
            status = ImportRowStatus.ERROR
            counts["error"] += 1
        elif duplicate_case is not None:
            status = ImportRowStatus.DUPLICATE
            counts["duplicate"] += 1
            warnings.append(f"Already exists as case {duplicate_case.case_number}.")
        elif warnings:
            status = ImportRowStatus.WARNING
            counts["warning"] += 1
            counts["valid"] += 1
        else:
            status = ImportRowStatus.VALID
            counts["valid"] += 1

        session.add(
            ImportRow(
                batch_id=batch.id,
                row_number=row_number,
                raw_data=_jsonable(raw),
                parsed_data=_jsonable(parsed),
                status=status,
                errors=errors or None,
                warnings=warnings or None,
                duplicate_of_case_id=duplicate_case.id if duplicate_case else None,
            )
        )

    batch.valid_rows = counts["valid"]
    batch.warning_rows = counts["warning"]
    batch.error_rows = counts["error"]
    batch.duplicate_rows = counts["duplicate"]


def _jsonable(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if value is None or isinstance(value, (str, int, float, bool)):
            out[key] = value
        elif isinstance(value, (datetime, date)):
            out[key] = value.isoformat()
        else:
            out[key] = str(value)
    return out


# --------------------------------------------------------------------------- #
# Commit
# --------------------------------------------------------------------------- #
async def commit_batch(
    session: AsyncSession,
    batch_id: uuid.UUID,
    *,
    actor: User,
    skip_duplicates: bool = True,
    auto_assign: bool = True,
    apply_file_status: bool = False,
    default_priority: CasePriority = CasePriority.NORMAL,
    request: Request | None = None,
) -> tuple[ImportBatch, list[uuid.UUID]]:
    batch = await get_batch(session, batch_id)
    if batch.status in {
        ImportBatchStatus.COMPLETED,
        ImportBatchStatus.COMPLETED_WITH_ERRORS,
    }:
        raise ConflictError(f"Batch {batch.batch_number} has already been imported.")
    if batch.status == ImportBatchStatus.ROLLED_BACK:
        raise ConflictError(f"Batch {batch.batch_number} was rolled back.")

    await get_template(session, batch.template_id)
    cache = ResolverCache()
    await cache.load(session)

    rows_result = await session.execute(
        select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.row_number)
    )
    rows = list(rows_result.scalars().all())

    batch.status = ImportBatchStatus.IMPORTING
    created_ids: list[uuid.UUID] = []
    notify_users: dict[uuid.UUID, int] = {}

    for row in rows:
        if row.status == ImportRowStatus.ERROR:
            continue
        if row.status == ImportRowStatus.DUPLICATE and skip_duplicates:
            row.status = ImportRowStatus.SKIPPED
            continue

        parsed = row.parsed_data or {}
        company = cache.company(parsed.get("company_code"))
        case_type = cache.case_type(parsed.get("case_type_code"), company)
        if company is None or case_type is None:
            row.status = ImportRowStatus.ERROR
            row.errors = (row.errors or []) + [
                "Company or case type could not be resolved at commit time."
            ]
            continue

        received = _as_datetime(parsed.get("received_at"))
        assignee = cache.user(parsed.get("assigned_to")) if auto_assign else None

        payload = CaseCreate(
            company_id=company.id,
            case_type_id=case_type.id,
            life_assured_name=clean(parsed.get("life_assured_name")),
            krn_no=clean(parsed.get("krn_no")) or None,
            policy_number=clean(parsed.get("policy_number")) or None,
            application_number=clean(parsed.get("application_number")) or None,
            address=clean(parsed.get("address")) or None,
            city=clean(parsed.get("city")) or None,
            state=clean(parsed.get("state")) or None,
            pin_code=clean(parsed.get("pin_code")) or None,
            contact_number=clean(parsed.get("contact_number")) or None,
            alternate_contact=clean(parsed.get("alternate_contact")) or None,
            email_id=clean(parsed.get("email_id")) or None,
            product_name=clean(parsed.get("product_name")) or None,
            nominee_name=clean(parsed.get("nominee_name")) or None,
            nominee_relation=clean(parsed.get("nominee_relation")) or None,
            external_reference=clean(parsed.get("external_reference")) or None,
            import_remark=clean(parsed.get("import_remark")) or None,
            received_at=received,
            priority=default_priority,
            assigned_to_id=assignee.id if assignee else None,
        )

        case = await case_service.create_case(
            session,
            payload,
            actor=actor,
            request=request,
            import_batch_id=batch.id,
            attach_form=True,
        )

        # Fields that are not part of CaseCreate but do arrive in the file.
        case.received_month = clean(parsed.get("received_month")) or None
        case.report_prepared_by = clean(parsed.get("report_prepared_by")) or None
        case.imported_aging_days = _as_int(parsed.get("aging_days"))
        case.report_date = _as_date(parsed.get("report_date"))
        case.completion_date = _as_date(parsed.get("completion_date"))

        # The client's Status column is *their* tracking note, not ours. A
        # file that says "Completed" would otherwise create a case nobody can
        # work on, so a new case always starts on our side of the workflow
        # unless the operator explicitly asks for the file's status.
        imported_status = map_status(parsed.get("status"))
        if imported_status is not None:
            case.import_remark = " · ".join(
                part
                for part in (
                    case.import_remark,
                    f"File status: {clean(parsed.get('status'))}",
                )
                if part
            )
        if apply_file_status and imported_status and imported_status != case.status:
            case.status = imported_status
            if imported_status in CLOSED_STATUSES:
                case.completed_at = utcnow()

        if case.category == CaseCategory.DEATH_CLAIM and case.death_claim is not None:
            case.death_claim.date_of_death = _as_date(parsed.get("date_of_death"))
            case.death_claim.place_of_death = clean(parsed.get("place_of_death")) or None
            case.death_claim.cause_of_death = clean(parsed.get("cause_of_death")) or None
            case.death_claim.claimant_name = clean(parsed.get("claimant_name")) or None
            case.death_claim.claimant_relation = clean(parsed.get("claimant_relation")) or None

        row.status = ImportRowStatus.IMPORTED
        row.created_case_id = case.id
        created_ids.append(case.id)
        if assignee is not None:
            notify_users[assignee.id] = notify_users.get(assignee.id, 0) + 1

    batch.imported_rows = len(created_ids)
    batch.committed_at = utcnow()
    batch.status = (
        ImportBatchStatus.COMPLETED_WITH_ERRORS if batch.error_rows else ImportBatchStatus.COMPLETED
    )

    for user_id, count in notify_users.items():
        await notification_service.notify(
            session,
            user_id=user_id,
            notification_type=NotificationType.CASE_ASSIGNED,
            title=f"{count} new case(s) assigned to you",
            body=f"From import batch {batch.batch_number}.",
            link="/cases/assigned-to-me",
        )
    await notification_service.notify(
        session,
        user_id=actor.id,
        notification_type=NotificationType.IMPORT_COMPLETED,
        title=f"Import {batch.batch_number} completed",
        body=f"{batch.imported_rows} case(s) created from {batch.original_filename}.",
        link=f"/imports/{batch.id}",
    )

    await audit_service.record(
        session,
        action=AuditAction.IMPORT_COMMITTED,
        module="Import",
        actor=actor,
        entity_type="ImportBatch",
        entity_id=batch.id,
        entity_label=batch.batch_number,
        new_values={
            "imported": batch.imported_rows,
            "skipped_duplicates": batch.duplicate_rows if skip_duplicates else 0,
            "errors": batch.error_rows,
        },
        request=request,
    )
    return batch, created_ids


async def _cases_with_real_work(
    session: AsyncSession, case_ids: list[uuid.UUID], batch_id: uuid.UUID
) -> set[uuid.UUID]:
    """Which of these cases somebody has actually worked on.

    Judged by what a person left behind, not by the status. Importing with
    auto-assign now puts a case straight into Work in Progress, so a status
    check alone declared every freshly imported case "already worked" and made
    the whole batch impossible to roll back — the opposite of what the status
    means here.

    Form values are matched on the batch that wrote them rather than on their
    source. A prefilled value takes its source from the template field, and
    some templates declare something other than BANK_SUPPLIED, so filtering by
    source counted the import's own values as somebody's work.
    """
    if not case_ids:
        return set()

    worked: set[uuid.UUID] = set()

    # Anything in the form that this import did not put there.
    rows = await session.execute(
        select(CaseForm.case_id)
        .join(CaseFieldValue, CaseFieldValue.case_form_id == CaseForm.id)
        .where(
            CaseForm.case_id.in_(case_ids),
            or_(
                CaseFieldValue.import_batch_id.is_(None),
                CaseFieldValue.import_batch_id != batch_id,
            ),
        )
        .distinct()
    )
    worked.update(rows.scalars().all())

    # Evidence, notes and generated reports each mean somebody was here.
    for model in (CaseDocument, CaseNote, GeneratedDocument):
        rows = await session.execute(
            select(model.case_id).where(model.case_id.in_(case_ids)).distinct()
        )
        worked.update(rows.scalars().all())

    return worked


async def rollback_batch(
    session: AsyncSession,
    batch_id: uuid.UUID,
    *,
    actor: User,
    request: Request | None = None,
) -> ImportBatch:
    """Delete the cases this batch created — only while none has been worked on."""
    batch = await get_batch(session, batch_id)
    if batch.status not in {
        ImportBatchStatus.COMPLETED,
        ImportBatchStatus.COMPLETED_WITH_ERRORS,
    }:
        raise ConflictError("Only a completed import batch can be rolled back.")

    result = await session.execute(select(Case).where(Case.import_batch_id == batch.id))
    cases = list(result.scalars().all())

    worked = await _cases_with_real_work(session, [case.id for case in cases], batch.id)
    blocked = [case.case_number for case in cases if case.id in worked]
    if blocked:
        raise ConflictError(
            "This batch cannot be rolled back because work has already started on "
            f"{len(blocked)} case(s).",
            details={"cases": blocked[:20]},
        )

    for case in cases:
        await session.delete(case)

    batch.status = ImportBatchStatus.ROLLED_BACK
    batch.rolled_back_at = utcnow()
    batch.rolled_back_by_id = actor.id
    batch.imported_rows = 0

    await audit_service.record(
        session,
        action=AuditAction.IMPORT_ROLLED_BACK,
        module="Import",
        actor=actor,
        entity_type="ImportBatch",
        entity_id=batch.id,
        entity_label=batch.batch_number,
        old_values={"cases_removed": len(cases)},
        remarks=f"{len(cases)} case(s) deleted.",
        request=request,
    )
    return batch


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
async def get_batch(session: AsyncSession, batch_id: uuid.UUID) -> ImportBatch:
    result = await session.execute(
        select(ImportBatch)
        .options(
            selectinload(ImportBatch.template),
            selectinload(ImportBatch.company),
            selectinload(ImportBatch.uploaded_by),
        )
        .where(ImportBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise NotFoundError("Import batch not found.")
    return batch


async def get_rows(
    session: AsyncSession,
    batch_id: uuid.UUID,
    *,
    statuses: list[ImportRowStatus] | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[ImportRow]:
    statement = select(ImportRow).where(ImportRow.batch_id == batch_id)
    if statuses:
        statement = statement.where(ImportRow.status.in_(statuses))
    statement = statement.order_by(ImportRow.row_number).offset(offset)
    if limit:
        statement = statement.limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


def batch_payload(batch: ImportBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "batch_number": batch.batch_number,
        "original_filename": batch.original_filename,
        "status": batch.status,
        "template_code": batch.template.code if batch.template else None,
        "company_name": batch.company.short_name if batch.company else None,
        "uploaded_by": (
            {
                "id": batch.uploaded_by.id,
                "full_name": batch.uploaded_by.full_name,
                "email": batch.uploaded_by.email,
            }
            if batch.uploaded_by
            else None
        ),
        "size_bytes": batch.size_bytes,
        "checksum_sha256": batch.checksum_sha256,
        "detected_headers": batch.detected_headers,
        "total_rows": batch.total_rows,
        "valid_rows": batch.valid_rows,
        "warning_rows": batch.warning_rows,
        "error_rows": batch.error_rows,
        "duplicate_rows": batch.duplicate_rows,
        "imported_rows": batch.imported_rows,
        "validated_at": batch.validated_at,
        "committed_at": batch.committed_at,
        "rolled_back_at": batch.rolled_back_at,
        "error_message": batch.error_message,
        "created_at": batch.created_at,
    }


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name, name.replace("_", " ").title())


# --------------------------------------------------------------------------- #
# Small coercions used at commit time (values come back from JSON)
# --------------------------------------------------------------------------- #
def _as_datetime(value: Any) -> datetime | None:
    parsed = _as_date(value)
    return start_of_day(parsed) if parsed else None


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        from app.utils.dates import parse_date

        return parse_date(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


async def default_mappings_for(template: ImportTemplate) -> list[ImportColumnMapping]:
    return sorted(template.mappings, key=lambda m: m.display_order)
