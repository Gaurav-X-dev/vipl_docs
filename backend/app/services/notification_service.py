"""In-app notification centre."""

from __future__ import annotations

import uuid

from sqlalchemy import case as case_expr
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.misc import Notification
from app.utils.dates import utcnow


async def notify(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    body: str | None = None,
    link: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title[:200],
        body=body,
        link=link,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(notification)
    return notification


async def notify_many(
    session: AsyncSession,
    *,
    user_ids: list[uuid.UUID],
    notification_type: NotificationType,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> int:
    unique_ids = {uid for uid in user_ids if uid}
    for user_id in unique_ids:
        await notify(
            session,
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            link=link,
        )
    return len(unique_ids)


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 30
) -> list[Notification]:
    statement = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        statement = statement.where(Notification.is_read.is_(False))
    statement = statement.order_by(Notification.created_at.desc()).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def counts(session: AsyncSession, user_id: uuid.UUID) -> tuple[int, int]:
    """Return ``(unread, total)`` for the header badge."""
    result = await session.execute(
        select(
            func.count(),
            func.sum(case_expr((Notification.is_read.is_(False), 1), else_=0)),
        ).where(Notification.user_id == user_id)
    )
    row = result.one()
    return int(row[1] or 0), int(row[0] or 0)


async def mark_read(
    session: AsyncSession, user_id: uuid.UUID, notification_ids: list[uuid.UUID] | None
) -> int:
    statement = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=utcnow())
    )
    if notification_ids:
        statement = statement.where(Notification.id.in_(notification_ids))
    result = await session.execute(statement)
    return int(result.rowcount or 0)
