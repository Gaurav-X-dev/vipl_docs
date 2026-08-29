"""Case endpoints, shared by the Investigation and Death Claim modules."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    DbSession,
    can_view_all_cases,
    require_permissions,
)
from app.core.errors import NotFoundError, ValidationError
from app.core.pagination import Page, PageParams, page_params
from app.models.audit import AuditLog, CaseTimelineEvent
from app.models.case import Case, CaseAssignment, CaseDocument, CaseNote, CaseStatusHistory
from app.models.document import GeneratedDocument
from app.models.enums import (
    ActivityAction,
    CaseCategory,
    CaseOutcome,
    CasePriority,
    CaseStatus,
    DocumentCategory,
    GeneratedFormat,
    TatState,
)
from app.models.user import User
from app.schemas.case import (
    AssignmentOut,
    AssignRequest,
    BulkAssignRequest,
    BulkStatusRequest,
    CaseCreate,
    CaseDetailOut,
    CaseDocumentOut,
    CaseFilters,
    CaseListItem,
    CaseNoteIn,
    CaseNoteOut,
    CaseUpdate,
    DeathClaimDetailIn,
    DeathClaimDetailOut,
    ImportedFieldOut,
    ReviewRequest,
    StatusChangeRequest,
    StatusHistoryOut,
    TimelineEventOut,
)
from app.schemas.common import IdResponse, Message
from app.schemas.form import CaseFormOut, SaveFormRequest, SaveFormResponse
from app.schemas.misc import (
    AuditLogOut,
    GeneratedDocumentOut,
    GenerateDocumentRequest,
)
from app.services import (
    activity_service,
    audit_service,
    case_service,
    case_workflow,
    document_service,
    export_service,
    form_service,
    navigation_service,
    settings_service,
)
from app.services.case_workflow import (
    aging_days,
    status_label,
    tat_days_remaining,
    tat_state,
    visit_label,
)
from app.utils.files import resolve_storage_path

router = APIRouter(prefix="/cases", tags=["Cases"])

ViewUser = Annotated[User, Depends(require_permissions("case.view"))]
EditUser = Annotated[User, Depends(require_permissions("case.edit"))]
AssignUser = Annotated[User, Depends(require_permissions("case.assign"))]
ReviewUser = Annotated[User, Depends(require_permissions("case.review"))]
ExportUser = Annotated[User, Depends(require_permissions("case.export"))]


# --------------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------------- #
def case_filters(
    search: str | None = Query(None, description="Case no, KRN, policy, name, phone"),
    category: CaseCategory | None = Query(None),
    company_id: uuid.UUID | None = Query(None),
    case_type_id: uuid.UUID | None = Query(None),
    status: list[CaseStatus] | None = Query(None),
    bucket: str | None = Query(
        None,
        description=(
            "Sidebar bucket key (pending, in_progress, office, …). Expanded "
            "into concrete statuses server-side so one definition drives both "
            "the menu counts and the list."
        ),
    ),
    outcome: list[CaseOutcome] | None = Query(None),
    priority: CasePriority | None = Query(None),
    assigned_to_id: uuid.UUID | None = Query(None),
    office_staff_id: uuid.UUID | None = Query(None),
    unassigned: bool | None = Query(None),
    awaiting_office: bool | None = Query(None),
    my_desk: bool | None = Query(None),
    include_archived: bool = Query(
        False,
        description=(
            "Include cases closed longer ago than the retention window. They "
            "are always kept in the database; this brings them back into view."
        ),
    ),
    tat_state_filter: TatState | None = Query(None, alias="tat_state"),
    received_from: date | None = Query(None),
    received_to: date | None = Query(None),
    completed_from: date | None = Query(None),
    completed_to: date | None = Query(None),
    city: str | None = Query(None),
    state: str | None = Query(None),
    import_batch_id: uuid.UUID | None = Query(None),
) -> CaseFilters:
    if bucket and not status:
        expanded = navigation_service.statuses_for(
            bucket, category_level=True
        ) or navigation_service.statuses_for(bucket)
        if expanded:
            status = [CaseStatus(value) for value in expanded]
    return CaseFilters(
        search=search,
        category=category,
        company_id=company_id,
        case_type_id=case_type_id,
        status=status,
        outcome=outcome,
        priority=priority,
        assigned_to_id=assigned_to_id,
        office_staff_id=office_staff_id,
        unassigned=unassigned,
        awaiting_office=awaiting_office,
        my_desk=my_desk,
        include_archived=include_archived,
        tat_state=tat_state_filter,
        received_from=received_from,
        received_to=received_to,
        completed_from=completed_from,
        completed_to=completed_to,
        city=city,
        state=state,
        import_batch_id=import_batch_id,
    )


FiltersDep = Annotated[CaseFilters, Depends(case_filters)]
PageDep = Annotated[PageParams, Depends(page_params)]


async def _display_settings(session) -> tuple[int, int]:
    warning_hours = await settings_service.get_int(session, "tat_breach_warning_hours", 24)
    online_timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    return warning_hours, online_timeout


async def _load_case(session, case_id: uuid.UUID, user: User) -> Case:
    case = await case_service.get_case(session, case_id)
    case_service.assert_can_access(case, user, can_view_all_cases(user))
    return case


# --------------------------------------------------------------------------- #
# List and detail
# --------------------------------------------------------------------------- #
@router.get("", response_model=Page[CaseListItem])
async def list_cases(
    session: DbSession, user: ViewUser, filters: FiltersDep, params: PageDep
) -> Page[CaseListItem]:
    warning_hours, online_timeout = await _display_settings(session)
    rows, total = await case_service.list_cases(
        session, filters, params, user=user, view_all=can_view_all_cases(user)
    )
    items = [
        CaseListItem(**case_service.case_list_payload(case, warning_hours, online_timeout))
        for case in rows
    ]
    return Page.build(items, total, params)


@router.get("/export")
async def export_cases(
    session: DbSession,
    user: ExportUser,
    request: Request,
    filters: FiltersDep,
    export_format: str = Query("xlsx", pattern="^(xlsx|csv)$", alias="format"),
) -> Response:
    """Export exactly what the current filters select."""
    warning_hours, _ = await _display_settings(session)
    statement = case_service.build_case_query(
        filters, user=user, view_all=can_view_all_cases(user)
    ).order_by(Case.received_at.desc())
    result = await session.execute(statement)
    cases = list(result.unique().scalars().all())

    rows = [
        export_service.case_export_row(
            case,
            aging_days(case.received_at, case.completed_at),
            tat_state(case.status, case.due_at, case.completed_at, warning_hours).value,
        )
        for case in cases
    ]

    prefix = (
        "death_claim_cases"
        if filters.category == CaseCategory.DEATH_CLAIM
        else "investigation_cases"
        if filters.category == CaseCategory.INVESTIGATION
        else "cases"
    )
    from app.models.enums import AuditAction

    await audit_service.record(
        session,
        action=AuditAction.EXPORT_RUN,
        module="Cases",
        actor=user,
        entity_type="CaseExport",
        remarks=f"{len(rows)} row(s) exported as {export_format}.",
        request=request,
    )
    await session.commit()

    if export_format == "csv":
        payload = export_service.to_csv(export_service.CASE_EXPORT_HEADERS, rows)
        media = "text/csv; charset=utf-8"
        name = export_service.filename(prefix, "csv")
    else:
        payload = export_service.to_xlsx(
            export_service.CASE_EXPORT_HEADERS, rows, sheet_title="Cases"
        )
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = export_service.filename(prefix, "xlsx")

    return Response(
        content=payload,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("", response_model=CaseDetailOut, status_code=201)
async def create_case(
    payload: CaseCreate,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("case.create"))],
) -> CaseDetailOut:
    case = await case_service.create_case(session, payload, actor=user, request=request)
    await session.commit()
    return await _detail(session, await case_service.get_case(session, case.id), user)


@router.get("/{case_id}", response_model=CaseDetailOut)
async def get_case(
    case_id: uuid.UUID, request: Request, session: DbSession, user: ViewUser
) -> CaseDetailOut:
    case = await _load_case(session, case_id, user)
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.CASE_OPENED,
        summary=f"Opened case {case.case_number}",
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    payload = await _detail(session, case, user)
    await session.commit()
    return payload


@router.patch("/{case_id}", response_model=CaseDetailOut)
async def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdate,
    request: Request,
    session: DbSession,
    user: EditUser,
) -> CaseDetailOut:
    case = await _load_case(session, case_id, user)
    await case_service.update_case(session, case, payload, actor=user, request=request)
    await session.commit()
    return await _detail(session, await case_service.get_case(session, case.id), user)


@router.patch("/{case_id}/death-claim", response_model=DeathClaimDetailOut)
async def update_death_claim(
    case_id: uuid.UUID,
    payload: DeathClaimDetailIn,
    request: Request,
    session: DbSession,
    user: EditUser,
) -> DeathClaimDetailOut:
    case = await _load_case(session, case_id, user)
    if case.death_claim is None:
        raise ValidationError("This case is not a death claim.")
    changes = payload.model_dump(exclude_unset=True)
    before = {key: getattr(case.death_claim, key, None) for key in changes}
    for key, value in changes.items():
        setattr(case.death_claim, key, value)
    old_values, new_values = audit_service.diff(before, changes)
    if new_values:
        from app.models.enums import AuditAction

        await audit_service.record(
            session,
            action=AuditAction.CASE_UPDATED,
            module="Death Claims",
            actor=user,
            entity_type="DeathClaimDetail",
            entity_id=case.id,
            entity_label=case.case_number,
            old_values=old_values,
            new_values=new_values,
            request=request,
        )
    await session.commit()
    return DeathClaimDetailOut.model_validate(case.death_claim)


async def _detail(session, case: Case, user: User) -> CaseDetailOut:
    warning_hours, online_timeout = await _display_settings(session)
    case_form = await form_service.get_case_form(session, case, create_if_missing=False)

    imported_fields: list[ImportedFieldOut] = []
    if case_form is not None:
        labels = {
            field.field_key: field.label
            for section in (case_form.template.sections if case_form.template else [])
            for field in section.fields
        }
        for row in case_form.values:
            if row.source.value != "BANK_SUPPLIED":
                continue
            imported_fields.append(
                ImportedFieldOut(
                    field=row.field_key,
                    label=labels.get(row.field_key, row.field_key),
                    value=row.value_text,
                    original_value=row.original_value,
                    source=row.source.value,
                    original_column=row.original_column,
                    imported_at=row.imported_at,
                    was_edited=bool(
                        row.original_value is not None
                        and row.original_value != row.value_text
                    ),
                )
            )

    counts = {}
    for model, key in (
        (CaseDocument, "document_count"),
        (GeneratedDocument, "generated_document_count"),
        (CaseNote, "note_count"),
    ):
        from sqlalchemy import func

        counts[key] = int(
            (
                await session.execute(
                    select(func.count()).select_from(model).where(model.case_id == case.id)
                )
            ).scalar_one()
        )

    tat_days_taken = None
    if case.completed_at and case.received_at:
        tat_days_taken = max(0, (case.completed_at - case.received_at).days)

    return CaseDetailOut(
        id=case.id,
        case_number=case.case_number,
        category=case.category,
        company_id=case.company_id,
        company_code=case.company.code,
        company_name=case.company.name,
        case_type_id=case.case_type_id,
        case_type_code=case.case_type.code,
        case_type_name=case.case_type.name,
        krn_no=case.krn_no,
        policy_number=case.policy_number,
        application_number=case.application_number,
        life_assured_name=case.life_assured_name,
        address=case.address,
        city=case.city,
        state=case.state,
        pin_code=case.pin_code,
        contact_number=case.contact_number,
        alternate_contact=case.alternate_contact,
        email_id=case.email_id,
        product_name=case.product_name,
        sum_assured=case.sum_assured,
        premium_amount=case.premium_amount,
        risk_commencement_date=case.risk_commencement_date,
        nominee_name=case.nominee_name,
        nominee_relation=case.nominee_relation,
        received_month=case.received_month,
        import_remark=case.import_remark,
        report_prepared_by=case.report_prepared_by,
        external_reference=case.external_reference,
        status=case.status,
        status_label=status_label(case.status),
        allowed_transitions=case_service.transitions_for(case),
        outcome=case.outcome,
        report_status=case.report_status,
        outcome_reason=case.outcome_reason,
        priority=case.priority,
        assigned_to=case_service.user_brief(case.assigned_to, online_timeout),
        assigned_by=case_service.user_brief(case.assigned_by, online_timeout),
        reviewed_by=case_service.user_brief(case.reviewed_by, online_timeout),
        created_by=case_service.user_brief(case.created_by, online_timeout),
        received_at=case.received_at,
        office_staff=case_service.user_brief(case.office_staff, online_timeout),
        visit_status=case.visit_status,
        visit_status_label=visit_label(case.visit_status),
        visit_scheduled_at=case.visit_scheduled_at,
        visit_started_at=case.visit_started_at,
        visited_at=case.visited_at,
        visit_remarks=case.visit_remarks,
        field_submitted_at=case.field_submitted_at,
        office_assigned_at=case.office_assigned_at,
        office_started_at=case.office_started_at,
        assigned_at=case.assigned_at,
        started_at=case.started_at,
        submitted_at=case.submitted_at,
        verified_at=case.verified_at,
        completed_at=case.completed_at,
        due_at=case.due_at,
        report_date=case.report_date,
        completion_date=case.completion_date,
        aging_days=aging_days(case.received_at, case.completed_at),
        tat_state=tat_state(case.status, case.due_at, case.completed_at, warning_hours),
        tat_days_remaining=tat_days_remaining(case.due_at, case.completed_at),
        tat_days_taken=tat_days_taken,
        is_imported=case.is_imported,
        import_batch_id=case.import_batch_id,
        imported_fields=imported_fields,
        death_claim=(
            DeathClaimDetailOut.model_validate(case.death_claim) if case.death_claim else None
        ),
        form_status=case_form.status if case_form else None,
        form_completion_percent=case_form.completion_percent if case_form else 0,
        created_at=case.created_at,
        updated_at=case.updated_at,
        **counts,
    )


# --------------------------------------------------------------------------- #
# Assignment
# --------------------------------------------------------------------------- #
@router.post("/{case_id}/assign", response_model=Message)
async def assign_case(
    case_id: uuid.UUID,
    payload: AssignRequest,
    request: Request,
    session: DbSession,
    user: AssignUser,
) -> Message:
    case = await case_service.get_case(session, case_id)
    await case_service.assign_case(
        session,
        case,
        assigned_to_id=payload.assigned_to_id,
        actor=user,
        due_at=payload.due_at,
        priority=payload.priority,
        notes=payload.notes,
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.CASE_ASSIGNED,
        summary=(
            f"Assigned case {case.case_number} to "
            f"{case.assigned_to.full_name if case.assigned_to else 'an investigator'}"
        ),
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    await session.commit()
    return Message(message=f"Case {case.case_number} assigned.")


@router.post("/bulk-assign", response_model=Message)
async def bulk_assign(
    payload: BulkAssignRequest,
    request: Request,
    session: DbSession,
    user: AssignUser,
) -> Message:
    assigned, skipped = 0, []
    for case_id in payload.case_ids:
        case = await case_service.get_case(session, case_id)
        try:
            await case_service.assign_case(
                session,
                case,
                assigned_to_id=payload.assigned_to_id,
                actor=user,
                due_at=payload.due_at,
                priority=payload.priority,
                notes=payload.notes,
                request=request,
            )
            assigned += 1
        except Exception as exc:  # noqa: BLE001 - report, do not abort the batch
            skipped.append(f"{case.case_number}: {exc}")
    await session.commit()
    return Message(
        message=f"{assigned} case(s) assigned.",
        detail="; ".join(skipped[:10]) if skipped else None,
    )


@router.get("/{case_id}/assignments", response_model=list[AssignmentOut])
async def assignment_history(
    case_id: uuid.UUID, session: DbSession, user: ViewUser
) -> list[AssignmentOut]:
    await _load_case(session, case_id, user)
    result = await session.execute(
        select(CaseAssignment)
        .options(
            selectinload(CaseAssignment.assigned_to),
            selectinload(CaseAssignment.assigned_by),
        )
        .where(CaseAssignment.case_id == case_id)
        .order_by(CaseAssignment.created_at.desc())
    )
    _, online_timeout = await _display_settings(session)
    return [
        AssignmentOut(
            id=row.id,
            assigned_to=case_service.user_brief(row.assigned_to, online_timeout),
            assigned_by=case_service.user_brief(row.assigned_by, online_timeout),
            is_reassignment=row.is_reassignment,
            due_at=row.due_at,
            priority=row.priority,
            notes=row.notes,
            created_at=row.created_at,
        )
        for row in result.scalars().all()
    ]


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
@router.post("/{case_id}/status", response_model=Message)
async def change_status(
    case_id: uuid.UUID,
    payload: StatusChangeRequest,
    request: Request,
    session: DbSession,
    user: ViewUser,
) -> Message:
    case = await _load_case(session, case_id, user)
    await case_service.change_status(
        session,
        case,
        target=payload.status,
        actor=user,
        comment=payload.comment,
        outcome=payload.outcome,
        report_status=payload.report_status,
        outcome_reason=payload.outcome_reason,
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.STATUS_CHANGED,
        summary=(f"Moved case {case.case_number} to {status_label(payload.status)}"),
        detail=payload.comment,
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    await session.commit()
    return Message(message=f"Case moved to {status_label(payload.status)}.")


@router.post("/{case_id}/review", response_model=Message)
async def review_case(
    case_id: uuid.UUID,
    payload: ReviewRequest,
    request: Request,
    session: DbSession,
    user: ReviewUser,
) -> Message:
    case = await case_service.get_case(session, case_id)
    target = CaseStatus.VERIFIED if payload.approve else CaseStatus.CORRECTION_REQUIRED
    if not payload.approve and not payload.comment:
        raise ValidationError("A reason is required when returning a case for correction.")
    await case_service.change_status(
        session,
        case,
        target=target,
        actor=user,
        comment=payload.comment,
        outcome=payload.outcome,
        report_status=payload.report_status,
        request=request,
    )
    case_form = await form_service.get_case_form(session, case, create_if_missing=False)
    if case_form is not None:
        from app.models.enums import CaseFormStatus

        case_form.status = (
            CaseFormStatus.APPROVED if payload.approve else CaseFormStatus.CORRECTION_REQUIRED
        )
        case_form.correction_remark = None if payload.approve else payload.comment
    await activity_service.log(
        session,
        user=user,
        action=(
            ActivityAction.CASE_APPROVED if payload.approve else ActivityAction.CORRECTION_REQUESTED
        ),
        summary=(
            f"Approved case {case.case_number}"
            if payload.approve
            else f"Returned case {case.case_number} for correction"
        ),
        detail=payload.comment,
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    await session.commit()
    return Message(message="Case approved." if payload.approve else "Case returned for correction.")


@router.post("/bulk-status", response_model=Message)
async def bulk_status(
    payload: BulkStatusRequest,
    request: Request,
    session: DbSession,
    user: ViewUser,
) -> Message:
    changed, skipped = 0, []
    for case_id in payload.case_ids:
        case = await case_service.get_case(session, case_id)
        try:
            await case_service.change_status(
                session,
                case,
                target=payload.status,
                actor=user,
                comment=payload.comment,
                request=request,
            )
            changed += 1
        except Exception as exc:  # noqa: BLE001 - partial success is expected here
            skipped.append(f"{case.case_number}: {exc}")
    await session.commit()
    return Message(
        message=f"{changed} case(s) updated.",
        detail="; ".join(skipped[:10]) if skipped else None,
    )


@router.get("/{case_id}/status-history", response_model=list[StatusHistoryOut])
async def status_history(
    case_id: uuid.UUID, session: DbSession, user: ViewUser
) -> list[StatusHistoryOut]:
    await _load_case(session, case_id, user)
    result = await session.execute(
        select(CaseStatusHistory)
        .options(selectinload(CaseStatusHistory.changed_by))
        .where(CaseStatusHistory.case_id == case_id)
        .order_by(CaseStatusHistory.created_at.desc())
    )
    _, online_timeout = await _display_settings(session)
    return [
        StatusHistoryOut(
            id=row.id,
            previous_status=row.previous_status,
            new_status=row.new_status,
            changed_by=case_service.user_brief(row.changed_by, online_timeout),
            comment=row.comment,
            created_at=row.created_at,
        )
        for row in result.scalars().all()
    ]


@router.get("/{case_id}/timeline", response_model=list[TimelineEventOut])
async def timeline(
    case_id: uuid.UUID, session: DbSession, user: ViewUser
) -> list[TimelineEventOut]:
    await _load_case(session, case_id, user)
    result = await session.execute(
        select(CaseTimelineEvent)
        .where(CaseTimelineEvent.case_id == case_id)
        .order_by(CaseTimelineEvent.occurred_at.desc())
    )
    return [TimelineEventOut.model_validate(row) for row in result.scalars().all()]


@router.get("/{case_id}/audit", response_model=list[AuditLogOut])
async def case_audit(
    case_id: uuid.UUID,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("audit.view"))],
) -> list[AuditLogOut]:
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == str(case_id))
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    )
    return [AuditLogOut.model_validate(row) for row in result.scalars().all()]


# --------------------------------------------------------------------------- #
# Form
# --------------------------------------------------------------------------- #
@router.get("/{case_id}/form", response_model=CaseFormOut)
async def get_form(case_id: uuid.UUID, session: DbSession, user: ViewUser) -> CaseFormOut:
    case = await _load_case(session, case_id, user)
    case_form = await form_service.get_case_form(session, case)
    if case_form is None:
        raise NotFoundError(
            f"No form template is configured for {case.company.short_name} / "
            f"{case.case_type.name}. An administrator can add one under "
            "Administration → Form Templates."
        )
    await session.commit()
    from app.models.enums import CLOSED_STATUSES, CaseFormStatus

    # A form is editable only while both the form and the case are open. A
    # case that arrived Completed in the client's file is history, not work.
    locked_reason: str | None = None
    if case_form.status == CaseFormStatus.APPROVED:
        locked_reason = "This report has been approved and can no longer be edited."
    elif case.status in CLOSED_STATUSES:
        locked_reason = (
            f"This case is {status_label(case.status)}, so its form is now "
            "read-only. Reopen the case to make changes."
        )

    template = case_form.template
    return CaseFormOut(
        id=case_form.id,
        case_id=case.id,
        template={
            "id": template.id,
            "code": template.code,
            "name": template.name,
            "company_id": template.company_id,
            "company_name": template.company.short_name if template.company else None,
            "case_type_id": template.case_type_id,
            "case_type_name": template.case_type.name if template.case_type else None,
            "case_category": template.case_type.category if template.case_type else None,
            "version": template.version,
            "is_active": template.is_active,
            "description": template.description,
            "source_document": template.source_document,
            "section_count": len(template.sections),
            "field_count": sum(len(s.fields) for s in template.sections),
            "created_at": template.created_at,
            "sections": template.sections,
        },
        status=case_form.status,
        completion_percent=case_form.completion_percent,
        submitted_at=case_form.submitted_at,
        correction_remark=case_form.correction_remark,
        values=form_service.values_payload(case_form),
        can_edit=locked_reason is None,
        locked_reason=locked_reason,
    )


@router.put("/{case_id}/form", response_model=SaveFormResponse)
async def save_form(
    case_id: uuid.UUID,
    payload: SaveFormRequest,
    request: Request,
    session: DbSession,
    user: ViewUser,
) -> SaveFormResponse:
    case = await _load_case(session, case_id, user)
    case_form = await form_service.get_case_form(session, case)
    if case_form is None:
        raise NotFoundError("This case has no form template attached.")

    saved, missing = await form_service.save_values(
        session,
        case,
        case_form,
        payload.values,
        actor=user,
        submit=payload.submit,
        request=request,
    )
    if payload.submit and case.status != CaseStatus.REPORT_SUBMITTED:
        if case.outcome is None:
            # save_values normally lifts the verdict off the form; reaching
            # here means the template has no verdict field at all.
            raise ValidationError(
                form_service.missing_outcome_hint(case_form.template)
            )
        # The machine moves one step at a time so a case cannot skip review.
        # An investigator pressing Submit should not have to know the
        # intermediate names, so walk the legal route instead of refusing the
        # jump with "Cannot move from Assigned to Submitted by Investigator".
        route = case_workflow.path_to(case.status, CaseStatus.REPORT_SUBMITTED)
        if not route:
            raise ValidationError(
                f"A case that is {status_label(case.status)} cannot be "
                "submitted as a report."
            )
        for step in route:
            await case_service.change_status(
                session,
                case,
                target=step,
                actor=user,
                comment=(
                    "Investigation form submitted"
                    if step == CaseStatus.REPORT_SUBMITTED
                    else "Advanced by form submission"
                ),
                request=request,
            )
    await activity_service.log(
        session,
        user=user,
        action=(ActivityAction.FORM_SUBMITTED if payload.submit else ActivityAction.FORM_SAVED),
        summary=(
            f"Submitted the investigation form for {case.case_number}"
            if payload.submit
            else f"Saved {saved} field(s) on {case.case_number}"
        ),
        case_id=case.id,
        entity_type="CaseForm",
        entity_id=case_form.id,
        entity_label=case.case_number,
        request=request,
    )
    await session.commit()
    return SaveFormResponse(
        status=case_form.status,
        completion_percent=case_form.completion_percent,
        saved_fields=saved,
        missing_required=missing,
        message=("Form submitted for review." if payload.submit else f"{saved} field(s) saved."),
    )


# --------------------------------------------------------------------------- #
# Notes
# --------------------------------------------------------------------------- #
@router.get("/{case_id}/notes", response_model=list[CaseNoteOut])
async def list_notes(case_id: uuid.UUID, session: DbSession, user: ViewUser) -> list[CaseNoteOut]:
    await _load_case(session, case_id, user)
    statement = (
        select(CaseNote)
        .options(selectinload(CaseNote.author))
        .where(CaseNote.case_id == case_id)
        .order_by(CaseNote.created_at.desc())
    )
    if not can_view_all_cases(user):
        statement = statement.where(CaseNote.is_internal.is_(False))
    result = await session.execute(statement)
    _, online_timeout = await _display_settings(session)
    return [
        CaseNoteOut(
            id=row.id,
            body=row.body,
            is_internal=row.is_internal,
            author=case_service.user_brief(row.author, online_timeout),
            created_at=row.created_at,
        )
        for row in result.scalars().all()
    ]


@router.post("/{case_id}/notes", response_model=IdResponse, status_code=201)
async def add_note(
    case_id: uuid.UUID,
    payload: CaseNoteIn,
    request: Request,
    session: DbSession,
    user: ViewUser,
) -> IdResponse:
    case = await _load_case(session, case_id, user)
    note = await case_service.add_note(
        session, case, body=payload.body, is_internal=payload.is_internal, actor=user
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.NOTE_ADDED,
        summary=f"Added a note to {case.case_number}",
        case_id=case.id,
        entity_type="CaseNote",
        entity_id=note.id,
        entity_label=case.case_number,
        request=request,
    )
    await session.commit()
    return IdResponse(id=note.id, message="Note added.")


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #
@router.get("/{case_id}/documents", response_model=list[CaseDocumentOut])
async def list_documents(
    case_id: uuid.UUID, session: DbSession, user: ViewUser
) -> list[CaseDocumentOut]:
    await _load_case(session, case_id, user)
    result = await session.execute(
        select(CaseDocument)
        .options(selectinload(CaseDocument.uploaded_by))
        .where(CaseDocument.case_id == case_id)
        .order_by(CaseDocument.created_at.desc())
    )
    _, online_timeout = await _display_settings(session)
    return [
        CaseDocumentOut(
            id=row.id,
            display_name=row.display_name,
            category=row.category,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            description=row.description,
            geo_latitude=float(row.geo_latitude) if row.geo_latitude else None,
            geo_longitude=float(row.geo_longitude) if row.geo_longitude else None,
            captured_at=row.captured_at,
            version=row.version,
            uploaded_by=case_service.user_brief(row.uploaded_by, online_timeout),
            created_at=row.created_at,
            download_url=f"/api/v1/cases/{case_id}/documents/{row.id}/download",
        )
        for row in result.scalars().all()
    ]


@router.post("/{case_id}/documents", response_model=IdResponse, status_code=201)
async def upload_document(
    case_id: uuid.UUID,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("document.upload"))],
    file: Annotated[UploadFile, File()],
    category: Annotated[DocumentCategory, Form()] = DocumentCategory.OTHER,
    description: Annotated[str | None, Form()] = None,
    geo_latitude: Annotated[float | None, Form()] = None,
    geo_longitude: Annotated[float | None, Form()] = None,
) -> IdResponse:
    case = await _load_case(session, case_id, user)
    payload = await file.read()
    document = await document_service.upload_evidence(
        session,
        case,
        filename=file.filename or "upload",
        content_type=file.content_type or "",
        payload=payload,
        category=category,
        description=description,
        geo_latitude=geo_latitude,
        geo_longitude=geo_longitude,
        actor=user,
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.DOCUMENT_UPLOADED,
        summary=f"Uploaded {document.display_name} to {case.case_number}",
        detail=category.value,
        case_id=case.id,
        entity_type="CaseDocument",
        entity_id=document.id,
        entity_label=document.display_name,
        request=request,
    )
    await session.commit()
    return IdResponse(id=document.id, message="Document uploaded.")


@router.get("/{case_id}/documents/{document_id}/download")
async def download_document(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DbSession,
    user: ViewUser,
) -> FileResponse:
    await _load_case(session, case_id, user)
    document = await document_service.get_evidence(session, document_id)
    if document.case_id != case_id:
        raise NotFoundError("Document not found on this case.")
    path = resolve_storage_path(document.relative_path)
    if not path.exists():
        raise NotFoundError("The stored file is missing.")
    return FileResponse(path, media_type=document.content_type, filename=document.display_name)


@router.delete("/{case_id}/documents/{document_id}", response_model=Message)
async def delete_document(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("document.delete"))],
) -> Message:
    await _load_case(session, case_id, user)
    document = await document_service.get_evidence(session, document_id)
    if document.case_id != case_id:
        raise NotFoundError("Document not found on this case.")
    await document_service.delete_evidence(session, document, actor=user, request=request)
    await session.commit()
    return Message(message="Document removed.")


# --------------------------------------------------------------------------- #
# Generated client documents
# --------------------------------------------------------------------------- #
@router.post("/{case_id}/generate", response_model=GeneratedDocumentOut, status_code=201)
async def generate_document(
    case_id: uuid.UUID,
    payload: GenerateDocumentRequest,
    request: Request,
    session: DbSession,
    user: Annotated[User, Depends(require_permissions("document.generate"))],
) -> GeneratedDocumentOut:
    case = await _load_case(session, case_id, user)
    document = await document_service.generate_document(
        session,
        case,
        output_format=payload.output_format,
        actor=user,
        force=payload.force,
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.DOCUMENT_GENERATED,
        summary=(f"Generated the {payload.output_format.value} for {case.case_number}"),
        detail=document.template.name if document.template else None,
        case_id=case.id,
        entity_type="GeneratedDocument",
        entity_id=document.id,
        entity_label=document.display_name,
        request=request,
    )
    await session.commit()
    return GeneratedDocumentOut(
        id=document.id,
        display_name=document.display_name,
        output_format=document.output_format,
        size_bytes=document.size_bytes,
        template_name=document.template.name if document.template else None,
        template_version=document.template_version,
        used_client_template=document.used_client_template,
        generated_by=None,
        generated_at=document.generated_at,
        download_url=f"/api/v1/cases/{case_id}/generated/{document.id}/download",
    )


@router.get("/{case_id}/generated", response_model=list[GeneratedDocumentOut])
async def list_generated(
    case_id: uuid.UUID, session: DbSession, user: ViewUser
) -> list[GeneratedDocumentOut]:
    await _load_case(session, case_id, user)
    result = await session.execute(
        select(GeneratedDocument)
        .options(
            selectinload(GeneratedDocument.template),
            selectinload(GeneratedDocument.generated_by),
        )
        .where(GeneratedDocument.case_id == case_id)
        .order_by(GeneratedDocument.generated_at.desc())
    )
    _, online_timeout = await _display_settings(session)
    return [
        GeneratedDocumentOut(
            id=row.id,
            display_name=row.display_name,
            output_format=row.output_format,
            size_bytes=row.size_bytes,
            template_name=row.template.name if row.template else None,
            template_version=row.template_version,
            used_client_template=row.used_client_template,
            generated_by=case_service.user_brief(row.generated_by, online_timeout),
            generated_at=row.generated_at,
            download_url=f"/api/v1/cases/{case_id}/generated/{row.id}/download",
        )
        for row in result.scalars().all()
    ]


@router.get("/{case_id}/generated/{document_id}/download")
async def download_generated(
    case_id: uuid.UUID,
    document_id: uuid.UUID,
    session: DbSession,
    user: ViewUser,
) -> FileResponse:
    await _load_case(session, case_id, user)
    document = await document_service.get_generated(session, document_id)
    if document.case_id != case_id:
        raise NotFoundError("Document not found on this case.")
    path = resolve_storage_path(document.relative_path)
    if not path.exists():
        raise NotFoundError("The generated file is missing from storage.")
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if document.output_format == GeneratedFormat.DOCX
        else "application/pdf"
    )
    return FileResponse(path, media_type=media, filename=document.display_name)
