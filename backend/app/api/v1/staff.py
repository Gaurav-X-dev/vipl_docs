"""Staff and HR endpoints."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, require_permissions
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.pagination import Page, PageParams, page_params, paginate
from app.core.security import generate_temporary_password
from app.models.case import Case
from app.models.enums import (
    AttendanceStatus,
    CaseStatus,
    LeaveStatus,
    StaffCategory,
)
from app.models.hr import Attendance, Department, Designation, Employee, LeaveRecord
from app.models.user import User, UserSession
from app.schemas.auth import LoginAttemptOut, ResetPasswordRequest, SessionOut
from app.schemas.case import CaseListItem
from app.schemas.common import IdResponse, Message
from app.schemas.staff import (
    AttendanceIn,
    AttendanceOut,
    DepartmentIn,
    DepartmentOut,
    DesignationIn,
    DesignationOut,
    LeaveDecision,
    LeaveIn,
    LeaveOut,
    StaffCreate,
    StaffDetailOut,
    StaffOut,
    StaffPerformanceOut,
    StaffStatusOut,
    StaffUpdate,
)
from app.services import (
    auth_service,
    case_service,
    dashboard_service,
    settings_service,
    staff_service,
)
from app.utils.dates import utcnow

router = APIRouter(prefix="/staff", tags=["Staff"])
hr_router = APIRouter(prefix="/hr", tags=["HR"])

ViewStaff = Annotated[User, Depends(require_permissions("staff.view"))]
CreateStaff = Annotated[User, Depends(require_permissions("staff.create"))]
EditStaff = Annotated[User, Depends(require_permissions("staff.edit"))]
DisableStaff = Annotated[User, Depends(require_permissions("staff.disable"))]
ViewHr = Annotated[User, Depends(require_permissions("hr.view"))]
ManageHr = Annotated[User, Depends(require_permissions("hr.manage"))]
PageDep = Annotated[PageParams, Depends(page_params)]


# --------------------------------------------------------------------------- #
# Staff
# --------------------------------------------------------------------------- #
@router.get("/status", response_model=list[StaffStatusOut])
async def staff_status(
    session: DbSession,
    user: ViewStaff,
    staff_category: StaffCategory | None = Query(None),
    only_assignable: bool = Query(True),
) -> list[StaffStatusOut]:
    """Green/red status plus workload — used by the assignment screens."""
    rows = await staff_service.status_list(
        session, staff_category=staff_category, only_assignable=only_assignable
    )
    return [StaffStatusOut(**row) for row in rows]


@router.get("", response_model=Page[StaffOut])
async def list_staff(
    session: DbSession,
    user: ViewStaff,
    params: PageDep,
    search: str | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
    designation_id: uuid.UUID | None = Query(None),
    staff_category: StaffCategory | None = Query(None),
    role_code: str | None = Query(None),
    is_active: bool | None = Query(None),
    online: bool | None = Query(None),
) -> Page[StaffOut]:
    timeout = await staff_service.online_timeout(session)
    threshold = utcnow() - timedelta(minutes=timeout)
    statement = staff_service.build_staff_query(
        search=search,
        department_id=department_id,
        designation_id=designation_id,
        staff_category=staff_category,
        role_code=role_code,
        is_active=is_active,
        online_only=online,
        online_threshold=threshold,
    )
    rows, total = await paginate(session, statement, params)
    workload = await case_service.workload_by_user(session)
    items = [
        StaffOut(**staff_service.staff_payload(employee, timeout, workload)) for employee in rows
    ]
    return Page.build(items, total, params)


@router.post("", response_model=IdResponse, status_code=201)
async def create_staff(
    payload: StaffCreate, request: Request, session: DbSession, user: CreateStaff
) -> IdResponse:
    employee, temporary = await staff_service.create_staff(
        session, payload, actor=user, request=request
    )
    await session.commit()
    return IdResponse(
        id=employee.id,
        message=(
            f"Staff created. Temporary password: {temporary}" if temporary else "Staff created."
        ),
    )


@router.get("/{employee_id}", response_model=StaffDetailOut)
async def get_staff(employee_id: uuid.UUID, session: DbSession, user: ViewStaff) -> StaffDetailOut:
    employee = await staff_service.get_employee(session, employee_id)
    timeout = await staff_service.online_timeout(session)
    workload = await case_service.workload_by_user(session)
    return StaffDetailOut(**staff_service.staff_detail_payload(employee, timeout, workload))


@router.patch("/{employee_id}", response_model=Message)
async def update_staff(
    employee_id: uuid.UUID,
    payload: StaffUpdate,
    request: Request,
    session: DbSession,
    user: EditStaff,
) -> Message:
    employee = await staff_service.get_employee(session, employee_id)
    await staff_service.update_staff(session, employee, payload, actor=user, request=request)
    await session.commit()
    return Message(message="Staff updated.")


@router.post("/{employee_id}/disable", response_model=Message)
async def disable_staff(
    employee_id: uuid.UUID, request: Request, session: DbSession, user: DisableStaff
) -> Message:
    employee = await staff_service.get_employee(session, employee_id)
    if employee.user is not None and employee.user.is_super_admin:
        raise ConflictError("The Super Admin account cannot be disabled.")
    await staff_service.update_staff(
        session,
        employee,
        StaffUpdate(is_active=False, login_enabled=False),
        actor=user,
        request=request,
    )
    await session.commit()
    return Message(message="Staff account disabled.")


@router.post("/{employee_id}/enable", response_model=Message)
async def enable_staff(
    employee_id: uuid.UUID, request: Request, session: DbSession, user: DisableStaff
) -> Message:
    employee = await staff_service.get_employee(session, employee_id)
    await staff_service.update_staff(
        session,
        employee,
        StaffUpdate(is_active=True, login_enabled=True),
        actor=user,
        request=request,
    )
    await session.commit()
    return Message(message="Staff account enabled.")


@router.post("/{employee_id}/reset-password", response_model=Message)
async def reset_password(
    employee_id: uuid.UUID,
    payload: ResetPasswordRequest,
    request: Request,
    session: DbSession,
    user: EditStaff,
) -> Message:
    employee = await staff_service.get_employee(session, employee_id)
    if employee.user is None:
        raise ValidationError("This employee has no login account.")
    new_password = payload.new_password or generate_temporary_password()
    await auth_service.admin_reset_password(
        session,
        employee.user,
        new_password,
        actor=user,
        require_change=payload.require_change_on_login,
        request=request,
    )
    await session.commit()
    return Message(
        message="Password reset.",
        detail=(
            f"Temporary password: {new_password}"
            if payload.new_password is None
            else "The new password has been applied."
        ),
    )


@router.get("/{employee_id}/cases", response_model=Page[CaseListItem])
async def staff_cases(
    employee_id: uuid.UUID,
    session: DbSession,
    user: ViewStaff,
    params: PageDep,
    completed: bool | None = Query(None),
) -> Page[CaseListItem]:
    employee = await staff_service.get_employee(session, employee_id)
    if employee.user is None:
        return Page.build([], 0, params)

    warning_hours = await settings_service.get_int(session, "tat_breach_warning_hours", 24)
    timeout = await staff_service.online_timeout(session)

    statement = (
        select(Case)
        .options(
            selectinload(Case.company),
            selectinload(Case.case_type),
            selectinload(Case.assigned_to),
        )
        .where(Case.assigned_to_id == employee.user_id)
    )
    if completed is True:
        statement = statement.where(Case.status == CaseStatus.COMPLETED)
    elif completed is False:
        statement = statement.where(Case.status != CaseStatus.COMPLETED)
    statement = statement.order_by(Case.received_at.desc())

    rows, total = await paginate(session, statement, params)
    items = [
        CaseListItem(**case_service.case_list_payload(case, warning_hours, timeout))
        for case in rows
    ]
    return Page.build(items, total, params)


@router.get("/{employee_id}/performance", response_model=StaffPerformanceOut)
async def staff_performance(
    employee_id: uuid.UUID, session: DbSession, user: ViewStaff
) -> StaffPerformanceOut:
    employee = await staff_service.get_employee(session, employee_id)
    if employee.user is None:
        raise NotFoundError("This employee has no login account.")
    rows = await dashboard_service.investigator_performance(
        session, user=user, view_all=True, limit=500
    )
    for row in rows:
        if row["staff_id"] == employee.user_id:
            return StaffPerformanceOut(**row)
    timeout = await staff_service.online_timeout(session)
    return StaffPerformanceOut(
        staff_id=employee.user_id,
        full_name=employee.full_name,
        staff_category=employee.staff_category,
        is_online=employee.user.is_online(timeout),
    )


@router.get("/{employee_id}/activity", response_model=list[SessionOut])
async def staff_sessions(
    employee_id: uuid.UUID, session: DbSession, user: ViewStaff
) -> list[SessionOut]:
    employee = await staff_service.get_employee(session, employee_id)
    if employee.user_id is None:
        return []
    rows = await auth_service.list_sessions(session, employee.user_id, limit=50)
    return [SessionOut.model_validate(row) for row in rows]


@router.get("/{employee_id}/login-attempts", response_model=list[LoginAttemptOut])
async def staff_login_attempts(
    employee_id: uuid.UUID, session: DbSession, user: ViewStaff
) -> list[LoginAttemptOut]:
    employee = await staff_service.get_employee(session, employee_id)
    if employee.user is None:
        return []
    rows = await auth_service.list_login_attempts(session, email=employee.user.email, limit=50)
    return [LoginAttemptOut.model_validate(row) for row in rows]


# --------------------------------------------------------------------------- #
# HR: departments and designations
# --------------------------------------------------------------------------- #
@hr_router.get("/departments", response_model=list[DepartmentOut])
async def list_departments(session: DbSession, user: ViewHr) -> list[DepartmentOut]:
    counts = dict(
        (
            await session.execute(
                select(Employee.department_id, func.count()).group_by(Employee.department_id)
            )
        ).all()
    )
    rows = (await session.execute(select(Department).order_by(Department.name))).scalars().all()
    return [
        DepartmentOut(
            id=row.id,
            code=row.code,
            name=row.name,
            description=row.description,
            is_active=row.is_active,
            employee_count=int(counts.get(row.id, 0)),
        )
        for row in rows
    ]


@hr_router.post("/departments", response_model=IdResponse, status_code=201)
async def create_department(
    payload: DepartmentIn, session: DbSession, user: ManageHr
) -> IdResponse:
    row = Department(**payload.model_dump())
    session.add(row)
    await session.commit()
    return IdResponse(id=row.id, message="Department created.")


@hr_router.patch("/departments/{department_id}", response_model=Message)
async def update_department(
    department_id: uuid.UUID,
    payload: DepartmentIn,
    session: DbSession,
    user: ManageHr,
) -> Message:
    row = await session.get(Department, department_id)
    if row is None:
        raise NotFoundError("Department not found.")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await session.commit()
    return Message(message="Department updated.")


@hr_router.get("/designations", response_model=list[DesignationOut])
async def list_designations(session: DbSession, user: ViewHr) -> list[DesignationOut]:
    counts = dict(
        (
            await session.execute(
                select(Employee.designation_id, func.count()).group_by(Employee.designation_id)
            )
        ).all()
    )
    rows = (await session.execute(select(Designation).order_by(Designation.name))).scalars().all()
    return [
        DesignationOut(
            id=row.id,
            code=row.code,
            name=row.name,
            grade=row.grade,
            description=row.description,
            is_active=row.is_active,
            employee_count=int(counts.get(row.id, 0)),
        )
        for row in rows
    ]


@hr_router.post("/designations", response_model=IdResponse, status_code=201)
async def create_designation(
    payload: DesignationIn, session: DbSession, user: ManageHr
) -> IdResponse:
    row = Designation(**payload.model_dump())
    session.add(row)
    await session.commit()
    return IdResponse(id=row.id, message="Designation created.")


@hr_router.patch("/designations/{designation_id}", response_model=Message)
async def update_designation(
    designation_id: uuid.UUID,
    payload: DesignationIn,
    session: DbSession,
    user: ManageHr,
) -> Message:
    row = await session.get(Designation, designation_id)
    if row is None:
        raise NotFoundError("Designation not found.")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    await session.commit()
    return Message(message="Designation updated.")


# --------------------------------------------------------------------------- #
# HR: employees, attendance, leave
# --------------------------------------------------------------------------- #
@hr_router.get("/employees", response_model=Page[StaffOut])
async def list_employees(
    session: DbSession,
    user: ViewHr,
    params: PageDep,
    search: str | None = Query(None),
    department_id: uuid.UUID | None = Query(None),
) -> Page[StaffOut]:
    timeout = await staff_service.online_timeout(session)
    statement = staff_service.build_staff_query(search=search, department_id=department_id)
    rows, total = await paginate(session, statement, params)
    return Page.build(
        [StaffOut(**staff_service.staff_payload(row, timeout)) for row in rows],
        total,
        params,
    )


@hr_router.get("/attendance", response_model=list[AttendanceOut])
async def list_attendance(
    session: DbSession,
    user: ViewHr,
    from_date: date = Query(...),
    to_date: date = Query(...),
    employee_id: uuid.UUID | None = Query(None),
) -> list[AttendanceOut]:
    statement = (
        select(Attendance)
        .options(selectinload(Attendance.employee))
        .where(Attendance.work_date >= from_date, Attendance.work_date <= to_date)
        .order_by(Attendance.work_date.desc())
    )
    if employee_id:
        statement = statement.where(Attendance.employee_id == employee_id)
    rows = (await session.execute(statement)).scalars().all()
    return [
        AttendanceOut(
            id=row.id,
            employee_id=row.employee_id,
            employee_name=row.employee.full_name if row.employee else None,
            work_date=row.work_date,
            status=row.status,
            check_in_at=row.check_in_at,
            check_out_at=row.check_out_at,
            worked_hours=float(row.worked_hours) if row.worked_hours else None,
            remarks=row.remarks,
            derived_from_login=row.derived_from_login,
        )
        for row in rows
    ]


@hr_router.post("/attendance", response_model=IdResponse, status_code=201)
async def mark_attendance(payload: AttendanceIn, session: DbSession, user: ManageHr) -> IdResponse:
    existing = (
        await session.execute(
            select(Attendance).where(
                Attendance.employee_id == payload.employee_id,
                Attendance.work_date == payload.work_date,
            )
        )
    ).scalar_one_or_none()
    row = existing or Attendance(employee_id=payload.employee_id, work_date=payload.work_date)
    row.status = payload.status
    row.check_in_at = payload.check_in_at
    row.check_out_at = payload.check_out_at
    row.remarks = payload.remarks
    if payload.check_in_at and payload.check_out_at:
        row.worked_hours = round(
            (payload.check_out_at - payload.check_in_at).total_seconds() / 3600, 2
        )
    if existing is None:
        session.add(row)
    await session.commit()
    return IdResponse(id=row.id, message="Attendance recorded.")


@hr_router.post("/attendance/sync-from-logins", response_model=Message)
async def sync_attendance(
    session: DbSession,
    user: ManageHr,
    work_date: date = Query(..., description="Day to derive attendance for"),
) -> Message:
    """Derive attendance from the login/heartbeat trail for one day."""
    from app.utils.dates import end_of_day, start_of_day

    day_start, day_end = start_of_day(work_date), end_of_day(work_date)
    rows = (
        await session.execute(
            select(
                UserSession.user_id,
                func.min(UserSession.started_at),
                func.max(UserSession.last_seen_at),
            )
            .where(UserSession.started_at >= day_start, UserSession.started_at <= day_end)
            .group_by(UserSession.user_id)
        )
    ).all()

    created = 0
    for user_id, first_seen, last_seen in rows:
        employee = (
            await session.execute(select(Employee).where(Employee.user_id == user_id))
        ).scalar_one_or_none()
        if employee is None:
            continue
        existing = (
            await session.execute(
                select(Attendance).where(
                    Attendance.employee_id == employee.id,
                    Attendance.work_date == work_date,
                )
            )
        ).scalar_one_or_none()
        if existing is not None and not existing.derived_from_login:
            continue  # never overwrite a manual entry
        record = existing or Attendance(employee_id=employee.id, work_date=work_date)
        worked = (last_seen - first_seen).total_seconds() / 3600
        record.status = AttendanceStatus.PRESENT if worked >= 4 else AttendanceStatus.HALF_DAY
        record.check_in_at = first_seen
        record.check_out_at = last_seen
        record.worked_hours = round(worked, 2)
        record.derived_from_login = True
        if existing is None:
            session.add(record)
        created += 1

    await session.commit()
    return Message(message=f"Attendance derived for {created} employee(s).")


@hr_router.get("/leaves", response_model=list[LeaveOut])
async def list_leaves(
    session: DbSession,
    user: ViewHr,
    status_filter: LeaveStatus | None = Query(None, alias="status"),
    employee_id: uuid.UUID | None = Query(None),
) -> list[LeaveOut]:
    statement = (
        select(LeaveRecord)
        .options(selectinload(LeaveRecord.employee))
        .order_by(LeaveRecord.from_date.desc())
    )
    if status_filter:
        statement = statement.where(LeaveRecord.status == status_filter)
    if employee_id:
        statement = statement.where(LeaveRecord.employee_id == employee_id)
    rows = (await session.execute(statement)).scalars().all()
    return [
        LeaveOut(
            id=row.id,
            employee_id=row.employee_id,
            employee_name=row.employee.full_name if row.employee else None,
            leave_type=row.leave_type,
            from_date=row.from_date,
            to_date=row.to_date,
            days=float(row.days),
            reason=row.reason,
            status=row.status,
            approved_by=None,
            approved_at=row.approved_at,
            decision_remark=row.decision_remark,
            created_at=row.created_at,
        )
        for row in rows
    ]


@hr_router.post("/leaves", response_model=IdResponse, status_code=201)
async def apply_leave(payload: LeaveIn, session: DbSession, user: ViewHr) -> IdResponse:
    if payload.to_date < payload.from_date:
        raise ValidationError("The end date cannot be before the start date.")
    row = LeaveRecord(**payload.model_dump())
    session.add(row)
    await session.commit()
    return IdResponse(id=row.id, message="Leave request submitted.")


@hr_router.post("/leaves/{leave_id}/decision", response_model=Message)
async def decide_leave(
    leave_id: uuid.UUID,
    payload: LeaveDecision,
    session: DbSession,
    user: ManageHr,
) -> Message:
    row = await session.get(LeaveRecord, leave_id)
    if row is None:
        raise NotFoundError("Leave record not found.")
    row.status = payload.status
    row.decision_remark = payload.decision_remark
    row.approved_by_id = user.id
    row.approved_at = utcnow()
    await session.commit()
    return Message(message=f"Leave {payload.status.value.lower()}.")
