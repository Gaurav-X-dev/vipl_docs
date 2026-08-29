export type Dict = Record<string, unknown>;

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone?: string;
  staff_category: string;
  is_super_admin: boolean;
  must_change_password?: boolean;
  permissions: string[];
  roles: { id: string; code: string; name: string }[];
  employee_code?: string;
  department?: string;
  designation?: string;
  last_login_at?: string;
}

export interface Page<T> {
  items: T[];
  meta: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  };
}

export interface UserBrief {
  id: string;
  full_name: string;
  email: string;
  staff_category?: string;
  is_online: boolean;
  last_activity_at?: string;
}

/* -------------------------------------------------------------- Cases */
export interface CaseItem {
  id: string;
  case_number: string;
  category: string;
  company_code: string;
  company_name: string;
  case_type_code: string;
  case_type_name: string;
  life_assured_name: string;
  policy_number?: string;
  application_number?: string;
  krn_no?: string;
  city?: string;
  state?: string;
  status: string;
  status_label: string;
  priority: string;
  assigned_to?: UserBrief;
  received_at: string;
  due_at?: string;
  completed_at?: string;
  aging_days: number;
  tat_state: string;
  tat_days_remaining?: number;
  outcome?: string;
  report_status?: string;
  is_imported: boolean;
  office_staff?: UserBrief;
  visit_status?: string;
  visit_status_label?: string;
}

export interface ImportedField {
  field: string;
  label: string;
  value?: string;
  original_value?: string;
  source: string;
  original_column?: string;
  imported_at?: string;
  was_edited: boolean;
}

export interface CaseDetail extends CaseItem {
  company_id: string;
  case_type_id: string;
  address?: string;
  pin_code?: string;
  contact_number?: string;
  alternate_contact?: string;
  email_id?: string;
  product_name?: string;
  sum_assured?: string;
  premium_amount?: string;
  risk_commencement_date?: string;
  nominee_name?: string;
  nominee_relation?: string;
  import_remark?: string;
  report_prepared_by?: string;
  external_reference?: string;
  allowed_transitions: string[];
  outcome_reason?: string;
  assigned_by?: UserBrief;
  reviewed_by?: UserBrief;
  created_by?: UserBrief;
  assigned_at?: string;
  started_at?: string;
  submitted_at?: string;
  verified_at?: string;
  report_date?: string;
  completion_date?: string;
  tat_days_taken?: number;
  import_batch_id?: string;
  field_submitted_at?: string;
  office_assigned_at?: string;
  office_started_at?: string;
  visit_scheduled_at?: string;
  visit_started_at?: string;
  visited_at?: string;
  visit_remarks?: string;
  imported_fields: ImportedField[];
  death_claim?: Dict | null;
  form_status?: string;
  form_completion_percent: number;
  document_count: number;
  generated_document_count: number;
  note_count: number;
  created_at: string;
  updated_at: string;
}

export interface CaseNote {
  id: string;
  body: string;
  is_internal: boolean;
  author?: UserBrief;
  created_at: string;
}

export interface CaseDocument {
  id: string;
  display_name: string;
  category: string;
  content_type: string;
  size_bytes: number;
  description?: string;
  geo_latitude?: number;
  geo_longitude?: number;
  version: number;
  uploaded_by?: UserBrief;
  created_at: string;
  download_url?: string;
}

export interface GeneratedDocument {
  id: string;
  display_name: string;
  output_format: string;
  size_bytes: number;
  template_name?: string;
  template_version?: number;
  used_client_template: boolean;
  generated_by?: UserBrief;
  generated_at: string;
  download_url?: string;
}

export interface TimelineEvent {
  id: string;
  event_type: string;
  summary: string;
  detail?: string;
  icon?: string;
  actor_label?: string;
  occurred_at: string;
}

export interface AssignmentRow {
  id: string;
  assigned_to?: UserBrief;
  assigned_by?: UserBrief;
  is_reassignment: boolean;
  due_at?: string;
  priority: string;
  notes?: string;
  created_at: string;
}

export interface StatusHistoryRow {
  id: string;
  previous_status?: string;
  new_status: string;
  changed_by?: UserBrief;
  comment?: string;
  created_at: string;
}

