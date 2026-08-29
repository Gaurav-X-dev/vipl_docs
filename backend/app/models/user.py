"""User accounts, sessions and login history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import StaffCategory
from app.models.rbac import Role, user_roles

if TYPE_CHECKING:
    from app.models.hr import Employee


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A login account.

    Staff members are users that also carry an :class:`Employee` profile; HR can
    hold employee records for people who have no login at all.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_last_activity_at", "last_activity_at"),
        Index("ix_users_is_active_staff_category", "is_active", "staff_category"),
    )

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(24), nullable=True)

    #: Field investigator vs back-office employee — Image 1 splits the two.
    staff_category: Mapped[StaffCategory] = mapped_column(
        Enum(StaffCategory, native_enum=False, length=24),
        nullable=False,
        default=StaffCategory.BACK_OFFICE,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    login_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_logout_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Refreshed by the frontend heartbeat; drives the green/red status dot.
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failed_login_count: Mapped[int] = mapped_column(nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles, back_populates="users", lazy="selectin"
    )
    employee: Mapped[Employee | None] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="noload"
    )

    # ---------------------------------------------------------------- helpers
    @property
    def role_codes(self) -> set[str]:
        return {role.code for role in self.roles}

    @property
    def permission_codes(self) -> set[str]:
        if self.is_super_admin:
            from app.core.permissions import ALL_PERMISSION_CODES

            return set(ALL_PERMISSION_CODES)
        codes: set[str] = set()
        for role in self.roles:
            if role.is_active:
                codes |= role.permission_codes
        return codes

    def has_permission(self, code: str) -> bool:
        return self.is_super_admin or code in self.permission_codes

    @property
    def is_locked(self) -> bool:
        if self.locked_until is None:
            return False
        return self.locked_until > datetime.now(UTC)

    def is_online(self, timeout_minutes: int) -> bool:
        """Green dot logic. Not a sticky flag — activity must be recent."""
        if not self.is_active or self.last_activity_at is None:
            return False
        threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
        last = self.last_activity_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
        return last >= threshold


class UserSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One row per login; kept for the login-history and current-session views."""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_user_sessions_user_active", "user_id", "is_active"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    device_label: Mapped[str | None] = mapped_column(String(128), nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship(back_populates="sessions", lazy="joined")


class LoginAttempt(UUIDPrimaryKeyMixin, Base):
    """Every login attempt, successful or not — feeds the security views."""

    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_attempts_email_created", "email", "created_at"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    successful: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failure_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
