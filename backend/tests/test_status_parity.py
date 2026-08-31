"""The frontend's status list must match the backend's.

Two statuses had gone missing from ``frontend/src/types.ts``: they existed in
the workflow, cases sat in them, and the status filter simply could not select
them. Nothing failed — the list is a plain array, so the omission was invisible
until someone went looking. This test makes the next omission fail loudly.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.models.enums import CaseStatus

TYPES_FILE = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "types.ts"
)


def _block(source: str, declaration: str, opening: str, closing: str) -> str:
    start = source.index(declaration)
    open_at = source.index(opening, start)
    close_at = source.index(closing, open_at)
    return source[open_at : close_at + 1]


@pytest.fixture(scope="module")
def types_source() -> str:
    if not TYPES_FILE.exists():
        pytest.skip("frontend/src/types.ts is not present in this checkout")
    return TYPES_FILE.read_text(encoding="utf-8")


def test_case_statuses_match_the_enum(types_source: str) -> None:
    block = _block(types_source, "export const CASE_STATUSES", "[", "]")
    listed = re.findall(r'"([A-Z_]+)"', block)

    assert listed == [status.value for status in CaseStatus], (
        "frontend CASE_STATUSES has drifted from CaseStatus. "
        f"Only in the frontend: {sorted(set(listed) - {s.value for s in CaseStatus})}. "
        f"Missing from the frontend: {sorted({s.value for s in CaseStatus} - set(listed))}."
    )


def test_every_status_has_a_frontend_label(types_source: str) -> None:
    block = _block(types_source, "export const STATUS_LABELS", "{", "}")
    labelled = set(re.findall(r"^\s*([A-Z_]+):", block, flags=re.MULTILINE))

    missing = {status.value for status in CaseStatus} - labelled
    assert not missing, f"No frontend label for: {sorted(missing)}"