/* --------------------------------------------------------- Form engine */
export interface FormFieldDef {
  id: string;
  field_key: string;
  label: string;
  field_type: string;
  is_required: boolean;
  display_order: number;
  col_span: number;
  options?: string[] | null;
  default_value?: string | null;
  placeholder?: string | null;
  help_text?: string | null;
  table_columns?: { key: string; label: string }[] | null;
  source: string;
  prefill_from?: string | null;
  document_mapping?: string | null;
  is_readonly: boolean;
  visible_when?: string | null;
}

export interface FormSectionDef {
  id: string;
  key: string;
  title: string;
  description?: string | null;
  display_order: number;
  is_repeatable: boolean;
  fields: FormFieldDef[];
}

export interface FormTemplateDetail {
  id: string;
  code: string;
  name: string;
  company_id: string;
  company_name?: string;
  case_type_id: string;
  case_type_name?: string;
  case_category?: string;
  version: number;
  is_active: boolean;
  description?: string;
  source_document?: string;
  section_count: number;
  field_count: number;
  created_at?: string;
  sections: FormSectionDef[];
}

export interface FieldValue {
  field_key: string;
  value?: string | null;
  value_json?: unknown;
  source: string;
  original_value?: string | null;
  original_column?: string | null;
  imported_at?: string | null;
  was_edited: boolean;
  updated_at?: string | null;
}

export interface CaseForm {
  id: string;
  case_id: string;
  template: FormTemplateDetail;
  status: string;
  completion_percent: number;
  submitted_at?: string;
  correction_remark?: string;
  values: Record<string, FieldValue>;
  can_edit: boolean;
  /** Why the form is read-only, when it is. */
  locked_reason?: string | null;
}

/* -------------------------------------------------------------- Staff */
export interface Staff {
  id: string;
  user_id?: string;
  employee_code: string;
  full_name: string;
  email?: string;
  mobile?: string;
  gender: string;
  staff_category: string;
  department?: string;
  designation?: string;
  employment_status: string;
  joining_date?: string;
  city?: string;
  state?: string;
  roles: string[];
  login_enabled: boolean;
  is_active: boolean;
  is_online: boolean;
  status_label: string;
  last_login_at?: string;
  last_activity_at?: string;
  last_logout_at?: string;
  open_cases: number;
  completed_cases: number;
  overdue_cases: number;
}

export interface StaffDetail extends Staff {
  date_of_birth?: string;
  alternate_mobile?: string;
  address_line1?: string;
  address_line2?: string;
  pin_code?: string;
  reporting_manager?: string;
  base_city?: string;
  base_state?: string;
  exit_date?: string;
  id_proof_type?: string;
  id_proof_number?: string;
  bank_account_name?: string;
  bank_account_number?: string;
  bank_name?: string;
  bank_ifsc?: string;
  notes?: string;
  must_change_password: boolean;
  last_login_ip?: string;
  role_ids: string[];
}

export interface StaffStatus {
  id: string;
  full_name: string;
  staff_category: string;
  is_online: boolean;
  status_label: string;
  last_activity_at?: string;
  open_cases: number;
  pending_cases: number;
  completed_cases: number;
  base_city?: string;
  base_state?: string;
}

export interface StaffPerformance {
  staff_id: string;
  full_name: string;
  staff_category: string;
  is_online: boolean;
  assigned: number;
  in_progress: number;
  report_in_progress: number;
  completed: number;
  pending: number;
  overdue: number;
  positive: number;
  negative: number;
  suspicious: number;
  average_tat_days?: number;
  completion_rate: number;
}

/* ----------------------------------------------------------------- HR */
export interface Department {
  id: string;
  code: string;
  name: string;
  description?: string;
  is_active: boolean;
  employee_count: number;
}

export interface Designation {
  id: string;
  code: string;
  name: string;
  grade?: string;
  description?: string;
  is_active: boolean;
  employee_count: number;
}

export interface AttendanceRow {
  id: string;
  employee_id: string;
  employee_name?: string;
  work_date: string;
  status: string;
  check_in_at?: string;
  check_out_at?: string;
  worked_hours?: number;
  remarks?: string;
  derived_from_login: boolean;
}

export interface LeaveRow {
  id: string;
  employee_id: string;
  employee_name?: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  days: number;
  reason?: string;
  status: string;
  approved_at?: string;
  decision_remark?: string;
  created_at: string;
}

/* ---------------------------------------------------- Companies etc. */
export interface Company {
  id: string;
  code: string;
  name: string;
  short_name: string;
  company_type: string;
  import_aliases?: string;
  address?: string;
  city?: string;
  state?: string;
  pin_code?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  default_tat_days: number;
  is_active: boolean;
  notes?: string;
  total_cases: number;
  open_cases: number;
  form_template_count: number;
  document_template_count: number;
}

