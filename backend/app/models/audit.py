"""Audit log, human-readable case timeline and per-user activity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, UUIDPrimaryKeyMixin
from app.models.enums import AuditAction
from app.models.form import JSONVariant

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only record of every meaningful change.

    Secrets are never stored here: password hashes, tokens and session keys are
    stripped before the diff is written.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_id", "created_at"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_audit_logs_action", "action"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False, length=40), nullable=False
    )
    module: Mapped[str] = mapped_column(String(48), nullable=False, default="System")
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_method: Mapped[str | None] = mapped_column(String(12), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(48), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    actor: Mapped[User | None] = relationship(lazy="joined")


class CaseTimelineEvent(UUIDPrimaryKeyMixin, Base):
    """Plain-language activity feed shown on the case detail page.

    Shares its source events with the audit log but is written for humans:
    ``"10:05 — Assigned to Rahul Sharma"`` rather than a field-level diff.
    """

    __tablename__ = "case_timeline_events"
    __table_args__ = (Index("ix_case_timeline_case_occurred", "case_id", "occurred_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class UserActivity(UUIDPrimaryKeyMixin, Base):
    """What each user did inside the application, in order.

    Distinct from :class:`AuditLog`: the audit log is the compliance record of
    *data changes*, this is the operational record of *user actions* — opened a
    case, saved a draft, downloaded a report. The Super Admin's User Activity
    screen reads this table.
    """

    __tablename__ = "user_activity"
    __table_args__ = (
        Index("ix_user_activity_user_created", "user_id", "created_at"),
        Index("ix_user_activity_action_created", "activity_type", "created_at"),
        Index("ix_user_activity_case", "case_id", "created_at"),
        Index("ix_user_activity_module", "module", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    activity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="HEARTBEAT")
    #: Cached so the log lists a name even after the account is removed.
    user_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    module: Mapped[str] = mapped_column(String(48), nullable=False, default="Session")
    #: One plain-language line: "Opened case INV-2026-00124".
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    case_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    page: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    user: Mapped[User | None] = relationship(lazy="joined")
