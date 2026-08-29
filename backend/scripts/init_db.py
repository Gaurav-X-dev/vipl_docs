"""Create the database schema.

PostgreSQL is the supported production database and uses Alembic::

    alembic upgrade head

For a quick local run on SQLite (no server needed) this script creates the
tables directly from the SQLAlchemy metadata — the same metadata Alembic
generates its migration from.

Usage (from ``backend/``)::

    python -m scripts.init_db
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.session import dispose_engine, engine  # noqa: E402
from app.models import Base  # noqa: E402


async def main() -> int:
    url = settings.DATABASE_URL
    if url.startswith("postgresql"):
        print(
            "PostgreSQL detected. Use Alembic so the schema stays versioned:\n"
            "\n    alembic upgrade head\n"
            "\nIf no migration exists yet, generate one first:\n"
            "\n    alembic revision --autogenerate -m \"initial schema\"\n"
        )
        await dispose_engine()
        return 1

    print(f"Creating {len(Base.metadata.tables)} tables on {url}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await dispose_engine()
    print("Schema created. Next: python -m scripts.seed --demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