export interface CaseType {
  id: string;
  code: string;
  name: string;
  category: string;
  description?: string;
  import_aliases?: string;
  default_tat_days: number;
  display_order: number;
  is_active: boolean;
  total_cases: number;
}

export interface FormTemplateSummary {
  id: string;
  code: string;
  name: string;
  company_id: string;
  company_name?: string;
  case_type_id: string;
  case_type_name?: string;
  case_category?: string;
  version: number;
  is_active: boolean;
  description?: string;
  source_document?: string;
  section_count: number;
  field_count: number;
  created_at?: string;
}

export interface DocumentTemplate {
  id: string;
  code: string;
  name: string;
  company_id: string;
  company_name?: string;
  case_type_id: string;
  case_type_name?: string;
  version: number;
  status: string;
  original_filename: string;
  has_tagged_copy: boolean;
  can_generate_docx: boolean;
  size_bytes: number;
  placeholder_count: number;
  notes?: string;
  created_at: string;
}

/* -------------------------------------------------------------- Import */
export interface ImportBatch {
  id: string;
  batch_number: string;
  original_filename: string;
  status: string;
  template_code?: string;
  company_name?: string;
  uploaded_by?: UserBrief;
  size_bytes: number;
  checksum_sha256: string;
  detected_headers?: string[];
  total_rows: number;
  valid_rows: number;
  warning_rows: number;
  error_rows: number;
  duplicate_rows: number;
  imported_rows: number;
  validated_at?: string;
  committed_at?: string;
  rolled_back_at?: string;
  error_message?: string;
  created_at: string;
}

export interface ImportPreviewRow {
  row_number: number;
  raw: Dict;
  parsed: Dict;
  status: string;
  errors: string[];
  warnings: string[];
  duplicate_of?: string;
}

export interface ImportPreview {
  batch: ImportBatch;
  summary: {
    total_rows: number;
    valid: number;
    warnings: number;
    errors: number;
    duplicates: number;
    imported: number;
  };
  headers: string[];
  mapping: Record<string, string | null>;
  unmapped_headers: string[];
  missing_required: string[];
  rows: ImportPreviewRow[];
}

export interface ImportTemplate {
  id: string;
  code: string;
  name: string;
  description?: string;
  company_id?: string;
  company_name?: string;
  header_row: number;
  sheet_name?: string;
  duplicate_key_fields?: string[];
  fallback_duplicate_key_fields?: string[];
  is_default: boolean;
  is_active: boolean;
  mappings: {
    id: string;
    source_column: string;
    source_aliases?: string;
    target_field: string;
    data_type: string;
    is_required: boolean;
    display_order: number;
    notes?: string;
  }[];
}

/* ------------------------------------------------- Dashboard & reports */
export interface DashboardSummary {
  server_time: string;
  timezone: string;
  total_assignment: number;
  total_cases: number;
  new_cases: number;
  imported_today: number;
  unassigned: number;
  assigned: number;
  wip_cases: number;
  rip_cases: number;
  pending: number;
  completed: number;
  rejected: number;
  overdue: number;
  investigation_cases: number;
  death_claim_cases: number;
  positive_cases: number;
  negative_cases: number;
  suspicious_cases: number;
  positive_percent: number;
  negative_percent: number;
  suspicious_percent: number;
  in_tat: number;
  out_of_tat: number;
  tat_about_to_breach: number;
  average_tat_days?: number;
  total_staff: number;
  active_investigators: number;
  inactive_investigators: number;
  active_back_office: number;
  inactive_back_office: number;
}

export interface DistributionItem {
  key: string;
  label: string;
  value: number;
  percent: number;
  color_token?: string;
}

export interface TrendPoint {
  bucket: string;
  label: string;
  total: number;
  completed: number;
  positive: number;
  negative: number;
  suspicious: number;
}

export interface CompanyPerformance {
  company_id: string;
  company_code: string;
  company_name: string;
  total: number;
  unassigned: number;
  wip: number;
  rip: number;
  completed: number;
  overdue: number;
  positive: number;
  negative: number;
  suspicious: number;
  average_tat_days?: number;
}

export interface RecentCase {
  id: string;
  case_number: string;
  company_name: string;
  case_type_name: string;
  life_assured_name: string;
  status: string;
  status_label: string;
  assigned_to?: string;
  received_at: string;
  due_at?: string;
  tat_state: string;
}

