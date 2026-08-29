"""Seed the database with roles, masters, templates and the Super Admin.

Usage (from ``backend/``)::

    python -m scripts.seed              # masters only
    python -m scripts.seed --demo       # masters + demo staff and cases

Idempotent: safe to run repeatedly.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.seeds.runner import seed_all  # noqa: E402


async def main(with_demo: bool) -> int:
    async with session_scope() as session:
        report = await seed_all(session)
        if with_demo:
            from app.seeds.demo import seed_demo

            demo_lines = await seed_demo(session)
            report.notes.extend(demo_lines)

    print("\n".join(report.as_lines()))
    await dispose_engine()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--demo",
        action="store_true",
        help="also create demo staff and a handful of demonstration cases",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.demo)))
