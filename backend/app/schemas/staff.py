"""Staff and HR payloads."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    AttendanceStatus,
    EmploymentStatus,
    Gender,
    LeaveStatus,
    LeaveType,
    StaffCategory,
)
from app.schemas.common import ORMModel


# --------------------------------------------------------------------------- #
# Staff (login account + employee profile)
# --------------------------------------------------------------------------- #
class StaffBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    gender: Gender = Gender.UNDISCLOSED
    date_of_birth: date | None = None
    mobile: str | None = Field(default=None, max_length=24)
    alternate_mobile: str | None = Field(default=None, max_length=24)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    pin_code: str | None = Field(default=None, max_length=12)
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    reporting_manager_id: uuid.UUID | None = None
    staff_category: StaffCategory = StaffCategory.FIELD
    joining_date: date | None = None
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    base_city: str | None = Field(default=None, max_length=120)
    base_state: str | None = Field(default=None, max_length=120)
    id_proof_type: str | None = Field(default=None, max_length=48)
    id_proof_number: str | None = Field(default=None, max_length=64)
    bank_account_name: str | None = Field(default=None, max_length=120)
    bank_account_number: str | None = Field(default=None, max_length=48)
    bank_name: str | None = Field(default=None, max_length=120)
    bank_ifsc: str | None = Field(default=None, max_length=24)
    notes: str | None = None


class StaffCreate(StaffBase):
    employee_code: str = Field(min_length=1, max_length=32)
    email: str = Field(min_length=3, max_length=320)
    password: str | None = Field(
        default=None,
        min_length=8,
        max_length=256,
        description="Leave empty to generate a temporary password.",
    )
    role_ids: list[uuid.UUID] = Field(default_factory=list)
    login_enabled: bool = True

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("Enter a valid email address.")
        return value


class StaffUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    middle_name: str | None = Field(default=None, max_length=80)
    last_name: str | None = Field(default=None, max_length=80)
    gender: Gender | None = None
    date_of_birth: date | None = None
    mobile: str | None = Field(default=None, max_length=24)
    alternate_mobile: str | None = Field(default=None, max_length=24)
    email: str | None = Field(default=None, min_length=3, max_length=320)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    pin_code: str | None = Field(default=None, max_length=12)
    department_id: uuid.UUID | None = None
    designation_id: uuid.UUID | None = None
    reporting_manager_id: uuid.UUID | None = None
    staff_category: StaffCategory | None = None
    joining_date: date | None = None
    exit_date: date | None = None
    employment_status: EmploymentStatus | None = None
    base_city: str | None = Field(default=None, max_length=120)
    base_state: str | None = Field(default=None, max_length=120)
    id_proof_type: str | None = Field(default=None, max_length=48)
    id_proof_number: str | None = Field(default=None, max_length=64)
    bank_account_name: str | None = Field(default=None, max_length=120)
    bank_account_number: str | None = Field(default=None, max_length=48)
    bank_name: str | None = Field(default=None, max_length=120)
    bank_ifsc: str | None = Field(default=None, max_length=24)
    notes: str | None = None
    role_ids: list[uuid.UUID] | None = None
    login_enabled: bool | None = None
    is_active: bool | None = None

    @field_validator("email")
    @classmethod
    def validate_email_shape(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return StaffCreate.validate_email_shape(value)


class StaffOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    employee_code: str
    full_name: str
    email: str | None = None
    mobile: str | None = None
    gender: Gender
    staff_category: StaffCategory
    department: str | None = None
    designation: str | None = None
    employment_status: EmploymentStatus
    joining_date: date | None = None
    city: str | None = None
    state: str | None = None
    roles: list[str] = []
    login_enabled: bool = False
    is_active: bool = True
    # Online indicator — Image 1 requires green/red per staff member.
    is_online: bool = False
    status_label: str = "Offline"
    last_login_at: datetime | None = None
    last_activity_at: datetime | None = None
    last_logout_at: datetime | None = None
    # Workload
    open_cases: int = 0
    completed_cases: int = 0
    overdue_cases: int = 0


class StaffDetailOut(StaffOut):
    date_of_birth: date | None = None
    alternate_mobile: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    pin_code: str | None = None
    reporting_manager: str | None = None
    base_city: str | None = None
    base_state: str | None = None
    exit_date: date | None = None
    id_proof_type: str | None = None
    id_proof_number: str | None = None
    bank_account_name: str | None = None
    bank_account_number: str | None = None
    bank_name: str | None = None
    bank_ifsc: str | None = None
    notes: str | None = None
    must_change_password: bool = False
    last_login_ip: str | None = None
    role_ids: list[uuid.UUID] = []


class StaffPerformanceOut(BaseModel):
    staff_id: uuid.UUID
    full_name: str
    staff_category: StaffCategory
    is_online: bool
    assigned: int = 0
    in_progress: int = 0
    report_in_progress: int = 0
    completed: int = 0
    pending: int = 0
    overdue: int = 0
    positive: int = 0
    negative: int = 0
    suspicious: int = 0
    average_tat_days: float | None = None
    completion_rate: float = 0.0


class StaffStatusOut(BaseModel):
    """Compact row for the assignment dialog and the dashboard status strip."""

    id: uuid.UUID
    full_name: str
    staff_category: StaffCategory
    is_online: bool
    status_label: str
    last_activity_at: datetime | None = None
    open_cases: int = 0
    pending_cases: int = 0
    completed_cases: int = 0
    base_city: str | None = None
    base_state: str | None = None


# --------------------------------------------------------------------------- #
# HR masters
# --------------------------------------------------------------------------- #
class DepartmentIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    is_active: bool = True


class DepartmentOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_active: bool
    employee_count: int = 0


class DesignationIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    grade: str | None = Field(default=None, max_length=32)
    description: str | None = None
    is_active: bool = True


class DesignationOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    grade: str | None = None
    description: str | None = None
    is_active: bool
    employee_count: int = 0


class AttendanceIn(BaseModel):
    employee_id: uuid.UUID
    work_date: date
    status: AttendanceStatus = AttendanceStatus.PRESENT
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    remarks: str | None = None


class AttendanceOut(ORMModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    work_date: date
    status: AttendanceStatus
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    worked_hours: float | None = None
    remarks: str | None = None
    derived_from_login: bool = False


class LeaveIn(BaseModel):
    employee_id: uuid.UUID
    leave_type: LeaveType
    from_date: date
    to_date: date
    days: float = Field(default=1, gt=0, le=365)
    reason: str | None = None


class LeaveDecision(BaseModel):
    status: LeaveStatus
    decision_remark: str | None = None


class LeaveOut(ORMModel):
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str | None = None
    leave_type: LeaveType
    from_date: date
    to_date: date
    days: float
    reason: str | None = None
    status: LeaveStatus
    approved_by: str | None = None
    approved_at: datetime | None = None
    decision_remark: str | None = None
    created_at: datetime
