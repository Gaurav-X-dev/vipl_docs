"""The per-user activity trail behind the Super Admin's monitoring screens.

Deliberately separate from :mod:`app.services.audit_service`:

* the **audit log** answers "what data changed, from what, to what, by whom" —
  it is the compliance record and is written only when something is persisted;
* the **activity log** answers "what did this person do today" — it records
  opening a case, saving a draft or downloading a report, none of which are
  data changes but all of which the client asked to be able to see.

Writing here never fails a request: a monitoring row is not worth losing a
user's work over, so the caller owns the transaction and failures are silent.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import Request
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import UserActivity
from app.models.enums import ACTIVITY_MODULES, ActivityAction
from app.models.user import User
from app.utils.dates import end_of_day, start_of_day, utcnow

#: Heartbeats are noise in the activity feed — they are collapsed into
#: ``users.last_activity_at`` instead of writing a row per ping.
NOISY_ACTIONS: frozenset[ActivityAction] = frozenset(
    {ActivityAction.HEARTBEAT, ActivityAction.PAGE_VIEW}
)


def module_for(action: ActivityAction) -> str:
    return ACTIVITY_MODULES.get(action, "General")


async def log(
    session: AsyncSession,
    *,
    user: User | None,
    action: ActivityAction,
    summary: str,
    detail: str | None = None,
    case_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    entity_label: str | None = None,
    request: Request | None = None,
) -> UserActivity | None:
    """Append one activity row. The caller owns the transaction."""
    if user is None:
        return None

    session_id: uuid.UUID | None = None
    ip_address: str | None = None
    page: str | None = None
    if request is not None:
        session_id = getattr(request.state, "session_id", None)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        elif request.client:
            ip_address = request.client.host
        page = str(request.url.path)[:255]

    entry = UserActivity(
        user_id=user.id,
        session_id=session_id,
        activity_type=action.value,
        user_label=user.full_name,
        module=module_for(action),
        summary=summary[:500],
        detail=detail,
        case_id=case_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else None,
        entity_label=entity_label[:255] if entity_label else None,
        page=page,
        ip_address=ip_address,
        created_at=utcnow(),
    )
    session.add(entry)
    return entry


def build_query(
    *,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    module: str | None = None,
    case_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    include_noise: bool = False,
) -> Select:
    """The filtered activity query shared by the API and the staff detail page."""
    query = select(UserActivity)
    if user_id is not None:
        query = query.where(UserActivity.user_id == user_id)
    if action:
        query = query.where(UserActivity.activity_type == action)
    elif not include_noise:
        query = query.where(UserActivity.activity_type.notin_([a.value for a in NOISY_ACTIONS]))
    if module:
        query = query.where(UserActivity.module == module)
    if case_id is not None:
        query = query.where(UserActivity.case_id == case_id)
    if date_from is not None:
        query = query.where(UserActivity.created_at >= start_of_day(date_from))
    if date_to is not None:
        query = query.where(UserActivity.created_at <= end_of_day(date_to))
    if search:
        needle = f"%{search.strip()}%"
        query = query.where(
            UserActivity.summary.ilike(needle)
            | UserActivity.entity_label.ilike(needle)
            | UserActivity.user_label.ilike(needle)
        )
    return query.order_by(UserActivity.created_at.desc())


async def latest_for_user(session: AsyncSession, user_id: uuid.UUID) -> UserActivity | None:
    """The single most recent meaningful action — "Currently: Editing INV-…"."""
    result = await session.execute(build_query(user_id=user_id).limit(1))
    return result.scalars().first()


async def latest_for_users(
    session: AsyncSession, user_ids: list[uuid.UUID]
) -> dict[uuid.UUID, UserActivity]:
    """One query for the whole monitoring table rather than one per row."""
    if not user_ids:
        return {}
    newest = (
        select(
            UserActivity.user_id.label("user_id"),
            func.max(UserActivity.created_at).label("at"),
        )
        .where(
            UserActivity.user_id.in_(user_ids),
            UserActivity.activity_type.notin_([a.value for a in NOISY_ACTIONS]),
        )
        .group_by(UserActivity.user_id)
        .subquery()
    )
    result = await session.execute(
        select(UserActivity).join(
            newest,
            (UserActivity.user_id == newest.c.user_id) & (UserActivity.created_at == newest.c.at),
        )
    )
    found: dict[uuid.UUID, UserActivity] = {}
    for row in result.scalars().all():
        found.setdefault(row.user_id, row)
    return found


async def count_today(session: AsyncSession, user_id: uuid.UUID) -> int:
    today = datetime.now().date()
    result = await session.execute(
        select(func.count())
        .select_from(UserActivity)
        .where(
            UserActivity.user_id == user_id,
            UserActivity.created_at >= start_of_day(today),
            UserActivity.activity_type.notin_([a.value for a in NOISY_ACTIONS]),
        )
    )
    return int(result.scalar_one() or 0)


async def modules(session: AsyncSession) -> list[str]:
    result = await session.execute(
        select(UserActivity.module).distinct().order_by(UserActivity.module)
    )
    return [m for m in result.scalars().all() if m]
