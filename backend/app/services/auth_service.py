"""Login, logout, refresh, heartbeat and password management."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

import jwt
from fastapi import Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.errors import AuthenticationError, RateLimitedError, ValidationError
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.models.audit import UserActivity
from app.models.enums import AuditAction
from app.models.rbac import Role
from app.models.user import LoginAttempt, User, UserSession
from app.services import audit_service
from app.utils.dates import utcnow

#: Deliberately vague — never reveal whether an email exists.
INVALID_CREDENTIALS = "The email address or password is incorrect."


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _device_label(user_agent: str | None) -> str | None:
    if not user_agent:
        return None
    agent = user_agent.lower()
    platform = next(
        (
            name
            for token, name in (
                ("windows", "Windows"),
                ("mac os", "macOS"),
                ("android", "Android"),
                ("iphone", "iPhone"),
                ("ipad", "iPad"),
                ("linux", "Linux"),
            )
            if token in agent
        ),
        "Unknown device",
    )
    browser = next(
        (
            name
            for token, name in (
                ("edg/", "Edge"),
                ("chrome", "Chrome"),
                ("firefox", "Firefox"),
                ("safari", "Safari"),
            )
            if token in agent
        ),
        "Browser",
    )
    return f"{browser} on {platform}"


async def _load_user(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions), selectinload(User.employee)
        )
        .where(func.lower(User.email) == email.strip().lower())
    )
    return result.scalar_one_or_none()


async def _record_attempt(
    session: AsyncSession,
    *,
    email: str,
    user: User | None,
    successful: bool,
    reason: str | None,
    request: Request | None,
) -> None:
    context = audit_service.request_context(request)
    session.add(
        LoginAttempt(
            email=email[:255],
            user_id=user.id if user else None,
            successful=successful,
            failure_reason=reason,
            ip_address=context.get("ip_address"),
            user_agent=context.get("user_agent"),
        )
    )


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    remember_me: bool,
    request: Request | None = None,
) -> tuple[User, UserSession, str, str, object]:
    """Authenticate and open a session.

    Returns ``(user, session_row, access_token, refresh_token, expires_at)``.
    """
    user = await _load_user(session, email)

    if user is not None and user.is_locked:
        await _record_attempt(
            session,
            email=email,
            user=user,
            successful=False,
            reason="account_locked",
            request=request,
        )
        await session.commit()
        raise RateLimitedError(
            "Too many failed sign-in attempts. Please try again in a few minutes."
        )

    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_login_count += 1
            if user.failed_login_count >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = utcnow() + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                user.failed_login_count = 0
        await _record_attempt(
            session,
            email=email,
            user=user,
            successful=False,
            reason="bad_credentials",
            request=request,
        )
        await audit_service.record(
            session,
            action=AuditAction.LOGIN_FAILED,
            module="Authentication",
            actor=None,
            actor_label=email,
            entity_type="User",
            entity_id=user.id if user else None,
            remarks="Invalid credentials",
            request=request,
        )
        await session.commit()
        raise AuthenticationError(INVALID_CREDENTIALS)

    if not user.is_active or not user.login_enabled:
        await _record_attempt(
            session,
            email=email,
            user=user,
            successful=False,
            reason="account_disabled",
            request=request,
        )
        await session.commit()
        raise AuthenticationError(
            "This account has been disabled. Contact your administrator.",
            error_code="account_disabled",
        )

    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    now = utcnow()
    context = audit_service.request_context(request)
    refresh_days = settings.REFRESH_TOKEN_EXPIRE_DAYS * (4 if remember_me else 1)

    session_row = UserSession(
        user_id=user.id,
        ip_address=context.get("ip_address"),
        user_agent=context.get("user_agent"),
        device_label=_device_label(context.get("user_agent")),
        started_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=refresh_days),
        is_active=True,
    )
    session.add(session_row)
    await session.flush()

    access_token, expires_at = create_token(str(user.id), "access", session_id=str(session_row.id))
    refresh_token, _ = create_token(
        str(user.id),
        "refresh",
        session_id=str(session_row.id),
        expires_delta=timedelta(days=refresh_days),
    )
    session_row.refresh_token_hash = _hash_token(refresh_token)

    user.last_login_at = now
    user.last_activity_at = now
    user.last_login_ip = context.get("ip_address")
    user.failed_login_count = 0
    user.locked_until = None

    session.add(
        UserActivity(
            user_id=user.id,
            session_id=session_row.id,
            activity_type="LOGIN",
            user_label=user.full_name,
            module="Authentication",
            summary="Signed in",
            ip_address=context.get("ip_address"),
        )
    )
    await _record_attempt(
        session, email=email, user=user, successful=True, reason=None, request=request
    )
    await audit_service.record(
        session,
        action=AuditAction.LOGIN,
        module="Authentication",
        actor=user,
        entity_type="User",
        entity_id=user.id,
        entity_label=user.email,
        request=request,
    )
    await session.commit()
    return user, session_row, access_token, refresh_token, expires_at


async def refresh(
    session: AsyncSession, refresh_token: str, request: Request | None = None
) -> tuple[User, str, object]:
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired refresh token.") from exc

    session_id = payload.get("sid")
    if not session_id:
        raise AuthenticationError("Invalid refresh token.")

    session_row = await session.get(UserSession, uuid.UUID(str(session_id)))
    if session_row is None or not session_row.is_active:
        raise AuthenticationError("This session has been signed out.")
    if session_row.refresh_token_hash != _hash_token(refresh_token):
        # Token reuse or theft — close the session defensively.
        session_row.is_active = False
        session_row.ended_at = utcnow()
        await session.commit()
        raise AuthenticationError("This refresh token is no longer valid.")

    result = await session.execute(
        select(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions), selectinload(User.employee)
        )
        .where(User.id == session_row.user_id)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or not user.login_enabled:
        raise AuthenticationError("This account is no longer active.")

    access_token, expires_at = create_token(str(user.id), "access", session_id=str(session_row.id))
    session_row.last_seen_at = utcnow()
    user.last_activity_at = utcnow()
    await session.commit()
    return user, access_token, expires_at


async def logout(
    session: AsyncSession,
    user: User,
    session_id: uuid.UUID | None,
    request: Request | None = None,
) -> None:
    now = utcnow()
    if session_id is not None:
        session_row = await session.get(UserSession, session_id)
        if session_row is not None and session_row.user_id == user.id:
            session_row.is_active = False
            session_row.ended_at = now
    else:
        await session.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.is_active.is_(True))
            .values(is_active=False, ended_at=now)
        )

    user.last_logout_at = now
    # Clearing activity flips the indicator to red immediately on sign-out.
    user.last_activity_at = None

    session.add(
        UserActivity(
            user_id=user.id,
            session_id=session_id,
            activity_type="LOGOUT",
            user_label=user.full_name,
            module="Authentication",
            summary="Signed out",
        )
    )
    await audit_service.record(
        session,
        action=AuditAction.LOGOUT,
        module="Authentication",
        actor=user,
        entity_type="User",
        entity_id=user.id,
        entity_label=user.email,
        request=request,
    )
    await session.commit()


async def heartbeat(
    session: AsyncSession,
    user: User,
    *,
    session_id: uuid.UUID | None,
    page: str | None,
    request: Request | None = None,
) -> None:
    """Refresh the activity stamp behind the green/red status indicator."""
    now = utcnow()
    user.last_activity_at = now
    if session_id is not None:
        session_row = await session.get(UserSession, session_id)
        if session_row is not None:
            session_row.last_seen_at = now
    context = audit_service.request_context(request)
    session.add(
        UserActivity(
            user_id=user.id,
            session_id=session_id,
            activity_type="HEARTBEAT",
            page=page,
            ip_address=context.get("ip_address"),
        )
    )
    await session.commit()


async def change_password(
    session: AsyncSession,
    user: User,
    *,
    current_password: str,
    new_password: str,
    request: Request | None = None,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthenticationError("Your current password is incorrect.")
    problems = validate_password_strength(new_password)
    if problems:
        raise ValidationError("The new password does not meet the policy.", details=problems)
    if verify_password(new_password, user.password_hash):
        raise ValidationError("The new password must differ from the current one.")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False

    # Every other session is invalidated after a password change.
    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.is_active.is_(True))
        .values(is_active=False, ended_at=utcnow())
    )

    await audit_service.record(
        session,
        action=AuditAction.PASSWORD_CHANGED,
        module="Authentication",
        actor=user,
        entity_type="User",
        entity_id=user.id,
        entity_label=user.email,
        remarks="Password changed by the account owner.",
        request=request,
    )
    await session.commit()


async def admin_reset_password(
    session: AsyncSession,
    target: User,
    new_password: str,
    *,
    actor: User,
    require_change: bool = True,
    request: Request | None = None,
) -> None:
    problems = validate_password_strength(new_password)
    if problems:
        raise ValidationError("The password does not meet the policy.", details=problems)
    target.password_hash = hash_password(new_password)
    target.password_changed_at = utcnow()
    target.must_change_password = require_change
    target.failed_login_count = 0
    target.locked_until = None

    await session.execute(
        update(UserSession)
        .where(UserSession.user_id == target.id, UserSession.is_active.is_(True))
        .values(is_active=False, ended_at=utcnow())
    )
    await audit_service.record(
        session,
        action=AuditAction.PASSWORD_CHANGED,
        module="Administration",
        actor=actor,
        entity_type="User",
        entity_id=target.id,
        entity_label=target.email,
        remarks="Password reset by an administrator.",
        request=request,
    )


async def current_user_payload(session: AsyncSession, user: User) -> dict:
    employee = user.employee
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "staff_category": user.staff_category.value,
        "is_super_admin": user.is_super_admin,
        "must_change_password": user.must_change_password,
        "last_login_at": user.last_login_at,
        "roles": [{"id": role.id, "code": role.code, "name": role.name} for role in user.roles],
        "permissions": sorted(user.permission_codes),
        "employee_code": employee.employee_code if employee else None,
        "department": (employee.department.name if employee and employee.department else None),
        "designation": (employee.designation.name if employee and employee.designation else None),
    }


async def list_sessions(
    session: AsyncSession, user_id: uuid.UUID, limit: int = 20
) -> list[UserSession]:
    result = await session.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id)
        .order_by(UserSession.started_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_login_attempts(
    session: AsyncSession, *, email: str | None = None, limit: int = 50
) -> list[LoginAttempt]:
    statement = select(LoginAttempt).order_by(LoginAttempt.created_at.desc()).limit(limit)
    if email:
        statement = statement.where(func.lower(LoginAttempt.email) == email.lower())
    result = await session.execute(statement)
    return list(result.scalars().all())
