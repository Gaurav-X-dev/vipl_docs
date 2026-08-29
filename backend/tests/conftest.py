"""Test fixtures.

The suite runs against an in-memory SQLite database so it needs no server and
leaves nothing behind. Schema is created from the same SQLAlchemy metadata the
Alembic migration is generated from.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Point every setting at throwaway values before the app package is imported.
os.environ["APP_ENV"] = "test"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-not-used-anywhere-else"
os.environ["SUPER_ADMIN_EMAIL"] = "admin@investigation.local"
os.environ["SUPER_ADMIN_PASSWORD"] = "Admin@123456"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import get_db  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Base  # noqa: E402
from app.seeds.runner import seed_all  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def engine(tmp_path_factory):
    storage = tmp_path_factory.mktemp("storage")
    settings.STORAGE_DIR = storage
    settings.ensure_storage_dirs()

    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )


@pytest_asyncio.fixture
async def db(session_factory) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def seeded(session_factory) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with session_factory() as session:
        await seed_all(session)
        await session.commit()
    yield session_factory


@pytest_asyncio.fixture
async def client(seeded) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with seeded() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.SUPER_ADMIN_EMAIL,
            "password": settings.SUPER_ADMIN_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["tokens"]["access_token"]


@pytest_asyncio.fixture
async def admin_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
