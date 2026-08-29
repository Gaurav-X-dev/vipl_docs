"""Remove repeated field keys from already-seeded form templates.

Answers are stored per ``field_key``, so two fields sharing one key inside a
template are a single answer shown in two places: filling either one changes
both, and clearing one clears the other. Several client forms genuinely ask
the same thing twice — a summary near the top and again in the Conclusion —
which is how the repeats got in.

The first occurrence in display order wins: that is the one written into the
insurer's own layout. Later repeats are deleted, and any answer already
recorded against the repeat is moved onto the surviving field first, so no
work is lost.

Usage (from ``backend/``)::

    python -m scripts.fix_duplicate_fields --dry-run
    python -m scripts.fix_duplicate_fields --confirm
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, select, update  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.models.form import (  # noqa: E402
    CaseFieldValue,
    FormField,
    FormSection,
    FormTemplate,
)


async def find_repeats() -> list[tuple[str, str, list[FormField]]]:
    """Return ``(template name, field key, fields in display order)`` per repeat."""
    async with session_scope() as session:
        result = await session.execute(
            select(FormTemplate).options(
                selectinload(FormTemplate.sections).selectinload(FormSection.fields)
            )
        )
        repeats: list[tuple[str, str, list[FormField]]] = []
        for template in result.unique().scalars().all():
            by_key: dict[str, list[FormField]] = {}
            for section in sorted(template.sections, key=lambda s: s.display_order):
                for field in sorted(section.fields, key=lambda f: f.display_order):
                    by_key.setdefault(field.field_key, []).append(field)
            for key, fields in by_key.items():
                if len(fields) > 1:
                    repeats.append((template.name, key, fields))
        return repeats


async def purge(dry_run: bool) -> tuple[int, int]:
    repeats = await find_repeats()
    if not repeats:
        print("No repeated field keys. Nothing to do.")
        return 0, 0

    print(f"{len(repeats)} repeated field key(s) across "
          f"{len({name for name, _k, _f in repeats})} template(s):\n")

    removed = 0
    moved = 0
    async with session_scope() as session:
        for name, key, fields in repeats:
            keeper, *extras = fields
            print(f"  {name[:48]}")
            print(f"    key '{key}' appears {len(fields)}x — keeping "
                  f"\"{keeper.label[:44]}\"")
            for extra in extras:
                print(f"    dropping \"{extra.label[:44]}\"")
                if dry_run:
                    removed += 1
                    continue

                # Any answer recorded against the repeat is re-pointed at the
                # surviving field before the repeat goes.
                result = await session.execute(
                    update(CaseFieldValue)
                    .where(CaseFieldValue.field_id == extra.id)
                    .values(field_id=keeper.id)
                )
                moved += int(result.rowcount or 0)
                await session.execute(
                    delete(FormField).where(FormField.id == extra.id)
                )
                removed += 1
            print()
    return removed, moved


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="apply the changes")
    parser.add_argument("--dry-run", action="store_true", help="report only")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.confirm
    try:
        removed, moved = await purge(dry_run)
        if not removed:
            return 0
        if dry_run:
            print(f"Would remove {removed} repeated field(s). Nothing was changed.")
            print("Re-run with --confirm to apply.")
        else:
            print(f"Removed {removed} repeated field(s).")
            if moved:
                print(f"Re-pointed {moved} recorded answer(s) at the kept field.")
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
