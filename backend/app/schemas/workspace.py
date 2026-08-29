"""Payloads for the dynamic sidebar, attendance clock and activity log."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    AssignmentStage,
    AssignmentState,
    ClockState,
    VisitStatus,
)
from app.schemas.common import ORMModel, UserBrief


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #
class NavBucket(BaseModel):
    key: str
    label: str
    count: int = 0


class NavForm(BaseModel):
    """One configured form under a company: its case type."""

    case_type_id: str
    name: str
    count: int = 0


class NavCompany(BaseModel):
    id: str
    code: str
    name: str
    short_name: str
    count: int = 0
    #: Listed by the menu when a company has more than one form here.
    forms: list[NavForm] = Field(default_factory=list)


class NavCategory(BaseModel):
    category: str
    label: str
    slug: str
    icon: str
    permission: str
    total: int = 0
    open_total: int = 0
    buckets: list[NavBucket] = Field(default_factory=list)
    companies: list[NavCompany] = Field(default_factory=list)


class MyDeskCounts(BaseModel):
    field_open: int = 0
    office_open: int = 0
    correction_required: int = 0
    completed: int = 0


class SidebarOut(BaseModel):
    categories: list[NavCategory] = Field(default_factory=list)
    my_desk: MyDeskCounts = Field(default_factory=MyDeskCounts)
    generated_at: datetime


# --------------------------------------------------------------------------- #
# Attendance
# --------------------------------------------------------------------------- #
class ClockActionIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)


class ClockStatusOut(BaseModel):
    """What the header widget renders.

    ``worked_display`` is pre-formatted server-side so every screen agrees on
    how a duration looks.
    """

    state: ClockState
    session_id: uuid.UUID | None = None
    clock_in_at: datetime | None = None
    clock_out_at: datetime | None = None
    worked_minutes_today: int = 0
    open_session_minutes: int = 0
    sessions_today: int = 0
    work_date: date
    worked_display: str = "00:00"
    can_clock_in: bool = True
    can_clock_out: bool = False


class AttendanceSessionOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    work_date: date
    clock_in_at: datetime
    clock_out_at: datetime | None = None
    worked_minutes: int | None = None
    worked_display: str = "00:00"
    is_open: bool = True
    auto_closed: bool = False
    clock_in_note: str | None = None
    clock_out_note: str | None = None


class AttendanceOverviewRow(BaseModel):
    user_id: uuid.UUID
    user_name: str
    email: str | None = None
    employee_id: uuid.UUID | None = None
    work_date: date
    first_clock_in: datetime | None = None
    last_clock_out: datetime | None = None
    worked_minutes: int = 0
    worked_display: str = "00:00"
    sessions: int = 0
    clock_state: ClockState
    auto_closed: bool = False
    is_online: bool = False
    current_activity: str | None = None


class AttendanceTotals(BaseModel):
    total_staff: int = 0
    clocked_in: int = 0
    clocked_out: int = 0
    present_today: int = 0
    not_clocked_in: int = 0
    total_worked_minutes: int = 0
    total_worked_display: str = "00:00"


class AttendanceDashboardOut(BaseModel):
    work_date: date
    totals: AttendanceTotals
    rows: list[AttendanceOverviewRow] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Activity log
# --------------------------------------------------------------------------- #
class ActivityOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    user_label: str | None = None
    activity_type: str
    module: str
    summary: str | None = None
    detail: str | None = None
    case_id: uuid.UUID | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    entity_label: str | None = None
    page: str | None = None
    ip_address: str | None = None
    created_at: datetime


class LiveUserRow(BaseModel):
    """One line of the Super Admin's "who is working right now" table."""

    user: UserBrief
    is_online: bool = False
    clock_state: ClockState = ClockState.CLOCKED_OUT
    clocked_in_at: datetime | None = None
    worked_minutes_today: int = 0
    worked_display: str = "00:00"
    last_activity_at: datetime | None = None
    current_module: str | None = None
    current_action: str | None = None
    active_cases: int = 0


# --------------------------------------------------------------------------- #
# Two-stage assignment
# --------------------------------------------------------------------------- #
class OfficeAssignIn(BaseModel):
    office_staff_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None


class BulkOfficeAssignIn(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    office_staff_id: uuid.UUID
    notes: str | None = Field(default=None, max_length=1000)


class ReopenCaseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class SubmitToOfficeIn(BaseModel):
    remarks: str | None = Field(default=None, max_length=2000)
    outcome: str | None = None


class VisitUpdateIn(BaseModel):
    visit_status: VisitStatus
    visit_scheduled_at: datetime | None = None
    remarks: str | None = Field(default=None, max_length=2000)


class StageAssignmentOut(ORMModel):
    id: uuid.UUID
    stage: AssignmentStage
    state: AssignmentState
    assigned_to: UserBrief | None = None
    assigned_by: UserBrief | None = None
    is_reassignment: bool = False
    due_at: datetime | None = None
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    released_at: datetime | None = None
    notes: str | None = None
    created_at: datetime


class AssignableStaffOut(BaseModel):
    """A candidate for assignment, with the workload figures shown in the dialog."""

    id: uuid.UUID
    full_name: str
    email: str
    staff_category: str | None = None
    roles: list[str] = Field(default_factory=list)
    is_online: bool = False
    clock_state: ClockState = ClockState.CLOCKED_OUT
    active_cases: int = 0
    pending_cases: int = 0
    completed_this_month: int = 0
    overdue_cases: int = 0
