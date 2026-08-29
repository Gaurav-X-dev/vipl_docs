"""Retention purge — the "90 days data remove" note on the client's Image 2.

Deletes completed / rejected / cancelled cases whose completion date is older
than the configured ``data_retention_days`` setting, together with everything
that hangs off them (forms, values, documents, notes, timeline). Open cases are
never touched.

Usage (from ``backend/``)::

    python -m scripts.purge_old_data --dry-run
    python -m scripts.purge_old_data --confirm

The purge is audited. Run it from the OS scheduler (Task Scheduler / cron).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import timedelta
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func, select  # noqa: E402

from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.models.case import Case  # noqa: E402
from app.models.enums import CLOSED_STATUSES, AuditAction  # noqa: E402
from app.services import audit_service, settings_service  # noqa: E402
from app.utils.dates import utcnow  # noqa: E402


async def run(dry_run: bool, override_days: int | None) -> int:
    async with session_scope() as session:
        days = override_days or await settings_service.get_int(
            session, "data_retention_days", 90
        )
        cutoff = utcnow() - timedelta(days=days)

        statement = select(Case).where(
            Case.status.in_(list(CLOSED_STATUSES)),
            Case.completed_at.is_not(None),
            Case.completed_at < cutoff,
        )
        cases = list((await session.execute(statement)).scalars().all())

        total = int(
            (await session.execute(select(func.count()).select_from(Case))).scalar_one()
        )
        print(f"Retention window : {days} days (cutoff {cutoff:%d-%m-%Y})")
        print(f"Cases in database: {total}")
        print(f"Eligible to purge: {len(cases)}")

        if not cases:
            await dispose_engine()
            return 0

        for case in cases[:20]:
            print(f"  - {case.case_number}  completed {case.completed_at:%d-%m-%Y}")
        if len(cases) > 20:
            print(f"  ... and {len(cases) - 20} more")

        if dry_run:
            print("\nDry run — nothing deleted.")
            await dispose_engine()
            return 0

        numbers = [case.case_number for case in cases]
        for case in cases:
            await session.delete(case)

        await audit_service.record(
            session,
            action=AuditAction.DATA_PURGED,
            module="Administration",
            actor=None,
            actor_label="Retention job",
            entity_type="Case",
            remarks=f"{len(numbers)} case(s) purged, older than {days} days.",
            new_values={"case_numbers": numbers[:200], "cutoff": cutoff.isoformat()},
        )
        print(f"\nPurged {len(numbers)} case(s).")

    await dispose_engine()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="report only")
    group.add_argument("--confirm", action="store_true", help="actually delete")
    parser.add_argument(
        "--days", type=int, default=None, help="override the retention window"
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.dry_run, args.days)))
