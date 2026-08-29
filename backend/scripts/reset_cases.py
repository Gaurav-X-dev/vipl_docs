"""Clear every case so a fresh daily file can be imported into a clean system.

This is the "start again from the real data" script. It removes the cases and
everything that hangs off them, and it leaves the *configuration* alone — the
companies, case types, form templates, document templates, staff, roles and
settings all took work to set up and are not touched.

Removed:

    cases, death claim details, assignments, status history, notes,
    case forms + field values + their change history, case timeline,
    uploaded evidence, generated documents, import batches and rows,
    case notifications, case-linked audit and activity rows,
    and the case-number counters (so numbering restarts at 1)

Kept:

    companies, case types, form templates, document templates,
    users, employees, roles, permissions, settings, attendance,
    login history

Usage (from ``backend/``)::

    python -m scripts.reset_cases --dry-run   # show what would go
    python -m scripts.reset_cases --confirm   # actually delete

Uploaded and generated files are deleted from disk too, unless you pass
``--keep-files``. Take a copy of the database first: this cannot be undone.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, func, select, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.models.audit import AuditLog, CaseTimelineEvent, UserActivity  # noqa: E402
from app.models.case import (  # noqa: E402
    Case,
    CaseAssignment,
    CaseDocument,
    CaseNote,
    CaseNumberSequence,
    CaseStatusHistory,
    DeathClaimDetail,
)
from app.models.document import GeneratedDocument  # noqa: E402
from app.models.form import (  # noqa: E402
    CaseFieldValue,
    CaseFieldValueHistory,
    CaseForm,
)
from app.models.importing import ImportBatch, ImportRow  # noqa: E402
from app.models.misc import Notification  # noqa: E402

#: Deleted in this order so a child never outlives its parent, which keeps the
#: script working on databases where foreign keys are not enforced.
ORDER = [
    ("case field value history", CaseFieldValueHistory),
    ("case field values", CaseFieldValue),
    ("case forms", CaseForm),
    ("case documents", CaseDocument),
    ("generated documents", GeneratedDocument),
    ("case notes", CaseNote),
    ("case status history", CaseStatusHistory),
    ("case assignments", CaseAssignment),
    ("death claim details", DeathClaimDetail),
    ("case timeline events", CaseTimelineEvent),
    ("import rows", ImportRow),
    ("import batches", ImportBatch),
    ("cases", Case),
    ("case number counters", CaseNumberSequence),
]

#: Storage folders emptied when files are removed.
FILE_DIRS = ("case_documents", "generated_documents", "imports")


async def counts() -> dict[str, int]:
    async with session_scope() as session:
        found: dict[str, int] = {}
        for label, model in ORDER:
            total = await session.execute(select(func.count()).select_from(model))
            found[label] = int(total.scalar_one() or 0)
        cased = await session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.entity_type == "Case")
        )
        found["case notifications"] = int(cased.scalar_one() or 0)
        activity = await session.execute(
            select(func.count())
            .select_from(UserActivity)
            .where(UserActivity.case_id.is_not(None))
        )
        found["case activity rows"] = int(activity.scalar_one() or 0)
        audit = await session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity_type.in_(["Case", "CaseForm", "CaseFieldValue"]))
        )
        found["case audit rows"] = int(audit.scalar_one() or 0)
        return found


async def purge() -> dict[str, int]:
    removed: dict[str, int] = {}
    async with session_scope() as session:
        # SQLite only honours ON DELETE rules when this is on; harmless
        # elsewhere. The explicit order above means we do not rely on it.
        if session.bind.dialect.name == "sqlite":
            await session.execute(text("PRAGMA foreign_keys = ON"))

        # These reference cases by a nullable column, so they must go *before*
        # the cases themselves: deleting a case first sets their case_id to
        # NULL and they would no longer match the filter.
        result = await session.execute(
            delete(Notification).where(Notification.entity_type == "Case")
        )
        removed["case notifications"] = int(result.rowcount or 0)

        result = await session.execute(
            delete(UserActivity).where(UserActivity.case_id.is_not(None))
        )
        removed["case activity rows"] = int(result.rowcount or 0)

        result = await session.execute(
            delete(AuditLog).where(
                AuditLog.entity_type.in_(["Case", "CaseForm", "CaseFieldValue"])
            )
        )
        removed["case audit rows"] = int(result.rowcount or 0)

        for label, model in ORDER:
            result = await session.execute(delete(model))
            removed[label] = int(result.rowcount or 0)
    return removed


def clear_files() -> list[str]:
    """Empty the case upload folders, leaving the folders themselves in place."""
    cleared: list[str] = []
    root = Path(settings.STORAGE_DIR)
    for name in FILE_DIRS:
        folder = root / name
        if not folder.exists():
            continue
        for child in folder.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
        cleared.append(str(folder))
    return cleared


def report(title: str, rows: dict[str, int]) -> None:
    print(title)
    print("-" * 60)
    width = max(len(key) for key in rows)
    for key, value in rows.items():
        print(f"  {key.ljust(width)}  {value:>6}")
    print("-" * 60)
    print(f"  {'total'.ljust(width)}  {sum(rows.values()):>6}\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm", action="store_true", help="actually delete (required)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="show the counts and stop"
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="leave uploaded and generated files on disk",
    )
    args = parser.parse_args()

    try:
        before = await counts()
        if not any(before.values()):
            print("Nothing to remove — there are no cases in this database.")
            return 0

        report("Case data currently in the database", before)

        if not args.confirm or args.dry_run:
            print("Nothing was deleted.")
            print("Re-run with --confirm to remove it. Back up the database first.")
            return 0

        removed = await purge()
        report("Removed", removed)

        if args.keep_files:
            print("Files left on disk (--keep-files).")
        else:
            for folder in clear_files():
                print(f"Emptied {folder}")

        print(
            "\nCompanies, case types, form templates, document templates, staff, "
            "roles and settings were not touched."
        )
        print("Case numbering restarts at 1 on the next import.")
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
