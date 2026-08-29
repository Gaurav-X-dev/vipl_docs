"""Rebuild every document template so a report carries only our own data.

The client's forms arrived as completed specimen reports. Tagging them by
searching for known values left the tabular answers behind, so a generated
report showed the specimen's findings next to our few mapped fields. This pass
reads the table layout instead: each label is matched to a field on that
company's form template, the answer cells become ``{{ field_key }}``, and any
answer we cannot account for is **cleared**.

An empty row in a report is a visible gap someone can fill. A stranger's
findings under our letterhead is a different kind of problem, so unmapped
always means empty.

Usage (from ``backend/``)::

    python -m scripts.retag_templates --dry-run     # coverage report only
    python -m scripts.retag_templates --confirm     # rewrite the tagged copies
    python -m scripts.retag_templates --confirm -v  # list every row decision

The originals in ``storage/document_templates/original/`` are never modified.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from docx import Document  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import dispose_engine, session_scope  # noqa: E402
from app.documents.table_tagger import (  # noqa: E402
    TableTagReport,
    build_index,
    tag_tables,
)
from app.documents.tagger import document_paragraphs, replace_in_paragraph  # noqa: E402
from app.models.document import DocumentTemplate  # noqa: E402
from app.models.enums import DocumentTemplateStatus  # noqa: E402
from app.models.form import FormSection, FormTemplate  # noqa: E402
from app.utils.files import relative_to_storage, resolve_storage_path  # noqa: E402
from scripts.tag_templates import REPLACEMENTS  # noqa: E402


async def collect() -> list[tuple[DocumentTemplate, FormTemplate]]:
    """Pair each document template with the form template that fills it."""
    async with session_scope() as session:
        documents = (
            (
                await session.execute(
                    select(DocumentTemplate).where(
                        DocumentTemplate.status != DocumentTemplateStatus.INACTIVE
                    )
                )
            )
            .scalars()
            .all()
        )
        forms = (
            (
                await session.execute(
                    select(FormTemplate).options(
                        selectinload(FormTemplate.sections).selectinload(
                            FormSection.fields
                        )
                    )
                )
            )
            .unique()
            .scalars()
            .all()
        )
        by_pair = {
            (form.company_id, form.case_type_id): form for form in forms
        }
        pairs: list[tuple[DocumentTemplate, FormTemplate]] = []
        for document in documents:
            form = by_pair.get((document.company_id, document.case_type_id))
            if form is not None:
                pairs.append((document, form))
        return pairs


def retag(
    document_template: DocumentTemplate,
    form_template: FormTemplate,
    *,
    write: bool,
) -> TableTagReport | None:
    source = resolve_storage_path(document_template.original_path)
    if not source.exists() or source.suffix.lower() != ".docx":
        return None

    fields = [
        field
        for section in form_template.sections
        for field in section.fields
    ]
    index = build_index(fields)
    report = TableTagReport(file=document_template.name or source.name)

    document = Document(str(source))
    tag_tables(list(document.tables), index, report)

    # The table pass owns the answer cells. Named specimen values also appear
    # in headings, signature blocks and running text — those come from the
    # hand-checked map, and anything it names must not survive either.
    literal = REPLACEMENTS.get(document_template.original_filename, {})
    paragraphs = document_paragraphs(document)
    for needle in sorted(literal, key=len, reverse=True):
        for paragraph in paragraphs:
            if replace_in_paragraph(paragraph, needle, literal[needle]):
                report.mapped.append((needle, literal[needle].strip("{} ")))

    if write:
        destination = settings.template_tagged_dir / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(destination))
        document_template.tagged_path = relative_to_storage(destination)
    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="write the templates")
    parser.add_argument("--dry-run", action="store_true", help="report only")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="list every row decision"
    )
    args = parser.parse_args()
    write = args.confirm and not args.dry_run

    try:
        pairs = await collect()
        if not pairs:
            print("No document template is paired with a form template.")
            return 1

        reports: list[TableTagReport] = []
        async with session_scope() as session:
            for document_template, form_template in pairs:
                merged = await session.merge(document_template)
                report = retag(merged, form_template, write=write)
                if report is None:
                    print(f"  - skipped {document_template.name} (not a .docx)")
                    continue
                reports.append(report)
                for line in report.as_lines(args.verbose):
                    print("  " + line)
            if not write:
                await session.rollback()

        print("\n" + "=" * 68)
        mapped = sum(len(r.mapped) for r in reports)
        blanked = sum(len(r.blanked) for r in reports)
        total = mapped + blanked
        print(
            f"  {len(reports)} template(s): {mapped} row(s) mapped, "
            f"{blanked} cleared "
            f"({mapped / total * 100:.0f}% coverage)" if total else "  nothing to do"
        )
        weak = [r for r in reports if r.coverage < 50]
        if weak:
            print("\n  Low coverage — these need their form template checked:")
            for report in weak:
                print(f"    {report.coverage:>3.0f}%  {report.file}")
        if not write:
            print("\n  Nothing was written. Re-run with --confirm to apply.")
        return 0
    finally:
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
