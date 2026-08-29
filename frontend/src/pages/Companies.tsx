import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, Pencil, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Status,
  num,
} from "../components";
import {
  Checkbox,
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
  COMPANY_TYPES,
  asOptions,
  titleCase,
  type CaseType,
  type Company,
} from "../types";

type CompanyForm = {
  code: string;
  name: string;
  short_name: string;
  company_type: string;
  import_aliases: string;
  address: string;
  city: string;
  state: string;
  pin_code: string;
  contact_person: string;
  email: string;
  phone: string;
  default_tat_days: string;
  is_active: boolean;
  notes: string;
};

const emptyCompany: CompanyForm = {
  code: "",
  name: "",
  short_name: "",
  company_type: "INSURANCE",
  import_aliases: "",
  address: "",
  city: "",
  state: "",
  pin_code: "",
  contact_person: "",
  email: "",
  phone: "",
  default_tat_days: "7",
  is_active: true,
  notes: "",
};

type CaseTypeForm = {
  code: string;
  name: string;
  category: string;
  description: string;
  import_aliases: string;
  default_tat_days: string;
  display_order: string;
  is_active: boolean;
};

const emptyCaseType: CaseTypeForm = {
  code: "",
  name: "",
  category: "INVESTIGATION",
  description: "",
  import_aliases: "",
  default_tat_days: "7",
  display_order: "100",
  is_active: true,
};

