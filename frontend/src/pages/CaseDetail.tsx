import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  Download,
  FileDown,
  FileText,
  MapPin,
  MessageSquarePlus,
  Paperclip,
  RotateCcw,
  Save,
  Send,
  Trash2,
  UploadCloud,
  UserRoundCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, download, errorMessage } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  Online,
  PageHeader,
  Status,
  fmtDate,
  fmtDateTime,
} from "../components";
import {
  Checkbox,
  ConfirmDialog,
  Field,
  Form,
  FormGrid,
  Modal,
  SelectInput,
  Tabs,
  TextArea,
  TextInput,
  useToast,
} from "../ui";
import {
  FIELD_STAGE_OVER,
  OUTCOMES,
  PRIORITIES,
  STATUS_LABELS,
  asOptions,
  titleCase,
  type AssignmentRow,
  type AuditLog,
  type CaseDetail as CaseDetailType,
  type CaseDocument,
  type CaseForm,
  type CaseNote,
  type GeneratedDocument,
  type MissingField,
  type StaffStatus,
  type StatusHistoryRow,
  type TimelineEvent,
} from "../types";

import {
  ReopenDialog,
  SubmitToOfficeDialog,
  VisitDialog,
  WorkflowTab,
} from "../casestage";
import { OfficeAssignDialog } from "../office";
import { EvidenceDialog, PhotoUploadPanel } from "../evidence";

/** Pull the server's list of empty required fields out of an API error. */
function missingFields(error: unknown): MissingField[] {
  const details = (
    error as {
      response?: { data?: { error?: { details?: { missing?: MissingField[] } } } };
    }
  )?.response?.data?.error?.details?.missing;
  return Array.isArray(details) ? details : [];
}

/** Scroll a form field into view and put the cursor in it. */
function focusField(fieldKey: string) {
  // Rendering the form tab is a state change, so wait a frame for the node.
  requestAnimationFrame(() => {
    const node = document.querySelector<HTMLElement>(
      `[data-field="${CSS.escape(fieldKey)}"]`,
    );
    if (!node) return;
    node.scrollIntoView({ behavior: "smooth", block: "center" });
    node
      .querySelector<HTMLElement>("input, select, textarea")
      ?.focus({ preventScroll: true });
  });
}

