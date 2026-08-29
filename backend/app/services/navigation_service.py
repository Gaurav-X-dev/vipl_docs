"""The dynamic, company-wise sidebar.

The client's operational reality is company-first: an investigator does not
think "show me submitted cases", they think "show me the Bajaj death claims".
So the sidebar is not a fixed menu. It is generated from the companies that
actually have cases right now, split by category, with live counts.

Nothing here is hard-coded. Importing a spreadsheet from a company nobody has
seen before makes that company appear in the sidebar on the next load, with no
code change and no administrator action.

Counts are computed with one grouped query per category, never by loading cases
into memory, and are scoped to what the caller is allowed to see.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.company import CaseType, Company
from app.models.enums import (
    CLOSED_STATUSES,
    OPEN_STATUSES,
    CaseCategory,
    CaseStatus,
)
from app.models.form import FormTemplate
from app.models.user import User
from app.services import case_service
from app.utils.dates import utcnow

#: The status buckets shown beneath every company node, in workflow order.
#: ``None`` means "all cases"; the rest map to a set of concrete statuses so a
#: bucket can span several machine states without the UI knowing about them.
BUCKETS: tuple[tuple[str, str, frozenset[CaseStatus] | None], ...] = (
    ("all", "All Cases", None),
    (
        "pending",
        "Pending",
        frozenset({CaseStatus.IMPORTED, CaseStatus.UNASSIGNED}),
    ),
    (
        "assigned",
        "Assigned",
        frozenset({CaseStatus.ASSIGNED, CaseStatus.ACCEPTED}),
    ),
    (
        "in_progress",
        "In Progress",
        frozenset(
            {
                CaseStatus.WIP,
                CaseStatus.FIELD_INVESTIGATION,
                CaseStatus.DOCUMENTS_PENDING,
                CaseStatus.RIP,
            }
        ),
    ),
    (
        "submitted",
        "Submitted",
        frozenset(
            {
                CaseStatus.REPORT_SUBMITTED,
                CaseStatus.AWAITING_OFFICE_ASSIGNMENT,
            }
        ),
    ),
    (
        "office",
        "Office Processing",
        frozenset({CaseStatus.OFFICE_PROCESSING}),
    ),
    (
        "review",
        "Under Review",
        frozenset({CaseStatus.UNDER_REVIEW, CaseStatus.CORRECTION_REQUIRED}),
    ),
    (
        "completed",
        "Completed",
        frozenset({CaseStatus.VERIFIED, CaseStatus.COMPLETED}),
    ),
)

#: The category-level quick filters, above the company list.
CATEGORY_BUCKETS: tuple[tuple[str, str, frozenset[CaseStatus] | None], ...] = (
    ("all", "All Cases", None),
    (
        "unassigned",
        "Unassigned",
        frozenset({CaseStatus.IMPORTED, CaseStatus.UNASSIGNED}),
    ),
    (
        "assigned",
        "Assigned",
        frozenset({CaseStatus.ASSIGNED, CaseStatus.ACCEPTED}),
    ),
    (
        "in_progress",
        "In Progress",
        frozenset(
            {
                CaseStatus.WIP,
                CaseStatus.FIELD_INVESTIGATION,
                CaseStatus.DOCUMENTS_PENDING,
                CaseStatus.RIP,
            }
        ),
    ),
    (
        "submitted",
        "Submitted by Investigator",
        frozenset({CaseStatus.REPORT_SUBMITTED}),
    ),
    (
        "awaiting_office",
        "Awaiting Office Assignment",
        frozenset({CaseStatus.AWAITING_OFFICE_ASSIGNMENT}),
    ),
    (
        "office",
        "Office Processing",
        frozenset({CaseStatus.OFFICE_PROCESSING}),
    ),
    (
        "review",
        "Under Review",
        frozenset({CaseStatus.UNDER_REVIEW}),
    ),
    (
        "correction",
        "Correction Required",
        frozenset({CaseStatus.CORRECTION_REQUIRED}),
    ),
    (
        "completed",
        "Completed",
        frozenset({CaseStatus.VERIFIED, CaseStatus.COMPLETED}),
    ),
)

CATEGORY_META: dict[CaseCategory, dict[str, str]] = {
    CaseCategory.INVESTIGATION: {
        "label": "Investigation",
        "slug": "investigation",
        "icon": "shield-check",
        "permission": "investigation.view",
    },
    CaseCategory.DEATH_CLAIM: {
        "label": "Death Claim",
        "slug": "death-claim",
        "icon": "heart-pulse",
        "permission": "death_claim.view",
    },
}


@dataclass
class FormNode:
    """One configured form: a company's case type in this category."""

    case_type_id: uuid.UUID
    name: str
    count: int = 0


