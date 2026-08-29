"""Two-stage case workflow endpoints and the locking of bank-supplied data.

Kept apart from :mod:`app.api.v1.cases` because these routes describe the
*operational hand-off* rather than the case record itself, and because the
collection routes here (``/cases/assignable-staff``) must be matched before the
``/cases/{case_id}`` catch-all — this router is therefore registered first.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, can_view_all_cases, require_permissions
from app.core.errors import AppError
from app.models.case import Case
from app.models.enums import AssignmentStage, CaseOutcome, ClockState
from app.models.user import User
from app.schemas.common import Message
from app.schemas.workspace import (
    AssignableStaffOut,
    BulkOfficeAssignIn,
    OfficeAssignIn,
    ReopenCaseIn,
    StageAssignmentOut,
    SubmitToOfficeIn,
    VisitUpdateIn,
)
from app.services import (
    attendance_service,
    case_service,
    case_stage_service,
    settings_service,
)

router = APIRouter(prefix="/cases", tags=["Case workflow"])

ViewUser = Annotated[User, Depends(require_permissions("case.view"))]
OfficeAssignUser = Annotated[User, Depends(require_permissions("case.assign_office"))]
EditUser = Annotated[User, Depends(require_permissions("case.edit"))]


async def _load_case(session: DbSession, case_id: uuid.UUID, user: User) -> Case:
    case = await case_service.get_case(session, case_id)
    case_service.assert_can_access(case, user, can_view_all_cases(user))
    return case


# --------------------------------------------------------------------------- #
# Collection routes — must precede /cases/{case_id}
# --------------------------------------------------------------------------- #
@router.get("/assignable-staff", response_model=list[AssignableStaffOut])
async def assignable_staff(
    session: DbSession,
    user: ViewUser,
    stage: AssignmentStage = Query(default=AssignmentStage.FIELD_INVESTIGATION),
    search: str | None = None,
) -> list[AssignableStaffOut]:
    """Candidates for assignment, with the workload figures the dialog shows.

    Presence and clock state sit side by side because they answer different
    questions: online means reachable, clocked in means on shift. Assigning to
    someone who is offline is allowed — it is just useful to know.
    """
    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.is_active.is_(True), User.login_enabled.is_(True))
        .order_by(User.full_name)
    )
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(User.full_name.ilike(term) | User.email.ilike(term))
    result = await session.execute(statement)
    candidates = list(result.unique().scalars().all())

    needed = (
        "investigation.edit"
        if stage == AssignmentStage.FIELD_INVESTIGATION
        else "case.process_office"
    )
    eligible = [
        account
        for account in candidates
        if account.is_super_admin or needed in account.permission_codes
    ]

    ids = [account.id for account in eligible]
    workload = await case_stage_service.workload_snapshot(session, ids)
    clocks = await attendance_service.clock_states_for(session, ids)
    online_timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    blank = {
        "active_cases": 0,
        "pending_cases": 0,
        "completed_this_month": 0,
        "overdue_cases": 0,
    }
    return [
        AssignableStaffOut(
            id=account.id,
            full_name=account.full_name,
            email=account.email,
            staff_category=account.staff_category.value,
            roles=[role.name for role in account.roles],
            is_online=account.is_online(online_timeout),
            clock_state=clocks.get(account.id, ClockState.CLOCKED_OUT),
            **workload.get(account.id, blank),
        )
        for account in eligible
    ]


@router.post("/bulk-assign-office", response_model=Message)
async def bulk_assign_office(
    payload: BulkOfficeAssignIn,
    request: Request,
    session: DbSession,
    user: OfficeAssignUser,
) -> Message:
    """Assign a queue of submitted cases to one office user in one go.

    A case that cannot move (wrong status, already theirs) is reported rather
    than aborting the batch — one bad row should not undo the other 99.
    """
    assigned = 0
    skipped: list[str] = []
    for case_id in payload.case_ids:
        case = await case_service.get_case(session, case_id)
        try:
            await case_stage_service.assign_office_staff(
                session,
                case,
                office_staff_id=payload.office_staff_id,
                actor=user,
                notes=payload.notes,
                request=request,
            )
            assigned += 1
        except AppError as exc:
            skipped.append(f"{case.case_number}: {exc.message}")
    await session.commit()
    detail = None
    if skipped:
        detail = f"{len(skipped)} skipped. " + "; ".join(skipped[:5])
    return Message(message=f"{assigned} case(s) assigned for office processing.", detail=detail)


# --------------------------------------------------------------------------- #
# Stage A -> Stage B
# --------------------------------------------------------------------------- #
@router.post("/{case_id}/submit-to-office", response_model=Message)
async def submit_to_office(
    case_id: uuid.UUID,
    payload: SubmitToOfficeIn,
    request: Request,
    session: DbSession,
    user: ViewUser,
) -> Message:
    """The field investigator hands the case in.

    This queues the case for office assignment; it never completes it. That
    decision belongs to the office and the reviewer.
    """
    case = await _load_case(session, case_id, user)
    outcome = CaseOutcome(payload.outcome) if payload.outcome else None
    await case_stage_service.submit_to_office(
        session,
        case,
        actor=user,
        remarks=payload.remarks,
        outcome=outcome,
        request=request,
    )
    await session.commit()
    return Message(
        message="Submitted to office.",
        detail="The case is now awaiting office assignment.",
    )


@router.post("/{case_id}/assign-office", response_model=Message)
async def assign_office(
    case_id: uuid.UUID,
    payload: OfficeAssignIn,
    request: Request,
    session: DbSession,
    user: OfficeAssignUser,
) -> Message:
    case = await _load_case(session, case_id, user)
    await case_stage_service.assign_office_staff(
        session,
        case,
        office_staff_id=payload.office_staff_id,
        actor=user,
        notes=payload.notes,
        due_at=payload.due_at,
        request=request,
    )
    await session.commit()
    return Message(message="Assigned for office processing.")


@router.post("/{case_id}/visit", response_model=Message)
async def update_visit(
    case_id: uuid.UUID,
    payload: VisitUpdateIn,
    request: Request,
    session: DbSession,
    user: ViewUser,
) -> Message:
    case = await _load_case(session, case_id, user)
    await case_stage_service.update_visit(
        session,
        case,
        visit_status=payload.visit_status,
        actor=user,
        scheduled_at=payload.visit_scheduled_at,
        remarks=payload.remarks,
        request=request,
    )
    await session.commit()
    return Message(message="Visit status updated.")


@router.get("/{case_id}/stage-assignments", response_model=list[StageAssignmentOut])
async def stage_assignments(
    case_id: uuid.UUID, session: DbSession, user: ViewUser
) -> list[StageAssignmentOut]:
    """The full custody chain: every stage, every holder, nothing overwritten."""
    case = await _load_case(session, case_id, user)
    rows = await case_stage_service.stage_assignments(session, case.id)
    online_timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    return [
        StageAssignmentOut(
            id=row.id,
            stage=row.stage,
            state=row.state,
            assigned_to=case_service.user_brief(row.assigned_to, online_timeout),
            assigned_by=case_service.user_brief(row.assigned_by, online_timeout),
            is_reassignment=row.is_reassignment,
            due_at=row.due_at,
            accepted_at=row.accepted_at,
            completed_at=row.completed_at,
            released_at=row.released_at,
            notes=row.notes,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/{case_id}/reopen", response_model=Message)
async def reopen_case(
    case_id: uuid.UUID,
    payload: ReopenCaseIn,
    request: Request,
    session: DbSession,
    user: EditUser,
) -> Message:
    """Bring a closed case back into the workflow, with a stated reason.

    Needed because a case can be closed by mistake — most often by a client
    file whose own Status column said Completed. Without this the case is a
    dead end: its form is read-only and nothing can move it.
    """
    case = await case_service.get_case(session, case_id)
    await case_stage_service.reopen_case(
        session, case, actor=user, reason=payload.reason, request=request
    )
    await session.commit()
    return Message(
        message="Case reopened.",
        detail=f"It is now {case.status.value.replace('_', ' ').title()}.",
    )
