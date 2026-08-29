"""Reports module: case, investigator, company, status and import reports."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DbSession, can_view_all_cases, require_permissions
from app.models.enums import AuditAction, CaseCategory
from app.models.importing import ImportBatch
from app.models.user import User
from app.schemas.case import CaseFilters
from app.schemas.misc import (
    CompanyPerformanceRow,
    DistributionItem,
    ImportReportRow,
)
from app.schemas.staff import StaffPerformanceOut
from app.services import (
    audit_service,
    case_service,
    dashboard_service,
    export_service,
    settings_service,
)
from app.services.case_workflow import aging_days, tat_state

router = APIRouter(prefix="/reports", tags=["Reports"])

ViewReports = Annotated[User, Depends(require_permissions("reports.view"))]
ExportReports = Annotated[User, Depends(require_permissions("reports.export"))]

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment(payload: bytes, name: str, media: str) -> Response:
    return Response(
        content=payload,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


class ReportFilterDep:
    def __init__(
        self,
        date_from: date | None = Query(None),
        date_to: date | None = Query(None),
        company_id: uuid.UUID | None = Query(None),
        case_type_id: uuid.UUID | None = Query(None),
        category: CaseCategory | None = Query(None),
        investigator_id: uuid.UUID | None = Query(None),
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        self.company_id = company_id
        self.case_type_id = case_type_id
        self.category = category
        self.investigator_id = investigator_id

    def dashboard_kwargs(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "case_type_id": self.case_type_id,
            "category": self.category,
            "date_from": self.date_from,
            "date_to": self.date_to,
        }

    def case_filters(self) -> CaseFilters:
        return CaseFilters(
            company_id=self.company_id,
            case_type_id=self.case_type_id,
            category=self.category,
            assigned_to_id=self.investigator_id,
            received_from=self.date_from,
            received_to=self.date_to,
        )


Filters = Annotated[ReportFilterDep, Depends(ReportFilterDep)]


@router.get("/case-status", response_model=list[DistributionItem])
async def case_status_report(
    session: DbSession, user: ViewReports, filters: Filters
) -> list[DistributionItem]:
    rows = await dashboard_service.status_distribution(
        session,
        user=user,
        view_all=can_view_all_cases(user),
        **filters.dashboard_kwargs(),
    )
    return [DistributionItem(**row) for row in rows]


@router.get("/company", response_model=list[CompanyPerformanceRow])
async def company_report(
    session: DbSession, user: ViewReports, filters: Filters
) -> list[CompanyPerformanceRow]:
    rows = await dashboard_service.company_performance(
        session,
        user=user,
        view_all=can_view_all_cases(user),
        **filters.dashboard_kwargs(),
    )
    return [CompanyPerformanceRow(**row) for row in rows]


@router.get("/investigator", response_model=list[StaffPerformanceOut])
async def investigator_report(
    session: DbSession, user: ViewReports, filters: Filters
) -> list[StaffPerformanceOut]:
    rows = await dashboard_service.investigator_performance(
        session,
        user=user,
        view_all=can_view_all_cases(user),
        limit=200,
        **filters.dashboard_kwargs(),
    )
    return [StaffPerformanceOut(**row) for row in rows]


@router.get("/imports", response_model=list[ImportReportRow])
async def import_report(
    session: DbSession,
    user: ViewReports,
    limit: int = Query(100, ge=1, le=500),
) -> list[ImportReportRow]:
    from sqlalchemy.orm import selectinload

    rows = (
        (
            await session.execute(
                select(ImportBatch)
                .options(selectinload(ImportBatch.uploaded_by))
                .order_by(ImportBatch.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        ImportReportRow(
            batch_number=row.batch_number,
            filename=row.original_filename,
            uploaded_by=row.uploaded_by.full_name if row.uploaded_by else None,
            created_at=row.created_at,
            total_rows=row.total_rows,
            imported_rows=row.imported_rows,
            error_rows=row.error_rows,
            duplicate_rows=row.duplicate_rows,
            status=row.status.value,
        )
        for row in rows
    ]


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
@router.get("/cases/export")
async def export_case_report(
    session: DbSession,
    user: ExportReports,
    request: Request,
    filters: Filters,
    export_format: str = Query("xlsx", pattern="^(xlsx|csv)$", alias="format"),
) -> Response:
    warning_hours = await settings_service.get_int(session, "tat_breach_warning_hours", 24)
    statement = case_service.build_case_query(
        filters.case_filters(), user=user, view_all=can_view_all_cases(user)
    )
    cases = list((await session.execute(statement)).unique().scalars().all())
    rows = [
        export_service.case_export_row(
            case,
            aging_days(case.received_at, case.completed_at),
            tat_state(case.status, case.due_at, case.completed_at, warning_hours).value,
        )
        for case in cases
    ]

    await audit_service.record(
        session,
        action=AuditAction.EXPORT_RUN,
        module="Reports",
        actor=user,
        entity_type="CaseReport",
        remarks=f"{len(rows)} row(s) exported.",
        request=request,
    )
    await session.commit()

    if export_format == "csv":
        return _attachment(
            export_service.to_csv(export_service.CASE_EXPORT_HEADERS, rows),
            export_service.filename("case_report", "csv"),
            "text/csv; charset=utf-8",
        )
    return _attachment(
        export_service.to_xlsx(export_service.CASE_EXPORT_HEADERS, rows, sheet_title="Case report"),
        export_service.filename("case_report", "xlsx"),
        XLSX_MEDIA,
    )


@router.get("/investigator/export")
async def export_investigator_report(
    session: DbSession, user: ExportReports, request: Request, filters: Filters
) -> Response:
    rows = await dashboard_service.investigator_performance(
        session,
        user=user,
        view_all=can_view_all_cases(user),
        limit=500,
        **filters.dashboard_kwargs(),
    )
    headers = (
        "Investigator",
        "Category",
        "Online",
        "Assigned",
        "In Progress",
        "Report in Progress",
        "Pending",
        "Completed",
        "Overdue",
        "Positive",
        "Negative",
        "Suspicious",
        "Completion %",
    )
    body = [
        [
            row["full_name"],
            row["staff_category"].value
            if hasattr(row["staff_category"], "value")
            else row["staff_category"],
            "Online" if row["is_online"] else "Offline",
            row["assigned"],
            row["in_progress"],
            row["report_in_progress"],
            row["pending"],
            row["completed"],
            row["overdue"],
            row["positive"],
            row["negative"],
            row["suspicious"],
            row["completion_rate"],
        ]
        for row in rows
    ]
    return _attachment(
        export_service.to_xlsx(headers, body, sheet_title="Staff performance"),
        export_service.filename("staff_performance", "xlsx"),
        XLSX_MEDIA,
    )


@router.get("/company/export")
async def export_company_report(
    session: DbSession, user: ExportReports, filters: Filters
) -> Response:
    rows = await dashboard_service.company_performance(
        session,
        user=user,
        view_all=can_view_all_cases(user),
        **filters.dashboard_kwargs(),
    )
    headers = (
        "Company",
        "Code",
        "Total",
        "Unassigned",
        "WIP",
        "RIP",
        "Completed",
        "Overdue",
        "Positive",
        "Negative",
        "Suspicious",
    )
    body = [
        [
            row["company_name"],
            row["company_code"],
            row["total"],
            row["unassigned"],
            row["wip"],
            row["rip"],
            row["completed"],
            row["overdue"],
            row["positive"],
            row["negative"],
            row["suspicious"],
        ]
        for row in rows
    ]
    return _attachment(
        export_service.to_xlsx(headers, body, sheet_title="Company report"),
        export_service.filename("company_report", "xlsx"),
        XLSX_MEDIA,
    )


@router.get("/imports/export")
async def export_import_report(session: DbSession, user: ExportReports) -> Response:
    rows = await import_report(session, user, limit=500)
    headers = (
        "Batch",
        "File",
        "Uploaded by",
        "Uploaded at",
        "Total rows",
        "Imported",
        "Errors",
        "Duplicates",
        "Status",
    )
    body = [
        [
            row.batch_number,
            row.filename,
            row.uploaded_by,
            row.created_at,
            row.total_rows,
            row.imported_rows,
            row.error_rows,
            row.duplicate_rows,
            row.status,
        ]
        for row in rows
    ]
    return _attachment(
        export_service.to_xlsx(headers, body, sheet_title="Import report"),
        export_service.filename("import_report", "xlsx"),
        XLSX_MEDIA,
    )
