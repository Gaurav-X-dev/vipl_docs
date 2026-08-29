"""Dashboard aggregations.

Every figure here comes from a database aggregate. Nothing downloads a case list
into the frontend to count it, and nothing is hard-coded. Each function maps to a
numbered requirement in ``docs/ATTACHMENT_ANALYSIS.md`` §3.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy import case as case_expr
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.company import CaseType, Company
from app.models.enums import (
    CLOSED_STATUSES,
    RIP_STATUSES,
    WIP_STATUSES,
    CaseCategory,
    CaseOutcome,
    CaseStatus,
    StaffCategory,
    TatState,
)
from app.models.user import User
from app.services import settings_service
from app.services.case_workflow import status_label
from app.utils.dates import (
    app_timezone,
    end_of_day,
    ensure_utc,
    start_of_day,
    utcnow,
)

OUTCOME_TONE = {
    CaseOutcome.POSITIVE: "success",
    CaseOutcome.NEGATIVE: "danger",
    CaseOutcome.SUSPICIOUS: "warning",
}


def _count_if(condition: Any) -> Any:
    return func.coalesce(func.sum(case_expr((condition, 1), else_=0)), 0)


def _percent(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _is_recent(moment: datetime | None, threshold: datetime) -> bool:
    """Compare safely: SQLite hands back naive datetimes, PostgreSQL aware ones."""
    normalised = ensure_utc(moment)
    return normalised is not None and normalised >= threshold


def scope_filters(
    statement: Select[Any],
    *,
    user: User,
    view_all: bool,
    company_id: uuid.UUID | None = None,
    case_type_id: uuid.UUID | None = None,
    category: CaseCategory | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Select[Any]:
    """Apply role scope and the dashboard's date/company/type filters.

    Role awareness is enforced here, on the server: an investigator's dashboard
    only ever aggregates the cases assigned to them.
    """
    if not view_all:
        statement = statement.where(Case.assigned_to_id == user.id)
    if company_id:
        statement = statement.where(Case.company_id == company_id)
    if case_type_id:
        statement = statement.where(Case.case_type_id == case_type_id)
    if category:
        statement = statement.where(Case.category == category)
    if date_from:
        statement = statement.where(Case.received_at >= start_of_day(date_from))
    if date_to:
        statement = statement.where(Case.received_at <= end_of_day(date_to))
    return statement


async def summary(
    session: AsyncSession,
    *,
    user: User,
    view_all: bool,
    company_id: uuid.UUID | None = None,
    case_type_id: uuid.UUID | None = None,
    category: CaseCategory | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """Every KPI tile on Image 1 and Image 2."""
    now = utcnow()
    warning_hours = await settings_service.get_int(session, "tat_breach_warning_hours", 24)
    online_timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    warn_at = now + timedelta(hours=warning_hours)
    today_start = start_of_day(now.astimezone(app_timezone()).date())

    open_case = Case.status.notin_(list(CLOSED_STATUSES))
    has_due = Case.due_at.is_not(None)

    statement = scope_filters(
        select(
            func.count().label("total"),
            _count_if(Case.status == CaseStatus.UNASSIGNED).label("unassigned"),
            _count_if(Case.status == CaseStatus.IMPORTED).label("imported"),
            _count_if(Case.status == CaseStatus.ASSIGNED).label("assigned"),
            _count_if(Case.status.in_(list(WIP_STATUSES))).label("wip"),
            _count_if(Case.status.in_(list(RIP_STATUSES))).label("rip"),
            _count_if(open_case).label("pending"),
            _count_if(Case.status == CaseStatus.COMPLETED).label("completed"),
            _count_if(Case.status == CaseStatus.REJECTED).label("rejected"),
            _count_if(Case.category == CaseCategory.INVESTIGATION).label("investigation"),
            _count_if(Case.category == CaseCategory.DEATH_CLAIM).label("death_claim"),
            _count_if(Case.outcome == CaseOutcome.POSITIVE).label("positive"),
            _count_if(Case.outcome == CaseOutcome.NEGATIVE).label("negative"),
            _count_if(Case.outcome == CaseOutcome.SUSPICIOUS).label("suspicious"),
            _count_if(Case.created_at >= today_start).label("imported_today"),
            _count_if(and_(has_due, open_case, Case.due_at < now)).label("overdue"),
            _count_if(and_(has_due, open_case, Case.due_at >= now, Case.due_at <= warn_at)).label(
                "about_to_breach"
            ),
            _count_if(and_(has_due, open_case, Case.due_at > warn_at)).label("in_tat_open"),
            _count_if(
                and_(
                    Case.status == CaseStatus.COMPLETED,
                    has_due,
                    Case.completed_at <= Case.due_at,
                )
            ).label("in_tat_done"),
            _count_if(
                and_(
                    Case.status == CaseStatus.COMPLETED,
                    has_due,
                    Case.completed_at > Case.due_at,
                )
            ).label("out_of_tat_done"),
        ),
        user=user,
        view_all=view_all,
        company_id=company_id,
        case_type_id=case_type_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )
    row = (await session.execute(statement)).one()

    decided = int(row.positive) + int(row.negative) + int(row.suspicious)
    total = int(row.total)

    staff = await staff_status_counts(session, online_timeout)
    average_tat = await average_tat_days(
        session,
        user=user,
        view_all=view_all,
        company_id=company_id,
        case_type_id=case_type_id,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )

    return {
        "server_time": now,
        "timezone": str(app_timezone()),
        "total_assignment": total,
        "total_cases": total,
        "new_cases": int(row.imported) + int(row.unassigned),
        "imported_today": int(row.imported_today),
        "unassigned": int(row.unassigned) + int(row.imported),
        "assigned": int(row.assigned),
        "wip_cases": int(row.wip),
        "rip_cases": int(row.rip),
        "pending": int(row.pending),
        "completed": int(row.completed),
        "rejected": int(row.rejected),
        "overdue": int(row.overdue),
        "investigation_cases": int(row.investigation),
        "death_claim_cases": int(row.death_claim),
        "positive_cases": int(row.positive),
        "negative_cases": int(row.negative),
        "suspicious_cases": int(row.suspicious),
        "positive_percent": _percent(int(row.positive), decided),
        "negative_percent": _percent(int(row.negative), decided),
        "suspicious_percent": _percent(int(row.suspicious), decided),
        "in_tat": int(row.in_tat_open) + int(row.in_tat_done),
        "out_of_tat": int(row.overdue) + int(row.out_of_tat_done),
        "tat_about_to_breach": int(row.about_to_breach),
        "average_tat_days": average_tat,
        **staff,
    }


async def staff_status_counts(session: AsyncSession, online_timeout_minutes: int) -> dict[str, int]:
    """Active vs non-active investigators and back-office staff (Image 1)."""
    threshold = utcnow() - timedelta(minutes=online_timeout_minutes)
    is_online = and_(User.last_activity_at.is_not(None), User.last_activity_at >= threshold)
    is_field = User.staff_category == StaffCategory.FIELD
    is_back_office = User.staff_category.in_([StaffCategory.BACK_OFFICE, StaffCategory.MANAGEMENT])

    row = (
        await session.execute(
            select(
                func.count().label("total"),
                _count_if(and_(is_field, is_online)).label("field_online"),
                _count_if(and_(is_field, ~is_online)).label("field_offline"),
                _count_if(and_(is_back_office, is_online)).label("office_online"),
                _count_if(and_(is_back_office, ~is_online)).label("office_offline"),
            ).where(User.is_active.is_(True))
        )
    ).one()

    return {
        "total_staff": int(row.total),
        "active_investigators": int(row.field_online),
        "inactive_investigators": int(row.field_offline),
        "active_back_office": int(row.office_online),
        "inactive_back_office": int(row.office_offline),
    }


async def average_tat_days(
    session: AsyncSession,
    *,
    user: User,
    view_all: bool,
    **filters: Any,
) -> float | None:
    """Mean completion time in days across completed cases."""
    statement = scope_filters(
        select(Case.received_at, Case.completed_at).where(
            Case.status == CaseStatus.COMPLETED, Case.completed_at.is_not(None)
        ),
        user=user,
        view_all=view_all,
        **filters,
    )
    rows = (await session.execute(statement)).all()
    if not rows:
        return None
    spans = [
        (completed - received).total_seconds() / 86400
        for received, completed in rows
        if received and completed
    ]
    return round(sum(spans) / len(spans), 1) if spans else None


async def outcome_distribution(
    session: AsyncSession, *, user: User, view_all: bool, **filters: Any
) -> list[dict[str, Any]]:
    """Positive / Negative / Suspicious with the ratio-in-% Image 1 asks for."""
    statement = scope_filters(
        select(Case.outcome, func.count().label("value")).where(Case.outcome.is_not(None)),
        user=user,
        view_all=view_all,
        **filters,
    ).group_by(Case.outcome)
    rows = (await session.execute(statement)).all()
    total = sum(int(row.value) for row in rows)
    return [
        {
            "key": row.outcome.value,
            "label": row.outcome.value.title(),
            "value": int(row.value),
            "percent": _percent(int(row.value), total),
            "color_token": OUTCOME_TONE.get(row.outcome, "neutral"),
        }
        for row in rows
    ]


async def status_distribution(
    session: AsyncSession, *, user: User, view_all: bool, **filters: Any
) -> list[dict[str, Any]]:
    statement = scope_filters(
        select(Case.status, func.count().label("value")),
        user=user,
        view_all=view_all,
        **filters,
    ).group_by(Case.status)
    rows = (await session.execute(statement)).all()
    total = sum(int(row.value) for row in rows)
    ordered = sorted(rows, key=lambda r: -int(r.value))
    return [
        {
            "key": row.status.value,
            "label": status_label(row.status),
            "value": int(row.value),
            "percent": _percent(int(row.value), total),
        }
        for row in ordered
    ]


async def category_distribution(
    session: AsyncSession, *, user: User, view_all: bool, **filters: Any
) -> list[dict[str, Any]]:
    statement = scope_filters(
        select(Case.category, func.count().label("value")),
        user=user,
        view_all=view_all,
        **filters,
    ).group_by(Case.category)
    rows = (await session.execute(statement)).all()
    total = sum(int(row.value) for row in rows)
    labels = {
        CaseCategory.INVESTIGATION: "Investigation",
        CaseCategory.DEATH_CLAIM: "Death Claim",
    }
    return [
        {
            "key": row.category.value,
            "label": labels.get(row.category, row.category.value.title()),
            "value": int(row.value),
            "percent": _percent(int(row.value), total),
        }
        for row in rows
    ]


async def trend(
    session: AsyncSession,
    *,
    user: User,
    view_all: bool,
    bucket: str = "day",
    days: int = 30,
    **filters: Any,
) -> list[dict[str, Any]]:
    """Day / week / month case trend — the selector drawn on Image 2."""
    now = utcnow()
    spans = {"day": days, "week": days * 7, "month": days * 30}
    window_start = now - timedelta(days=spans.get(bucket, days))

    statement = scope_filters(
        select(
            Case.received_at,
            Case.status,
            Case.outcome,
        ).where(Case.received_at >= window_start),
        user=user,
        view_all=view_all,
        **filters,
    )
    rows = (await session.execute(statement)).all()

    tz = app_timezone()
    buckets: dict[str, dict[str, Any]] = {}

    def bucket_key(moment: datetime) -> tuple[str, str]:
        local = moment.astimezone(tz)
        if bucket == "month":
            return local.strftime("%Y-%m"), local.strftime("%b %Y")
        if bucket == "week":
            iso = local.isocalendar()
            return f"{iso.year}-W{iso.week:02d}", f"W{iso.week} {local:%b}"
        return local.strftime("%Y-%m-%d"), local.strftime("%d %b")

    for received_at, status, outcome in rows:
        key, label = bucket_key(received_at)
        entry = buckets.setdefault(
            key,
            {
                "bucket": key,
                "label": label,
                "total": 0,
                "completed": 0,
                "positive": 0,
                "negative": 0,
                "suspicious": 0,
            },
        )
        entry["total"] += 1
        if status == CaseStatus.COMPLETED:
            entry["completed"] += 1
        if outcome == CaseOutcome.POSITIVE:
            entry["positive"] += 1
        elif outcome == CaseOutcome.NEGATIVE:
            entry["negative"] += 1
        elif outcome == CaseOutcome.SUSPICIOUS:
            entry["suspicious"] += 1

    return [buckets[key] for key in sorted(buckets)]


async def company_performance(
    session: AsyncSession, *, user: User, view_all: bool, **filters: Any
) -> list[dict[str, Any]]:
    """ "Overall columns company wise" from Image 2."""
    now = utcnow()
    open_case = Case.status.notin_(list(CLOSED_STATUSES))

    statement = (
        scope_filters(
            select(
                Company.id.label("company_id"),
                Company.code.label("company_code"),
                Company.short_name.label("company_name"),
                func.count().label("total"),
                _count_if(Case.status.in_([CaseStatus.UNASSIGNED, CaseStatus.IMPORTED])).label(
                    "unassigned"
                ),
                _count_if(Case.status.in_(list(WIP_STATUSES))).label("wip"),
                _count_if(Case.status.in_(list(RIP_STATUSES))).label("rip"),
                _count_if(Case.status == CaseStatus.COMPLETED).label("completed"),
                _count_if(and_(Case.due_at.is_not(None), open_case, Case.due_at < now)).label(
                    "overdue"
                ),
                _count_if(Case.outcome == CaseOutcome.POSITIVE).label("positive"),
                _count_if(Case.outcome == CaseOutcome.NEGATIVE).label("negative"),
                _count_if(Case.outcome == CaseOutcome.SUSPICIOUS).label("suspicious"),
            ).join(Company, Case.company_id == Company.id),
            user=user,
            view_all=view_all,
            **filters,
        )
        .group_by(Company.id, Company.code, Company.short_name)
        .order_by(func.count().desc())
    )

    rows = (await session.execute(statement)).all()
    return [
        {
            "company_id": row.company_id,
            "company_code": row.company_code,
            "company_name": row.company_name,
            "total": int(row.total),
            "unassigned": int(row.unassigned),
            "wip": int(row.wip),
            "rip": int(row.rip),
            "completed": int(row.completed),
            "overdue": int(row.overdue),
            "positive": int(row.positive),
            "negative": int(row.negative),
            "suspicious": int(row.suspicious),
            "average_tat_days": None,
        }
        for row in rows
    ]


async def investigator_performance(
    session: AsyncSession, *, user: User, view_all: bool, limit: int = 25, **filters: Any
) -> list[dict[str, Any]]:
    """ "In progress state -> work in prog -> users" from Image 2."""
    now = utcnow()
    online_timeout = await settings_service.get_int(session, "staff_online_timeout_minutes", 5)
    threshold = now - timedelta(minutes=online_timeout)
    open_case = Case.status.notin_(list(CLOSED_STATUSES))

    statement = (
        scope_filters(
            select(
                User.id.label("staff_id"),
                User.full_name,
                User.staff_category,
                User.last_activity_at,
                func.count().label("assigned"),
                _count_if(Case.status.in_(list(WIP_STATUSES))).label("in_progress"),
                _count_if(Case.status.in_(list(RIP_STATUSES))).label("rip"),
                _count_if(Case.status == CaseStatus.COMPLETED).label("completed"),
                _count_if(open_case).label("pending"),
                _count_if(and_(Case.due_at.is_not(None), open_case, Case.due_at < now)).label(
                    "overdue"
                ),
                _count_if(Case.outcome == CaseOutcome.POSITIVE).label("positive"),
                _count_if(Case.outcome == CaseOutcome.NEGATIVE).label("negative"),
                _count_if(Case.outcome == CaseOutcome.SUSPICIOUS).label("suspicious"),
            ).join(User, Case.assigned_to_id == User.id),
            user=user,
            view_all=view_all,
            **filters,
        )
        .group_by(User.id, User.full_name, User.staff_category, User.last_activity_at)
        .order_by(func.count().desc())
        .limit(limit)
    )

    rows = (await session.execute(statement)).all()
    return [
        {
            "staff_id": row.staff_id,
            "full_name": row.full_name,
            "staff_category": row.staff_category,
            "is_online": _is_recent(row.last_activity_at, threshold),
            "assigned": int(row.assigned),
            "in_progress": int(row.in_progress),
            "report_in_progress": int(row.rip),
            "completed": int(row.completed),
            "pending": int(row.pending),
            "overdue": int(row.overdue),
            "positive": int(row.positive),
            "negative": int(row.negative),
            "suspicious": int(row.suspicious),
            "average_tat_days": None,
            "completion_rate": _percent(int(row.completed), int(row.assigned)),
        }
        for row in rows
    ]


async def recent_cases(
    session: AsyncSession,
    *,
    user: User,
    view_all: bool,
    limit: int = 10,
    only_overdue: bool = False,
    only_unassigned: bool = False,
) -> list[dict[str, Any]]:
    now = utcnow()
    warning_hours = await settings_service.get_int(session, "tat_breach_warning_hours", 24)
    statement = (
        select(Case, Company.short_name, CaseType.name, User.full_name)
        .join(Company, Case.company_id == Company.id)
        .join(CaseType, Case.case_type_id == CaseType.id)
        .outerjoin(User, Case.assigned_to_id == User.id)
    )
    if not view_all:
        statement = statement.where(Case.assigned_to_id == user.id)
    if only_overdue:
        statement = statement.where(
            Case.due_at.is_not(None),
            Case.due_at < now,
            Case.status.notin_(list(CLOSED_STATUSES)),
        ).order_by(Case.due_at.asc())
    elif only_unassigned:
        statement = statement.where(Case.assigned_to_id.is_(None)).order_by(Case.received_at.asc())
    else:
        statement = statement.order_by(Case.created_at.desc())

    rows = (await session.execute(statement.limit(limit))).all()

    from app.services.case_workflow import tat_state

    return [
        {
            "id": case.id,
            "case_number": case.case_number,
            "company_name": company_name,
            "case_type_name": case_type_name,
            "life_assured_name": case.life_assured_name,
            "status": case.status.value,
            "status_label": status_label(case.status),
            "assigned_to": assignee,
            "received_at": case.received_at,
            "due_at": case.due_at,
            "tat_state": tat_state(
                case.status, case.due_at, case.completed_at, warning_hours
            ).value,
        }
        for case, company_name, case_type_name, assignee in rows
    ]


async def tat_breakdown(
    session: AsyncSession, *, user: User, view_all: bool, **filters: Any
) -> list[dict[str, Any]]:
    data = await summary(session, user=user, view_all=view_all, **filters)
    total = data["in_tat"] + data["out_of_tat"] + data["tat_about_to_breach"]
    return [
        {
            "key": TatState.IN_TAT.value,
            "label": "In TAT",
            "value": data["in_tat"],
            "percent": _percent(data["in_tat"], total),
            "color_token": "success",
        },
        {
            "key": TatState.ABOUT_TO_BREACH.value,
            "label": "About to breach",
            "value": data["tat_about_to_breach"],
            "percent": _percent(data["tat_about_to_breach"], total),
            "color_token": "warning",
        },
        {
            "key": TatState.OUT_OF_TAT.value,
            "label": "Out of TAT",
            "value": data["out_of_tat"],
            "percent": _percent(data["out_of_tat"], total),
            "color_token": "danger",
        },
    ]