export default function Companies() {
  const { can } = useAuth();
  const [tab, setTab] = useState("companies");
  const canManage = can("company.manage");

  return (
    <>
      <PageHeader
        title="Companies & case types"
        subtitle="Banks, insurers and the kinds of assignment they send. Import aliases let the daily Excel resolve automatically."
      />
      <Tabs
        tabs={[
          { key: "companies", label: "Companies" },
          { key: "case-types", label: "Case types" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "companies" ? (
        <CompanyTab canManage={canManage} />
      ) : (
        <CaseTypeTab canManage={canManage} />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
function CompanyTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Company | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<CompanyForm>(emptyCompany);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const query = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () =>
      api
        .get<Company[]>("/companies", { params: { include_inactive: true } })
        .then((r) => r.data),
  });

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term) return query.data ?? [];
    return (query.data ?? []).filter((c) =>
      [c.code, c.name, c.short_name, c.city, c.state]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(term)),
    );
  }, [query.data, search]);

  const save = useMutation({
    mutationFn: (payload: CompanyForm) => {
      const body = {
        ...payload,
        default_tat_days: Number(payload.default_tat_days) || 7,
        import_aliases: payload.import_aliases || null,
        address: payload.address || null,
        city: payload.city || null,
        state: payload.state || null,
        pin_code: payload.pin_code || null,
        contact_person: payload.contact_person || null,
        email: payload.email || null,
        phone: payload.phone || null,
        notes: payload.notes || null,
      };
      return editing
        ? api.patch(`/companies/${editing.id}`, body)
        : api.post("/companies", body);
    },
    onSuccess: () => {
      toast.success(editing ? "Company updated." : "Company created.");
      client.invalidateQueries({ queryKey: ["companies"] });
      closeModal();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  function openCreate() {
    setEditing(null);
    setForm(emptyCompany);
    setErrors({});
    setCreating(true);
  }

  function openEdit(company: Company) {
    setEditing(company);
    setForm({
      code: company.code,
      name: company.name,
      short_name: company.short_name,
      company_type: company.company_type,
      import_aliases: company.import_aliases ?? "",
      address: company.address ?? "",
      city: company.city ?? "",
      state: company.state ?? "",
      pin_code: company.pin_code ?? "",
      contact_person: company.contact_person ?? "",
      email: company.email ?? "",
      phone: company.phone ?? "",
      default_tat_days: String(company.default_tat_days),
      is_active: company.is_active,
      notes: company.notes ?? "",
    });
    setErrors({});
    setCreating(true);
  }

  function closeModal() {
    setCreating(false);
    setEditing(null);
  }

  function submit() {
    const next: Record<string, string> = {};
    if (!form.code.trim()) next.code = "Code is required.";
    if (!form.name.trim()) next.name = "Name is required.";
    if (!form.short_name.trim()) next.short_name = "Short name is required.";
    setErrors(next);
    if (Object.keys(next).length) return;
    save.mutate(form);
  }

  const set = <K extends keyof CompanyForm>(key: K, value: CompanyForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <>
      <Card>
        <div className="filters">
          <div className="search">
            <Search />
            <input
              placeholder="Search company name, code or city…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {canManage && (
            <button className="primary" onClick={openCreate}>
              <Plus /> Add company
            </button>
          )}
        </div>

        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !visible.length ? (
          <Empty
            title="No companies found"
            detail="Add the banks and insurers that send you cases."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Company</th>
                  <th>Type</th>
                  <th>Import aliases</th>
                  <th>TAT</th>
                  <th>Cases</th>
                  <th>Templates</th>
                  <th>Status</th>
                  {canManage && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {visible.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <b>{c.short_name}</b>
                      <small>
                        {c.code} · {c.name}
                      </small>
                    </td>
                    <td>{titleCase(c.company_type)}</td>
                    <td className="aliases">
                      {c.import_aliases
                        ? c.import_aliases.split("|").slice(0, 4).join(", ")
                        : "—"}
                    </td>
                    <td>{c.default_tat_days} days</td>
                    <td>
                      <b>{num(c.total_cases)}</b>
                      <small>{num(c.open_cases)} open</small>
                    </td>
                    <td>
                      <small>
                        {c.form_template_count} form ·{" "}
                        {c.document_template_count} doc
                      </small>
                    </td>
                    <td>
                      <Status value={c.is_active ? "ACTIVE" : "INACTIVE"} />
                    </td>
                    {canManage && (
                      <td>
                        <button
                          className="icon-button"
                          title="Edit company"
                          onClick={() => openEdit(c)}
                        >
                          <Pencil />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={creating}
        wide
        title={editing ? `Edit ${editing.short_name}` : "Add company"}
        subtitle="Aliases are matched against the 'Co. Name' column of the daily import, separated by a pipe."
        onClose={closeModal}
        footer={
          <>
            <button className="secondary" onClick={closeModal}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={submit}
              disabled={save.isPending}
            >
              {save.isPending ? "Saving…" : editing ? "Save changes" : "Create company"}
            </button>
          </>
        }
      >
        <Form onSubmit={submit}>
          <FormGrid>
            <Field label="Code" required error={errors.code}>
              <TextInput
                value={form.code}
                onChange={(v) => set("code", v.toUpperCase())}
                placeholder="ICICI"
                disabled={Boolean(editing)}
              />
            </Field>
            <Field label="Short name" required error={errors.short_name}>
              <TextInput
                value={form.short_name}
                onChange={(v) => set("short_name", v)}
                placeholder="ICICI Prudential"
              />
            </Field>
            <Field label="Registered name" required span={2} error={errors.name}>
              <TextInput
                value={form.name}
                onChange={(v) => set("name", v)}
                placeholder="ICICI Prudential Life Insurance Company Limited"
              />
            </Field>
            <Field label="Company type">
              <SelectInput
                value={form.company_type}
                onChange={(v) => set("company_type", v)}
                options={asOptions(COMPANY_TYPES)}
                allowEmpty={false}
              />
            </Field>
            <Field label="Default TAT (days)">
              <TextInput
                type="number"
                min={1}
                max={365}
                value={form.default_tat_days}
                onChange={(v) => set("default_tat_days", v)}
              />
            </Field>
            <Field
              label="Import aliases"
              span={2}
              hint="Pipe separated, e.g. ICICI|ICICI Pru|IPRU"
            >
              <TextInput
                value={form.import_aliases}
                onChange={(v) => set("import_aliases", v)}
              />
            </Field>
            <Field label="Contact person">
              <TextInput
                value={form.contact_person}
                onChange={(v) => set("contact_person", v)}
              />
            </Field>
            <Field label="Phone">
              <TextInput value={form.phone} onChange={(v) => set("phone", v)} />
            </Field>
            <Field label="Email">
              <TextInput
                type="email"
                value={form.email}
                onChange={(v) => set("email", v)}
              />
            </Field>
            <Field label="City">
              <TextInput value={form.city} onChange={(v) => set("city", v)} />
            </Field>
            <Field label="State">
              <TextInput value={form.state} onChange={(v) => set("state", v)} />
            </Field>
            <Field label="PIN code">
              <TextInput
                value={form.pin_code}
                onChange={(v) => set("pin_code", v)}
              />
            </Field>
            <Field label="Address" span={2}>
              <TextArea
                value={form.address}
                onChange={(v) => set("address", v)}
                rows={2}
              />
            </Field>
            <Field label="Notes" span={2}>
              <TextArea
                value={form.notes}
                onChange={(v) => set("notes", v)}
                rows={2}
              />
            </Field>
            <Field label="Availability" span={2}>
              <Checkbox
                checked={form.is_active}
                onChange={(v) => set("is_active", v)}
                label="Active — new cases can be created for this company"
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}

/* ------------------------------------------------------------------ */
function CaseTypeTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<CaseType | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CaseTypeForm>(emptyCaseType);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const query = useQuery({
    queryKey: ["case-types", "all"],
    queryFn: () =>
      api
        .get<CaseType[]>("/case-types", { params: { include_inactive: true } })
        .then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: (payload: CaseTypeForm) => {
      const body = {
        ...payload,
        default_tat_days: Number(payload.default_tat_days) || 7,
        display_order: Number(payload.display_order) || 100,
        description: payload.description || null,
        import_aliases: payload.import_aliases || null,
      };
      return editing
        ? api.patch(`/case-types/${editing.id}`, body)
        : api.post("/case-types", body);
    },
    onSuccess: () => {
      toast.success(editing ? "Case type updated." : "Case type created.");
      client.invalidateQueries({ queryKey: ["case-types"] });
      setOpen(false);
      setEditing(null);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  function openCreate() {
    setEditing(null);
    setForm(emptyCaseType);
    setErrors({});
    setOpen(true);
  }

  function openEdit(row: CaseType) {
    setEditing(row);
    setForm({
      code: row.code,
      name: row.name,
      category: row.category,
      description: row.description ?? "",
      import_aliases: row.import_aliases ?? "",
      default_tat_days: String(row.default_tat_days),
      display_order: String(row.display_order),
      is_active: row.is_active,
    });
    setErrors({});
    setOpen(true);
  }

  function submit() {
    const next: Record<string, string> = {};
    if (!form.code.trim()) next.code = "Code is required.";
    if (!form.name.trim()) next.name = "Name is required.";
    setErrors(next);
    if (Object.keys(next).length) return;
    save.mutate(form);
  }

  const set = <K extends keyof CaseTypeForm>(key: K, value: CaseTypeForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  return (
    <>
      <Card>
        {canManage && (
          <div className="filters">
            <div className="filters-note">
              <Building2 />
              <span>
                Case types decide which company form and client document a case
                uses.
              </span>
            </div>
            <button className="primary" onClick={openCreate}>
              <Plus /> Add case type
            </button>
          </div>
        )}
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty title="No case types" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Case type</th>
                  <th>Module</th>
                  <th>Import aliases</th>
                  <th>TAT</th>
                  <th>Cases</th>
                  <th>Status</th>
                  {canManage && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {query.data.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <b>{t.name}</b>
                      <small>{t.code}</small>
                    </td>
                    <td>
                      <Status value={t.category} />
                    </td>
                    <td className="aliases">
                      {t.import_aliases
                        ? t.import_aliases.split("|").slice(0, 4).join(", ")
                        : "—"}
                    </td>
                    <td>{t.default_tat_days} days</td>
                    <td>{num(t.total_cases)}</td>
                    <td>
                      <Status value={t.is_active ? "ACTIVE" : "INACTIVE"} />
                    </td>
                    {canManage && (
                      <td>
                        <button
                          className="icon-button"
                          title="Edit case type"
                          onClick={() => openEdit(t)}
                        >
                          <Pencil />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={open}
        title={editing ? `Edit ${editing.name}` : "Add case type"}
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={submit}
              disabled={save.isPending}
            >
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </>
        }
      >
        <Form onSubmit={submit}>
          <FormGrid>
            <Field label="Code" required error={errors.code}>
              <TextInput
                value={form.code}
                onChange={(v) => set("code", v.toUpperCase().replaceAll(" ", "_"))}
                disabled={Boolean(editing)}
                placeholder="PRE_ISSUANCE"
              />
            </Field>
            <Field label="Name" required error={errors.name}>
              <TextInput value={form.name} onChange={(v) => set("name", v)} />
            </Field>
            <Field label="Module">
              <SelectInput
                value={form.category}
                onChange={(v) => set("category", v)}
                options={[
                  { value: "INVESTIGATION", label: "Investigation" },
                  { value: "DEATH_CLAIM", label: "Death Claim" },
                ]}
                allowEmpty={false}
              />
            </Field>
            <Field label="Default TAT (days)">
              <TextInput
                type="number"
                min={1}
                max={365}
                value={form.default_tat_days}
                onChange={(v) => set("default_tat_days", v)}
              />
            </Field>
            <Field label="Display order">
              <TextInput
                type="number"
                value={form.display_order}
                onChange={(v) => set("display_order", v)}
              />
            </Field>
            <Field label="Import aliases" span={2} hint="Pipe separated">
              <TextInput
                value={form.import_aliases}
                onChange={(v) => set("import_aliases", v)}
              />
            </Field>
            <Field label="Description" span={2}>
              <TextArea
                value={form.description}
                onChange={(v) => set("description", v)}
                rows={2}
              />
            </Field>
            <Field label="Availability" span={2}>
              <Checkbox
                checked={form.is_active}
                onChange={(v) => set("is_active", v)}
                label="Active"
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}
