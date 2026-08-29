"""Dynamic navigation, clock in / clock out, and the user activity log.

Three small routers that share one theme: they describe *who is working on
what, right now*. Everything here is scoped server-side — an investigator's
sidebar counts, attendance and activity are their own, and only a user holding
the matching ``*.view_all`` permission sees anyone else's.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, client_ip, require_permissions
from app.core.errors import NotFoundError, PermissionDeniedError
from app.core.pagination import Page, PageParams, page_params, paginate
from app.models.audit import UserActivity
from app.models.case import Case
from app.models.enums import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    ActivityAction,
    AuditAction,
    CaseStatus,
    ClockState,
)
from app.models.user import User
from app.schemas.common import Message, UserBrief
from app.schemas.workspace import (
    ActivityOut,
    AttendanceDashboardOut,
    AttendanceOverviewRow,
    AttendanceSessionOut,
    AttendanceTotals,
    ClockActionIn,
    ClockStatusOut,
    LiveUserRow,
    SidebarOut,
)
from app.services import activity_service, attendance_service, audit_service, navigation_service
from app.services.settings_service import get_int
from app.utils.dates import utcnow

PageDep = Annotated[PageParams, Depends(page_params)]

router = APIRouter(prefix="/navigation", tags=["Navigation"])
attendance_router = APIRouter(prefix="/attendance", tags=["Attendance"])
activity_router = APIRouter(prefix="/activity", tags=["Activity"])


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
@router.get("/sidebar", response_model=SidebarOut)
async def sidebar(session: DbSession, user: CurrentUser) -> SidebarOut:
    """The company-wise menu tree, generated from live data.

    Called on every page load, so it is deliberately cheap: two grouped
    aggregate queries per category plus four scalar counts, and no case rows
    are ever loaded into memory.
    """
    payload = await navigation_service.sidebar(session, user)
    return SidebarOut.model_validate(payload)


@router.get("/buckets")
async def bucket_definitions() -> dict[str, list[dict]]:
    """Bucket key -> concrete statuses, so the case list can filter locally."""
    return {
        "company": [
            {
                "key": key,
                "label": label,
                "statuses": sorted(s.value for s in members) if members else None,
            }
            for key, label, members in navigation_service.BUCKETS
        ],
        "category": [
            {
                "key": key,
                "label": label,
                "statuses": sorted(s.value for s in members) if members else None,
            }
            for key, label, members in navigation_service.CATEGORY_BUCKETS
        ],
    }


# --------------------------------------------------------------------------- #
# Attendance — self service
# --------------------------------------------------------------------------- #
def _status_payload(status: attendance_service.ClockStatus) -> ClockStatusOut:
    return ClockStatusOut(
        state=status.state,
        session_id=status.session_id,
        clock_in_at=status.clock_in_at,
        clock_out_at=status.clock_out_at,
        worked_minutes_today=status.worked_minutes_today,
        open_session_minutes=status.open_session_minutes,
        sessions_today=status.sessions_today,
        work_date=status.work_date,
        worked_display=attendance_service.format_duration(status.worked_minutes_today),
        can_clock_in=status.state == ClockState.CLOCKED_OUT,
        can_clock_out=status.state == ClockState.CLOCKED_IN,
    )


def _session_payload(row) -> AttendanceSessionOut:
    payload = AttendanceSessionOut.model_validate(row)
    payload.worked_display = attendance_service.format_duration(
        attendance_service.session_minutes(row)
    )
    return payload


@attendance_router.get("/me", response_model=ClockStatusOut)
async def my_clock_status(session: DbSession, user: CurrentUser) -> ClockStatusOut:
    status = await attendance_service.status_for(session, user)
    await session.commit()
    return _status_payload(status)


@attendance_router.post("/clock-in", response_model=ClockStatusOut)
async def clock_in(
    payload: ClockActionIn,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> ClockStatusOut:
    """Start a shift.

    Signing in is not attendance — this is the only thing that starts the
    clock, and it refuses a second shift while one is already open.
    """
    row = await attendance_service.clock_in(
        session, user=user, note=payload.note, ip_address=client_ip(request)
    )
    await audit_service.record(
        session,
        action=AuditAction.CLOCK_IN,
        module="Attendance",
        actor=user,
        entity_type="AttendanceSession",
        entity_id=row.id,
        entity_label=f"{user.full_name} — {row.work_date.isoformat()}",
        new_values={"clock_in_at": row.clock_in_at, "note": payload.note},
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.CLOCK_IN,
        summary="Clocked in",
        detail=payload.note,
        entity_type="AttendanceSession",
        entity_id=row.id,
        request=request,
    )
    status = await attendance_service.status_for(session, user)
    await session.commit()
    return _status_payload(status)


@attendance_router.post("/clock-out", response_model=ClockStatusOut)
async def clock_out(
    payload: ClockActionIn,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> ClockStatusOut:
    row = await attendance_service.clock_out(
        session, user=user, note=payload.note, ip_address=client_ip(request)
    )
    worked = attendance_service.format_duration(row.worked_minutes)
    await audit_service.record(
        session,
        action=AuditAction.CLOCK_OUT,
        module="Attendance",
        actor=user,
        entity_type="AttendanceSession",
        entity_id=row.id,
        entity_label=f"{user.full_name} — {row.work_date.isoformat()}",
        new_values={"clock_out_at": row.clock_out_at, "worked": worked},
        request=request,
    )
    await activity_service.log(
        session,
        user=user,
        action=ActivityAction.CLOCK_OUT,
        summary=f"Clocked out after {worked}",
        detail=payload.note,
        entity_type="AttendanceSession",
        entity_id=row.id,
        request=request,
    )
    status = await attendance_service.status_for(session, user)
    await session.commit()
    return _status_payload(status)


@attendance_router.get("/me/sessions", response_model=list[AttendanceSessionOut])
async def my_sessions(
    session: DbSession,
    user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AttendanceSessionOut]:
    rows = await attendance_service.history_for(
        session, user.id, date_from=date_from, date_to=date_to, limit=limit
    )
    return [_session_payload(row) for row in rows]


# --------------------------------------------------------------------------- #
# Attendance — administration
# --------------------------------------------------------------------------- #
@attendance_router.get(
    "/dashboard",
    response_model=AttendanceDashboardOut,
    dependencies=[Depends(require_permissions("attendance.view_all"))],
)
async def attendance_dashboard(
    session: DbSession,
    user: CurrentUser,
    work_date: date | None = None,
) -> AttendanceDashboardOut:
    """Who is on shift today, and for how long."""
    day = work_date or attendance_service.working_day()
    await attendance_service.close_stale_sessions(session)
    await session.commit()

    totals = await attendance_service.day_totals(session, day)
    rows = await attendance_service.day_overview(session, day)
    timeout = await get_int(session, "staff_online_timeout_minutes", 5)

    user_ids = [row["user_id"] for row in rows]
    latest = await activity_service.latest_for_users(session, user_ids)
    presence = await _online_map(session, user_ids, timeout)

    return AttendanceDashboardOut(
        work_date=day,
        totals=AttendanceTotals(
            **totals,
            total_worked_display=attendance_service.format_duration(totals["total_worked_minutes"]),
        ),
        rows=[
            AttendanceOverviewRow(
                **row,
                worked_display=attendance_service.format_duration(row["worked_minutes"]),
                is_online=presence.get(row["user_id"], False),
                current_activity=(
                    latest[row["user_id"]].summary if row["user_id"] in latest else None
                ),
            )
            for row in rows
        ],
    )


@attendance_router.get(
    "/sessions/{user_id}",
    response_model=list[AttendanceSessionOut],
    dependencies=[Depends(require_permissions("attendance.view_all"))],
)
async def sessions_for_user(
    user_id: uuid.UUID,
    session: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[AttendanceSessionOut]:
    rows = await attendance_service.history_for(
        session, user_id, date_from=date_from, date_to=date_to, limit=limit
    )
    return [_session_payload(row) for row in rows]


@attendance_router.get(
    "/live",
    response_model=list[LiveUserRow],
    dependencies=[Depends(require_permissions("attendance.view_all"))],
)
async def live_users(session: DbSession) -> list[LiveUserRow]:
    """The Super Admin's monitoring table.

    "Currently" is the user's most recent recorded action, not a claim of
    real-time observation — nothing here is inferred beyond what was logged.
    """
    timeout = await get_int(session, "staff_online_timeout_minutes", 5)
    result = await session.execute(
        select(User)
        .where(User.is_active.is_(True), User.login_enabled.is_(True))
        .order_by(User.full_name)
    )
    users = list(result.scalars().all())
    user_ids = [u.id for u in users]

    clock_states = await attendance_service.clock_states_for(session, user_ids)
    worked = await attendance_service.worked_minutes_for(
        session, user_ids, attendance_service.working_day()
    )
    latest = await activity_service.latest_for_users(session, user_ids)
    open_counts = await _open_case_counts(session, user_ids)

    rows: list[LiveUserRow] = []
    for account in users:
        activity = latest.get(account.id)
        clock_state = clock_states.get(account.id, ClockState.CLOCKED_OUT)
        clocked_in_at = None
        if clock_state == ClockState.CLOCKED_IN:
            live = await attendance_service.open_session(session, account.id)
            clocked_in_at = live.clock_in_at if live else None
        minutes = worked.get(account.id, 0)
        rows.append(
            LiveUserRow(
                user=UserBrief(
                    id=account.id,
                    full_name=account.full_name,
                    email=account.email,
                    staff_category=account.staff_category.value,
                    is_online=account.is_online(timeout),
                    last_activity_at=account.last_activity_at,
                ),
                is_online=account.is_online(timeout),
                clock_state=clock_state,
                clocked_in_at=clocked_in_at,
                worked_minutes_today=minutes,
                worked_display=attendance_service.format_duration(minutes),
                last_activity_at=account.last_activity_at,
                current_module=activity.module if activity else None,
                current_action=activity.summary if activity else None,
                active_cases=open_counts.get(account.id, 0),
            )
        )
    return rows


async def _online_map(
    session: DbSession, user_ids: list[uuid.UUID], timeout: int
) -> dict[uuid.UUID, bool]:
    if not user_ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(user_ids)))
    return {u.id: u.is_online(timeout) for u in result.scalars().all()}


async def _open_case_counts(session: DbSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Open cases on each person's desk, counting both stages."""
    if not user_ids:
        return {}
    open_values = [s.value for s in OPEN_STATUSES]
    counts: dict[uuid.UUID, int] = {}
    for column in (Case.assigned_to_id, Case.office_staff_id):
        result = await session.execute(
            select(column, func.count())
            .where(column.in_(user_ids), Case.status.in_(open_values))
            .group_by(column)
        )
        for owner_id, total in result.all():
            if owner_id is not None:
                counts[owner_id] = counts.get(owner_id, 0) + int(total)
    return counts


