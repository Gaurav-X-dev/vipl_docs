"""Clock in / clock out attendance.

The client's rule, and the reason this is not derived from the login trail:

    Online/Offline  is NOT  Clocked In/Clocked Out

Someone can be signed in without being on shift (browsing the dashboard from
home) and on shift without the browser open (out on a field visit). So presence
comes from ``users.last_activity_at`` and attendance comes only from an explicit
:class:`AttendanceSession`. Both are shown, never conflated.

Invalid states this module refuses:

* clocking out without an open session;
* a second clock-in while one is already open;
* two open sessions for one user, ever.

A shift left open past midnight is closed automatically at the end of its own
working day and flagged ``auto_closed`` so the correction is visible rather
than silently inflating someone's hours.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError, WorkflowError
from app.models.enums import AttendanceStatus, ClockState
from app.models.hr import Attendance, AttendanceSession, Employee
from app.models.user import User
from app.utils.dates import (
    end_of_day,
    ensure_utc,
    to_app_tz,
    utcnow,
)

#: A shift open longer than this is treated as a forgotten clock-out.
MAX_SHIFT_HOURS = 16


def working_day(moment: datetime | None = None) -> date:
    """Today in the application's timezone, not the server's."""
    localised = to_app_tz(moment or utcnow())
    return localised.date() if localised else datetime.now().date()


def session_minutes(row: AttendanceSession, now: datetime | None = None) -> int:
    """Worked minutes, live for an open session and frozen once closed."""
    if row.worked_minutes is not None:
        return row.worked_minutes
    start = ensure_utc(row.clock_in_at)
    end = ensure_utc(row.clock_out_at) or ensure_utc(now) or utcnow()
    if start is None or end is None or end <= start:
        return 0
    return int((end - start).total_seconds() // 60)


@dataclass
class ClockStatus:
    """Everything the header widget needs, in one object."""

    state: ClockState
    session_id: uuid.UUID | None
    clock_in_at: datetime | None
    clock_out_at: datetime | None
    worked_minutes_today: int
    open_session_minutes: int
    sessions_today: int
    work_date: date


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
async def open_session(session: AsyncSession, user_id: uuid.UUID) -> AttendanceSession | None:
    result = await session.execute(
        select(AttendanceSession)
        .where(
            AttendanceSession.user_id == user_id,
            AttendanceSession.is_open.is_(True),
        )
        .order_by(AttendanceSession.clock_in_at.desc())
    )
    return result.scalars().first()


async def sessions_for_day(
    session: AsyncSession, user_id: uuid.UUID, day: date
) -> list[AttendanceSession]:
    result = await session.execute(
        select(AttendanceSession)
        .where(
            AttendanceSession.user_id == user_id,
            AttendanceSession.work_date == day,
        )
        .order_by(AttendanceSession.clock_in_at)
    )
    return list(result.scalars().all())


async def status_for(session: AsyncSession, user: User) -> ClockStatus:
    day = working_day()
    await close_stale_sessions(session, user_id=user.id)
    today = await sessions_for_day(session, user.id, day)
    live = next((row for row in today if row.is_open), None)
    total = sum(session_minutes(row) for row in today)
    last_closed = next((row for row in reversed(today) if not row.is_open), None)
    return ClockStatus(
        state=ClockState.CLOCKED_IN if live else ClockState.CLOCKED_OUT,
        session_id=live.id if live else None,
        # Always UTC-aware on the way out: a naive timestamp serialises
        # without a zone and the browser then reads it as local time, which
        # makes the running shift clock jump by the offset.
        clock_in_at=ensure_utc(
            live.clock_in_at if live else (today[0].clock_in_at if today else None)
        ),
        clock_out_at=ensure_utc(last_closed.clock_out_at if last_closed else None),
        worked_minutes_today=total,
        open_session_minutes=session_minutes(live) if live else 0,
        sessions_today=len(today),
        work_date=day,
    )


async def clock_states_for(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, ClockState]:
    """Clock state for a list of users in one query, for the staff tables."""
    if not user_ids:
        return {}
    result = await session.execute(
        select(AttendanceSession.user_id).where(
            AttendanceSession.user_id.in_(user_ids),
            AttendanceSession.is_open.is_(True),
        )
    )
    clocked_in = set(result.scalars().all())
    return {
        user_id: (ClockState.CLOCKED_IN if user_id in clocked_in else ClockState.CLOCKED_OUT)
        for user_id in user_ids
    }


async def worked_minutes_for(
    session: AsyncSession, user_ids: list[uuid.UUID], day: date
) -> dict[uuid.UUID, int]:
    if not user_ids:
        return {}
    result = await session.execute(
        select(AttendanceSession).where(
            AttendanceSession.user_id.in_(user_ids),
            AttendanceSession.work_date == day,
        )
    )
    totals: dict[uuid.UUID, int] = {}
    for row in result.scalars().all():
        totals[row.user_id] = totals.get(row.user_id, 0) + session_minutes(row)
    return totals


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
async def close_stale_sessions(session: AsyncSession, user_id: uuid.UUID | None = None) -> int:
    """Close shifts nobody clocked out of. Returns how many were closed."""
    cutoff = utcnow() - timedelta(hours=MAX_SHIFT_HOURS)
    query = select(AttendanceSession).where(
        AttendanceSession.is_open.is_(True),
        AttendanceSession.clock_in_at <= cutoff,
    )
    if user_id is not None:
        query = query.where(AttendanceSession.user_id == user_id)
    result = await session.execute(query)
    stale = list(result.scalars().all())
    for row in stale:
        start = ensure_utc(row.clock_in_at) or utcnow()
        # Close at the end of the shift's own working day, never "now" - an
        # untouched session must not accrue days of overtime.
        row.clock_out_at = min(end_of_day(row.work_date), start + timedelta(hours=MAX_SHIFT_HOURS))
        row.worked_minutes = session_minutes(row, now=row.clock_out_at)
        row.is_open = False
        row.auto_closed = True
        row.clock_out_note = "Closed automatically - no clock-out was recorded."
        await _roll_up_day(session, row.user_id, row.employee_id, row.work_date)
    return len(stale)


async def clock_in(
    session: AsyncSession,
    *,
    user: User,
    note: str | None = None,
    ip_address: str | None = None,
) -> AttendanceSession:
    await close_stale_sessions(session, user_id=user.id)
    existing = await open_session(session, user.id)
    if existing is not None:
        raise WorkflowError(
            "You are already clocked in. Clock out before starting a new shift.",
            details={"clocked_in_at": existing.clock_in_at.isoformat()},
        )

    employee_id = await _employee_id_for(session, user.id)
    now = utcnow()
    row = AttendanceSession(
        user_id=user.id,
        employee_id=employee_id,
        work_date=working_day(now),
        clock_in_at=now,
        is_open=True,
        clock_in_ip=ip_address,
        clock_in_note=(note or None),
    )
    session.add(row)
    await session.flush()
    await _roll_up_day(session, user.id, employee_id, row.work_date)
    return row


async def clock_out(
    session: AsyncSession,
    *,
    user: User,
    note: str | None = None,
    ip_address: str | None = None,
) -> AttendanceSession:
    row = await open_session(session, user.id)
    if row is None:
        raise WorkflowError("You are not clocked in, so there is nothing to clock out of.")
    now = utcnow()
    start = ensure_utc(row.clock_in_at)
    if start is not None and now < start:
        raise ValidationError("Clock-out cannot be earlier than clock-in.")
    row.clock_out_at = now
    row.worked_minutes = session_minutes(row, now=now)
    row.is_open = False
    row.clock_out_ip = ip_address
    row.clock_out_note = note or None
    await session.flush()
    await _roll_up_day(session, user.id, row.employee_id, row.work_date)
    return row


async def _employee_id_for(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    result = await session.execute(select(Employee.id).where(Employee.user_id == user_id))
    return result.scalars().first()


async def _roll_up_day(
    session: AsyncSession,
    user_id: uuid.UUID,
    employee_id: uuid.UUID | None,
    day: date,
) -> Attendance | None:
    """Keep the daily HR ``attendance`` row in step with the clock sessions.

    HR-entered rows are never overwritten: only rows this function created, or
    that were derived from logins, are refreshed.
    """
    if employee_id is None:
        return None
    rows = await sessions_for_day(session, user_id, day)
    total = sum(session_minutes(row) for row in rows)
    # SQLite hands back naive datetimes while a row added in this transaction
    # still holds the aware value it was created with. Comparing the two raises,
    # so everything is normalised to UTC before any min/max.
    starts = [moment for moment in (ensure_utc(r.clock_in_at) for r in rows) if moment]
    ends = [moment for moment in (ensure_utc(r.clock_out_at) for r in rows) if moment]
    first_in = min(starts, default=None)
    last_out = max(ends, default=None)

    result = await session.execute(
        select(Attendance).where(Attendance.employee_id == employee_id, Attendance.work_date == day)
    )
    record = result.scalars().first()
    if record is None:
        record = Attendance(
            employee_id=employee_id,
            work_date=day,
            status=AttendanceStatus.PRESENT,
            derived_from_clock=True,
        )
        session.add(record)
    elif not record.derived_from_clock and not record.derived_from_login:
        # A human edited this day by hand - leave their figures alone.
        return record

    record.derived_from_clock = True
    record.derived_from_login = False
    record.check_in_at = first_in
    record.check_out_at = last_out
    record.worked_hours = round(total / 60, 2) if total else 0
    if total and total < 4 * 60:
        record.status = AttendanceStatus.HALF_DAY
    elif total:
        record.status = AttendanceStatus.PRESENT
    return record


# --------------------------------------------------------------------------- #
# Admin views
# --------------------------------------------------------------------------- #
async def day_overview(session: AsyncSession, day: date) -> list[dict]:
    """One row per user who has any clock activity on ``day``."""
    result = await session.execute(
        select(AttendanceSession)
        .where(AttendanceSession.work_date == day)
        .order_by(AttendanceSession.clock_in_at)
    )
    grouped: dict[uuid.UUID, list[AttendanceSession]] = {}
    for row in result.scalars().all():
        grouped.setdefault(row.user_id, []).append(row)

    overview: list[dict] = []
    for rows in grouped.values():
        total = sum(session_minutes(row) for row in rows)
        live = next((r for r in rows if r.is_open), None)
        closed = [
            moment for moment in (ensure_utc(r.clock_out_at) for r in rows) if moment
        ]
        owner = rows[0].user
        overview.append(
            {
                "user_id": rows[0].user_id,
                "user_name": owner.full_name if owner else "Unknown",
                "email": owner.email if owner else None,
                "employee_id": rows[0].employee_id,
                "work_date": day,
                "first_clock_in": ensure_utc(rows[0].clock_in_at),
                "last_clock_out": max(closed, default=None),
                "worked_minutes": total,
                "sessions": len(rows),
                "clock_state": (ClockState.CLOCKED_IN if live else ClockState.CLOCKED_OUT),
                "auto_closed": any(r.auto_closed for r in rows),
            }
        )
    overview.sort(key=lambda item: str(item["user_name"]).lower())
    return overview


async def day_totals(session: AsyncSession, day: date) -> dict[str, int]:
    """Head-count tiles for the attendance dashboard."""
    active_users = await session.execute(
        select(func.count())
        .select_from(User)
        .where(User.is_active.is_(True), User.login_enabled.is_(True))
    )
    total_staff = int(active_users.scalar_one() or 0)

    clocked_in = await session.execute(
        select(func.count(func.distinct(AttendanceSession.user_id))).where(
            AttendanceSession.is_open.is_(True)
        )
    )
    in_now = int(clocked_in.scalar_one() or 0)

    any_today = await session.execute(
        select(func.count(func.distinct(AttendanceSession.user_id))).where(
            AttendanceSession.work_date == day
        )
    )
    present = int(any_today.scalar_one() or 0)

    minutes = await session.execute(
        select(func.coalesce(func.sum(AttendanceSession.worked_minutes), 0)).where(
            AttendanceSession.work_date == day
        )
    )
    return {
        "total_staff": total_staff,
        "clocked_in": in_now,
        "clocked_out": max(0, present - in_now),
        "present_today": present,
        "not_clocked_in": max(0, total_staff - present),
        "total_worked_minutes": int(minutes.scalar_one() or 0),
    }


async def history_for(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 200,
) -> list[AttendanceSession]:
    query = select(AttendanceSession).where(AttendanceSession.user_id == user_id)
    if date_from is not None:
        query = query.where(AttendanceSession.work_date >= date_from)
    if date_to is not None:
        query = query.where(AttendanceSession.work_date <= date_to)
    result = await session.execute(
        query.order_by(AttendanceSession.clock_in_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


def format_duration(minutes: int | None) -> str:
    """512 minutes becomes "08:32" - the format both dashboards display."""
    if not minutes or minutes < 0:
        return "00:00"
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