export interface ImportReportRow {
  batch_number: string;
  filename: string;
  uploaded_by?: string;
  created_at: string;
  total_rows: number;
  imported_rows: number;
  error_rows: number;
  duplicate_rows: number;
  status: string;
}

/* ------------------------------------------------------- Admin & audit */
export interface AuditLog {
  id: string;
  actor_label?: string;
  action: string;
  module: string;
  entity_type?: string;
  entity_id?: string;
  entity_label?: string;
  old_values?: Dict;
  new_values?: Dict;
  remarks?: string;
  ip_address?: string;
  request_method?: string;
  request_path?: string;
  created_at: string;
}

export interface Permission {
  id: string;
  code: string;
  module: string;
  description: string;
}

export interface Role {
  id: string;
  code: string;
  name: string;
  description: string;
  is_system: boolean;
  is_active: boolean;
  user_count: number;
  permissions: string[];
}

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  staff_category: string;
  is_active: boolean;
  login_enabled: boolean;
  is_super_admin: boolean;
  is_online: boolean;
  roles: string[];
  last_login_at?: string;
}

export interface AppSetting {
  id: string;
  key: string;
  value?: string;
  value_type: string;
  group: string;
  label: string;
  description?: string;
  is_editable: boolean;
}

export interface Notification {
  id: string;
  notification_type: string;
  title: string;
  body?: string;
  link?: string;
  is_read: boolean;
  created_at: string;
}

/* ------------------------------------------------------------- Options */
export const CASE_STATUSES = [
  "IMPORTED",
  "UNASSIGNED",
  "ASSIGNED",
  "ACCEPTED",
  "WIP",
  "FIELD_INVESTIGATION",
  "DOCUMENTS_PENDING",
  "RIP",
  "REPORT_SUBMITTED",
  "UNDER_REVIEW",
  "CORRECTION_REQUIRED",
  "VERIFIED",
  "COMPLETED",
  "REJECTED",
  "CANCELLED",
] as const;

export const STATUS_LABELS: Record<string, string> = {
  IMPORTED: "Imported",
  UNASSIGNED: "Unassigned",
  ASSIGNED: "Assigned",
  ACCEPTED: "Accepted",
  WIP: "Work in Progress (WIP)",
  FIELD_INVESTIGATION: "Field Investigation",
  DOCUMENTS_PENDING: "Documents Pending",
  RIP: "Report in Progress (RIP)",
  REPORT_SUBMITTED: "Submitted by Investigator",
  UNDER_REVIEW: "Under Review",
  CORRECTION_REQUIRED: "Correction Required",
  VERIFIED: "Verified",
  COMPLETED: "Completed",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
};

export const OUTCOMES = ["POSITIVE", "NEGATIVE", "SUSPICIOUS"] as const;
export const PRIORITIES = ["LOW", "NORMAL", "HIGH", "URGENT"] as const;
export const STAFF_CATEGORIES = ["FIELD", "BACK_OFFICE", "MANAGEMENT"] as const;
export const GENDERS = ["MALE", "FEMALE", "OTHER", "UNDISCLOSED"] as const;
export const EMPLOYMENT_STATUSES = [
  "ACTIVE",
  "PROBATION",
  "NOTICE_PERIOD",
  "RESIGNED",
  "TERMINATED",
  "ON_LEAVE",
] as const;
export const COMPANY_TYPES = [
  "BANK",
  "INSURANCE",
  "INVESTIGATION_CLIENT",
  "OTHER",
] as const;
export const DOCUMENT_CATEGORIES = [
  "KYC",
  "PHOTOGRAPH",
  "MEDICAL",
  "DEATH_CERTIFICATE",
  "FIR_PMR",
  "STATEMENT",
  "INCOME_PROOF",
  "AGE_PROOF",
  "REPORT",
  "OTHER",
] as const;
export const ATTENDANCE_STATUSES = [
  "PRESENT",
  "ABSENT",
  "HALF_DAY",
  "WEEK_OFF",
  "HOLIDAY",
  "ON_LEAVE",
  "FIELD_DUTY",
] as const;
export const LEAVE_TYPES = [
  "CASUAL",
  "SICK",
  "EARNED",
  "UNPAID",
  "MATERNITY",
  "PATERNITY",
  "COMPENSATORY",
] as const;