# --------------------------------------------------------------------------- #
# Activity log
# --------------------------------------------------------------------------- #
@activity_router.get("", response_model=Page[ActivityOut])
async def list_activity(
    session: DbSession,
    user: CurrentUser,
    params: PageDep,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    module: str | None = None,
    case_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    include_noise: bool = False,
) -> Page[ActivityOut]:
    """The Super Admin's User Activity Log.

    Without ``activity.view_all`` the filter is forced to the caller's own
    rows, so a curious investigator cannot read a colleague's day by editing
    the querystring.
    """
    can_view_all = user.is_super_admin or "activity.view_all" in user.permission_codes
    if not can_view_all:
        if "activity.view_self" not in user.permission_codes:
            raise PermissionDeniedError("You cannot view activity logs.")
        user_id = user.id

    query = activity_service.build_query(
        user_id=user_id,
        action=action,
        module=module,
        case_id=case_id,
        date_from=date_from,
        date_to=date_to,
        search=search,
        include_noise=include_noise,
    )
    rows, total = await paginate(session, query, params)
    return Page.build([ActivityOut.model_validate(row) for row in rows], total, params)


@activity_router.get("/modules", response_model=list[str])
async def activity_modules(session: DbSession, user: CurrentUser) -> list[str]:
    return await activity_service.modules(session)


