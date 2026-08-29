"""Staff management: login account + employee profile as one unit."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.permissions import INVESTIGATOR_ROLE_CODE
from app.core.security import generate_temporary_password, hash_password
from app.models.enums import AuditAction, StaffCategory
from app.models.hr import Department, Designation, Employee
from app.models.rbac import Role
from app.models.user import User
from app.schemas.staff import StaffCreate, StaffUpdate
from app.services import audit_service, settings_service
from app.utils.dates import utcnow


async def online_timeout(session: AsyncSession) -> int:
    return await settings_service.get_int(session, "staff_online_timeout_minutes", 5)


def status_label(is_online: bool) -> str:
    return "Online" if is_online else "Offline"


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
def build_staff_query(
    *,
    search: str | None = None,
    department_id: uuid.UUID | None = None,
    designation_id: uuid.UUID | None = None,
    staff_category: StaffCategory | None = None,
    role_code: str | None = None,
    is_active: bool | None = None,
    online_only: bool | None = None,
    online_threshold=None,
) -> Select[Any]:
    statement = (
        select(Employee)
        .options(
            selectinload(Employee.user).selectinload(User.roles),
            selectinload(Employee.department),
            selectinload(Employee.designation),
        )
        .outerjoin(User, Employee.user_id == User.id)
    )
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Employee.employee_code.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
                Employee.mobile.ilike(term),
                Employee.email.ilike(term),
                User.email.ilike(term),
                User.full_name.ilike(term),
            )
        )
    if department_id:
        statement = statement.where(Employee.department_id == department_id)
    if designation_id:
        statement = statement.where(Employee.designation_id == designation_id)
    if staff_category:
        statement = statement.where(Employee.staff_category == staff_category)
    if is_active is not None:
        statement = statement.where(
            User.is_active.is_(is_active) if is_active is not None else True
        )
    if role_code:
        statement = statement.where(User.roles.any(Role.code == role_code))
    if online_only is True and online_threshold is not None:
        statement = statement.where(
            User.last_activity_at.is_not(None),
            User.last_activity_at >= online_threshold,
        )
    elif online_only is False and online_threshold is not None:
        statement = statement.where(
            or_(
                User.last_activity_at.is_(None),
                User.last_activity_at < online_threshold,
            )
        )
    return statement.order_by(Employee.first_name.asc(), Employee.employee_code.asc())


async def get_employee(session: AsyncSession, employee_id: uuid.UUID) -> Employee:
    result = await session.execute(
        select(Employee)
        .options(
            selectinload(Employee.user).selectinload(User.roles),
            selectinload(Employee.department),
            selectinload(Employee.designation),
            selectinload(Employee.reporting_manager),
        )
        .where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if employee is None:
        raise NotFoundError("Staff member not found.")
    return employee


def staff_payload(
    employee: Employee,
    timeout_minutes: int,
    workload: dict[uuid.UUID, dict[str, int]] | None = None,
) -> dict[str, Any]:
    user = employee.user
    is_online = bool(user and user.is_online(timeout_minutes))
    stats = workload.get(user.id, {}) if workload and user is not None else {}
    return {
        "id": employee.id,
        "user_id": user.id if user else None,
        "employee_code": employee.employee_code,
        "full_name": employee.full_name,
        "email": (user.email if user else employee.email),
        "mobile": employee.mobile,
        "gender": employee.gender,
        "staff_category": employee.staff_category,
        "department": employee.department.name if employee.department else None,
        "designation": employee.designation.name if employee.designation else None,
        "employment_status": employee.employment_status,
        "joining_date": employee.joining_date,
        "city": employee.city,
        "state": employee.state,
        "roles": [role.name for role in user.roles] if user else [],
        "login_enabled": bool(user and user.login_enabled),
        "is_active": bool(user.is_active) if user else True,
        "is_online": is_online,
        "status_label": status_label(is_online),
        "last_login_at": user.last_login_at if user else None,
        "last_activity_at": user.last_activity_at if user else None,
        "last_logout_at": user.last_logout_at if user else None,
        "open_cases": stats.get("open", 0),
        "completed_cases": stats.get("completed", 0),
        "overdue_cases": stats.get("overdue", 0),
    }


def staff_detail_payload(
    employee: Employee,
    timeout_minutes: int,
    workload: dict[uuid.UUID, dict[str, int]] | None = None,
) -> dict[str, Any]:
    payload = staff_payload(employee, timeout_minutes, workload)
    user = employee.user
    payload.update(
        {
            "date_of_birth": employee.date_of_birth,
            "alternate_mobile": employee.alternate_mobile,
            "address_line1": employee.address_line1,
            "address_line2": employee.address_line2,
            "pin_code": employee.pin_code,
            "reporting_manager": (
                employee.reporting_manager.full_name if employee.reporting_manager else None
            ),
            "base_city": employee.base_city,
            "base_state": employee.base_state,
            "exit_date": employee.exit_date,
            "id_proof_type": employee.id_proof_type,
            "id_proof_number": employee.id_proof_number,
            "bank_account_name": employee.bank_account_name,
            "bank_account_number": employee.bank_account_number,
            "bank_name": employee.bank_name,
            "bank_ifsc": employee.bank_ifsc,
            "notes": employee.notes,
            "must_change_password": bool(user and user.must_change_password),
            "last_login_ip": user.last_login_ip if user else None,
            "role_ids": [role.id for role in user.roles] if user else [],
        }
    )
    return payload


# --------------------------------------------------------------------------- #
# Mutations
# --------------------------------------------------------------------------- #
async def _assert_unique(
    session: AsyncSession,
    *,
    email: str,
    employee_code: str,
    exclude_user_id: uuid.UUID | None = None,
    exclude_employee_id: uuid.UUID | None = None,
) -> None:
    email_query = select(User).where(func.lower(User.email) == email.lower())
    if exclude_user_id:
        email_query = email_query.where(User.id != exclude_user_id)
    if (await session.execute(email_query)).scalar_one_or_none() is not None:
        raise ConflictError(f"A user with the email {email} already exists.")

    code_query = select(Employee).where(func.lower(Employee.employee_code) == employee_code.lower())
    if exclude_employee_id:
        code_query = code_query.where(Employee.id != exclude_employee_id)
    if (await session.execute(code_query)).scalar_one_or_none() is not None:
        raise ConflictError(f"Employee code {employee_code} is already in use.")


async def create_staff(
    session: AsyncSession,
    payload: StaffCreate,
    *,
    actor: User,
    request: Request | None = None,
) -> tuple[Employee, str | None]:
    """Create the login account and the employee profile together.

    Returns ``(employee, temporary_password)`` — the temporary password is only
    returned when the system generated it, and is never stored in plain text.
    """
    await _assert_unique(session, email=str(payload.email), employee_code=payload.employee_code)

    generated: str | None = None
    raw_password = payload.password
    if not raw_password:
        raw_password = generate_temporary_password()
        generated = raw_password

    full_name = " ".join(
        part for part in (payload.first_name, payload.middle_name, payload.last_name) if part
    )
    user = User(
        email=str(payload.email).lower(),
        password_hash=hash_password(raw_password),
        full_name=full_name,
        phone=payload.mobile,
        staff_category=payload.staff_category,
        login_enabled=payload.login_enabled,
        is_active=True,
        must_change_password=generated is not None,
        password_changed_at=utcnow(),
    )
    assigned_role_codes: list[str] = []
    if payload.role_ids:
        roles = (
            (await session.execute(select(Role).where(Role.id.in_(payload.role_ids))))
            .scalars()
            .all()
        )
        if len(roles) != len(set(payload.role_ids)):
            raise ValidationError("One or more selected roles do not exist.")
        user.roles = list(roles)
        assigned_role_codes = [role.code for role in roles]
    elif payload.staff_category == StaffCategory.FIELD:
        # A field employee without an explicit role would be able to log in but
        # could not see the cases assigned to them. Apply the least-privileged
        # investigator role as the professional default.
        investigator_role = (
            await session.execute(select(Role).where(Role.code == INVESTIGATOR_ROLE_CODE))
        ).scalar_one_or_none()
        if investigator_role is not None:
            user.roles = [investigator_role]
            assigned_role_codes = [investigator_role.code]
    session.add(user)
    await session.flush()

    employee = Employee(
        employee_code=payload.employee_code,
        user_id=user.id,
        first_name=payload.first_name,
        middle_name=payload.middle_name,
        last_name=payload.last_name,
        gender=payload.gender,
        date_of_birth=payload.date_of_birth,
        mobile=payload.mobile,
        alternate_mobile=payload.alternate_mobile,
        email=str(payload.email).lower(),
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        pin_code=payload.pin_code,
        department_id=payload.department_id,
        designation_id=payload.designation_id,
        reporting_manager_id=payload.reporting_manager_id,
        staff_category=payload.staff_category,
        joining_date=payload.joining_date,
        employment_status=payload.employment_status,
        base_city=payload.base_city or payload.city,
        base_state=payload.base_state or payload.state,
        id_proof_type=payload.id_proof_type,
        id_proof_number=payload.id_proof_number,
        bank_account_name=payload.bank_account_name,
        bank_account_number=payload.bank_account_number,
        bank_name=payload.bank_name,
        bank_ifsc=payload.bank_ifsc,
        notes=payload.notes,
    )
    session.add(employee)
    await session.flush()

    await audit_service.record(
        session,
        action=AuditAction.STAFF_CREATED,
        module="Staff",
        actor=actor,
        entity_type="Employee",
        entity_id=employee.id,
        entity_label=f"{employee.employee_code} — {employee.full_name}",
        new_values={
            "employee_code": employee.employee_code,
            "email": user.email,
            "staff_category": employee.staff_category.value,
            # Do not access a not-yet-loaded relationship on AsyncSession.
            "roles": assigned_role_codes,
        },
        request=request,
    )
    return employee, generated


async def update_staff(
    session: AsyncSession,
    employee: Employee,
    payload: StaffUpdate,
    *,
    actor: User,
    request: Request | None = None,
) -> Employee:
    changes = payload.model_dump(exclude_unset=True)
    role_ids = changes.pop("role_ids", None)
    login_enabled = changes.pop("login_enabled", None)
    is_active = changes.pop("is_active", None)
    email = changes.pop("email", None)

    user = employee.user
    if email and user is not None and str(email).lower() != user.email:
        await _assert_unique(
            session,
            email=str(email),
            employee_code=employee.employee_code,
            exclude_user_id=user.id,
            exclude_employee_id=employee.id,
        )
        user.email = str(email).lower()
        employee.email = str(email).lower()

    before = {key: getattr(employee, key, None) for key in changes}
    for key, value in changes.items():
        setattr(employee, key, value)

    if user is not None:
        if any(k in changes for k in ("first_name", "middle_name", "last_name")):
            user.full_name = employee.full_name
        if "mobile" in changes:
            user.phone = employee.mobile
        if "staff_category" in changes:
            user.staff_category = employee.staff_category
        if login_enabled is not None:
            user.login_enabled = login_enabled
        if is_active is not None:
            user.is_active = is_active
            if not is_active:
                user.last_activity_at = None
        if role_ids is not None:
            if user.is_super_admin:
                raise ConflictError("The Super Admin's roles cannot be changed.")
            roles = (
                (await session.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all()
            )
            user.roles = list(roles)

    old_values, new_values = audit_service.diff(before, changes)
    action = (
        AuditAction.STAFF_DISABLED
        if is_active is False or login_enabled is False
        else AuditAction.STAFF_UPDATED
    )
    await audit_service.record(
        session,
        action=action,
        module="Staff",
        actor=actor,
        entity_type="Employee",
        entity_id=employee.id,
        entity_label=f"{employee.employee_code} — {employee.full_name}",
        old_values=old_values,
        new_values={
            **new_values,
            **({"login_enabled": login_enabled} if login_enabled is not None else {}),
            **({"is_active": is_active} if is_active is not None else {}),
            **({"role_ids": role_ids} if role_ids is not None else {}),
        },
        request=request,
    )
    return employee


# --------------------------------------------------------------------------- #
# Status list used by the assignment screen and the dashboard strip
# --------------------------------------------------------------------------- #
async def status_list(
    session: AsyncSession,
    *,
    staff_category: StaffCategory | None = None,
    only_assignable: bool = True,
) -> list[dict[str, Any]]:
    from app.services import case_service

    timeout_minutes = await online_timeout(session)
    workload = await case_service.workload_by_user(session)

    statement = (
        select(User, Employee)
        .outerjoin(Employee, Employee.user_id == User.id)
        .where(User.is_active.is_(True))
    )
    if only_assignable:
        statement = statement.where(User.login_enabled.is_(True))
    if staff_category:
        statement = statement.where(User.staff_category == staff_category)

    rows = (await session.execute(statement)).unique().all()
    payload: list[dict[str, Any]] = []
    for user, employee in rows:
        # ``is_online`` normalises naive timestamps, which SQLite returns.
        is_online = user.is_online(timeout_minutes)
        stats = workload.get(user.id, {})
        payload.append(
            {
                "id": user.id,
                "full_name": user.full_name,
                "staff_category": user.staff_category,
                "is_online": is_online,
                "status_label": status_label(is_online),
                "last_activity_at": user.last_activity_at,
                "open_cases": stats.get("open", 0),
                "pending_cases": stats.get("wip", 0) + stats.get("rip", 0),
                "completed_cases": stats.get("completed", 0),
                "base_city": employee.base_city if employee else None,
                "base_state": employee.base_state if employee else None,
            }
        )
    # Online staff first, then the lightest workload — the order an admin wants
    # when choosing who to give the next case to.
    payload.sort(key=lambda row: (not row["is_online"], row["open_cases"]))
    return payload


async def ensure_masters(session: AsyncSession) -> None:
    """Guarantee at least one department and designation exist."""
    if (await session.execute(select(func.count()).select_from(Department))).scalar_one() == 0:
        session.add(Department(code="OPS", name="Operations"))
    if (await session.execute(select(func.count()).select_from(Designation))).scalar_one() == 0:
        session.add(Designation(code="IO", name="Investigating Officer"))
