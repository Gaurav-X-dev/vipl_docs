"""Aggregates every v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    case_stages,
    cases,
    dashboard,
    imports,
    masters,
    reports,
    staff,
    workspace,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
# Registered before ``cases`` so /cases/assignable-staff is matched as a
# collection route rather than swallowed by /cases/{case_id}.
api_router.include_router(case_stages.router)
api_router.include_router(cases.router)
api_router.include_router(imports.router)
api_router.include_router(staff.router)
api_router.include_router(staff.hr_router)
api_router.include_router(masters.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(admin.notifications_router)
api_router.include_router(workspace.router)
api_router.include_router(workspace.attendance_router)
api_router.include_router(workspace.activity_router)
