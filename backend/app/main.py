"""FastAPI application entry point."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.db.session import SessionLocal, dispose_engine, engine
from app.schemas.common import HealthOut
from app.utils.dates import app_timezone, utcnow

VERSION = "1.0.0"

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.ensure_storage_dirs()
    logger.info(
        "%s starting (env=%s, tz=%s)",
        settings.APP_NAME,
        settings.APP_ENV,
        settings.APP_TIMEZONE,
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("database connection OK")
    except Exception as exc:  # noqa: BLE001 - the app must still start to report it
        logger.error("database unreachable at startup: %s", exc)
    yield
    await dispose_engine()
    logger.info("%s stopped", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=VERSION,
    description=(
        "Bank / insurance investigation and death claim case management. "
        "Excel intake, company-specific forms, investigator workflow and "
        "client document generation."
    ),
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-Id"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)

register_exception_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Attach a request id and reject oversized bodies before they are read."""
    request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]

    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit():
        limit = max(settings.max_upload_bytes, settings.max_import_bytes) + 1024 * 1024
        if int(content_length) > limit:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "payload_too_large",
                        "message": "The request body is too large.",
                    }
                },
            )

    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers["X-Response-Time-Ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    # Conservative hardening headers; the API serves JSON and file downloads only.
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.get("/health", response_model=HealthOut, tags=["System"])
async def health() -> HealthOut:
    database = "up"
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - health must not raise
        database = "down"
    return HealthOut(
        status="ok" if database == "up" else "degraded",
        app=settings.APP_NAME,
        environment=settings.APP_ENV,
        version=VERSION,
        timezone=str(app_timezone()),
        server_time=utcnow(),
        database=database,
    )


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
