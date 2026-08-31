"""Case creation, listing, assignment and status transitions."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import Select, and_, func, or_, select, update
from sqlalchemy import case as case_expr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.pagination import PageParams, paginate
from app.models.case import (
    Case,
    CaseAssignment,
    CaseNote,
    CaseNumberSequence,
    CaseStatusHistory,
    DeathClaimDetail,
)
from app.models.company import CaseType, Company
from app.models.enums import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    RIP_STATUSES,
    WIP_STATUSES,
    AssignmentStage,
    AssignmentState,
    AuditAction,
    CaseCategory,
    CaseOutcome,
    CasePriority,
    CaseStatus,
    NotificationType,
    ReportStatus,
    TatState,
)
from app.models.user import User
from app.schemas.case import CaseCreate, CaseFilters, CaseUpdate
from app.services import audit_service, notification_service, settings_service
from app.services.case_workflow import (
    aging_days,
    allowed_transitions,
    assert_transition,
    compute_due_at,
    may_set_status,
    status_after_assignment,
    status_label,
    tat_days_remaining,
    tat_state,
    visit_label,
)
from app.utils.dates import end_of_day, ensure_utc, start_of_day, utcnow

CASE_SORT_COLUMNS: dict[str, Any] = {
    "case_number": Case.case_number,
    "life_assured_name": Case.life_assured_name,
    "status": Case.status,
    "priority": Case.priority,
    "received_at": Case.received_at,
    "due_at": Case.due_at,
    "completed_at": Case.completed_at,
    "created_at": Case.created_at,
    "updated_at": Case.updated_at,
}


# --------------------------------------------------------------------------- #
# Case numbering
# --------------------------------------------------------------------------- #
async def next_case_number(
    session: AsyncSession, category: CaseCategory, when: datetime | None = None
) -> str:
    """Allocate the next case number atomically.

    Uses ``UPDATE ... RETURNING`` on a per-(prefix, year) counter row, so two
    concurrent imports can never mint the same number. Deliberately not
    ``max(id) + 1``.
    """
    prefix = (
        await settings_service.get_value(session, "case_prefix_death_claim", "DCL")
        if category == CaseCategory.DEATH_CLAIM
        else await settings_service.get_value(session, "case_prefix_investigation", "INV")
    )
    prefix = str(prefix or ("DCL" if category == CaseCategory.DEATH_CLAIM else "INV"))
    year = (ensure_utc(when) or utcnow()).year

    statement = (
        update(CaseNumberSequence)
        .where(
            CaseNumberSequence.prefix == prefix,
            CaseNumberSequence.year == year,
        )
        .values(last_value=CaseNumberSequence.last_value + 1)
        .returning(CaseNumberSequence.last_value)
    )
    result = await session.execute(statement)
    value = result.scalar_one_or_none()

    if value is None:
        session.add(CaseNumberSequence(prefix=prefix, year=year, last_value=1))
        await session.flush()
        value = 1

    return f"{prefix}-{year}-{value:06d}"


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
async def get_case(session: AsyncSession, case_id: uuid.UUID) -> Case:
    result = await session.execute(
        select(Case)
        .options(
            selectinload(Case.company),
            selectinload(Case.case_type),
            selectinload(Case.assigned_to),
            selectinload(Case.assigned_by),
            selectinload(Case.reviewed_by),
            selectinload(Case.created_by),
            selectinload(Case.death_claim),
        )
        .where(Case.id == case_id)
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise NotFoundError("Case not found.")
    return case


def assert_can_access(case: Case, user: User, view_all: bool) -> None:
    """Field and office staff may only open the cases on their own desk."""
    if view_all:
        return
    if case.assigned_to_id and case.assigned_to_id == user.id:
        return
    if case.office_staff_id and case.office_staff_id == user.id:
        return
    if case.created_by_id == user.id:
        return
    raise PermissionDeniedError("This case is not assigned to you.")


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
def build_case_query(
    filters: CaseFilters,
    *,
    user: User | None = None,
    view_all: bool = True,
    archive_before: datetime | None = None,
) -> Select[tuple[Case]]:
    """The filtered case query.

    ``archive_before`` implements the client's "90 days data remove": a case
    that has been closed for longer than the retention window drops out of the
    working views. Nothing is deleted — the row, its form, its documents and
    its audit trail all stay — it simply stops cluttering the desks. Passing
    ``include_archived`` on the filters brings it back.
    """
    statement = (
        select(Case)
        .options(
            selectinload(Case.company),
            selectinload(Case.case_type),
            selectinload(Case.assigned_to),
            selectinload(Case.office_staff),
        )
        .join(Company, Case.company_id == Company.id)
        .join(CaseType, Case.case_type_id == CaseType.id)
    )

    if not view_all and user is not None:
        # A user without case.view_all sees their own desk, at either stage.
        statement = statement.where(
            or_(
                Case.assigned_to_id == user.id,
                Case.office_staff_id == user.id,
                Case.created_by_id == user.id,
            )
        )

    if archive_before is not None and not filters.include_archived:
        statement = statement.where(
            or_(
                Case.status.notin_(list(CLOSED_STATUSES)),
                Case.completed_at.is_(None),
                Case.completed_at >= archive_before,
            )
        )

    if filters.category:
        statement = statement.where(Case.category == filters.category)
    if filters.company_id:
        statement = statement.where(Case.company_id == filters.company_id)
    if filters.case_type_id:
        statement = statement.where(Case.case_type_id == filters.case_type_id)
    if filters.status:
        statement = statement.where(Case.status.in_(filters.status))
    if filters.outcome:
        statement = statement.where(Case.outcome.in_(filters.outcome))
    if filters.priority:
        statement = statement.where(Case.priority == filters.priority)
    if filters.assigned_to_id:
        statement = statement.where(Case.assigned_to_id == filters.assigned_to_id)
    if filters.office_staff_id:
        statement = statement.where(Case.office_staff_id == filters.office_staff_id)
    if filters.unassigned:
        statement = statement.where(Case.assigned_to_id.is_(None))
    if filters.awaiting_office:
        statement = statement.where(
            Case.status == CaseStatus.AWAITING_OFFICE_ASSIGNMENT
        )
    if filters.my_desk and user is not None:
        statement = statement.where(
            or_(Case.assigned_to_id == user.id, Case.office_staff_id == user.id)
        )
    if filters.city:
        statement = statement.where(Case.city.ilike(f"%{filters.city}%"))
    if filters.state:
        statement = statement.where(Case.state.ilike(f"%{filters.state}%"))
    if filters.import_batch_id:
        statement = statement.where(Case.import_batch_id == filters.import_batch_id)
    if filters.received_from:
        statement = statement.where(Case.received_at >= start_of_day(filters.received_from))
    if filters.received_to:
        statement = statement.where(Case.received_at <= end_of_day(filters.received_to))
    if filters.completed_from:
        statement = statement.where(Case.completed_at >= start_of_day(filters.completed_from))
    if filters.completed_to:
        statement = statement.where(Case.completed_at <= end_of_day(filters.completed_to))

    if filters.search:
        term = f"%{filters.search.strip()}%"
        statement = statement.where(
            or_(
                Case.case_number.ilike(term),
                Case.krn_no.ilike(term),
                Case.policy_number.ilike(term),
                Case.application_number.ilike(term),
                Case.life_assured_name.ilike(term),
                Case.contact_number.ilike(term),
                Case.nominee_name.ilike(term),
                Case.external_reference.ilike(term),
                Company.name.ilike(term),
                Company.short_name.ilike(term),
            )
        )

    if filters.tat_state:
        now = utcnow()
        if filters.tat_state == TatState.OUT_OF_TAT:
            statement = statement.where(
                Case.due_at.is_not(None),
                Case.status.notin_(list(CLOSED_STATUSES)),
                Case.due_at < now,
            )
        elif filters.tat_state == TatState.IN_TAT:
            statement = statement.where(
                Case.due_at.is_not(None),
                Case.status.notin_(list(CLOSED_STATUSES)),
                Case.due_at >= now,
            )
        elif filters.tat_state == TatState.NOT_APPLICABLE:
            statement = statement.where(Case.due_at.is_(None))

    return statement


def apply_sort(statement: Select[Any], params: PageParams) -> Select[Any]:
    column = CASE_SORT_COLUMNS.get(params.sort_by or "received_at", Case.received_at)
    return statement.order_by(
        column.asc() if params.sort_dir == "asc" else column.desc(), Case.id.desc()
    )


async def archive_cutoff(session: AsyncSession) -> datetime:
    """Cases completed before this moment are out of the working views."""
    days = await settings_service.get_int(session, "data_retention_days", 90)
    return utcnow() - timedelta(days=max(1, days))


async def list_cases(
    session: AsyncSession,
    filters: CaseFilters,
    params: PageParams,
    *,
    user: User,
    view_all: bool,
) -> tuple[list[Case], int]:
    statement = apply_sort(
        build_case_query(
            filters,
            user=user,
            view_all=view_all,
            archive_before=await archive_cutoff(session),
        ),
        params,
    )
    return await paginate(session, statement, params)


# --------------------------------------------------------------------------- #
# Serialisation helpers
# --------------------------------------------------------------------------- #
def user_brief(user: User | None, online_timeout: int) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "staff_category": user.staff_category.value,
        "is_online": user.is_online(online_timeout),
        "last_activity_at": user.last_activity_at,
    }


def case_list_payload(case: Case, warning_hours: int, online_timeout: int) -> dict:
    state = tat_state(case.status, case.due_at, case.completed_at, warning_hours)
    return {
        "id": case.id,
        "case_number": case.case_number,
        "category": case.category,
        "company_code": case.company.code,
        "company_name": case.company.short_name or case.company.name,
        "case_type_code": case.case_type.code,
        "case_type_name": case.case_type.name,
        "krn_no": case.krn_no,
        "policy_number": case.policy_number,
        "application_number": case.application_number,
        "life_assured_name": case.life_assured_name,
        "city": case.city,
        "state": case.state,
        "status": case.status,
        "status_label": status_label(case.status),
        "outcome": case.outcome,
        "report_status": case.report_status,
        "priority": case.priority,
        "assigned_to": user_brief(case.assigned_to, online_timeout),
        "office_staff": user_brief(case.office_staff, online_timeout),
        "visit_status": case.visit_status,
        "visit_status_label": visit_label(case.visit_status),
        "received_at": case.received_at,
        "due_at": case.due_at,
        "completed_at": case.completed_at,
        "aging_days": aging_days(case.received_at, case.completed_at),
        "tat_state": state,
        "tat_days_remaining": tat_days_remaining(case.due_at, case.completed_at),
        "is_imported": case.is_imported,
    }


# --------------------------------------------------------------------------- #
# Creation
# --------------------------------------------------------------------------- #
async def resolve_tat_days(session: AsyncSession, company: Company, case_type: CaseType) -> int:
    default = await settings_service.get_int(session, "default_tat_days", 7)
    for candidate in (case_type.default_tat_days, company.default_tat_days, default):
        if candidate:
            return int(candidate)
    return 7


async def create_case(
    session: AsyncSession,
    payload: CaseCreate,
    *,
    actor: User | None,
    request: Request | None = None,
    import_batch_id: uuid.UUID | None = None,
    attach_form: bool = True,
) -> Case:
    company = await session.get(Company, payload.company_id)
    if company is None or not company.is_active:
        raise ValidationError("The selected company does not exist or is inactive.")
    case_type = await session.get(CaseType, payload.case_type_id)
    if case_type is None or not case_type.is_active:
        raise ValidationError("The selected case type does not exist or is inactive.")

    received_at = ensure_utc(payload.received_at) or utcnow()
    tat_days = await resolve_tat_days(session, company, case_type)

    case = Case(
        case_number=await next_case_number(session, case_type.category, received_at),
        category=case_type.category,
        company_id=company.id,
        case_type_id=case_type.id,
        krn_no=payload.krn_no,
        policy_number=payload.policy_number,
        application_number=payload.application_number,
        life_assured_name=payload.life_assured_name,
        address=payload.address,
        city=payload.city,
        state=payload.state,
        pin_code=payload.pin_code,
        contact_number=payload.contact_number,
        alternate_contact=payload.alternate_contact,
        email_id=payload.email_id,
        product_name=payload.product_name,
        sum_assured=payload.sum_assured,
        premium_amount=payload.premium_amount,
        risk_commencement_date=payload.risk_commencement_date,
        nominee_name=payload.nominee_name,
        nominee_relation=payload.nominee_relation,
        external_reference=payload.external_reference,
        import_remark=payload.import_remark,
        received_at=received_at,
        due_at=compute_due_at(received_at, tat_days, ensure_utc(payload.due_at)),
        priority=payload.priority,
        status=CaseStatus.IMPORTED if import_batch_id else CaseStatus.UNASSIGNED,
        created_by_id=actor.id if actor else None,
        import_batch_id=import_batch_id,
        is_imported=import_batch_id is not None,
    )
    session.add(case)
    await session.flush()

    if case_type.category == CaseCategory.DEATH_CLAIM:
        death_claim = DeathClaimDetail(case_id=case.id)
        case.death_claim = death_claim
        session.add(death_claim)

    session.add(
        CaseStatusHistory(
            case_id=case.id,
            previous_status=None,
            new_status=case.status,
            changed_by_id=actor.id if actor else None,
            comment="Case created from import" if import_batch_id else "Case created",
        )
    )

    await audit_service.record(
        session,
        action=AuditAction.CASE_IMPORTED if import_batch_id else AuditAction.CASE_CREATED,
        module="Cases",
        actor=actor,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        new_values={
            "case_number": case.case_number,
            "company": company.code,
            "case_type": case_type.code,
            "life_assured_name": case.life_assured_name,
        },
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="CASE_CREATED",
        summary=(
            f"Case imported for {company.short_name}"
            if import_batch_id
            else f"Case created for {company.short_name}"
        ),
        detail=f"{case_type.name} — {case.life_assured_name}",
        actor=actor,
        icon="plus",
    )

    if payload.assigned_to_id:
        await assign_case(
            session,
            case,
            assigned_to_id=payload.assigned_to_id,
            actor=actor,
            due_at=case.due_at,
            priority=case.priority,
            notes="Assigned at creation",
            request=request,
        )

    if attach_form:
        from app.services import form_service

        await form_service.attach_template(session, case, actor=actor)

    return case


async def update_case(
    session: AsyncSession,
    case: Case,
    payload: CaseUpdate,
    *,
    actor: User,
    request: Request | None = None,
) -> Case:
    changes = payload.model_dump(exclude_unset=True)
    before = {key: getattr(case, key, None) for key in changes}
    for key, value in changes.items():
        setattr(case, key, value)
    old_values, new_values = audit_service.diff(before, changes)
    if new_values:
        await audit_service.record(
            session,
            action=AuditAction.CASE_UPDATED,
            module="Cases",
            actor=actor,
            entity_type="Case",
            entity_id=case.id,
            entity_label=case.case_number,
            old_values=old_values,
            new_values=new_values,
            request=request,
        )
        await audit_service.timeline(
            session,
            case_id=case.id,
            event_type="CASE_UPDATED",
            summary=f"Case details updated ({len(new_values)} field(s))",
            detail=", ".join(sorted(new_values)),
            actor=actor,
            icon="edit",
        )
    return case


# --------------------------------------------------------------------------- #
# Assignment
# --------------------------------------------------------------------------- #
async def assign_case(
    session: AsyncSession,
    case: Case,
    *,
    assigned_to_id: uuid.UUID,
    actor: User | None,
    due_at: datetime | None = None,
    priority: CasePriority | None = None,
    notes: str | None = None,
    request: Request | None = None,
) -> Case:
    if case.status in CLOSED_STATUSES:
        raise ConflictError(f"{status_label(case.status)} cases cannot be reassigned.")

    assignee = await session.get(User, assigned_to_id)
    if assignee is None or not assignee.is_active:
        raise ValidationError("The selected staff member is not available.")

    previous_id = case.assigned_to_id
    is_reassignment = previous_id is not None and previous_id != assigned_to_id
    if previous_id == assigned_to_id:
        raise ConflictError(f"The case is already assigned to {assignee.full_name}.")

    now = utcnow()
    case.assigned_to_id = assignee.id
    case.assigned_by_id = actor.id if actor else None
    case.assigned_at = now
    if due_at is not None:
        case.due_at = ensure_utc(due_at)
    if priority is not None:
        case.priority = priority

    previous_status = case.status
    case.status = status_after_assignment(case.status)
    # Assignment is now what starts the work, so it is also what stamps the
    # start time — otherwise the case reads "Work in Progress" with no
    # "Started" date beside it.
    if case.status == CaseStatus.WIP and case.started_at is None:
        case.started_at = now

    await close_stage_assignments(
        session,
        case_id=case.id,
        stage=AssignmentStage.FIELD_INVESTIGATION,
        state=AssignmentState.RELEASED,
    )
    session.add(
        CaseAssignment(
            case_id=case.id,
            stage=AssignmentStage.FIELD_INVESTIGATION,
            state=AssignmentState.ACTIVE,
            assigned_to_id=assignee.id,
            assigned_by_id=actor.id if actor else None,
            previous_assignee_id=previous_id,
            is_reassignment=is_reassignment,
            due_at=case.due_at,
            priority=case.priority,
            notes=notes,
        )
    )
    if previous_status != case.status:
        session.add(
            CaseStatusHistory(
                case_id=case.id,
                previous_status=previous_status,
                new_status=case.status,
                changed_by_id=actor.id if actor else None,
                comment="Status advanced by assignment",
            )
        )

    await audit_service.record(
        session,
        action=AuditAction.CASE_REASSIGNED if is_reassignment else AuditAction.CASE_ASSIGNED,
        module="Cases",
        actor=actor,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        old_values={"assigned_to_id": previous_id} if previous_id else None,
        new_values={"assigned_to_id": assignee.id, "due_at": case.due_at},
        remarks=notes,
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="CASE_ASSIGNED",
        summary=(
            f"Reassigned to {assignee.full_name}"
            if is_reassignment
            else f"Assigned to {assignee.full_name}"
        ),
        detail=notes,
        actor=actor,
        icon="user-check",
    )
    await notification_service.notify(
        session,
        user_id=assignee.id,
        notification_type=(
            NotificationType.CASE_REASSIGNED if is_reassignment else NotificationType.CASE_ASSIGNED
        ),
        title=f"Case {case.case_number} assigned to you",
        body=f"{case.company.short_name} — {case.life_assured_name}",
        link=_case_link(case),
        entity_type="Case",
        entity_id=str(case.id),
    )
    return case


async def close_stage_assignments(
    session: AsyncSession,
    *,
    case_id: uuid.UUID,
    stage: AssignmentStage,
    state: AssignmentState = AssignmentState.COMPLETED,
) -> int:
    """Close the open assignments for one stage without deleting them.

    Assignment history is append-only: reassigning a case marks the previous
    row RELEASED and adds a new one, so "who had this case in March" always has
    an answer.
    """
    now = utcnow()
    result = await session.execute(
        update(CaseAssignment)
        .where(
            CaseAssignment.case_id == case_id,
            CaseAssignment.stage == stage,
            CaseAssignment.state == AssignmentState.ACTIVE,
        )
        .values(
            state=state,
            released_at=now,
            completed_at=now if state == AssignmentState.COMPLETED else None,
        )
    )
    return int(result.rowcount or 0)


def _case_link(case: Case) -> str:
    segment = "death-claims" if case.category == CaseCategory.DEATH_CLAIM else "investigations"
    return f"/{segment}/{case.id}"


# --------------------------------------------------------------------------- #
# Status transitions
# --------------------------------------------------------------------------- #
def assert_may_set_status(case: Case, target: CaseStatus, actor: User) -> None:
    """Refuse a status change the actor is not entitled to make.

    The endpoint asked only for ``case.view``, which meant an investigator
    could take their own case straight to Completed and skip the office,
    review and quality-check stages entirely. Permission is checked here
    rather than on the route so that every path into ``change_status`` is
    covered by the same rule.
    """
    if may_set_status(
        target,
        permission_codes=actor.permission_codes,
        is_super_admin=actor.is_super_admin,
        is_assignee=case.assigned_to_id == actor.id,
        is_office_staff=case.office_staff_id == actor.id,
    ):
        return
    raise PermissionDeniedError(
        f"You are not allowed to move a case to {status_label(target)}."
    )


async def change_status(
    session: AsyncSession,
    case: Case,
    *,
    target: CaseStatus,
    actor: User,
    comment: str | None = None,
    outcome: CaseOutcome | None = None,
    report_status: ReportStatus | None = None,
    outcome_reason: str | None = None,
    request: Request | None = None,
) -> Case:
    effective_outcome = outcome or case.outcome
    assert_transition(case.status, target, effective_outcome)
    assert_may_set_status(case, target, actor)

    previous = case.status
    now = utcnow()
    case.status = target
    if outcome is not None:
        case.outcome = outcome
    if report_status is not None:
        case.report_status = report_status
    if outcome_reason is not None:
        case.outcome_reason = outcome_reason

    if target in {CaseStatus.ACCEPTED, CaseStatus.WIP} and case.started_at is None:
        case.started_at = now
    if target == CaseStatus.REPORT_SUBMITTED:
        case.submitted_at = now
    if target == CaseStatus.VERIFIED:
        case.verified_at = now
        case.reviewed_by_id = actor.id
    if target == CaseStatus.COMPLETED:
        case.completed_at = now
        case.completion_date = now.date()
        if case.report_status is None:
            case.report_status = ReportStatus.FINAL

    session.add(
        CaseStatusHistory(
            case_id=case.id,
            previous_status=previous,
            new_status=target,
            changed_by_id=actor.id,
            comment=comment,
        )
    )
    await audit_service.record(
        session,
        action=AuditAction.CASE_STATUS_CHANGED,
        module="Cases",
        actor=actor,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        old_values={"status": previous.value},
        new_values={
            "status": target.value,
            "outcome": case.outcome.value if case.outcome else None,
        },
        remarks=comment,
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="STATUS_CHANGED",
        summary=f"Status changed to {status_label(target)}",
        detail=comment,
        actor=actor,
        icon="flag",
    )

    if target == CaseStatus.CORRECTION_REQUIRED and case.assigned_to_id:
        await notification_service.notify(
            session,
            user_id=case.assigned_to_id,
            notification_type=NotificationType.CORRECTION_REQUESTED,
            title=f"Correction requested on {case.case_number}",
            body=comment or "The reviewer has returned this case for correction.",
            link=_case_link(case),
            entity_type="Case",
            entity_id=str(case.id),
        )
    elif target in {CaseStatus.VERIFIED, CaseStatus.COMPLETED} and case.assigned_to_id:
        await notification_service.notify(
            session,
            user_id=case.assigned_to_id,
            notification_type=(
                NotificationType.CASE_COMPLETED
                if target == CaseStatus.COMPLETED
                else NotificationType.CASE_APPROVED
            ),
            title=f"Case {case.case_number} {status_label(target).lower()}",
            body=comment,
            link=_case_link(case),
            entity_type="Case",
            entity_id=str(case.id),
        )

    # The review and quality-check steps hand the case back to "an admin"
    # rather than to one named person, so the audience is everyone who is
    # allowed to act on it. The actor is excluded: they just did the thing.
    if target in {CaseStatus.UNDER_REVIEW, CaseStatus.QUALITY_CHECK}:
        await notification_service.notify_permission_holders(
            session,
            permission="case.review",
            notification_type=NotificationType.SYSTEM,
            title=(
                f"Case {case.case_number} is ready for review"
                if target == CaseStatus.UNDER_REVIEW
                else f"Case {case.case_number} sent to quality check"
            ),
            body=f"{case.company.short_name} — {case.life_assured_name}",
            link=_case_link(case),
            entity_type="Case",
            entity_id=str(case.id),
            exclude_user_id=actor.id,
        )
    return case


# --------------------------------------------------------------------------- #
# Notes
# --------------------------------------------------------------------------- #
async def add_note(
    session: AsyncSession,
    case: Case,
    *,
    body: str,
    is_internal: bool,
    actor: User,
) -> CaseNote:
    note = CaseNote(case_id=case.id, author_id=actor.id, body=body, is_internal=is_internal)
    session.add(note)
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="NOTE_ADDED",
        summary="Note added",
        detail=body[:400],
        actor=actor,
        icon="message",
    )
    return note


# --------------------------------------------------------------------------- #
# Workload helpers used by assignment screens and the dashboard
# --------------------------------------------------------------------------- #
async def workload_by_user(session: AsyncSession) -> dict[uuid.UUID, dict[str, int]]:
    """Per-investigator open / WIP / RIP / completed / overdue counts."""
    now = utcnow()

    def _count_if(condition) -> Any:
        return func.sum(case_expr((condition, 1), else_=0))

    result = await session.execute(
        select(
            Case.assigned_to_id,
            func.count().label("total"),
            _count_if(Case.status.in_(list(OPEN_STATUSES))).label("open"),
            _count_if(Case.status.in_(list(WIP_STATUSES))).label("wip"),
            _count_if(Case.status.in_(list(RIP_STATUSES))).label("rip"),
            _count_if(Case.status == CaseStatus.COMPLETED).label("completed"),
            _count_if(
                and_(
                    Case.due_at.is_not(None),
                    Case.due_at < now,
                    Case.status.notin_(list(CLOSED_STATUSES)),
                )
            ).label("overdue"),
        )
        .where(Case.assigned_to_id.is_not(None))
        .group_by(Case.assigned_to_id)
    )
    workload: dict[uuid.UUID, dict[str, int]] = {}
    for row in result:
        workload[row.assigned_to_id] = {
            "total": int(row.total or 0),
            "open": int(row.open or 0),
            "wip": int(row.wip or 0),
            "rip": int(row.rip or 0),
            "completed": int(row.completed or 0),
            "overdue": int(row.overdue or 0),
        }
    return workload


def transitions_for(case: Case) -> list[str]:
    return [status.value for status in allowed_transitions(case.status)]


async def find_duplicate(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    krn_no: str | None,
    policy_number: str | None,
    application_number: str | None,
    life_assured_name: str | None,
) -> Case | None:
    """Duplicate detection derived from the sample Excel (see §4 of the analysis)."""
    if krn_no:
        result = await session.execute(
            select(Case).where(Case.company_id == company_id, Case.krn_no == krn_no)
        )
        existing = result.scalars().first()
        if existing:
            return existing

    conditions = [Case.company_id == company_id]
    if policy_number:
        conditions.append(Case.policy_number == policy_number)
    elif application_number:
        conditions.append(Case.application_number == application_number)
    else:
        return None
    if life_assured_name:
        conditions.append(func.lower(Case.life_assured_name) == life_assured_name.lower())

    result = await session.execute(select(Case).where(and_(*conditions)))
    return result.scalars().first()


def month_label(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%b-%Y")