@dataclass
class CompanyNode:
    id: uuid.UUID
    code: str
    name: str
    short_name: str
    total: int = 0
    forms: dict[uuid.UUID, FormNode] = field(default_factory=dict)


def bucket_of(status: CaseStatus) -> str | None:
    """Which sidebar bucket a status falls into, ignoring the "all" bucket."""
    for key, _label, members in BUCKETS:
        if members is not None and status in members:
            return key
    return None


def category_bucket_of(status: CaseStatus) -> list[str]:
    """A status can appear in more than one category bucket (e.g. Completed)."""
    return [
        key
        for key, _label, members in CATEGORY_BUCKETS
        if members is not None and status in members
    ]


def statuses_for(bucket: str, *, category_level: bool = False) -> list[str] | None:
    """Translate a bucket key back into concrete statuses for the case list."""
    source = CATEGORY_BUCKETS if category_level else BUCKETS
    for key, _label, members in source:
        if key == bucket:
            return None if members is None else sorted(s.value for s in members)
    return None


def scope_to_user(query: Select, user: User) -> Select:
    """Investigators and office staff see only the cases on their own desk."""
    if user.is_super_admin or "case.view_all" in user.permission_codes:
        return query
    return query.where((Case.assigned_to_id == user.id) | (Case.office_staff_id == user.id))


async def _counts_by_company_status(
    session: AsyncSession, category: CaseCategory, user: User
) -> list[tuple[uuid.UUID, uuid.UUID, CaseStatus, int]]:
    # The menu counts what the case list shows, so a case archived by the
    # retention window disappears from both at the same moment.
    cutoff = await case_service.archive_cutoff(session)
    query = (
        select(
            Case.company_id,
            Case.case_type_id,
            Case.status,
            func.count().label("n"),
        )
        .where(
            Case.category == category,
            or_(
                Case.status.notin_([s.value for s in CLOSED_STATUSES]),
                Case.completed_at.is_(None),
                Case.completed_at >= cutoff,
            ),
        )
        .group_by(Case.company_id, Case.case_type_id, Case.status)
    )
    result = await session.execute(scope_to_user(query, user))
    return [(row[0], row[1], row[2], int(row[3])) for row in result.all()]


def form_label(template: FormTemplate, case_type: CaseType) -> str:
    """What the menu calls a form: the client's own file name.

    The agency knows these documents by their file names — "Icici Add",
    "LMS", "Land lord death claim" — not by the tidy case-type names the
    system groups them under. Showing anything else makes people hunt for a
    form they have been using for years. The case type still does the routing
    and the filtering; it is only the label that follows the document.
    """
    source = (template.source_document or "").rsplit("/", 1)[-1]
    stem = source.rsplit(".", 1)[0].strip()
    return stem or case_type.name


async def _forms_for(
    session: AsyncSession, category: CaseCategory
) -> list[tuple[Company, CaseType, FormTemplate]]:
    """Every configured form in this category, as (company, case type).

    Not "companies that happen to have a case right now" — the client wants
    their whole client list standing in the menu, so a new day's file lands
    somewhere the operator already knows to look. And a company can hold
    several forms in one category: ICICI alone has a Death Claim, an FTI and a
    Landlord assessment, so listing the company once would hide two of them.
    """
    result = await session.execute(
        select(Company, CaseType, FormTemplate)
        .join(FormTemplate, FormTemplate.company_id == Company.id)
        .join(CaseType, CaseType.id == FormTemplate.case_type_id)
        .where(
            Company.is_active.is_(True),
            FormTemplate.is_active.is_(True),
            CaseType.category == category,
        )
        .order_by(Company.short_name, FormTemplate.source_document)
    )
    return [(company, case_type, template) for company, case_type, template in result.all()]