export const titleCase = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());

export const asOptions = (values: readonly string[]) =>
  values.map((v) => ({ value: v, label: titleCase(v) }));


/* ---------------------------------------------- Dynamic navigation */
export interface NavBucket {
  key: string;
  label: string;
  count: number;
}

/** One configured form under a company: its case type. */
export interface NavForm {
  case_type_id: string;
  name: string;
  count: number;
}

export interface NavCompany {
  id: string;
  code: string;
  name: string;
  short_name: string;
  count: number;
  /** Listed by the menu when a company has more than one form here. */
  forms: NavForm[];
}

export interface NavCategory {
  category: string;
  label: string;
  /** "investigation" or "death-claim" — the URL segment. */
  slug: string;
  icon: string;
  permission: string;
  total: number;
  open_total: number;
  buckets: NavBucket[];
  companies: NavCompany[];
}

export interface MyDeskCounts {
  field_open: number;
  office_open: number;
  correction_required: number;
  completed: number;
}

export interface Sidebar {
  categories: NavCategory[];
  my_desk: MyDeskCounts;
  generated_at: string;
}

/* ------------------------------------------------------ Attendance */
export type ClockState = "CLOCKED_IN" | "CLOCKED_OUT";

export interface ClockStatus {
  state: ClockState;
  session_id?: string | null;
  clock_in_at?: string | null;
  clock_out_at?: string | null;
  worked_minutes_today: number;
  open_session_minutes: number;
  sessions_today: number;
  work_date: string;
  worked_display: string;
  can_clock_in: boolean;
  can_clock_out: boolean;
}

export interface AttendanceSessionRow {
  id: string;
  user_id: string;
  work_date: string;
  clock_in_at: string;
  clock_out_at?: string | null;
  worked_minutes?: number | null;
  worked_display: string;
  is_open: boolean;
  auto_closed: boolean;
  clock_in_note?: string | null;
  clock_out_note?: string | null;
}

export interface AttendanceOverviewRow {
  user_id: string;
  user_name: string;
  email?: string;
  employee_id?: string;
  work_date: string;
  first_clock_in?: string;
  last_clock_out?: string;
  worked_minutes: number;
  worked_display: string;
  sessions: number;
  clock_state: ClockState;
  auto_closed: boolean;
  is_online: boolean;
  current_activity?: string;
}

export interface AttendanceTotals {
  total_staff: number;
  clocked_in: number;
  clocked_out: number;
  present_today: number;
  not_clocked_in: number;
  total_worked_minutes: number;
  total_worked_display: string;
}

export interface AttendanceDashboard {
  work_date: string;
  totals: AttendanceTotals;
  rows: AttendanceOverviewRow[];
}

/* --------------------------------------------------- Activity log */
export interface ActivityRow {
  id: string;
  user_id: string;
  user_label?: string;
  activity_type: string;
  module: string;
  summary?: string;
  detail?: string;
  case_id?: string;
  entity_type?: string;
  entity_id?: string;
  entity_label?: string;
  page?: string;
  ip_address?: string;
  created_at: string;
}

export interface ActivityActionOption {
  value: string;
  label: string;
  module: string;
}

export interface LiveUserRow {
  user: UserBrief;
  is_online: boolean;
  clock_state: ClockState;
  clocked_in_at?: string;
  worked_minutes_today: number;
  worked_display: string;
  last_activity_at?: string;
  current_module?: string;
  current_action?: string;
  active_cases: number;
}

/* ---------------------------------------------- Two-stage workflow */
export interface StageAssignment {
  id: string;
  stage: "FIELD_INVESTIGATION" | "OFFICE_PROCESSING" | "REVIEW";
  state: "ACTIVE" | "COMPLETED" | "RELEASED" | "CANCELLED";
  assigned_to?: UserBrief;
  assigned_by?: UserBrief;
  is_reassignment: boolean;
  due_at?: string;
  accepted_at?: string;
  completed_at?: string;
  released_at?: string;
  notes?: string;
  created_at: string;
}

export interface AssignableStaff {
  id: string;
  full_name: string;
  email: string;
  staff_category?: string;
  roles: string[];
  is_online: boolean;
  clock_state: ClockState;
  active_cases: number;
  pending_cases: number;
  completed_this_month: number;
  overdue_cases: number;
}


/** A required answer that is still empty, and where to find it on the form. */
export interface MissingField {
  field_key: string;
  label: string;
  section: string;
}
