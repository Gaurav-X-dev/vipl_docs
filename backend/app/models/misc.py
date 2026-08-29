"""Notifications, saved filters and the application settings table."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import NotificationType
from app.models.form import JSONVariant

if TYPE_CHECKING:
    from app.models.user import User


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    notification_type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=40), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Frontend route the notification links to.
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(lazy="noload")


class AppSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Runtime-editable settings. Seeded from the environment on first boot."""

    __tablename__ = "app_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_app_settings_key"),)

    key: Mapped[str] = mapped_column(String(96), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="string")
    group: Mapped[str] = mapped_column(String(48), nullable=False, default="General")
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    def typed_value(self) -> Any:
        raw = self.value
        if raw is None:
            return None
        if self.value_type == "int":
            try:
                return int(raw)
            except ValueError:
                return None
        if self.value_type == "bool":
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        if self.value_type == "json":
            import json

            try:
                return json.loads(raw)
            except ValueError:
                return None
        return raw


class SavedFilter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named list view a user wants to come back to."""

    __tablename__ = "saved_filters"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", "name", name="uq_saved_filters_user_name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[str] = mapped_column(String(48), nullable=False, default="cases")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    query: Mapped[dict[str, Any]] = mapped_column(JSONVariant, nullable=False)
    is_shared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
