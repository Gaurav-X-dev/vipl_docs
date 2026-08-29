"""The core case entity plus assignment, status history, notes and evidence."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
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
from app.models.company import CaseType, Company
from app.models.enums import (
    AssignmentStage,
    AssignmentState,
    CaseCategory,
    CaseOutcome,
    CasePriority,
    CaseStatus,
    DocumentCategory,
    ReportStatus,
    VisitStatus,
)

if TYPE_CHECKING:
    from app.models.form import CaseForm
    from app.models.user import User


class Case(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One assignment received from a bank or insurer.

    Column groups:

    * *bank supplied* — arrives in the daily Excel (Image 3) and is shown on the
      Imported Data tab with a "Bank/Client supplied" badge;
    * *system generated* — case number, TAT timestamps;
    * everything else is entered by staff.
    """

    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("case_number", name="uq_cases_case_number"),
        Index("ix_cases_company_status", "company_id", "status"),
        Index("ix_cases_category_status", "category", "status"),
        Index("ix_cases_assigned_status", "assigned_to_id", "status"),
        Index("ix_cases_office_status", "office_staff_id", "status"),
        Index("ix_cases_company_category", "company_id", "category", "status"),
        Index("ix_cases_received_at", "received_at"),
        Index("ix_cases_due_at", "due_at"),
        Index("ix_cases_company_krn", "company_id", "krn_no"),
        Index("ix_cases_policy_number", "policy_number"),
        Index("ix_cases_application_number", "application_number"),
        Index("ix_cases_life_assured_name", "life_assured_name"),
    )

    # --- identity ---------------------------------------------------------
    case_number: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[CaseCategory] = mapped_column(
        Enum(CaseCategory, native_enum=False, length=24), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    case_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("case_types.id", ondelete="RESTRICT"), nullable=False
    )

    # --- bank supplied (Image 3 columns) ----------------------------------
    krn_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    application_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    life_assured_name: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    received_month: Mapped[str | None] = mapped_column(String(24), nullable=True)
    import_remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_prepared_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(96), nullable=True)

    # --- commonly used case header data -----------------------------------
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    alternate_contact: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sum_assured: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    premium_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    risk_commencement_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    nominee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    nominee_relation: Mapped[str | None] = mapped_column(String(96), nullable=True)

    # --- workflow ---------------------------------------------------------
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, native_enum=False, length=32),
        nullable=False,
        default=CaseStatus.IMPORTED,
    )
    outcome: Mapped[CaseOutcome | None] = mapped_column(
        Enum(CaseOutcome, native_enum=False, length=24), nullable=True
    )
    report_status: Mapped[ReportStatus | None] = mapped_column(
        Enum(ReportStatus, native_enum=False, length=16), nullable=True
    )
    priority: Mapped[CasePriority] = mapped_column(
        Enum(CasePriority, native_enum=False, length=16),
        nullable=False,
        default=CasePriority.NORMAL,
    )
    outcome_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Stage B owner. Set once the investigator's report reaches the office and
    #: kept alongside ``assigned_to_id`` — the field assignment is never lost.
    office_staff_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    office_assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # --- field visit ------------------------------------------------------
    visit_status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus, native_enum=False, length=32),
        nullable=False,
        default=VisitStatus.NOT_STARTED,
    )
    visit_scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    visit_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    visit_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- TAT timeline (system generated) ----------------------------------
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: When the field investigator handed the case to the office (stage A end).
    field_submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    office_assigned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    office_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Ageing as supplied in the Excel; the live value is computed from dates.
    imported_aging_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- provenance -------------------------------------------------------
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("import_batches.id", ondelete="SET NULL"), nullable=True
    )
    is_imported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- relationships ----------------------------------------------------
    company: Mapped[Company] = relationship(lazy="joined")
    case_type: Mapped[CaseType] = relationship(lazy="joined")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    assigned_by: Mapped[User | None] = relationship(foreign_keys=[assigned_by_id], lazy="noload")
    reviewed_by: Mapped[User | None] = relationship(foreign_keys=[reviewed_by_id], lazy="noload")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="noload")
    office_staff: Mapped[User | None] = relationship(foreign_keys=[office_staff_id], lazy="joined")
    office_assigned_by: Mapped[User | None] = relationship(
        foreign_keys=[office_assigned_by_id], lazy="noload"
    )

    death_claim: Mapped[DeathClaimDetail | None] = relationship(
        back_populates="case",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    forms: Mapped[list[CaseForm]] = relationship(
        back_populates="case", cascade="all, delete-orphan", lazy="noload"
    )
    assignments: Mapped[list[CaseAssignment]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="CaseAssignment.created_at.desc()",
    )
    status_history: Mapped[list[CaseStatusHistory]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="CaseStatusHistory.created_at.desc()",
    )
    notes: Mapped[list[CaseNote]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="CaseNote.created_at.desc()",
    )
    documents: Mapped[list[CaseDocument]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="CaseDocument.created_at.desc()",
    )


class DeathClaimDetail(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Structured death-claim header, used by dashboards and client documents.

    Field names follow the Bajaj / HDFC / ICICI / SUD claim forms.
    """

    __tablename__ = "death_claim_details"

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    claimant_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    claimant_relation: Mapped[str | None] = mapped_column(String(96), nullable=True)
    claimant_age: Mapped[str | None] = mapped_column(String(32), nullable=True)
    claimant_occupation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    claimant_income: Mapped[str | None] = mapped_column(String(96), nullable=True)
    claimant_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimant_contact: Mapped[str | None] = mapped_column(String(32), nullable=True)

    date_of_death: Mapped[date | None] = mapped_column(Date, nullable=True)
    place_of_death: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cause_of_death: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type_of_death: Mapped[str | None] = mapped_column(String(64), nullable=True)
    la_date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    la_age: Mapped[str | None] = mapped_column(String(32), nullable=True)
    la_occupation: Mapped[str | None] = mapped_column(String(160), nullable=True)
    la_annual_income: Mapped[str | None] = mapped_column(String(96), nullable=True)
    la_qualification: Mapped[str | None] = mapped_column(String(120), nullable=True)
    la_marital_status: Mapped[str | None] = mapped_column(String(48), nullable=True)
    standard_of_living: Mapped[str | None] = mapped_column(String(64), nullable=True)

    death_certificate_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    death_certificate_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    rti_applied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    rti_status: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # "Key sensing of the case" checklist, straight from the ICICI claim form.
    profile_mismatch: Mapped[str | None] = mapped_column(String(24), nullable=True)
    medical_non_disclosure: Mapped[str | None] = mapped_column(String(24), nullable=True)
    death_before_issuance: Mapped[str | None] = mapped_column(String(24), nullable=True)
    impersonation: Mapped[str | None] = mapped_column(String(24), nullable=True)
    forged_documents: Mapped[str | None] = mapped_column(String(24), nullable=True)
    nexus_involvement: Mapped[str | None] = mapped_column(String(24), nullable=True)
    industry_shopping: Mapped[str | None] = mapped_column(String(24), nullable=True)
    other_adverse_findings: Mapped[str | None] = mapped_column(String(24), nullable=True)
    no_adverse_findings: Mapped[str | None] = mapped_column(String(24), nullable=True)

    case: Mapped[Case] = relationship(back_populates="death_claim", lazy="noload")


class CaseAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Full assignment history — never overwritten, only appended."""

    __tablename__ = "case_assignments"
    __table_args__ = (
        Index("ix_case_assignments_case_created", "case_id", "created_at"),
        Index("ix_case_assignments_case_stage", "case_id", "stage", "state"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Which half of the workflow this assignment belongs to.
    stage: Mapped[AssignmentStage] = mapped_column(
        Enum(AssignmentStage, native_enum=False, length=32),
        nullable=False,
        default=AssignmentStage.FIELD_INVESTIGATION,
    )
    state: Mapped[AssignmentState] = mapped_column(
        Enum(AssignmentState, native_enum=False, length=16),
        nullable=False,
        default=AssignmentState.ACTIVE,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_reassignment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[CasePriority] = mapped_column(
        Enum(CasePriority, native_enum=False, length=16),
        nullable=False,
        default=CasePriority.NORMAL,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case: Mapped[Case] = relationship(back_populates="assignments", lazy="noload")
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    assigned_by: Mapped[User | None] = relationship(foreign_keys=[assigned_by_id], lazy="joined")


class CaseStatusHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_status_history"
    __table_args__ = (Index("ix_case_status_history_case_created", "case_id", "created_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    previous_status: Mapped[CaseStatus | None] = mapped_column(
        Enum(CaseStatus, native_enum=False, length=32), nullable=True
    )
    new_status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, native_enum=False, length=32), nullable=False
    )
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    case: Mapped[Case] = relationship(back_populates="status_history", lazy="noload")
    changed_by: Mapped[User | None] = relationship(lazy="joined")


class CaseNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "case_notes"
    __table_args__ = (Index("ix_case_notes_case_created", "case_id", "created_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    #: Internal notes are hidden from the investigator-facing timeline.
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    case: Mapped[Case] = relationship(back_populates="notes", lazy="noload")
    author: Mapped[User | None] = relationship(lazy="joined")


class CaseDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Evidence uploaded against a case."""

    __tablename__ = "case_documents"
    __table_args__ = (Index("ix_case_documents_case_category", "case_id", "category"),)

    case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[DocumentCategory] = mapped_column(
        Enum(DocumentCategory, native_enum=False, length=32),
        nullable=False,
        default=DocumentCategory.OTHER,
    )
    #: Name shown in the UI — the browser-supplied name, sanitised.
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Name on disk — generated, never taken from the browser.
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Geo tagging is mandatory on several client forms.
    geo_latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    geo_longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    case: Mapped[Case] = relationship(back_populates="documents", lazy="noload")
    uploaded_by: Mapped[User | None] = relationship(lazy="joined")


class CaseNumberSequence(Base):
    """Concurrency-safe per-year, per-prefix counter for case numbers."""

    __tablename__ = "case_number_sequences"

    prefix: Mapped[str] = mapped_column(String(16), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