async def category_tree(
    session: AsyncSession, category: CaseCategory, user: User
) -> dict[str, Any]:
    """One category branch: every configured form, grouped by company.

    A company with a single form in this category is one row. A company with
    several — ICICI carries three death-claim forms — lists them, because
    "ICICI" alone would leave two of its forms with nowhere to be clicked.
    """
    rows = await _counts_by_company_status(session, category, user)
    meta = CATEGORY_META[category]

    nodes: dict[uuid.UUID, CompanyNode] = {}
    for company, case_type, template in await _forms_for(session, category):
        node = nodes.setdefault(
            company.id,
            CompanyNode(
                id=company.id,
                code=company.code,
                name=company.name,
                short_name=company.short_name,
            ),
        )
        node.forms.setdefault(
            case_type.id,
            FormNode(
                case_type_id=case_type.id, name=form_label(template, case_type)
            ),
        )

    category_counts: dict[str, int] = {key: 0 for key, _l, _m in CATEGORY_BUCKETS}
    total = 0
    open_total = 0

    for company_id, case_type_id, status, count in rows:
        total += count
        if status in OPEN_STATUSES:
            open_total += count
        category_counts["all"] += count
        for key in category_bucket_of(status):
            category_counts[key] += count

        node = nodes.get(company_id)
        if node is None:
            # Work exists for a company whose form was retired. Keep it
            # visible rather than hiding open cases.
            company = await session.get(Company, company_id)
            if company is None:
                continue
            node = CompanyNode(
                id=company.id,
                code=company.code,
                name=company.name,
                short_name=company.short_name,
            )
            nodes[company_id] = node
        node.total += count
        form = node.forms.get(case_type_id)
        if form is None:
            case_type = await session.get(CaseType, case_type_id)
            if case_type is None:
                continue
            form = FormNode(case_type_id=case_type_id, name=case_type.name)
            node.forms[case_type_id] = form
        form.count += count

    ordered = sorted(nodes.values(), key=lambda node: node.short_name.lower())

    return {
        "category": category.value,
        "label": meta["label"],
        "slug": meta["slug"],
        "icon": meta["icon"],
        "permission": meta["permission"],
        "total": total,
        "open_total": open_total,
        "buckets": [
            {"key": key, "label": label, "count": category_counts.get(key, 0)}
            for key, label, _members in CATEGORY_BUCKETS
        ],
        "companies": [
            {
                "id": str(node.id),
                "code": node.code,
                "name": node.name,
                "short_name": node.short_name,
                "count": node.total,
                "forms": [
                    {
                        "case_type_id": str(form.case_type_id),
                        "name": form.name,
                        "count": form.count,
                    }
                    for form in sorted(
                        node.forms.values(), key=lambda f: f.name.lower()
                    )
                ],
            }
            for node in ordered
        ],
    }


async def sidebar(session: AsyncSession, user: User) -> dict[str, Any]:
    """The whole navigation payload for the signed-in user.

    Categories the user has no permission for are omitted entirely rather than
    rendered empty, so an investigator's sidebar is genuinely their sidebar.
    """
    granted = user.permission_codes
    categories: list[dict[str, Any]] = []
    for category, meta in CATEGORY_META.items():
        if not user.is_super_admin and meta["permission"] not in granted:
            continue
        categories.append(await category_tree(session, category, user))

    my_cases = await _my_desk_counts(session, user)
    return {
        "categories": categories,
        "my_desk": my_cases,
        "generated_at": utcnow(),
    }


async def _my_desk_counts(session: AsyncSession, user: User) -> dict[str, int]:
    """Counts for the "My Cases" group, for whichever desk the user works."""
    field_open = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            Case.assigned_to_id == user.id,
            Case.status.in_([s.value for s in OPEN_STATUSES]),
        )
    )
    office_open = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            Case.office_staff_id == user.id,
            Case.status.in_([s.value for s in OPEN_STATUSES]),
        )
    )
    correction = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            Case.assigned_to_id == user.id,
            Case.status == CaseStatus.CORRECTION_REQUIRED,
        )
    )
    completed = await session.execute(
        select(func.count())
        .select_from(Case)
        .where(
            (Case.assigned_to_id == user.id) | (Case.office_staff_id == user.id),
            Case.status.in_([s.value for s in CLOSED_STATUSES]),
        )
    )
    return {
        "field_open": int(field_open.scalar_one() or 0),
        "office_open": int(office_open.scalar_one() or 0),
        "correction_required": int(correction.scalar_one() or 0),
        "completed": int(completed.scalar_one() or 0),
    }
