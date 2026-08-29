"""Authentication endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUserOut,
    ForgotPasswordRequest,
    HeartbeatRequest,
    HeartbeatResponse,
    LoginAttemptOut,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    SessionOut,
    TokenPair,
)
from app.schemas.common import Message
from app.services import auth_service, settings_service
from app.utils.dates import utcnow

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request, session: DbSession) -> LoginResponse:
    user, session_row, access_token, refresh_token, expires_at = await auth_service.login(
        session,
        email=str(payload.email),
        password=payload.password,
        remember_me=payload.remember_me,
        request=request,
    )
    return LoginResponse(
        tokens=TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        ),
        user=CurrentUserOut(**await auth_service.current_user_payload(session, user)),
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, request: Request, session: DbSession) -> TokenPair:
    _, access_token, expires_at = await auth_service.refresh(
        session, payload.refresh_token, request
    )
    return TokenPair(
        access_token=access_token,
        refresh_token=payload.refresh_token,
        expires_at=expires_at,
    )


@router.post("/logout", response_model=Message)
async def logout(request: Request, session: DbSession, user: CurrentUser) -> Message:
    session_id = getattr(request.state, "session_id", None)
    await auth_service.logout(session, user, session_id, request)
    return Message(message="Signed out.")


@router.get("/me", response_model=CurrentUserOut)
async def me(session: DbSession, user: CurrentUser) -> CurrentUserOut:
    return CurrentUserOut(**await auth_service.current_user_payload(session, user))


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    payload: HeartbeatRequest,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> HeartbeatResponse:
    """Keeps the staff online indicator green while the user is actually working."""
    session_id = getattr(request.state, "session_id", None)
    await auth_service.heartbeat(
        session, user, session_id=session_id, page=payload.page, request=request
    )
    timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    # Ping comfortably inside the window so a slow network never flips to red.
    return HeartbeatResponse(
        server_time=utcnow(),
        online=True,
        next_ping_seconds=max(30, int(timeout * 60 / 3)),
    )


@router.post("/change-password", response_model=Message)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    session: DbSession,
    user: CurrentUser,
) -> Message:
    await auth_service.change_password(
        session,
        user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        request=request,
    )
    return Message(
        message="Password changed.",
        detail="You have been signed out of all other devices.",
    )


@router.post("/forgot-password", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(payload: ForgotPasswordRequest) -> Message:
    """Self-service reset request.

    Always returns the same response so the endpoint cannot be used to discover
    which email addresses exist. Delivery is handled out of band by an
    administrator until an SMTP relay is configured for this deployment.
    """
    return Message(
        message="If that email is registered, an administrator has been notified.",
        detail="Contact your administrator if you do not receive a reset shortly.",
    )


@router.get("/sessions", response_model=list[SessionOut])
async def my_sessions(session: DbSession, user: CurrentUser) -> list[SessionOut]:
    rows = await auth_service.list_sessions(session, user.id)
    return [SessionOut.model_validate(row) for row in rows]


@router.delete("/sessions/{session_id}", response_model=Message)
async def end_session(
    session_id: uuid.UUID, request: Request, session: DbSession, user: CurrentUser
) -> Message:
    await auth_service.logout(session, user, session_id, request)
    return Message(message="Session ended.")


@router.get("/login-attempts", response_model=list[LoginAttemptOut])
async def my_login_attempts(session: DbSession, user: CurrentUser) -> list[LoginAttemptOut]:
    rows = await auth_service.list_login_attempts(session, email=user.email, limit=25)
    return [LoginAttemptOut.model_validate(row) for row in rows]