export default function CaseDetail() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState("overview");
  const [values, setValues] = useState<Record<string, string>>({});
  const [missing, setMissing] = useState<MissingField[]>([]);
  const [dialog, setDialog] = useState<
    | "assign"
    | "status"
    | "review"
    | "note"
    | "upload"
    | "office"
    | "submit-office"
    | "visit"
    | "reopen"
    | null
  >(null);

  const detail = useQuery({
    queryKey: ["case", id],
    queryFn: () =>
      api.get<CaseDetailType>(`/cases/${id}`).then((r) => r.data),
  });

  const form = useQuery({
    queryKey: ["case-form", id],
    retry: false,
    queryFn: () => api.get<CaseForm>(`/cases/${id}/form`).then((r) => r.data),
  });

  const invalidate = () => {
    client.invalidateQueries({ queryKey: ["case", id] });
    client.invalidateQueries({ queryKey: ["case-form", id] });
    client.invalidateQueries({ queryKey: ["case-timeline", id] });
    client.invalidateQueries({ queryKey: ["cases"] });
    client.invalidateQueries({ queryKey: ["case-stages", id] });
    client.invalidateQueries({ queryKey: ["case-locked", id] });
    client.invalidateQueries({ queryKey: ["navigation"] });
  };

  const merged = useMemo(() => {
    const server = form.data?.values ?? {};
    const flat: Record<string, string> = {};
    for (const [key, entry] of Object.entries(server)) {
      flat[key] = entry.value ?? "";
    }
    return { ...flat, ...values };
  }, [form.data, values]);

  const save = useMutation({
    mutationFn: (submit: boolean) =>
      api.put(`/cases/${id}/form`, { values: merged, submit }),
    onSuccess: (_data, submit) => {
      toast.success(submit ? "Report submitted for review." : "Draft saved.");
      setMissing([]);
      setValues({});
      invalidate();
    },
    onError: (error) => {
      // A long report has hundreds of fields. Rather than naming the empty
      // ones and leaving the user to hunt, mark them and scroll to the first.
      const found = missingFields(error);
      setMissing(found);
      toast.error(errorMessage(error));
      if (found.length) {
        setTab("form");
        focusField(found[0].field_key);
      }
    },
  });

  const generate = useMutation({
    mutationFn: (format: "DOCX" | "PDF") =>
      api
        .post(`/cases/${id}/generate`, {
          output_format: format,
          force: false,
        })
        .then((r) => r.data as GeneratedDocument),
    onSuccess: async (doc) => {
      client.invalidateQueries({ queryKey: ["case-generated", id] });
      client.invalidateQueries({ queryKey: ["case", id] });
      try {
        await download(
          `/cases/${id}/generated/${doc.id}/download`,
          doc.display_name,
        );
        toast.success("Document generated and downloaded.");
      } catch (error) {
        toast.error(errorMessage(error));
      }
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (detail.isLoading) return <Loading />;
  if (detail.isError || !detail.data)
    return <ErrorState message={errorMessage(detail.error)} />;

  const c = detail.data;
  const canAssign = can("case.assign");
  const canReview = can("case.review");
  const canGenerate = can("document.generate");
  const canUpload = can("document.upload");
  const template = form.data?.template;
  const dirty = Object.keys(values).length > 0;

  return (
    <>
      <Link to={c.category === "DEATH_CLAIM" ? "/cases?category=DEATH_CLAIM" : "/cases"} className="back">
        <ArrowLeft /> Back to cases
      </Link>

      <PageHeader
        title={c.case_number}
        subtitle={`${c.company_name} · ${c.case_type_name}`}
        actions={
          <>
            {canGenerate && (
              <>
                <button
                  className="secondary"
                  disabled={generate.isPending}
                  onClick={() => generate.mutate("DOCX")}
                  title="Render the insurer's own Word form"
                >
                  <FileDown /> DOCX
                </button>
                <button
                  className="secondary"
                  disabled={generate.isPending}
                  onClick={() => generate.mutate("PDF")}
                >
                  <Download /> PDF
                </button>
                <button
                  className="secondary"
                  onClick={() => window.print()}
                  title="Print this case"
                >
                  Print
                </button>
              </>
            )}
            {canReview &&
              ["REPORT_SUBMITTED", "OFFICE_PROCESSING", "UNDER_REVIEW"].includes(
                c.status,
              ) && (
                <button className="primary" onClick={() => setDialog("review")}>
                  Review report
                </button>
              )}
            {can("case.assign_office") &&
              (c.field_submitted_at || FIELD_STAGE_OVER.includes(c.status)) &&
              !["COMPLETED", "VERIFIED", "CANCELLED", "REJECTED"].includes(
                c.status,
              ) && (
                <button className="primary" onClick={() => setDialog("office")}>
                  <Building2 />{" "}
                  {c.office_staff ? "Reassign office" : "Assign to office"}
                </button>
              )}
            {can("investigation.edit") &&
              !c.field_submitted_at &&
              !FIELD_STAGE_OVER.includes(c.status) &&
              !["IMPORTED", "UNASSIGNED"].includes(c.status) && (
                <button
                  className="primary"
                  onClick={() => setDialog("submit-office")}
                >
                  <Send /> Submit to office
                </button>
              )}
            {can("case.edit") &&
              ["COMPLETED", "REJECTED", "CANCELLED"].includes(c.status) && (
                <button className="primary" onClick={() => setDialog("reopen")}>
                  <RotateCcw /> Reopen case
                </button>
              )}
            {canAssign && (
              <button className="secondary" onClick={() => setDialog("assign")}>
                <UserRoundCheck />{" "}
                {c.assigned_to ? "Reassign" : "Assign investigator"}
              </button>
            )}
          </>
        }
      />

      <div className="case-hero">
        <div>
          <span className="company-logo">{c.company_code.slice(0, 3)}</span>
          <span>
            <b>{c.life_assured_name}</b>
            <small>
              {c.policy_number ||
                c.application_number ||
                c.krn_no ||
                "No external reference"}
            </small>
          </span>
        </div>
        <button
          className="hero-status"
          onClick={() => setDialog("status")}
          title="Change status"
          disabled={!c.allowed_transitions.length}
        >
          <Status value={c.status} label={c.status_label} />
        </button>
        <div>
          <span>Outcome</span>
          <b>{c.outcome ? titleCase(c.outcome) : "Not set"}</b>
        </div>
        <div>
          <span>TAT</span>
          <Status value={c.tat_state} />
          <small>{c.aging_days} days aging</small>
        </div>
        <div>
          <span>Investigator</span>
          {c.assigned_to ? (
            <>
              <b>{c.assigned_to.full_name}</b>
              <Online online={c.assigned_to.is_online} />
            </>
          ) : (
            <b>Unassigned</b>
          )}
        </div>
        <div>
          <span>Office staff</span>
          {c.office_staff ? (
            <>
              <b>{c.office_staff.full_name}</b>
              <Online online={c.office_staff.is_online} />
            </>
          ) : (
            <b>
              {c.status === "AWAITING_OFFICE_ASSIGNMENT"
                ? "Awaiting assignment"
                : "Not yet"}
            </b>
          )}
        </div>
        <div>
          <span>Visit</span>
          <b>{c.visit_status_label ?? "Not started"}</b>
        </div>
      </div>

      <Tabs
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "imported", label: "Imported data", count: c.imported_fields.length },
          { key: "form", label: "Investigation form" },
          { key: "documents", label: "Documents", count: c.document_count },
          { key: "workflow", label: "Workflow" },
          { key: "assignment", label: "Assignment" },
          { key: "timeline", label: "Timeline" },
          { key: "notes", label: "Notes", count: c.note_count },
          ...(can("audit.view") ? [{ key: "audit", label: "Audit" }] : []),
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" && <OverviewTab c={c} />}
      {tab === "imported" && <ImportedTab c={c} />}
      {tab === "form" && (
        <FormTab
          caseId={id}
          form={form.data}
          isLoading={form.isLoading}
          isError={form.isError}
          error={form.error}
          merged={merged}
          setValues={setValues}
          dirty={dirty}
          saving={save.isPending}
          onSave={() => save.mutate(false)}
          onSubmit={() => save.mutate(true)}
          templateName={template?.name}
          missing={missing}
          onJump={focusField}
        />
      )}
      {tab === "documents" && (
        <DocumentsTab
          caseId={id}
          canUpload={canUpload}
          canDelete={can("document.delete")}
          onUpload={() => setDialog("upload")}
        />
      )}
      {tab === "workflow" && (
        <WorkflowTab
          c={c}
          onAssignOffice={() => setDialog("office")}
          onSubmitToOffice={() => setDialog("submit-office")}
          onUpdateVisit={() => setDialog("visit")}
        />
      )}
      {tab === "assignment" && <AssignmentTab caseId={id} />}
      {tab === "timeline" && <TimelineTab caseId={id} />}
      {tab === "notes" && (
        <NotesTab caseId={id} onAdd={() => setDialog("note")} />
      )}
      {tab === "audit" && <AuditTab caseId={id} />}

      <AssignDialog
        open={dialog === "assign"}
        caseId={id}
        current={c.assigned_to?.id}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <StatusDialog
        open={dialog === "status"}
        caseId={id}
        allowed={c.allowed_transitions}
        currentOutcome={c.outcome}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <ReviewDialog
        open={dialog === "review"}
        caseId={id}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <NoteDialog
        open={dialog === "note"}
        caseId={id}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <EvidenceDialog
        open={dialog === "upload"}
        caseId={id}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <OfficeAssignDialog
        open={dialog === "office"}
        caseId={id}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <SubmitToOfficeDialog
        open={dialog === "submit-office"}
        caseId={id}
        currentOutcome={c.outcome}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <VisitDialog
        open={dialog === "visit"}
        caseId={id}
        current={c.visit_status}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
      <ReopenDialog
        open={dialog === "reopen"}
        caseId={id}
        currentStatus={c.status_label}
        onClose={() => setDialog(null)}
        onDone={invalidate}
      />
    </>
  );
}

/* ------------------------------------------------------------ Overview */
function OverviewTab({ c }: { c: CaseDetailType }) {
  const { can } = useAuth();
  return (
    <div className="detail-grid">
      <Card title="Case information">
        <dl className="details">
          {[
            ["KRN number", c.krn_no],
            ["Policy number", c.policy_number],
            ["Application number", c.application_number],
            ["Product", c.product_name],
            ["Sum assured", c.sum_assured],
            ["Premium", c.premium_amount],
            ["Risk commencement", fmtDate(c.risk_commencement_date)],
            ["Nominee", c.nominee_name],
            ["Nominee relation", c.nominee_relation],
            ["Priority", titleCase(c.priority)],
            ["Report status", c.report_status ? titleCase(c.report_status) : null],
          ].map(([label, value]) => (
            <div key={String(label)}>
              <dt>{label}</dt>
              <dd>{value || "—"}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="Location & contact">
        <div className="location">
          <MapPin />
          <div>
            <b>
              {c.city || "Location unavailable"}
              {c.state ? `, ${c.state}` : ""}
            </b>
            <p>
              {c.address || "No address supplied"} {c.pin_code || ""}
            </p>
            <span>{c.contact_number || "No contact number"}</span>
            {c.alternate_contact && <span>Alt: {c.alternate_contact}</span>}
            {c.email_id && <span>{c.email_id}</span>}
          </div>
        </div>
      </Card>

      {can("document.upload") && (
        <Card title="Photographs">
          <PhotoUploadPanel caseId={c.id} />
        </Card>
      )}

      <Card title="Turn around time">
        <dl className="details">
          {[
            ["Received", fmtDateTime(c.received_at)],
            ["Assigned", fmtDateTime(c.assigned_at)],
            ["Started", fmtDateTime(c.started_at)],
            ["Submitted", fmtDateTime(c.submitted_at)],
            ["Verified", fmtDateTime(c.verified_at)],
            ["Completed", fmtDateTime(c.completed_at)],
            ["Due", fmtDateTime(c.due_at)],
            [
              "Days taken",
              c.tat_days_taken !== undefined && c.tat_days_taken !== null
                ? `${c.tat_days_taken} days`
                : null,
            ],
          ].map(([label, value]) => (
            <div key={String(label)}>
              <dt>{label}</dt>
              <dd>{value || "—"}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {c.death_claim && (
        <Card title="Claim details" className="wide">
          <dl className="details">
            {Object.entries(c.death_claim)
              .filter(([key]) => key !== "id")
              .filter(([, value]) => value !== null && value !== "")
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{titleCase(key)}</dt>
                  <dd>{String(value)}</dd>
                </div>
              ))}
          </dl>
        </Card>
      )}

      {c.outcome_reason && (
        <Card title="Conclusion" className="wide">
          <p className="wrap">{c.outcome_reason}</p>
        </Card>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ Imported */
function ImportedTab({ c }: { c: CaseDetailType }) {
  if (c.imported_fields.length) return <ImportedProvenance c={c} />;
  if (!c.imported_fields.length)
    return (
      <Card>
        <Empty
          title="No bank-supplied data"
          detail="This case was created manually rather than imported from a client file."
        />
      </Card>
    );

  return null;
}

function ImportedProvenance({ c }: { c: CaseDetailType }) {
  return (
    <Card
      title="Client-supplied data"
      action={<Status value="BANK_SUPPLIED" label="Imported" />}
    >
      <p className="card-note">
        These values arrived in the daily import. The original is retained even
        after an investigator edits the field.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th>Current value</th>
              <th>Original from client</th>
              <th>Source column</th>
              <th>Imported</th>
            </tr>
          </thead>
          <tbody>
            {c.imported_fields.map((f) => (
              <tr key={f.field}>
                <td>
                  <b>{f.label}</b>
                </td>
                <td>{f.value || "—"}</td>
                <td className={f.was_edited ? "changed-value" : ""}>
                  {f.original_value || "—"}
                  {f.was_edited && <small>edited by staff</small>}
                </td>
                <td>
                  <code>{f.original_column || "—"}</code>
                </td>
                <td>{fmtDateTime(f.imported_at ?? undefined)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ---------------------------------------------------------------- Form */
function FormTab({
  form,
  isLoading,
  isError,
  error,
  merged,
  setValues,
  dirty,
  saving,
  onSave,
  onSubmit,
  templateName,
  missing = [],
  onJump,
}: {
  caseId: string;
  form?: CaseForm;
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  merged: Record<string, string>;
  setValues: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
  onSubmit: () => void;
  templateName?: string;
  missing?: MissingField[];
  onJump?: (fieldKey: string) => void;
}) {
  if (isLoading) return <Loading />;
  if (isError)
    return (
      <Card>
        <ErrorState message={errorMessage(error)} />
      </Card>
    );
  if (!form) return <Card><Empty title="No form attached" /></Card>;

  const readOnly = !form.can_edit;
  const missingKeys = new Set(missing.map((m) => m.field_key));

  return (
    <>
      <div className="form-banner">
        <FileText />
        <span>
          <b>{templateName || "Company investigation form"}</b>
          <small>
            Version {form.template.version} · Imported fields are marked and
            retained for audit.
          </small>
        </span>
        <span className="completion">{form.completion_percent}% complete</span>
      </div>

      {missing.length > 0 && (
        <div className="banner danger">
          <div>
            <b>
              {missing.length} required field
              {missing.length === 1 ? "" : "s"} still empty
            </b>
            <span>Click one to jump straight to it.</span>
            <div className="missing-list">
              {missing.map((item) => (
                <button
                  key={item.field_key}
                  type="button"
                  className="missing-chip"
                  onClick={() => onJump?.(item.field_key)}
                >
                  {item.label}
                  <small>{item.section}</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {readOnly && (
        <div className="banner warning">
          <div>
            <b>This form is read-only</b>
            <span>
              {form.locked_reason ??
                "This report can no longer be edited."}
            </span>
          </div>
        </div>
      )}

      {form.correction_remark && (
        <div className="banner warning">
          <div>
            <b>Correction requested</b>
            <span>{form.correction_remark}</span>
          </div>
        </div>
      )}

      {form.template.sections.map((section) => (
        <Card title={section.title} key={section.id}>
          {section.description && (
            <p className="card-note">{section.description}</p>
          )}
          <div className="dynamic-form">
            {section.fields.map((field) => {
              const key = field.field_key;
              const value = merged[key] ?? "";
              const disabled = readOnly || field.is_readonly;
              const change = (next: string) =>
                setValues((v) => ({ ...v, [key]: next }));
              const bankSupplied = field.source === "BANK_SUPPLIED";

              return (
                <label
                  className={[
                    field.col_span >= 12 ? "span-2" : "",
                    missingKeys.has(key) ? "field-missing" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  key={field.id}
                  data-field={key}
                >
                  <span>
                    {field.label}
                    {field.is_required && <i> *</i>}
                  </span>

                  {field.field_type === "TEXTAREA" ? (
                    <TextArea
                      value={value}
                      onChange={change}
                      disabled={disabled}
                      rows={4}
                    />
                  ) : field.field_type === "SELECT" ||
                    field.field_type === "RADIO" ||
                    field.field_type === "YES_NO_NA" ? (
                    <SelectInput
                      value={value}
                      onChange={change}
                      disabled={disabled}
                      options={(field.field_type === "YES_NO_NA"
                        ? ["YES", "NO", "NA"]
                        : (field.options ?? []).map(String)
                      ).map((o) => ({ value: o, label: o }))}
                    />
                  ) : field.field_type === "BOOLEAN" ? (
                    <Checkbox
                      checked={value === "true" || value === "YES"}
                      disabled={disabled}
                      onChange={(checked) => change(checked ? "YES" : "NO")}
                      label="Yes"
                    />
                  ) : field.field_type === "TABLE" ? (
                    <TextArea
                      value={value}
                      onChange={change}
                      disabled={disabled}
                      rows={3}
                      placeholder="One row per line"
                    />
                  ) : (
                    <TextInput
                      type={
                        field.field_type === "DATE"
                          ? "date"
                          : field.field_type === "DATETIME"
                            ? "datetime-local"
                            : field.field_type === "TIME"
                              ? "time"
                              : field.field_type === "NUMBER" ||
                                  field.field_type === "CURRENCY"
                                ? "number"
                                : field.field_type === "EMAIL"
                                  ? "email"
                                  : "text"
                      }
                      value={value}
                      onChange={change}
                      disabled={disabled}
                      placeholder={field.placeholder ?? undefined}
                    />
                  )}

                  {bankSupplied && (
                    <small className="badge badge-bank-supplied">
                      Supplied by the client · correct it if it is wrong
                    </small>
                  )}
                  {field.help_text && !bankSupplied && (
                    <small>{field.help_text}</small>
                  )}
                </label>
              );
            })}
          </div>
        </Card>
      ))}

      {!readOnly && (
        <div className="sticky-save">
          <span>
            {dirty
              ? "Unsaved changes — every edit is audit logged."
              : "All changes saved."}
          </span>
          <button className="secondary" onClick={onSave} disabled={saving}>
            <Save /> {saving ? "Saving…" : "Save draft"}
          </button>
          <button className="primary" onClick={onSubmit} disabled={saving}>
            <Send /> Submit for review
          </button>
        </div>
      )}
    </>
  );
}

/* ----------------------------------------------------------- Documents */
function DocumentsTab({
  caseId,
  canUpload,
  canDelete,
  onUpload,
}: {
  caseId: string;
  canUpload: boolean;
  canDelete: boolean;
  onUpload: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [removing, setRemoving] = useState<CaseDocument | null>(null);

  const documents = useQuery({
    queryKey: ["case-documents", caseId],
    queryFn: () =>
      api.get<CaseDocument[]>(`/cases/${caseId}/documents`).then((r) => r.data),
  });

  const generated = useQuery({
    queryKey: ["case-generated", caseId],
    queryFn: () =>
      api
        .get<GeneratedDocument[]>(`/cases/${caseId}/generated`)
        .then((r) => r.data),
  });

  const remove = useMutation({
    mutationFn: (documentId: string) =>
      api.delete(`/cases/${caseId}/documents/${documentId}`),
    onSuccess: () => {
      toast.success("Document removed.");
      client.invalidateQueries({ queryKey: ["case-documents", caseId] });
      client.invalidateQueries({ queryKey: ["case", caseId] });
      setRemoving(null);
    },
    onError: (e) => {
      toast.error(errorMessage(e));
      setRemoving(null);
    },
  });

  async function get(path: string, name: string) {
    try {
      await download(path, name);
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <>
      <Card
        title="Evidence"
        action={
          canUpload && (
            <button className="primary" onClick={onUpload}>
              <UploadCloud /> Upload evidence
            </button>
          )
        }
      >
        {documents.isLoading ? (
          <Loading />
        ) : documents.isError ? (
          <ErrorState message={errorMessage(documents.error)} />
        ) : !documents.data?.length ? (
          <Empty
            title="No evidence uploaded"
            detail="Photographs must carry location tagging with a date and time stamp."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Category</th>
                  <th>Size</th>
                  <th>Geo tag</th>
                  <th>Uploaded by</th>
                  <th>When</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {documents.data.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <Paperclip className="table-icon" />
                      <b>{d.display_name}</b>
                      {d.description && <small>{d.description}</small>}
                    </td>
                    <td>
                      <Status value={d.category} />
                    </td>
                    <td>{(d.size_bytes / 1024).toFixed(0)} KB</td>
                    <td>
                      {d.geo_latitude && d.geo_longitude
                        ? `${d.geo_latitude.toFixed(4)}, ${d.geo_longitude.toFixed(4)}`
                        : "—"}
                    </td>
                    <td>{d.uploaded_by?.full_name || "—"}</td>
                    <td>{fmtDateTime(d.created_at)}</td>
                    <td className="row-actions">
                      <button
                        className="icon-button"
                        title="Download"
                        onClick={() =>
                          get(
                            `/cases/${caseId}/documents/${d.id}/download`,
                            d.display_name,
                          )
                        }
                      >
                        <Download />
                      </button>
                      {canDelete && (
                        <button
                          className="icon-button danger"
                          title="Remove"
                          onClick={() => setRemoving(d)}
                        >
                          <Trash2 />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Generated client documents">
        {generated.isLoading ? (
          <Loading />
        ) : !generated.data?.length ? (
          <Empty
            title="Nothing generated yet"
            detail="Generate the client form once the case is verified or completed."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Format</th>
                  <th>Template</th>
                  <th>Rendered from</th>
                  <th>Generated by</th>
                  <th>When</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {generated.data.map((g) => (
                  <tr key={g.id}>
                    <td>
                      <b>{g.display_name}</b>
                    </td>
                    <td>
                      <Status value={g.output_format} />
                    </td>
                    <td>
                      {g.template_name || "Built-in layout"}
                      {g.template_version && <small>v{g.template_version}</small>}
                    </td>
                    <td>
                      {g.used_client_template
                        ? "Client's own Word form"
                        : "Built-in PDF report"}
                    </td>
                    <td>{g.generated_by?.full_name || "—"}</td>
                    <td>{fmtDateTime(g.generated_at)}</td>
                    <td>
                      <button
                        className="icon-button"
                        title="Download"
                        onClick={() =>
                          get(
                            `/cases/${caseId}/generated/${g.id}/download`,
                            g.display_name,
                          )
                        }
                      >
                        <Download />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(removing)}
        title="Remove this document?"
        message={`${removing?.display_name} will no longer appear on the case. The deletion is audit logged.`}
        confirmLabel="Remove"
        danger
        busy={remove.isPending}
        onConfirm={() => removing && remove.mutate(removing.id)}
        onClose={() => setRemoving(null)}
      />
    </>
  );
}

/* ---------------------------------------------------------- Assignment */
function AssignmentTab({ caseId }: { caseId: string }) {
  const assignments = useQuery({
    queryKey: ["case-assignments", caseId],
    queryFn: () =>
      api
        .get<AssignmentRow[]>(`/cases/${caseId}/assignments`)
        .then((r) => r.data),
  });

  const history = useQuery({
    queryKey: ["case-status-history", caseId],
    queryFn: () =>
      api
        .get<StatusHistoryRow[]>(`/cases/${caseId}/status-history`)
        .then((r) => r.data),
  });

  return (
    <>
      <Card title="Assignment history">
        {assignments.isLoading ? (
          <Loading />
        ) : !assignments.data?.length ? (
          <Empty title="Never assigned" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Assigned to</th>
                  <th>Assigned by</th>
                  <th>Type</th>
                  <th>Priority</th>
                  <th>Due</th>
                  <th>Notes</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {assignments.data.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <b>{a.assigned_to?.full_name || "—"}</b>
                    </td>
                    <td>{a.assigned_by?.full_name || "System"}</td>
                    <td>
                      <Status
                        value={a.is_reassignment ? "REASSIGNED" : "ASSIGNED"}
                      />
                    </td>
                    <td>{titleCase(a.priority)}</td>
                    <td>{fmtDate(a.due_at)}</td>
                    <td className="wrap">{a.notes || "—"}</td>
                    <td>{fmtDateTime(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Status history">
        {history.isLoading ? (
          <Loading />
        ) : !history.data?.length ? (
          <Empty title="No status changes" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>From</th>
                  <th>To</th>
                  <th>Changed by</th>
                  <th>Comment</th>
                  <th>When</th>
                </tr>
              </thead>
              <tbody>
                {history.data.map((h) => (
                  <tr key={h.id}>
                    <td>
                      {h.previous_status ? (
                        <Status
                          value={h.previous_status}
                          label={STATUS_LABELS[h.previous_status]}
                        />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <Status
                        value={h.new_status}
                        label={STATUS_LABELS[h.new_status]}
                      />
                    </td>
                    <td>{h.changed_by?.full_name || "System"}</td>
                    <td className="wrap">{h.comment || "—"}</td>
                    <td>{fmtDateTime(h.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/* ------------------------------------------------------------ Timeline */
function TimelineTab({ caseId }: { caseId: string }) {
  const query = useQuery({
    queryKey: ["case-timeline", caseId],
    queryFn: () =>
      api.get<TimelineEvent[]>(`/cases/${caseId}/timeline`).then((r) => r.data),
  });

  if (query.isLoading) return <Loading />;
  if (query.isError)
    return (
      <Card>
        <ErrorState message={errorMessage(query.error)} />
      </Card>
    );
  if (!query.data?.length)
    return (
      <Card>
        <Empty title="No activity yet" />
      </Card>
    );

  return (
    <Card title="Case activity">
      <ol className="timeline">
        {query.data.map((event) => (
          <li key={event.id}>
            <span className="timeline-dot" />
            <div>
              <b>{event.summary}</b>
              {event.detail && <p>{event.detail}</p>}
              <small>
                {fmtDateTime(event.occurred_at)} ·{" "}
                {event.actor_label || "System"}
              </small>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

/* --------------------------------------------------------------- Notes */
function NotesTab({
  caseId,
  onAdd,
}: {
  caseId: string;
  onAdd: () => void;
}) {
  const query = useQuery({
    queryKey: ["case-notes", caseId],
    queryFn: () =>
      api.get<CaseNote[]>(`/cases/${caseId}/notes`).then((r) => r.data),
  });

  return (
    <Card
      title="Notes"
      action={
        <button className="primary" onClick={onAdd}>
          <MessageSquarePlus /> Add note
        </button>
      }
    >
      {query.isLoading ? (
        <Loading />
      ) : !query.data?.length ? (
        <Empty title="No notes yet" />
      ) : (
        <ol className="note-list">
          {query.data.map((note) => (
            <li key={note.id}>
              <header>
                <b>{note.author?.full_name || "System"}</b>
                <small>{fmtDateTime(note.created_at)}</small>
                {note.is_internal && <Status value="INTERNAL" />}
              </header>
              <p className="wrap">{note.body}</p>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}

/* --------------------------------------------------------------- Audit */
function AuditTab({ caseId }: { caseId: string }) {
  const query = useQuery({
    queryKey: ["case-audit", caseId],
    queryFn: () =>
      api.get<AuditLog[]>(`/cases/${caseId}/audit`).then((r) => r.data),
  });

  if (query.isLoading) return <Loading />;
  if (query.isError)
    return (
      <Card>
        <ErrorState message={errorMessage(query.error)} />
      </Card>
    );

  return (
    <Card title="Audit trail">
      {!query.data?.length ? (
        <Empty title="No audit entries" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Changes</th>
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((row) => (
                <tr key={row.id}>
                  <td>{fmtDateTime(row.created_at)}</td>
                  <td>{row.actor_label || "System"}</td>
                  <td>
                    <Status value={row.action} label={titleCase(row.action)} />
                  </td>
                  <td className="wrap">
                    {row.new_values
                      ? Object.entries(row.new_values)
                          .map(([k, v]) => `${titleCase(k)}: ${String(v)}`)
                          .join(" · ")
                      : row.remarks || "—"}
                  </td>
                  <td>{row.ip_address || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

/* ------------------------------------------------------------- Dialogs */
function AssignDialog({
  open,
  caseId,
  current,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  current?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [assignee, setAssignee] = useState("");
  const [due, setDue] = useState("");
  const [priority, setPriority] = useState("");
  const [notes, setNotes] = useState("");

  const staff = useQuery({
    queryKey: ["staff", "status"],
    enabled: open,
    queryFn: () =>
      api
        .get<StaffStatus[]>("/staff/status", {
          params: { staff_category: "FIELD" },
        })
        .then((r) => r.data),
  });

  const assign = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/assign`, {
        assigned_to_id: assignee,
        due_at: due ? new Date(due).toISOString() : null,
        priority: priority || null,
        notes: notes || null,
      }),
    onSuccess: () => {
      toast.success("Case assigned.");
      onDone();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      wide
      title="Assign case"
      subtitle="Online investigators are listed first, lightest workload at the top."
      onClose={onClose}
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => assign.mutate()}
            disabled={assign.isPending || !assignee}
          >
            {assign.isPending ? "Assigning…" : "Assign case"}
          </button>
        </>
      }
    >
      {staff.isLoading ? (
        <Loading />
      ) : (
        <>
          <div className="assignee-list">
            {(staff.data ?? []).map((s) => (
              <button
                key={s.id}
                type="button"
                className={
                  assignee === s.id ? "assignee selected" : "assignee"
                }
                onClick={() => setAssignee(s.id)}
                disabled={s.id === current}
              >
                <span className="avatar small">
                  {s.full_name
                    .split(" ")
                    .map((x) => x[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <span className="assignee-main">
                  <b>{s.full_name}</b>
                  <small>
                    {[s.base_city, s.base_state].filter(Boolean).join(", ") ||
                      "No base location"}
                  </small>
                </span>
                <Online online={s.is_online} label={s.status_label} />
                <span className="assignee-load">
                  <b>{s.open_cases}</b>
                  <small>open</small>
                </span>
                {s.id === current && <Status value="CURRENT" />}
              </button>
            ))}
          </div>
          <FormGrid>
            <Field label="Due date">
              <TextInput type="date" value={due} onChange={setDue} />
            </Field>
            <Field label="Priority">
              <SelectInput
                value={priority}
                onChange={setPriority}
                placeholder="Keep current"
                options={asOptions(PRIORITIES)}
              />
            </Field>
            <Field label="Notes for the investigator" span={2}>
              <TextArea value={notes} onChange={setNotes} rows={2} />
            </Field>
          </FormGrid>
        </>
      )}
    </Modal>
  );
}

function StatusDialog({
  open,
  caseId,
  allowed,
  currentOutcome,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  allowed: string[];
  currentOutcome?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [comment, setComment] = useState("");
  const [outcome, setOutcome] = useState(currentOutcome ?? "");
  const [reportStatus, setReportStatus] = useState("");

  const needsOutcome = ["REPORT_SUBMITTED", "VERIFIED", "COMPLETED"].includes(
    status,
  );

  const change = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/status`, {
        status,
        comment: comment || null,
        outcome: outcome || null,
        report_status: reportStatus || null,
      }),
    onSuccess: () => {
      toast.success("Status updated.");
      onDone();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      title="Change case status"
      subtitle="Only transitions the workflow permits are listed."
      onClose={onClose}
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => change.mutate()}
            disabled={
              change.isPending ||
              !status ||
              (needsOutcome && !outcome && !currentOutcome)
            }
          >
            {change.isPending ? "Updating…" : "Update status"}
          </button>
        </>
      }
    >
      <Form onSubmit={() => change.mutate()}>
        <FormGrid>
          <Field label="New status" required span={2}>
            <SelectInput
              value={status}
              onChange={setStatus}
              placeholder="Select the next status…"
              options={allowed.map((s) => ({
                value: s,
                label: STATUS_LABELS[s] ?? titleCase(s),
              }))}
            />
          </Field>
          {needsOutcome && (
            <>
              <Field
                label="Outcome"
                required
                hint="Required before a report can leave the investigator."
              >
                <SelectInput
                  value={outcome}
                  onChange={setOutcome}
                  options={asOptions(OUTCOMES)}
                />
              </Field>
              <Field label="Report status">
                <SelectInput
                  value={reportStatus}
                  onChange={setReportStatus}
                  options={[
                    { value: "INTERIM", label: "Interim" },
                    { value: "FINAL", label: "Final" },
                  ]}
                />
              </Field>
            </>
          )}
          <Field label="Comment" span={2}>
            <TextArea value={comment} onChange={setComment} rows={3} />
          </Field>
        </FormGrid>
      </Form>
    </Modal>
  );
}

function ReviewDialog({
  open,
  caseId,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [approve, setApprove] = useState(true);
  const [comment, setComment] = useState("");
  const [outcome, setOutcome] = useState("");

  const review = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/review`, {
        approve,
        comment: comment || null,
        outcome: outcome || null,
      }),
    onSuccess: () => {
      toast.success(approve ? "Case approved." : "Returned for correction.");
      onDone();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      title="Review submitted report"
      onClose={onClose}
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className={approve ? "primary" : "danger"}
            onClick={() => review.mutate()}
            disabled={review.isPending || (!approve && !comment.trim())}
          >
            {review.isPending
              ? "Saving…"
              : approve
                ? "Approve"
                : "Return for correction"}
          </button>
        </>
      }
    >
      <Form onSubmit={() => review.mutate()}>
        <FormGrid>
          <Field label="Decision" span={2}>
            <SelectInput
              value={approve ? "approve" : "return"}
              onChange={(v) => setApprove(v === "approve")}
              allowEmpty={false}
              options={[
                { value: "approve", label: "Approve — mark verified" },
                { value: "return", label: "Return for correction" },
              ]}
            />
          </Field>
          {approve && (
            <Field label="Confirm outcome" hint="Leave blank to keep the investigator's outcome.">
              <SelectInput
                value={outcome}
                onChange={setOutcome}
                options={asOptions(OUTCOMES)}
              />
            </Field>
          )}
          <Field
            label={approve ? "Comment" : "Reason for correction"}
            required={!approve}
            span={2}
          >
            <TextArea value={comment} onChange={setComment} rows={3} />
          </Field>
        </FormGrid>
      </Form>
    </Modal>
  );
}

function NoteDialog({
  open,
  caseId,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);

  const add = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/notes`, { body, is_internal: internal }),
    onSuccess: () => {
      toast.success("Note added.");
      client.invalidateQueries({ queryKey: ["case-notes", caseId] });
      onDone();
      setBody("");
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      title="Add note"
      onClose={onClose}
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => add.mutate()}
            disabled={add.isPending || !body.trim()}
          >
            {add.isPending ? "Saving…" : "Add note"}
          </button>
        </>
      }
    >
      <Form onSubmit={() => add.mutate()}>
        <Field label="Note" required span={2}>
          <TextArea value={body} onChange={setBody} rows={5} />
        </Field>
        <Checkbox
          checked={internal}
          onChange={setInternal}
          label="Internal note — hidden from the investigator's timeline"
        />
      </Form>
    </Modal>
  );
}
