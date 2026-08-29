import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileText,
  UploadCloud,
} from "lucide-react";
import { useRef, useState } from "react";
import { api, download, errorMessage } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Status,
  fmtDate,
} from "../components";
import {
  Field,
  Form,
  FormGrid,
  Modal,
  PermissionDenied,
  SelectInput,
  Tabs,
  TextArea,
  TextInput,
  useToast,
} from "../ui";
import type {
  CaseType,
  Company,
  DocumentTemplate,
  FormTemplateDetail,
  FormTemplateSummary,
  ImportTemplate,
} from "../types";

export default function Templates() {
  const { can } = useAuth();
  const [tab, setTab] = useState("forms");

  if (!can("template.view")) return <PermissionDenied what="templates" />;
  const canManage = can("template.manage");

  return (
    <>
      <PageHeader
        title="Template management"
        subtitle="Company investigation forms, the client Word documents they produce, and the Excel column mapping."
      />
      <Tabs
        tabs={[
          { key: "forms", label: "Form templates" },
          { key: "documents", label: "Document templates" },
          { key: "import", label: "Import mapping" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "forms" && <FormTemplatesTab canManage={canManage} />}
      {tab === "documents" && <DocumentTemplatesTab canManage={canManage} />}
      {tab === "import" && <ImportMappingTab />}
    </>
  );
}

/* ----------------------------------------------------- Form templates */
function FormTemplatesTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [company, setCompany] = useState("");
  const [viewing, setViewing] = useState<string | null>(null);

  const companies = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () => api.get<Company[]>("/companies").then((r) => r.data),
  });

  const query = useQuery({
    queryKey: ["form-templates", company],
    queryFn: () =>
      api
        .get<FormTemplateSummary[]>("/form-templates", {
          params: { company_id: company || undefined },
        })
        .then((r) => r.data),
  });

  const detail = useQuery({
    queryKey: ["form-template", viewing],
    enabled: Boolean(viewing),
    queryFn: () =>
      api
        .get<FormTemplateDetail>(`/form-templates/${viewing}`)
        .then((r) => r.data),
  });

  const activate = useMutation({
    mutationFn: (id: string) => api.post(`/form-templates/${id}/activate`),
    onSuccess: () => {
      toast.success("Template version activated.");
      client.invalidateQueries({ queryKey: ["form-templates"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <Card>
        <div className="filters">
          <SelectInput
            value={company}
            onChange={setCompany}
            placeholder="All companies"
            options={(companies.data ?? []).map((c) => ({
              value: c.id,
              label: c.short_name,
            }))}
          />
          <div className="filters-note">
            <FileText />
            <span>
              Layouts were transcribed from the client documents. Completed cases
              keep the version they were filled under.
            </span>
          </div>
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty title="No form templates" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Template</th>
                  <th>Company</th>
                  <th>Case type</th>
                  <th>Version</th>
                  <th>Structure</th>
                  <th>Source document</th>
                  <th>Status</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {query.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <b>{t.name}</b>
                      <small>{t.code}</small>
                    </td>
                    <td>{t.company_name || "—"}</td>
                    <td>{t.case_type_name || "—"}</td>
                    <td>v{t.version}</td>
                    <td>
                      <small>
                        {t.section_count} sections · {t.field_count} fields
                      </small>
                    </td>
                    <td className="aliases">
                      <small>{t.source_document || "Created in app"}</small>
                    </td>
                    <td>
                      <Status value={t.is_active ? "ACTIVE" : "INACTIVE"} />
                    </td>
                    <td className="row-actions">
                      <button
                        className="text-link"
                        onClick={() => setViewing(t.id)}
                      >
                        View fields
                      </button>
                      {canManage && !t.is_active && (
                        <button
                          className="text-link"
                          disabled={activate.isPending}
                          onClick={() => activate.mutate(t.id)}
                        >
                          Make active
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

      <Modal
        open={Boolean(viewing)}
        wide
        title={detail.data?.name ?? "Form template"}
        subtitle={
          detail.data
            ? `${detail.data.company_name} · ${detail.data.case_type_name} · v${detail.data.version}`
            : undefined
        }
        onClose={() => setViewing(null)}
      >
        {detail.isLoading ? (
          <Loading />
        ) : detail.isError ? (
          <ErrorState message={errorMessage(detail.error)} />
        ) : (
          <div className="template-preview">
            {(detail.data?.sections ?? []).map((section) => (
              <section key={section.id}>
                <h3>{section.title}</h3>
                {section.description && <p>{section.description}</p>}
                <ul>
                  {section.fields.map((field) => (
                    <li key={field.id}>
                      <span>
                        {field.label}
                        {field.is_required && <i> *</i>}
                      </span>
                      <small>
                        {field.field_type.toLowerCase()}
                        {field.source === "BANK_SUPPLIED" && " · bank supplied"}
                        {field.document_mapping &&
                          ` · {{ ${field.document_mapping} }}`}
                      </small>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </Modal>
    </>
  );
}

/* ------------------------------------------------- Document templates */
function DocumentTemplatesTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({
    company_id: "",
    case_type_id: "",
    name: "",
    notes: "",
  });

  const companies = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () => api.get<Company[]>("/companies").then((r) => r.data),
  });
  const caseTypes = useQuery({
    queryKey: ["case-types", "all"],
    queryFn: () => api.get<CaseType[]>("/case-types").then((r) => r.data),
  });

  const query = useQuery({
    queryKey: ["document-templates"],
    queryFn: () =>
      api.get<DocumentTemplate[]>("/document-templates").then((r) => r.data),
  });

  const upload = useMutation({
    mutationFn: () => {
      const data = new FormData();
      data.append("file", file as File);
      data.append("company_id", form.company_id);
      data.append("case_type_id", form.case_type_id);
      data.append("name", form.name);
      if (form.notes) data.append("notes", form.notes);
      return api
        .post("/document-templates", data)
        .then((r) => r.data as { message: string });
    },
    onSuccess: (data) => {
      toast.success(data.message);
      client.invalidateQueries({ queryKey: ["document-templates"] });
      setOpen(false);
      setFile(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const legacy = (query.data ?? []).filter(
    (t) => t.status === "NEEDS_CONVERSION",
  );

  return (
    <>
      {legacy.length > 0 && (
        <div className="banner warning">
          <AlertTriangle />
          <div>
            <b>
              {legacy.length} legacy .doc template
              {legacy.length > 1 ? "s" : ""} cannot be filled automatically
            </b>
            <span>
              {legacy.map((t) => t.original_filename).join(", ")} — open in Word,
              save as .docx and upload as a new version. PDF generation keeps
              working meanwhile.
            </span>
          </div>
        </div>
      )}
      <Card>
        <div className="filters">
          <div className="filters-note">
            <FileText />
            <span>
              Generation renders the client's own Word file, so their layout is
              preserved exactly.
            </span>
          </div>
          {canManage && (
            <button
              className="primary"
              onClick={() => {
                setForm({
                  company_id: "",
                  case_type_id: "",
                  name: "",
                  notes: "",
                });
                setFile(null);
                setOpen(true);
              }}
            >
              <UploadCloud /> Upload template
            </button>
          )}
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty title="No document templates" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Template</th>
                  <th>Company</th>
                  <th>Case type</th>
                  <th>Version</th>
                  <th>Placeholders</th>
                  <th>DOCX ready</th>
                  <th>Uploaded</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {query.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <b>{t.name}</b>
                      <small>{t.original_filename}</small>
                    </td>
                    <td>{t.company_name || "—"}</td>
                    <td>{t.case_type_name || "—"}</td>
                    <td>v{t.version}</td>
                    <td>{t.placeholder_count || "—"}</td>
                    <td>
                      {t.can_generate_docx ? (
                        <span className="inline-ok">
                          <CheckCircle2 /> Ready
                        </span>
                      ) : (
                        <Status value={t.status} />
                      )}
                    </td>
                    <td>{fmtDate(t.created_at)}</td>
                    <td className="row-actions">
                      <button
                        className="icon-button"
                        title="Download original"
                        onClick={() =>
                          download(
                            `/document-templates/${t.id}/download`,
                            t.original_filename,
                          ).catch((e) => toast.error(errorMessage(e)))
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

      <Modal
        open={open}
        title="Upload document template"
        subtitle="A new version is created; existing completed cases keep rendering the version they used."
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => upload.mutate()}
              disabled={
                upload.isPending ||
                !file ||
                !form.company_id ||
                !form.case_type_id ||
                !form.name
              }
            >
              {upload.isPending ? "Uploading…" : "Upload"}
            </button>
          </>
        }
      >
        <Form onSubmit={() => upload.mutate()}>
          <FormGrid>
            <Field label="Company" required>
              <SelectInput
                value={form.company_id}
                onChange={(v) => setForm((f) => ({ ...f, company_id: v }))}
                options={(companies.data ?? []).map((c) => ({
                  value: c.id,
                  label: c.short_name,
                }))}
              />
            </Field>
            <Field label="Case type" required>
              <SelectInput
                value={form.case_type_id}
                onChange={(v) => setForm((f) => ({ ...f, case_type_id: v }))}
                options={(caseTypes.data ?? []).map((c) => ({
                  value: c.id,
                  label: c.name,
                }))}
              />
            </Field>
            <Field label="Template name" required span={2}>
              <TextInput
                value={form.name}
                onChange={(v) => setForm((f) => ({ ...f, name: v }))}
                placeholder="ICICI Prudential — Claim Investigation Report"
              />
            </Field>
            <Field
              label="Word file"
              required
              span={2}
              hint="A .docx already containing {{ placeholders }} is usable immediately."
            >
              <>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".docx,.doc"
                  hidden
                  onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <button
                  type="button"
                  className="file-picker"
                  onClick={() => fileRef.current?.click()}
                >
                  <UploadCloud />
                  {file ? file.name : "Choose .docx file"}
                </button>
              </>
            </Field>
            <Field label="Notes" span={2}>
              <TextArea
                value={form.notes}
                onChange={(v) => setForm((f) => ({ ...f, notes: v }))}
                rows={2}
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}

/* ------------------------------------------------------ Import mapping */
function ImportMappingTab() {
  const query = useQuery({
    queryKey: ["import-templates"],
    queryFn: () =>
      api.get<ImportTemplate[]>("/imports/templates").then((r) => r.data),
  });

  if (query.isLoading) return <Loading />;
  if (query.isError)
    return <ErrorState message={errorMessage(query.error)} />;
  if (!query.data?.length) return <Empty title="No import templates" />;

  return (
    <>
      {query.data.map((template) => (
        <Card
          key={template.id}
          title={`${template.name} (${template.code})`}
          action={
            template.is_default ? <Status value="DEFAULT" /> : undefined
          }
        >
          {template.description && (
            <p className="card-note">{template.description}</p>
          )}
          <div className="key-facts">
            <span>
              <small>Header row</small>
              <b>{template.header_row}</b>
            </span>
            <span>
              <small>Duplicate key</small>
              <b>{(template.duplicate_key_fields ?? []).join(" + ") || "—"}</b>
            </span>
            <span>
              <small>Fallback key</small>
              <b>
                {(template.fallback_duplicate_key_fields ?? []).join(" + ") ||
                  "—"}
              </b>
            </span>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Excel column</th>
                  <th>Internal field</th>
                  <th>Type</th>
                  <th>Required</th>
                  <th>Also accepted</th>
                </tr>
              </thead>
              <tbody>
                {template.mappings.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <b>{m.source_column}</b>
                    </td>
                    <td>
                      <code>{m.target_field}</code>
                    </td>
                    <td>{m.data_type}</td>
                    <td>{m.is_required ? "Yes" : "No"}</td>
                    <td className="aliases">
                      {m.source_aliases
                        ? m.source_aliases.split("|").join(", ")
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
    </>
  );
}
