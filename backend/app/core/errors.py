"""Application error types and the FastAPI exception handlers."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings

#: Starlette renamed this constant; 422 is the stable wire value.
HTTP_422 = 422

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for every error the application raises deliberately."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "app_error"

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if error_code:
            self.error_code = error_code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationError(AppError):
    status_code = HTTP_422
    error_code = "validation_error"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "authentication_failed"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "permission_denied"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"


class WorkflowError(AppError):
    """Raised when a requested state transition is not allowed."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "invalid_transition"


def _payload(
    error_code: str, message: str, details: Any = None, request_id: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {"error": {"code": error_code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    if request_id:
        body["error"]["request_id"] = request_id
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(
                exc.error_code,
                exc.message,
                exc.details,
                getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err.get("loc", [])[1:]),
                "message": err.get("msg", "invalid value"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=HTTP_422,
            content=_payload(
                "validation_error",
                "The submitted data is not valid.",
                details,
                getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("database integrity error: %s", exc)
        message = "The operation conflicts with existing data."
        origin = str(getattr(exc, "orig", "") or "")
        if "unique" in origin.lower() or "duplicate" in origin.lower():
            message = "A record with these unique values already exists."
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_payload(
                "integrity_error",
                message,
                origin if settings.DEBUG else None,
                getattr(request.state, "request_id", None),
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        incident = uuid.uuid4().hex[:12]
        logger.exception("unhandled error [incident=%s] on %s", incident, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_payload(
                "internal_error",
                (
                    f"An unexpected error occurred. Incident reference: {incident}."
                    if not settings.DEBUG
                    else f"{type(exc).__name__}: {exc}"
                ),
                None,
                getattr(request.state, "request_id", None),
            ),
        )
