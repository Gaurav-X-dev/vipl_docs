"""Async engine and session factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _engine_kwargs() -> dict:
    kwargs: dict = {"echo": settings.DB_ECHO, "pool_pre_ping": True, "future": True}
    # SQLite (used by the test-suite) does not support these pool options.
    if not settings.DATABASE_URL.startswith("sqlite"):
        kwargs["pool_size"] = settings.DB_POOL_SIZE
        kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
    return kwargs


engine: AsyncEngine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs())

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, rolled back on error."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Transactional scope for scripts and background jobs."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    await engine.dispose()
