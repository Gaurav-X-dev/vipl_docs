"""FastAPI dependencies: current user, permission guards, common query params."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.rbac import Role
from app.models.user import User, UserSession
from app.utils.dates import utcnow

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> User:
    """Resolve the caller from the bearer token, refreshing their activity."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication is required.")

    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError(
            "Your session has expired. Please sign in again.",
            error_code="token_expired",
        ) from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise AuthenticationError("Invalid authentication token.") from exc

    result = await session.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("Account not found.")
    if not user.is_active or not user.login_enabled:
        raise AuthenticationError(
            "This account has been disabled. Contact your administrator.",
            error_code="account_disabled",
        )

    session_id = payload.get("sid")
    if session_id:
        session_row = await session.get(UserSession, uuid.UUID(str(session_id)))
        if session_row is None or not session_row.is_active:
            raise AuthenticationError(
                "This session has been signed out.", error_code="session_ended"
            )
        session_row.last_seen_at = utcnow()
        request.state.session_id = session_row.id

    # Any authenticated request counts as activity for the online indicator.
    user.last_activity_at = utcnow()
    await session.commit()

    request.state.user_id = user.id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permissions(*codes: str, mode: str = "all") -> Callable[..., Coroutine[Any, Any, User]]:
    """Dependency factory enforcing permissions **on the server**.

    Hiding a button in React is not authorisation; every protected route uses
    this.
    """

    async def _guard(user: CurrentUser) -> User:
        if user.is_super_admin:
            return user
        granted = user.permission_codes
        ok = (
            all(code in granted for code in codes)
            if mode == "all"
            else any(code in granted for code in codes)
        )
        if not ok:
            joiner = " and " if mode == "all" else " or "
            raise PermissionDeniedError(
                "You do not have permission to perform this action.",
                details={"required": joiner.join(codes)},
            )
        return user

    return _guard


def require_super_admin() -> Callable[..., Coroutine[Any, Any, User]]:
    async def _guard(user: CurrentUser) -> User:
        if not user.is_super_admin:
            raise PermissionDeniedError("Only the Super Admin can do this.")
        return user

    return _guard


def can_view_all_cases(user: User) -> bool:
    """Investigators see only their own cases unless explicitly permitted."""
    return user.is_super_admin or "case.view_all" in user.permission_codes


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
