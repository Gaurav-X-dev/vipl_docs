"""The two-stage operational workflow and the locking of bank-supplied data.

Stage A ends when the field investigator submits. Stage B begins when a manager
assigns the case to office staff. Critically, submitting **does not complete a
case** — it queues it:

    Investigator submits -> Awaiting Office Assignment -> Office Processing

The field assignment is never overwritten by the office assignment; both live
in ``case_assignments`` with a ``stage``, so the full custody chain survives.

Client-supplied values are marked, not locked: staff can correct a wrong policy
number on the spot, and the original plus every change stays on the record.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, PermissionDeniedError, ValidationError
from app.models.case import Case, CaseAssignment, CaseStatusHistory
from app.models.enums import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    ActivityAction,
    AssignmentStage,
    AssignmentState,
    AuditAction,
    CaseOutcome,
    CaseStatus,
    NotificationType,
    VisitStatus,
)
from app.models.user import User
from app.services import activity_service, audit_service, notification_service
from app.services.case_service import _case_link, close_stage_assignments
from app.services.case_workflow import (
    assert_field_submittable,
    assert_office_assignable,
    status_after_office_assignment,
    status_label,
    visit_label,
)
from app.utils.dates import ensure_utc, utcnow


# --------------------------------------------------------------------------- #
# Stage A -> Stage B
# --------------------------------------------------------------------------- #
async def submit_to_office(
    session: AsyncSession,
    case: Case,
    *,
    actor: User,
    remarks: str | None = None,
    outcome: CaseOutcome | None = None,
    request: Request | None = None,
) -> Case:
    """Hand a completed field investigation to the back office.

    Deliberately never jumps to Completed. The client was explicit that a case
    leaving the investigator's hands enters an internal queue, and that a
    manager decides who processes it.
    """
    assert_field_submittable(case.status)

    # Submitting is the investigator's own act. Holding case.view_all — which
    # every reviewer does — was previously enough to submit somebody else's
    # case on their behalf.
    if not (
        actor.is_super_admin
        or case.assigned_to_id == actor.id
        or "case.edit" in actor.permission_codes
    ):
        raise PermissionDeniedError(
            "Only the investigator this case is assigned to can submit it."
        )

    if outcome is not None:
        case.outcome = outcome
    if case.outcome is None:
        raise ValidationError(
            "Record an outcome of Positive, Negative or Suspicious before "
            "submitting this case to the office."
        )

    now = utcnow()
    previous_status = case.status
    case.status = CaseStatus.AWAITING_OFFICE_ASSIGNMENT
    case.visit_status = VisitStatus.SUBMITTED_TO_OFFICE
    case.field_submitted_at = now
    case.submitted_at = now
    if remarks:
        case.visit_remarks = remarks

    # The field assignment is finished, not cancelled — it stays on the record.
    await close_stage_assignments(
        session,
        case_id=case.id,
        stage=AssignmentStage.FIELD_INVESTIGATION,
        state=AssignmentState.COMPLETED,
    )

    session.add(
        CaseStatusHistory(
            case_id=case.id,
            previous_status=previous_status,
            new_status=case.status,
            changed_by_id=actor.id,
            comment=remarks or "Submitted to office by the field investigator",
        )
    )
    await audit_service.record(
        session,
        action=AuditAction.CASE_SUBMITTED_TO_OFFICE,
        module="Cases",
        actor=actor,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        old_values={"status": previous_status.value},
        new_values={"status": case.status.value, "outcome": case.outcome.value},
        remarks=remarks,
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="SUBMITTED_TO_OFFICE",
        summary=f"Submitted to office by {actor.full_name}",
        detail=remarks,
        actor=actor,
        icon="send",
    )
    await activity_service.log(
        session,
        user=actor,
        action=ActivityAction.FORM_SUBMITTED,
        summary=f"Submitted case {case.case_number} to office",
        detail=remarks,
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    await _notify_office_queue(session, case)
    return case


async def _notify_office_queue(session: AsyncSession, case: Case) -> None:
    """Tell whoever can assign office work that something is waiting."""
    result = await session.execute(
        select(User).where(User.is_active.is_(True), User.login_enabled.is_(True))
    )
    for account in result.scalars().all():
        if account.is_super_admin or "case.assign_office" in account.permission_codes:
            await notification_service.notify(
                session,
                user_id=account.id,
                notification_type=NotificationType.SYSTEM,
                title=f"Case {case.case_number} awaiting office assignment",
                body=f"{case.company.short_name} — {case.life_assured_name}",
                link=_case_link(case),
                entity_type="Case",
                entity_id=str(case.id),
            )


async def assign_office_staff(
    session: AsyncSession,
    case: Case,
    *,
    office_staff_id: uuid.UUID,
    actor: User,
    notes: str | None = None,
    due_at: datetime | None = None,
    request: Request | None = None,
) -> Case:
    """Stage B assignment. Leaves the field assignment untouched."""
    assert_office_assignable(case.status)

    assignee = await session.get(User, office_staff_id)
    if assignee is None or not assignee.is_active or not assignee.login_enabled:
        raise ValidationError("The selected staff member is not available.")

    previous_id = case.office_staff_id
    if previous_id == office_staff_id:
        raise ConflictError(f"Office processing is already with {assignee.full_name}.")
    is_reassignment = previous_id is not None

    now = utcnow()
    case.office_staff_id = assignee.id
    case.office_assigned_by_id = actor.id
    case.office_assigned_at = now
    if due_at is not None:
        case.due_at = ensure_utc(due_at)

    previous_status = case.status
    case.status = status_after_office_assignment(case.status)
    if case.office_started_at is None:
        case.office_started_at = now

    await close_stage_assignments(
        session,
        case_id=case.id,
        stage=AssignmentStage.OFFICE_PROCESSING,
        state=AssignmentState.RELEASED,
    )
    session.add(
        CaseAssignment(
            case_id=case.id,
            stage=AssignmentStage.OFFICE_PROCESSING,
            state=AssignmentState.ACTIVE,
            assigned_to_id=assignee.id,
            assigned_by_id=actor.id,
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
                changed_by_id=actor.id,
                comment="Office processing started",
            )
        )

    await audit_service.record(
        session,
        action=(
            AuditAction.CASE_OFFICE_REASSIGNED
            if is_reassignment
            else AuditAction.CASE_OFFICE_ASSIGNED
        ),
        module="Cases",
        actor=actor,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        old_values={"office_staff_id": previous_id} if previous_id else None,
        new_values={"office_staff_id": assignee.id, "status": case.status.value},
        remarks=notes,
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="OFFICE_ASSIGNED",
        summary=(
            f"Office processing reassigned to {assignee.full_name}"
            if is_reassignment
            else f"Assigned to office staff {assignee.full_name}"
        ),
        detail=notes,
        actor=actor,
        icon="building",
    )
    await activity_service.log(
        session,
        user=actor,
        action=ActivityAction.CASE_ASSIGNED,
        summary=(f"Assigned case {case.case_number} to {assignee.full_name} for office processing"),
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    await notification_service.notify(
        session,
        user_id=assignee.id,
        notification_type=NotificationType.CASE_ASSIGNED,
        title=f"Case {case.case_number} is ready for office processing",
        body=f"{case.company.short_name} — {case.life_assured_name}",
        link=_case_link(case),
        entity_type="Case",
        entity_id=str(case.id),
    )
    return case


async def update_visit(
    session: AsyncSession,
    case: Case,
    *,
    visit_status: VisitStatus,
    actor: User,
    scheduled_at: datetime | None = None,
    remarks: str | None = None,
    request: Request | None = None,
) -> Case:
    """Record field-visit progress, which is tracked apart from case status."""
    if case.status in CLOSED_STATUSES:
        raise ConflictError(f"{status_label(case.status)} cases cannot have their visit updated.")

    previous = case.visit_status
    now = utcnow()
    case.visit_status = visit_status
    if remarks:
        case.visit_remarks = remarks

    if visit_status == VisitStatus.VISIT_SCHEDULED:
        case.visit_scheduled_at = ensure_utc(scheduled_at) or now
    elif visit_status == VisitStatus.VISIT_IN_PROGRESS:
        case.visit_started_at = case.visit_started_at or now
    elif visit_status in {
        VisitStatus.VISITED,
        VisitStatus.INFORMATION_COLLECTED,
        VisitStatus.FORM_COMPLETED,
    }:
        case.visited_at = case.visited_at or now

    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="VISIT_UPDATED",
        summary=f"Visit status: {visit_label(visit_status)}",
        detail=remarks,
        actor=actor,
        icon="map-pin",
    )
    await activity_service.log(
        session,
        user=actor,
        action=ActivityAction.CASE_EDITED,
        summary=(f"Set visit status of {case.case_number} to {visit_label(visit_status)}"),
        detail=f"Previously {visit_label(previous)}",
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    return case


# --------------------------------------------------------------------------- #
# Assignment candidates
# --------------------------------------------------------------------------- #
async def workload_snapshot(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    """Active / pending / completed counts across both stages, in one pass."""
    if not user_ids:
        return {}
    snapshot: dict[uuid.UUID, dict[str, int]] = {
        user_id: {
            "active_cases": 0,
            "pending_cases": 0,
            "completed_this_month": 0,
            "overdue_cases": 0,
        }
        for user_id in user_ids
    }

    now = utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    open_values = [s.value for s in OPEN_STATUSES]
    pending_values = [
        CaseStatus.ASSIGNED.value,
        CaseStatus.ACCEPTED.value,
        CaseStatus.AWAITING_OFFICE_ASSIGNMENT.value,
    ]

    for column in (Case.assigned_to_id, Case.office_staff_id):
        active = await session.execute(
            select(column, func.count())
            .where(column.in_(user_ids), Case.status.in_(open_values))
            .group_by(column)
        )
        for owner, total in active.all():
            if owner in snapshot:
                snapshot[owner]["active_cases"] += int(total)

        pending = await session.execute(
            select(column, func.count())
            .where(column.in_(user_ids), Case.status.in_(pending_values))
            .group_by(column)
        )
        for owner, total in pending.all():
            if owner in snapshot:
                snapshot[owner]["pending_cases"] += int(total)

        done = await session.execute(
            select(column, func.count())
            .where(
                column.in_(user_ids),
                Case.status == CaseStatus.COMPLETED,
                Case.completed_at >= month_start,
            )
            .group_by(column)
        )
        for owner, total in done.all():
            if owner in snapshot:
                snapshot[owner]["completed_this_month"] += int(total)

        overdue = await session.execute(
            select(column, func.count())
            .where(
                column.in_(user_ids),
                Case.status.in_(open_values),
                Case.due_at.is_not(None),
                Case.due_at < now,
            )
            .group_by(column)
        )
        for owner, total in overdue.all():
            if owner in snapshot:
                snapshot[owner]["overdue_cases"] += int(total)

    return snapshot


async def stage_assignments(session: AsyncSession, case_id: uuid.UUID) -> list[CaseAssignment]:
    result = await session.execute(
        select(CaseAssignment)
        .where(CaseAssignment.case_id == case_id)
        .order_by(CaseAssignment.created_at.desc())
    )
    return list(result.scalars().all())


def stage_summary(case: Case, assignments: list[CaseAssignment]) -> dict[str, Any]:
    """Which desk holds the case, and who held it before."""
    active_field = next(
        (
            a
            for a in assignments
            if a.stage == AssignmentStage.FIELD_INVESTIGATION and a.state == AssignmentState.ACTIVE
        ),
        None,
    )
    active_office = next(
        (
            a
            for a in assignments
            if a.stage == AssignmentStage.OFFICE_PROCESSING and a.state == AssignmentState.ACTIVE
        ),
        None,
    )
    return {
        "field_assignment_id": str(active_field.id) if active_field else None,
        "office_assignment_id": str(active_office.id) if active_office else None,
        "field_stage_complete": case.field_submitted_at is not None,
        "office_stage_started": case.office_assigned_at is not None,
        "total_assignments": len(assignments),
    }


# --------------------------------------------------------------------------- #
# Reopening a closed case
# --------------------------------------------------------------------------- #
async def reopen_case(
    session: AsyncSession,
    case: Case,
    *,
    actor: User,
    reason: str,
    request: Request | None = None,
) -> Case:
    """Put a closed case back into the workflow.

    Completed, Rejected and Cancelled are terminal in the status machine, and
    should stay that way — a case does not drift out of a final state by
    accident. But a case can be closed in error (a client file that carried
    someone else's status, a premature completion), and there has to be a way
    back that is deliberate and on the record.

    The case returns to the desk that last held it, so reopening a completed
    office case does not silently send it back to the field.
    """
    if case.status not in CLOSED_STATUSES:
        raise ConflictError(
            f"{status_label(case.status)} cases are already open."
        )
    if not reason or len(reason.strip()) < 5:
        raise ValidationError("State why this case is being reopened.")

    previous = case.status
    target = (
        CaseStatus.OFFICE_PROCESSING
        if case.office_staff_id is not None
        else CaseStatus.ASSIGNED
        if case.assigned_to_id is not None
        else CaseStatus.UNASSIGNED
    )

    case.status = target
    case.completed_at = None
    case.completion_date = None
    case.verified_at = None

    session.add(
        CaseStatusHistory(
            case_id=case.id,
            previous_status=previous,
            new_status=target,
            changed_by_id=actor.id,
            comment=f"Reopened — {reason.strip()}",
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
        new_values={"status": target.value},
        remarks=f"Reopened: {reason.strip()}",
        request=request,
    )
    await audit_service.timeline(
        session,
        case_id=case.id,
        event_type="CASE_REOPENED",
        summary=f"Reopened from {status_label(previous)}",
        detail=reason.strip(),
        actor=actor,
        icon="rotate-ccw",
    )
    await activity_service.log(
        session,
        user=actor,
        action=ActivityAction.STATUS_CHANGED,
        summary=f"Reopened case {case.case_number}",
        detail=reason.strip(),
        case_id=case.id,
        entity_type="Case",
        entity_id=case.id,
        entity_label=case.case_number,
        request=request,
    )
    return case
