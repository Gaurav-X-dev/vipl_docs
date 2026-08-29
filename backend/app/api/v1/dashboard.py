"""Dashboard endpoints — optimised aggregates, never full-table downloads."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, require_permissions
from app.models.enums import CaseCategory
from app.models.user import User
from app.schemas.misc import (
    CompanyPerformanceRow,
    DashboardSummary,
    DistributionItem,
    RecentCaseRow,
    TrendPoint,
)
from app.schemas.staff import StaffPerformanceOut, StaffStatusOut
from app.services import dashboard_service, staff_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DashboardUser = Annotated[User, Depends(require_permissions("dashboard.view"))]


def _scope(user: User) -> bool:
    """Organisation-wide figures require an explicit permission."""
    return user.is_super_admin or "dashboard.view_all" in user.permission_codes


class Filters:
    """Shared dashboard query parameters (Image 2's filter row)."""

    def __init__(
        self,
        company_id: uuid.UUID | None = Query(None),
        case_type_id: uuid.UUID | None = Query(None),
        category: CaseCategory | None = Query(None),
        date_from: date | None = Query(None),
        date_to: date | None = Query(None),
    ) -> None:
        self.company_id = company_id
        self.case_type_id = case_type_id
        self.category = category
        self.date_from = date_from
        self.date_to = date_to

    def as_kwargs(self) -> dict:
        return {
            "company_id": self.company_id,
            "case_type_id": self.case_type_id,
            "category": self.category,
            "date_from": self.date_from,
            "date_to": self.date_to,
        }


FilterDep = Annotated[Filters, Depends(Filters)]


@router.get("/summary", response_model=DashboardSummary)
async def summary(session: DbSession, user: DashboardUser, filters: FilterDep) -> DashboardSummary:
    data = await dashboard_service.summary(
        session, user=user, view_all=_scope(user), **filters.as_kwargs()
    )
    return DashboardSummary(**data)


@router.get("/outcome-distribution", response_model=list[DistributionItem])
async def outcome_distribution(
    session: DbSession, user: DashboardUser, filters: FilterDep
) -> list[DistributionItem]:
    rows = await dashboard_service.outcome_distribution(
        session, user=user, view_all=_scope(user), **filters.as_kwargs()
    )
    return [DistributionItem(**row) for row in rows]


@router.get("/status-distribution", response_model=list[DistributionItem])
async def status_distribution(
    session: DbSession, user: DashboardUser, filters: FilterDep
) -> list[DistributionItem]:
    rows = await dashboard_service.status_distribution(
        session, user=user, view_all=_scope(user), **filters.as_kwargs()
    )
    return [DistributionItem(**row) for row in rows]


@router.get("/category-distribution", response_model=list[DistributionItem])
async def category_distribution(
    session: DbSession, user: DashboardUser, filters: FilterDep
) -> list[DistributionItem]:
    rows = await dashboard_service.category_distribution(
        session, user=user, view_all=_scope(user), **filters.as_kwargs()
    )
    return [DistributionItem(**row) for row in rows]


@router.get("/tat-breakdown", response_model=list[DistributionItem])
async def tat_breakdown(
    session: DbSession, user: DashboardUser, filters: FilterDep
) -> list[DistributionItem]:
    rows = await dashboard_service.tat_breakdown(
        session, user=user, view_all=_scope(user), **filters.as_kwargs()
    )
    return [DistributionItem(**row) for row in rows]


@router.get("/trend", response_model=list[TrendPoint])
async def trend(
    session: DbSession,
    user: DashboardUser,
    filters: FilterDep,
    bucket: Literal["day", "week", "month"] = Query("day"),
    days: int = Query(30, ge=1, le=365),
) -> list[TrendPoint]:
    rows = await dashboard_service.trend(
        session,
        user=user,
        view_all=_scope(user),
        bucket=bucket,
        days=days,
        **filters.as_kwargs(),
    )
    return [TrendPoint(**row) for row in rows]


@router.get("/company-performance", response_model=list[CompanyPerformanceRow])
async def company_performance(
    session: DbSession, user: DashboardUser, filters: FilterDep
) -> list[CompanyPerformanceRow]:
    rows = await dashboard_service.company_performance(
        session, user=user, view_all=_scope(user), **filters.as_kwargs()
    )
    return [CompanyPerformanceRow(**row) for row in rows]


@router.get("/investigator-performance", response_model=list[StaffPerformanceOut])
async def investigator_performance(
    session: DbSession,
    user: DashboardUser,
    filters: FilterDep,
    limit: int = Query(25, ge=1, le=100),
) -> list[StaffPerformanceOut]:
    rows = await dashboard_service.investigator_performance(
        session, user=user, view_all=_scope(user), limit=limit, **filters.as_kwargs()
    )
    return [StaffPerformanceOut(**row) for row in rows]


@router.get("/recent-cases", response_model=list[RecentCaseRow])
async def recent_cases(
    session: DbSession,
    user: DashboardUser,
    limit: int = Query(10, ge=1, le=50),
) -> list[RecentCaseRow]:
    rows = await dashboard_service.recent_cases(
        session, user=user, view_all=_scope(user), limit=limit
    )
    return [RecentCaseRow(**row) for row in rows]


@router.get("/overdue-cases", response_model=list[RecentCaseRow])
async def overdue_cases(
    session: DbSession, user: DashboardUser, limit: int = Query(10, ge=1, le=50)
) -> list[RecentCaseRow]:
    rows = await dashboard_service.recent_cases(
        session, user=user, view_all=_scope(user), limit=limit, only_overdue=True
    )
    return [RecentCaseRow(**row) for row in rows]


@router.get("/pending-assignments", response_model=list[RecentCaseRow])
async def pending_assignments(
    session: DbSession, user: DashboardUser, limit: int = Query(10, ge=1, le=50)
) -> list[RecentCaseRow]:
    rows = await dashboard_service.recent_cases(
        session, user=user, view_all=_scope(user), limit=limit, only_unassigned=True
    )
    return [RecentCaseRow(**row) for row in rows]


@router.get("/staff-status", response_model=list[StaffStatusOut])
async def staff_status(session: DbSession, user: DashboardUser) -> list[StaffStatusOut]:
    """Green/red strip: active vs non-active investigators and back office."""
    rows = await staff_service.status_list(session, only_assignable=False)
    return [StaffStatusOut(**row) for row in rows]
