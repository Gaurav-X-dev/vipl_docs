"""HR module: departments, designations, employees, attendance and leave."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    AttendanceStatus,
    EmploymentStatus,
    Gender,
    LeaveStatus,
    LeaveType,
    StaffCategory,
)

if TYPE_CHECKING:
    from app.models.user import User


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    employees: Mapped[list[Employee]] = relationship(back_populates="department", lazy="noload")


class Designation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "designations"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    grade: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    employees: Mapped[list[Employee]] = relationship(back_populates="designation", lazy="noload")


class Employee(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """HR record. Optionally linked one-to-one with a login :class:`User`."""

    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("employee_code", name="uq_employees_employee_code"),
        Index("ix_employees_department_designation", "department_id", "designation_id"),
    )

    employee_code: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    gender: Mapped[Gender] = mapped_column(
        Enum(Gender, native_enum=False, length=16),
        nullable=False,
        default=Gender.UNDISCLOSED,
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    mobile: Mapped[str | None] = mapped_column(String(24), nullable=True)
    alternate_mobile: Mapped[str | None] = mapped_column(String(24), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(12), nullable=True)

    department_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    designation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("designations.id", ondelete="SET NULL"), nullable=True
    )
    reporting_manager_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    staff_category: Mapped[StaffCategory] = mapped_column(
        Enum(StaffCategory, native_enum=False, length=24),
        nullable=False,
        default=StaffCategory.BACK_OFFICE,
    )
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    employment_status: Mapped[EmploymentStatus] = mapped_column(
        Enum(EmploymentStatus, native_enum=False, length=24),
        nullable=False,
        default=EmploymentStatus.ACTIVE,
    )

    #: Base location — used when assigning field work by geography.
    base_city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    base_state: Mapped[str | None] = mapped_column(String(120), nullable=True)

    profile_photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    id_proof_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    id_proof_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    id_proof_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    bank_account_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(48), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(24), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="employee", lazy="joined")
    department: Mapped[Department | None] = relationship(back_populates="employees", lazy="joined")
    designation: Mapped[Designation | None] = relationship(
        back_populates="employees", lazy="joined"
    )
    reporting_manager: Mapped[Employee | None] = relationship(
        remote_side="Employee.id", lazy="noload"
    )

    @property
    def full_name(self) -> str:
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(part for part in parts if part)


class Attendance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_attendance_employee_date"),
        Index("ix_attendance_work_date", "work_date"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, length=24),
        nullable=False,
        default=AttendanceStatus.PRESENT,
    )
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worked_hours: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: True when the row was derived from the login/heartbeat trail.
    derived_from_login: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: True when the row was rolled up from clock in / clock out sessions.
    derived_from_clock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    employee: Mapped[Employee] = relationship(lazy="joined")


class AttendanceSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One clock-in / clock-out pair.

    Attendance is deliberately *not* inferred from login. A user may be signed
    in without being on shift, and on shift without the browser open, so this
    table is the only source of working hours. The daily :class:`Attendance`
    row is rolled up from these sessions.
    """

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        Index("ix_attendance_sessions_user_date", "user_id", "work_date"),
        Index("ix_attendance_sessions_open", "user_id", "is_open"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)

    clock_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Stored on clock-out so reports never have to recompute across timezones.
    worked_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Exactly one open session per user is permitted; enforced in the service.
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    #: Set when a shift left open overnight was closed by the system.
    auto_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    clock_in_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clock_out_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    clock_in_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    clock_out_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(lazy="joined")
    employee: Mapped[Employee | None] = relationship(lazy="noload")


class LeaveRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leave_records"
    __table_args__ = (Index("ix_leave_records_employee_from", "employee_id", "from_date"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, native_enum=False, length=24), nullable=False
    )
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[float] = mapped_column(Numeric(4, 1), nullable=False, default=1)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus, native_enum=False, length=16),
        nullable=False,
        default=LeaveStatus.PENDING,
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    employee: Mapped[Employee] = relationship(lazy="joined")