@activity_router.get("/actions", response_model=list[dict])
async def activity_actions() -> list[dict]:
    return [
        {
            "value": action.value,
            "label": action.value.replace("_", " ").title(),
            "module": activity_service.module_for(action),
        }
        for action in ActivityAction
    ]


@activity_router.get("/me", response_model=Page[ActivityOut])
async def my_activity(
    session: DbSession,
    user: CurrentUser,
    params: PageDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[ActivityOut]:
    query = activity_service.build_query(user_id=user.id, date_from=date_from, date_to=date_to)
    rows, total = await paginate(session, query, params)
    return Page.build([ActivityOut.model_validate(row) for row in rows], total, params)


@activity_router.get(
    "/summary/{user_id}",
    dependencies=[Depends(require_permissions("activity.view_all"))],
)
async def user_activity_summary(user_id: uuid.UUID, session: DbSession) -> dict[str, object]:
    """Headline figures for one person, used by the staff detail page."""
    account = await session.get(User, user_id)
    if account is None:
        raise NotFoundError("That user does not exist.")

    day = attendance_service.working_day()
    worked = await attendance_service.worked_minutes_for(session, [user_id], day)
    states = await attendance_service.clock_states_for(session, [user_id])
    latest = await activity_service.latest_for_user(session, user_id)
    open_counts = await _open_case_counts(session, [user_id])

    completed = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            (Case.assigned_to_id == user_id) | (Case.office_staff_id == user_id),
            Case.status.in_([s.value for s in CLOSED_STATUSES]),
        )
    )
    correction = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            Case.assigned_to_id == user_id,
            Case.status == CaseStatus.CORRECTION_REQUIRED,
        )
    )
    return {
        "user_id": str(user_id),
        "full_name": account.full_name,
        "work_date": day.isoformat(),
        "clock_state": states.get(user_id, ClockState.CLOCKED_OUT).value,
        "worked_minutes_today": worked.get(user_id, 0),
        "worked_display": attendance_service.format_duration(worked.get(user_id, 0)),
        "actions_today": await activity_service.count_today(session, user_id),
        "last_action": latest.summary if latest else None,
        "last_action_at": latest.created_at.isoformat() if latest else None,
        "open_cases": open_counts.get(user_id, 0),
        "completed_cases": int(completed.scalar_one() or 0),
        "correction_required": int(correction.scalar_one() or 0),
        "last_seen_at": (
            account.last_activity_at.isoformat() if account.last_activity_at else None
        ),
        "as_of": utcnow().isoformat(),
    }


@activity_router.get(
    "/case/{case_id}",
    response_model=list[ActivityOut],
    dependencies=[Depends(require_permissions("audit.view"))],
)
async def case_activity(
    case_id: uuid.UUID,
    session: DbSession,
    limit: int = Query(default=200, ge=1, le=500),
) -> list[ActivityOut]:
    """Everything anyone did on one case — the operational view, not the audit."""
    result = await session.execute(
        select(UserActivity)
        .where(UserActivity.case_id == case_id)
        .order_by(UserActivity.created_at.desc())
        .limit(limit)
    )
    return [ActivityOut.model_validate(row) for row in result.scalars().all()]


@activity_router.post("/heartbeat", response_model=Message)
async def heartbeat(
    request: Request,
    session: DbSession,
    user: CurrentUser,
    page: str | None = None,
) -> Message:
    """Presence ping. Explicitly *not* attendance — it never touches the clock."""
    user.last_activity_at = utcnow()
    if page:
        await activity_service.log(
            session,
            user=user,
            action=ActivityAction.PAGE_VIEW,
            summary=f"Viewed {page}",
            request=request,
        )
    await session.commit()
    return Message(message="ok")
