"""Authentication payloads."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    # ``EmailStr`` rejects RFC-reserved development domains such as ``.local``.
    # VIPL's documented bootstrap account intentionally uses
    # admin@investigation.local, so login accepts a conservative email shape
    # and leaves canonicalisation/account lookup to the auth service.
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("Enter a valid email address.")
        return value


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


class ResetPasswordRequest(BaseModel):
    """Admin-initiated reset. Self-service reset is delivered out of band."""

    user_id: uuid.UUID
    new_password: str | None = Field(
        default=None,
        min_length=8,
        max_length=256,
        description="Leave empty to have a strong temporary password generated.",
    )
    require_change_on_login: bool = True


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        return LoginRequest.validate_email_shape(value)


class RoleBrief(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class CurrentUserOut(ORMModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None
    staff_category: str
    is_super_admin: bool
    must_change_password: bool
    last_login_at: datetime | None = None
    roles: list[RoleBrief] = []
    permissions: list[str] = []
    employee_code: str | None = None
    department: str | None = None
    designation: str | None = None


class LoginResponse(BaseModel):
    tokens: TokenPair
    user: CurrentUserOut


class HeartbeatRequest(BaseModel):
    page: str | None = Field(default=None, max_length=255)


class HeartbeatResponse(BaseModel):
    server_time: datetime
    online: bool = True
    #: Seconds the client should wait before sending the next heartbeat.
    next_ping_seconds: int = 60


class SessionOut(ORMModel):
    id: uuid.UUID
    ip_address: str | None = None
    user_agent: str | None = None
    device_label: str | None = None
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None = None
    is_active: bool


class LoginAttemptOut(ORMModel):
    id: uuid.UUID
    email: str
    successful: bool
    failure_reason: str | None = None
    ip_address: str | None = None
    created_at: datetime
