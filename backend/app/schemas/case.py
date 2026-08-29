"""Case, assignment, note, evidence and workflow payloads."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    CaseCategory,
    CaseFormStatus,
    CaseOutcome,
    CasePriority,
    CaseStatus,
    DocumentCategory,
    ReportStatus,
    TatState,
    VisitStatus,
)
from app.schemas.common import ORMModel, UserBrief


class CaseListItem(BaseModel):
    """One row of the case table. Deliberately compact — lists can be huge."""

    id: uuid.UUID
    case_number: str
    category: CaseCategory
    company_code: str
    company_name: str
    case_type_code: str
    case_type_name: str
    krn_no: str | None = None
    policy_number: str | None = None
    application_number: str | None = None
    life_assured_name: str
    city: str | None = None
    state: str | None = None
    status: CaseStatus
    status_label: str
    outcome: CaseOutcome | None = None
    report_status: ReportStatus | None = None
    priority: CasePriority
    assigned_to: UserBrief | None = None
    #: Stage B owner. Shown alongside the investigator, never instead of them.
    office_staff: UserBrief | None = None
    visit_status: VisitStatus = VisitStatus.NOT_STARTED
    visit_status_label: str = "Not Started"
    received_at: datetime
    due_at: datetime | None = None
    completed_at: datetime | None = None
    aging_days: int | None = None
    tat_state: TatState = TatState.NOT_APPLICABLE
    tat_days_remaining: int | None = None
    is_imported: bool = False


class CaseCreate(BaseModel):
    company_id: uuid.UUID
    case_type_id: uuid.UUID
    life_assured_name: str = Field(min_length=2, max_length=200)
    krn_no: str | None = Field(default=None, max_length=64)
    policy_number: str | None = Field(default=None, max_length=64)
    application_number: str | None = Field(default=None, max_length=64)
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    pin_code: str | None = Field(default=None, max_length=12)
    contact_number: str | None = Field(default=None, max_length=32)
    alternate_contact: str | None = Field(default=None, max_length=32)
    email_id: str | None = Field(default=None, max_length=255)
    product_name: str | None = Field(default=None, max_length=160)
    sum_assured: Decimal | None = None
    premium_amount: Decimal | None = None
    risk_commencement_date: date | None = None
    nominee_name: str | None = Field(default=None, max_length=200)
    nominee_relation: str | None = Field(default=None, max_length=96)
    received_at: datetime | None = None
    due_at: datetime | None = None
    priority: CasePriority = CasePriority.NORMAL
    external_reference: str | None = Field(default=None, max_length=96)
    import_remark: str | None = None
    assigned_to_id: uuid.UUID | None = None

    @field_validator("life_assured_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return value.strip()


class CaseUpdate(BaseModel):
    life_assured_name: str | None = Field(default=None, min_length=2, max_length=200)
    krn_no: str | None = Field(default=None, max_length=64)
    policy_number: str | None = Field(default=None, max_length=64)
    application_number: str | None = Field(default=None, max_length=64)
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    pin_code: str | None = Field(default=None, max_length=12)
    contact_number: str | None = Field(default=None, max_length=32)
    alternate_contact: str | None = Field(default=None, max_length=32)
    email_id: str | None = Field(default=None, max_length=255)
    product_name: str | None = Field(default=None, max_length=160)
    sum_assured: Decimal | None = None
    premium_amount: Decimal | None = None
    risk_commencement_date: date | None = None
    nominee_name: str | None = Field(default=None, max_length=200)
    nominee_relation: str | None = Field(default=None, max_length=96)
    priority: CasePriority | None = None
    due_at: datetime | None = None
    report_date: date | None = None
    external_reference: str | None = Field(default=None, max_length=96)


class DeathClaimDetailIn(BaseModel):
    claimant_name: str | None = Field(default=None, max_length=200)
    claimant_relation: str | None = Field(default=None, max_length=96)
    claimant_age: str | None = Field(default=None, max_length=32)
    claimant_occupation: str | None = Field(default=None, max_length=160)
    claimant_income: str | None = Field(default=None, max_length=96)
    claimant_address: str | None = None
    claimant_contact: str | None = Field(default=None, max_length=32)
    date_of_death: date | None = None
    place_of_death: str | None = Field(default=None, max_length=255)
    cause_of_death: str | None = Field(default=None, max_length=255)
    type_of_death: str | None = Field(default=None, max_length=64)
    la_date_of_birth: date | None = None
    la_age: str | None = Field(default=None, max_length=32)
    la_occupation: str | None = Field(default=None, max_length=160)
    la_annual_income: str | None = Field(default=None, max_length=96)
    la_qualification: str | None = Field(default=None, max_length=120)
    la_marital_status: str | None = Field(default=None, max_length=48)
    standard_of_living: str | None = Field(default=None, max_length=64)
    death_certificate_verified: bool | None = None
    death_certificate_remarks: str | None = None
    rti_applied: bool | None = None
    rti_status: str | None = Field(default=None, max_length=120)
    profile_mismatch: str | None = Field(default=None, max_length=24)
    medical_non_disclosure: str | None = Field(default=None, max_length=24)
    death_before_issuance: str | None = Field(default=None, max_length=24)
    impersonation: str | None = Field(default=None, max_length=24)
    forged_documents: str | None = Field(default=None, max_length=24)
    nexus_involvement: str | None = Field(default=None, max_length=24)
    industry_shopping: str | None = Field(default=None, max_length=24)
    other_adverse_findings: str | None = Field(default=None, max_length=24)
    no_adverse_findings: str | None = Field(default=None, max_length=24)


class DeathClaimDetailOut(DeathClaimDetailIn, ORMModel):
    id: uuid.UUID


class ImportedFieldOut(BaseModel):
    """One bank-supplied value with its provenance, for the Imported Data tab."""

    field: str
    label: str
    value: str | None = None
    original_value: str | None = None
    source: str = "BANK_SUPPLIED"
    original_column: str | None = None
    imported_at: datetime | None = None
    was_edited: bool = False


class CaseDetailOut(BaseModel):
    id: uuid.UUID
    case_number: str
    category: CaseCategory
    company_id: uuid.UUID
    company_code: str
    company_name: str
    case_type_id: uuid.UUID
    case_type_code: str
    case_type_name: str

    krn_no: str | None = None
    policy_number: str | None = None
    application_number: str | None = None
    life_assured_name: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pin_code: str | None = None
    contact_number: str | None = None
    alternate_contact: str | None = None
    email_id: str | None = None
    product_name: str | None = None
    sum_assured: Decimal | None = None
    premium_amount: Decimal | None = None
    risk_commencement_date: date | None = None
    nominee_name: str | None = None
    nominee_relation: str | None = None
    received_month: str | None = None
    import_remark: str | None = None
    report_prepared_by: str | None = None
    external_reference: str | None = None

    status: CaseStatus
    status_label: str
    allowed_transitions: list[str] = []
    outcome: CaseOutcome | None = None
    report_status: ReportStatus | None = None
    outcome_reason: str | None = None
    priority: CasePriority

    assigned_to: UserBrief | None = None
    assigned_by: UserBrief | None = None
    reviewed_by: UserBrief | None = None
    created_by: UserBrief | None = None
    office_staff: UserBrief | None = None
    office_assigned_by: UserBrief | None = None

    visit_status: VisitStatus = VisitStatus.NOT_STARTED
    visit_status_label: str = "Not Started"
    visit_scheduled_at: datetime | None = None
    visit_started_at: datetime | None = None
    visited_at: datetime | None = None
    visit_remarks: str | None = None

    received_at: datetime
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    field_submitted_at: datetime | None = None
    office_assigned_at: datetime | None = None
    office_started_at: datetime | None = None
    verified_at: datetime | None = None
    completed_at: datetime | None = None
    due_at: datetime | None = None
    report_date: date | None = None
    completion_date: date | None = None

    aging_days: int | None = None
    tat_state: TatState = TatState.NOT_APPLICABLE
    tat_days_remaining: int | None = None
    tat_days_taken: int | None = None

    is_imported: bool = False
    import_batch_id: uuid.UUID | None = None
    imported_fields: list[ImportedFieldOut] = []

    death_claim: DeathClaimDetailOut | None = None
    form_status: CaseFormStatus | None = None
    form_completion_percent: int = 0
    document_count: int = 0
    generated_document_count: int = 0
    note_count: int = 0

    created_at: datetime
    updated_at: datetime


class AssignRequest(BaseModel):
    assigned_to_id: uuid.UUID
    due_at: datetime | None = None
    priority: CasePriority | None = None
    notes: str | None = None


class BulkAssignRequest(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    assigned_to_id: uuid.UUID
    due_at: datetime | None = None
    priority: CasePriority | None = None
    notes: str | None = None


class StatusChangeRequest(BaseModel):
    status: CaseStatus
    comment: str | None = None
    outcome: CaseOutcome | None = None
    report_status: ReportStatus | None = None
    outcome_reason: str | None = None


class ReviewRequest(BaseModel):
    approve: bool
    comment: str | None = None
    outcome: CaseOutcome | None = None
    report_status: ReportStatus | None = None


class BulkStatusRequest(BaseModel):
    case_ids: list[uuid.UUID] = Field(min_length=1, max_length=500)
    status: CaseStatus
    comment: str | None = None


class CaseNoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=8000)
    is_internal: bool = False


class CaseNoteOut(ORMModel):
    id: uuid.UUID
    body: str
    is_internal: bool
    author: UserBrief | None = None
    created_at: datetime


class CaseDocumentOut(ORMModel):
    id: uuid.UUID
    display_name: str
    category: DocumentCategory
    content_type: str
    size_bytes: int
    description: str | None = None
    geo_latitude: float | None = None
    geo_longitude: float | None = None
    captured_at: datetime | None = None
    version: int = 1
    uploaded_by: UserBrief | None = None
    created_at: datetime
    download_url: str | None = None


class AssignmentOut(ORMModel):
    id: uuid.UUID
    assigned_to: UserBrief | None = None
    assigned_by: UserBrief | None = None
    is_reassignment: bool
    due_at: datetime | None = None
    priority: CasePriority
    notes: str | None = None
    created_at: datetime


class StatusHistoryOut(ORMModel):
    id: uuid.UUID
    previous_status: CaseStatus | None = None
    new_status: CaseStatus
    changed_by: UserBrief | None = None
    comment: str | None = None
    created_at: datetime


class TimelineEventOut(ORMModel):
    id: uuid.UUID
    event_type: str
    summary: str
    detail: str | None = None
    icon: str | None = None
    actor_label: str | None = None
    occurred_at: datetime


class CaseFilters(BaseModel):
    """Every filter the case list and the exports understand."""

    search: str | None = None
    category: CaseCategory | None = None
    company_id: uuid.UUID | None = None
    case_type_id: uuid.UUID | None = None
    status: list[CaseStatus] | None = None
    outcome: list[CaseOutcome] | None = None
    priority: CasePriority | None = None
    assigned_to_id: uuid.UUID | None = None
    office_staff_id: uuid.UUID | None = None
    unassigned: bool | None = None
    #: True lists cases awaiting an office owner, whoever ran the field work.
    awaiting_office: bool | None = None
    #: Everything on the caller's own desk, either stage.
    my_desk: bool | None = None
    #: Closed cases past the retention window are hidden by default. They are
    #: never deleted — this brings them back into view.
    include_archived: bool = False
    tat_state: TatState | None = None
    received_from: date | None = None
    received_to: date | None = None
    completed_from: date | None = None
    completed_to: date | None = None
    city: str | None = None
    state: str | None = None
    import_batch_id: uuid.UUID | None = None
