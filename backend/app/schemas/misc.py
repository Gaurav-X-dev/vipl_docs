"""Company, import, document, dashboard, audit and settings payloads."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    AuditAction,
    CaseCategory,
    CompanyType,
    DocumentTemplateStatus,
    GeneratedFormat,
    ImportBatchStatus,
    ImportRowStatus,
    NotificationType,
)
from app.schemas.common import ORMModel, UserBrief


# --------------------------------------------------------------------------- #
# Companies and case types
# --------------------------------------------------------------------------- #
class CompanyIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=200)
    short_name: str = Field(min_length=1, max_length=64)
    company_type: CompanyType = CompanyType.INSURANCE
    import_aliases: str | None = None
    address: str | None = None
    city: str | None = Field(default=None, max_length=120)
    state: str | None = Field(default=None, max_length=120)
    pin_code: str | None = Field(default=None, max_length=12)
    contact_person: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    default_tat_days: int = Field(default=7, ge=1, le=365)
    is_active: bool = True
    notes: str | None = None


class CompanyOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    short_name: str
    company_type: CompanyType
    import_aliases: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pin_code: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    logo_path: str | None = None
    default_tat_days: int
    is_active: bool
    notes: str | None = None
    total_cases: int = 0
    open_cases: int = 0
    form_template_count: int = 0
    document_template_count: int = 0


class CaseTypeIn(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=120)
    category: CaseCategory
    description: str | None = None
    import_aliases: str | None = None
    default_tat_days: int = Field(default=7, ge=1, le=365)
    display_order: int = 100
    is_active: bool = True


class CaseTypeOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    category: CaseCategory
    description: str | None = None
    import_aliases: str | None = None
    default_tat_days: int
    display_order: int
    is_active: bool
    total_cases: int = 0


# --------------------------------------------------------------------------- #
# Import
# --------------------------------------------------------------------------- #
class ImportColumnMappingOut(ORMModel):
    id: uuid.UUID
    source_column: str
    source_aliases: str | None = None
    target_field: str
    data_type: str
    is_required: bool
    display_order: int
    transform: str | None = None
    notes: str | None = None


class ImportColumnMappingIn(BaseModel):
    source_column: str = Field(min_length=1, max_length=160)
    source_aliases: str | None = None
    target_field: str = Field(min_length=1, max_length=64)
    data_type: str = "text"
    is_required: bool = False
    display_order: int = 0
    transform: str | None = None
    notes: str | None = None


class ImportTemplateOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    company_id: uuid.UUID | None = None
    company_name: str | None = None
    header_row: int
    sheet_name: str | None = None
    duplicate_key_fields: list[str] | None = None
    fallback_duplicate_key_fields: list[str] | None = None
    is_default: bool
    is_active: bool
    mappings: list[ImportColumnMappingOut] = []


class ImportTemplateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    company_id: uuid.UUID | None = None
    header_row: int = Field(default=1, ge=1, le=50)
    sheet_name: str | None = None
    duplicate_key_fields: list[str] | None = None
    fallback_duplicate_key_fields: list[str] | None = None
    is_default: bool = False
    is_active: bool = True
    mappings: list[ImportColumnMappingIn] = Field(default_factory=list)


class ImportPreviewRow(BaseModel):
    row_number: int
    raw: dict[str, Any]
    parsed: dict[str, Any] = Field(default_factory=dict)
    status: ImportRowStatus
    errors: list[str] = []
    warnings: list[str] = []
    duplicate_of: str | None = None


class ImportSummary(BaseModel):
    total_rows: int = 0
    valid: int = 0
    warnings: int = 0
    errors: int = 0
    duplicates: int = 0
    imported: int = 0


class ImportBatchOut(ORMModel):
    id: uuid.UUID
    batch_number: str
    original_filename: str
    status: ImportBatchStatus
    template_code: str | None = None
    company_name: str | None = None
    uploaded_by: UserBrief | None = None
    size_bytes: int
    checksum_sha256: str
    detected_headers: list[str] | None = None
    total_rows: int
    valid_rows: int
    warning_rows: int
    error_rows: int
    duplicate_rows: int
    imported_rows: int
    validated_at: datetime | None = None
    committed_at: datetime | None = None
    rolled_back_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class ImportPreviewOut(BaseModel):
    batch: ImportBatchOut
    summary: ImportSummary
    headers: list[str]
    #: header -> internal field (or ``None`` when the column is ignored)
    mapping: dict[str, str | None]
    unmapped_headers: list[str] = []
    missing_required: list[str] = []
    rows: list[ImportPreviewRow] = []


class ImportCommitRequest(BaseModel):
    #: Header -> internal field overrides chosen on the mapping screen.
    mapping_overrides: dict[str, str | None] | None = None
    skip_duplicates: bool = True
    auto_assign: bool = True
    #: Off by default. The client's Status column records *their* progress, so
    #: honouring it would create cases that arrive already closed. Turn this on
    #: only when loading historic records you do not intend to work.
    apply_file_status: bool = False
    default_priority: str | None = None


class ImportCommitOut(BaseModel):
    batch: ImportBatchOut
    summary: ImportSummary
    created_case_ids: list[uuid.UUID] = []
    message: str


# --------------------------------------------------------------------------- #
# Document templates
# --------------------------------------------------------------------------- #
class DocumentTemplateOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    company_id: uuid.UUID
    company_name: str | None = None
    case_type_id: uuid.UUID
    case_type_name: str | None = None
    version: int
    status: DocumentTemplateStatus
    original_filename: str
    has_tagged_copy: bool = False
    can_generate_docx: bool = False
    size_bytes: int
    placeholder_count: int = 0
    notes: str | None = None
    created_at: datetime


class GeneratedDocumentOut(ORMModel):
    id: uuid.UUID
    display_name: str
    output_format: GeneratedFormat
    size_bytes: int
    template_name: str | None = None
    template_version: int | None = None
    used_client_template: bool = True
    generated_by: UserBrief | None = None
    generated_at: datetime
    download_url: str | None = None


class GenerateDocumentRequest(BaseModel):
    output_format: GeneratedFormat = GeneratedFormat.DOCX
    #: Regenerate even when a document already exists for this template version.
    force: bool = False


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class DashboardSummary(BaseModel):
    """Every tile on Image 1 and Image 2, computed in the database."""

    server_time: datetime
    timezone: str

    total_assignment: int = 0
    total_cases: int = 0
    new_cases: int = 0
    imported_today: int = 0
    unassigned: int = 0
    assigned: int = 0
    wip_cases: int = 0
    rip_cases: int = 0
    pending: int = 0
    completed: int = 0
    rejected: int = 0
    overdue: int = 0

    investigation_cases: int = 0
    death_claim_cases: int = 0

    positive_cases: int = 0
    negative_cases: int = 0
    suspicious_cases: int = 0
    positive_percent: float = 0.0
    negative_percent: float = 0.0
    suspicious_percent: float = 0.0

    in_tat: int = 0
    out_of_tat: int = 0
    tat_about_to_breach: int = 0
    average_tat_days: float | None = None

    total_staff: int = 0
    active_investigators: int = 0
    inactive_investigators: int = 0
    active_back_office: int = 0
    inactive_back_office: int = 0


class TrendPoint(BaseModel):
    bucket: str
    label: str
    total: int = 0
    completed: int = 0
    positive: int = 0
    negative: int = 0
    suspicious: int = 0


class DistributionItem(BaseModel):
    key: str
    label: str
    value: int
    percent: float = 0.0
    color_token: str | None = None


class CompanyPerformanceRow(BaseModel):
    company_id: uuid.UUID
    company_code: str
    company_name: str
    total: int = 0
    unassigned: int = 0
    wip: int = 0
    rip: int = 0
    completed: int = 0
    overdue: int = 0
    positive: int = 0
    negative: int = 0
    suspicious: int = 0
    average_tat_days: float | None = None


class RecentCaseRow(BaseModel):
    id: uuid.UUID
    case_number: str
    company_name: str
    case_type_name: str
    life_assured_name: str
    status: str
    status_label: str
    assigned_to: str | None = None
    received_at: datetime
    due_at: datetime | None = None
    tat_state: str


# --------------------------------------------------------------------------- #
# Audit and notifications
# --------------------------------------------------------------------------- #
class AuditLogOut(ORMModel):
    id: uuid.UUID
    actor_label: str | None = None
    action: AuditAction
    module: str
    entity_type: str | None = None
    entity_id: str | None = None
    entity_label: str | None = None
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    remarks: str | None = None
    ip_address: str | None = None
    request_method: str | None = None
    request_path: str | None = None
    created_at: datetime


class NotificationOut(ORMModel):
    id: uuid.UUID
    notification_type: NotificationType
    title: str
    body: str | None = None
    link: str | None = None
    is_read: bool
    created_at: datetime


class NotificationCount(BaseModel):
    unread: int = 0
    total: int = 0


# --------------------------------------------------------------------------- #
# Settings and roles
# --------------------------------------------------------------------------- #
class SettingOut(ORMModel):
    id: uuid.UUID
    key: str
    value: str | None = None
    value_type: str
    group: str
    label: str
    description: str | None = None
    is_editable: bool


class SettingUpdate(BaseModel):
    values: dict[str, Any]


class PermissionOut(ORMModel):
    id: uuid.UUID
    code: str
    module: str
    description: str


class RoleOut(ORMModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    is_system: bool
    is_active: bool
    user_count: int = 0
    permissions: list[str] = []


class RoleIn(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=96)
    description: str = ""
    is_active: bool = True
    permission_codes: list[str] = Field(default_factory=list)


class RolePermissionUpdate(BaseModel):
    permission_codes: list[str]


# --------------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------------- #
class ReportFilters(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    company_id: uuid.UUID | None = None
    case_type_id: uuid.UUID | None = None
    category: CaseCategory | None = None
    status: str | None = None
    outcome: str | None = None
    investigator_id: uuid.UUID | None = None


class ImportReportRow(BaseModel):
    batch_number: str
    filename: str
    uploaded_by: str | None = None
    created_at: datetime
    total_rows: int
    imported_rows: int
    error_rows: int
    duplicate_rows: int
    status: str
