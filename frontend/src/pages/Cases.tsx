import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  Download,
  FilterX,
  Plus,
  Search,
  UserRoundCheck,
} from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api, download, errorMessage, toParams } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  Online,
  PageHeader,
  Pagination,
  Status,
  fmtDate,
} from "../components";
import {
  Checkbox,
  Field,
  Form,
  FormGrid,
  Modal,
  SelectInput,
  TextArea,
  TextInput,
  useDebounced,
  useToast,
} from "../ui";
import {
  CASE_STATUSES,
  PRIORITIES,
  STATUS_LABELS,
  asOptions,
  titleCase,
  type CaseItem,
  type CaseType,
  type Company,
  type NavCategory,
  type Page,
  type Sidebar,
  type StaffStatus,
} from "../types";
import { OfficeAssignDialog } from "../office";

const TAT_STATES = [
  { value: "IN_TAT", label: "In TAT" },
  { value: "ABOUT_TO_BREACH", label: "About to breach" },
  { value: "OUT_OF_TAT", label: "Out of TAT" },
];

/** URL segment -> case category, so /investigation is a real route. */
const PATH_CATEGORY: Record<string, string> = {
  "/investigation": "INVESTIGATION",
  "/death-claim": "DEATH_CLAIM",
};

export default function Cases() {
  const [params] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { can } = useAuth();
  const toast = useToast();
  // The sidebar drives this page: the category comes from the path, the
  // company and status bucket from the querystring. Landing here from the
  // menu therefore needs no further filtering by hand.
  const category = PATH_CATEGORY[location.pathname] ?? params.get("category") ?? "";
  const scopedCompanyId = params.get("company_id") ?? "";
  const bucket = params.get("bucket") ?? "";
  const scopedCaseTypeId = params.get("case_type_id") ?? "";

  const [filters, setFilters] = useState({
    search: "",
    status: "",
    tat_state: "",
    company_id: "",
    case_type_id: "",
    priority: "",
    assigned_to_id: "",
    unassigned: "",
    received_from: "",
    received_to: "",
  });
  // Cases closed longer ago than the retention window drop out of the working
  // views. They are never deleted, so this brings them back when someone needs
  // to look one up.
  const [includeArchived, setIncludeArchived] = useState(false);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string[]>([]);
  const [dialog, setDialog] = useState<
    "create" | "bulk" | "office" | null
  >(null);
  const debouncedSearch = useDebounced(filters.search);

  const companies = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () => api.get<Company[]>("/companies").then((r) => r.data),
  });
  const caseTypes = useQuery({
    queryKey: ["case-types", "all"],
    queryFn: () => api.get<CaseType[]>("/case-types").then((r) => r.data),
  });
  const staff = useQuery({
    queryKey: ["staff", "status", "all"],
    queryFn: () =>
      api
        .get<StaffStatus[]>("/staff/status", {
          params: { only_assignable: false },
        })
        .then((r) => r.data),
    enabled: can("staff.view"),
  });

  const nav = useQuery({
    queryKey: ["navigation", "sidebar"],
    queryFn: () => api.get<Sidebar>("/navigation/sidebar").then((r) => r.data),
    staleTime: 30000,
  });

  const queryParams = toParams({
    category: category || undefined,
    company_id: scopedCompanyId || filters.company_id || undefined,
    case_type_id: scopedCaseTypeId || filters.case_type_id || undefined,
    bucket: filters.status ? undefined : bucket || undefined,
    search: debouncedSearch,
    status: filters.status || undefined,
    tat_state: filters.tat_state,
    priority: filters.priority,
    assigned_to_id: filters.assigned_to_id,
    unassigned: filters.unassigned === "yes" ? true : undefined,
    received_from: filters.received_from,
    received_to: filters.received_to,
    include_archived: includeArchived || undefined,
    page,
    page_size: 20,
  });

  const query = useQuery({
    queryKey: ["cases", queryParams],
    queryFn: () =>
      api.get<Page<CaseItem>>("/cases", { params: queryParams }).then((r) => r.data),
  });

  const set = (key: keyof typeof filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
    setSelected([]);
  };

  const clearFilters = () => {
    setFilters({
      search: "",
      status: "",
      tat_state: "",
      company_id: "",
      case_type_id: "",
      priority: "",
      assigned_to_id: "",
      unassigned: "",
      received_from: "",
      received_to: "",
    });
    setPage(1);
  };

  const activeFilters = Object.entries(filters).filter(
    ([, v]) => v !== "",
  ).length;

  const items = query.data?.items ?? [];
  const allSelected = items.length > 0 && selected.length === items.length;

  async function exportCases(format: "xlsx" | "csv") {
    try {
      const search = new URLSearchParams(
        toParams({ ...queryParams, page: undefined, page_size: undefined, format }) as Record<string, string>,
      );
      await download(`/cases/export?${search}`, `cases.${format}`);
      toast.success("Export downloaded.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  const branch: NavCategory | undefined = (nav.data?.categories ?? []).find(
    (c) => c.category === category,
  );
  const scopedCompany = branch?.companies.find((c) => c.id === scopedCompanyId);
  const scopedForm = scopedCompany?.forms.find(
    (f) => f.case_type_id === scopedCaseTypeId,
  );
  const bucketLabel =
    branch?.buckets.find((b) => b.key === bucket)?.label ?? "";

  // Same labels as the menu: the client's own file names.
  const formOptions = scopedCompany
    ? scopedCompany.forms.map((f) => ({ value: f.case_type_id, label: f.name }))
    : Array.from(
        new Map(
          (branch?.companies ?? [])
            .flatMap((c) => c.forms)
            .map((f) => [f.case_type_id, { value: f.case_type_id, label: f.name }]),
        ).values(),
      );

  const baseTitle =
    category === "DEATH_CLAIM"
      ? "Death claim cases"
      : category === "INVESTIGATION"
        ? "Investigation cases"
        : "All cases";
  // The heading mirrors the menu path the user clicked, so they can see at a
  // glance which of a company's several forms they are looking at.
  const title = scopedForm
    ? `${scopedCompany?.short_name} — ${scopedForm.name}`
    : scopedCompany
      ? `${scopedCompany.short_name} — ${category === "DEATH_CLAIM" ? "death claims" : "investigation"}`
      : baseTitle;
  const subtitle = bucketLabel && bucket !== "all"
    ? `Showing ${bucketLabel.toLowerCase()}. Filters below narrow this further.`
    : "Search, review, assign and track every case from receipt to completion.";

  return (
    <>
      <PageHeader
        title={title}
        subtitle={subtitle}
        actions={
          <>
            {can("case.export") && (
              <>
                <button
                  className="secondary"
                  onClick={() => exportCases("xlsx")}
                >
                  <Download /> Excel
                </button>
                <button className="secondary" onClick={() => exportCases("csv")}>
                  CSV
                </button>
              </>
            )}
            {can("case.create") && (
              <button className="primary" onClick={() => setDialog("create")}>
                <Plus /> New case
              </button>
            )}
          </>
        }
      />

      <Card>
        <div className="filters">
          <div className="search">
            <Search />
            <input
              placeholder="Search case no, KRN, policy, name or phone…"
              value={filters.search}
              onChange={(e) => set("search", e.target.value)}
            />
          </div>
          <SelectInput
            value={filters.status}
            onChange={(v) => set("status", v)}
            placeholder="All statuses"
            options={CASE_STATUSES.map((s) => ({
              value: s,
              label: STATUS_LABELS[s],
            }))}
          />
          <SelectInput
            value={filters.tat_state}
            onChange={(v) => set("tat_state", v)}
            placeholder="Any TAT"
            options={TAT_STATES}
          />
          <SelectInput
            value={scopedCompanyId || filters.company_id}
            onChange={(v) => {
              // Changing the company by hand leaves the sidebar's scope.
              if (scopedCompanyId) navigate(v ? `?company_id=${v}` : "");
              set("company_id", v);
            }}
            placeholder="All companies"
            options={(companies.data ?? []).map((c) => ({
              value: c.id,
              label: c.short_name,
            }))}
          />
          <SelectInput
            value={scopedCaseTypeId || filters.case_type_id}
            onChange={(v) => {
              if (scopedCaseTypeId || scopedCompanyId) {
                const next = new URLSearchParams();
                if (scopedCompanyId) next.set("company_id", scopedCompanyId);
                if (v) next.set("case_type_id", v);
                navigate(`?${next}`);
              }
              set("case_type_id", v);
            }}
            placeholder="All forms"
            options={formOptions}
          />
          <SelectInput
            value={filters.assigned_to_id}
            onChange={(v) => set("assigned_to_id", v)}
            placeholder="Any investigator"
            options={(staff.data ?? []).map((s) => ({
              value: s.id,
              label: s.full_name,
            }))}
          />
          <SelectInput
            value={filters.unassigned}
            onChange={(v) => set("unassigned", v)}
            placeholder="Assigned or not"
            options={[{ value: "yes", label: "Unassigned only" }]}
          />
          <SelectInput
            value={filters.priority}
            onChange={(v) => set("priority", v)}
            placeholder="Any priority"
            options={asOptions(PRIORITIES)}
          />
          <Field label="Received from">
            <TextInput
              type="date"
              value={filters.received_from}
              onChange={(v) => set("received_from", v)}
            />
          </Field>
          <Field label="Received to">
            <TextInput
              type="date"
              value={filters.received_to}
              onChange={(v) => set("received_to", v)}
            />
          </Field>
          <Checkbox
            checked={includeArchived}
            onChange={(next) => {
              setIncludeArchived(next);
              setPage(1);
            }}
            label="Include archived"
          />
          {activeFilters > 0 && (
            <button className="secondary" onClick={clearFilters}>
              <FilterX /> Clear ({activeFilters})
            </button>
          )}
        </div>

        {selected.length > 0 && can("case.assign") && (
          <div className="bulk-bar">
            <span>
              <b>{selected.length}</b> case{selected.length > 1 ? "s" : ""}{" "}
              selected
            </span>
            <button className="primary" onClick={() => setDialog("bulk")}>
              <UserRoundCheck /> Assign investigator
            </button>
            {can("case.assign_office") && (
              <button className="secondary" onClick={() => setDialog("office")}>
                <Building2 /> Assign to office
              </button>
            )}
            <button className="secondary" onClick={() => setSelected([])}>
              Clear selection
            </button>
          </div>
        )}

        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !items.length ? (
          <Empty
            title="No cases match these filters"
            detail="Adjust the filters, or import the daily file to create cases."
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="case-table">
                <thead>
                  <tr>
                    {can("case.assign") && (
                      <th className="tick">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          aria-label="Select all on this page"
                          onChange={(e) =>
                            setSelected(
                              e.target.checked ? items.map((c) => c.id) : [],
                            )
                          }
                        />
                      </th>
                    )}
                    <th>Case reference</th>
                    <th>Customer / LA</th>
                    <th>Company</th>
                    <th>Status</th>
                    <th>Outcome</th>
                    <th>Investigator</th>
                    <th>Office staff</th>
                    <th>TAT</th>
                    <th>Received</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr key={c.id}>
                      {can("case.assign") && (
                        <td className="tick">
                          <input
                            type="checkbox"
                            checked={selected.includes(c.id)}
                            aria-label={`Select ${c.case_number}`}
                            onChange={(e) =>
                              setSelected((list) =>
                                e.target.checked
                                  ? [...list, c.id]
                                  : list.filter((x) => x !== c.id),
                              )
                            }
                          />
                        </td>
                      )}
                      <td>
                        <Link to={`/cases/${c.id}`}>
                          <b>{c.case_number}</b>
                        </Link>
                        <small>{c.case_type_name}</small>
                      </td>
                      <td>
                        <b>{c.life_assured_name}</b>
                        <small>
                          {c.policy_number || c.krn_no || "No reference"}
                        </small>
                      </td>
                      <td>
                        <span className="company-chip">{c.company_code}</span>
                      </td>
                      <td>
                        <Status value={c.status} label={c.status_label} />
                      </td>
                      <td>
                        {c.outcome ? (
                          <Status value={c.outcome} />
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        {c.assigned_to ? (
                          <>
                            <span>{c.assigned_to.full_name}</span>
                            <Online online={c.assigned_to.is_online} />
                          </>
                        ) : (
                          <span className="muted">Unassigned</span>
                        )}
                      </td>
                      <td>
                        {c.office_staff ? (
                          <>
                            <span>{c.office_staff.full_name}</span>
                            <Online online={c.office_staff.is_online} />
                          </>
                        ) : c.status === "AWAITING_OFFICE_ASSIGNMENT" ? (
                          <span className="pill lock">Awaiting office</span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>
                        <Status value={c.tat_state} />
                        <small>{c.aging_days} days aging</small>
                      </td>
                      <td>{fmtDate(c.received_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {query.data && (
              <Pagination
                page={query.data.meta.page}
                totalPages={query.data.meta.total_pages}
                onPage={setPage}
              />
            )}
          </>
        )}
      </Card>

      <CreateCaseDialog
        open={dialog === "create"}
        companies={companies.data ?? []}
        caseTypes={caseTypes.data ?? []}
        onClose={() => setDialog(null)}
      />
      <BulkAssignDialog
        open={dialog === "bulk"}
        caseIds={selected}
        onClose={() => setDialog(null)}
        onDone={() => setSelected([])}
      />
      <OfficeAssignDialog
        open={dialog === "office"}
        caseIds={selected}
        onClose={() => setDialog(null)}
        onDone={() => setSelected([])}
      />
    </>
  );
}

/* ------------------------------------------------------------------ */
function CreateCaseDialog({
  open,
  companies,
  caseTypes,
  onClose,
}: {
  open: boolean;
  companies: Company[];
  caseTypes: CaseType[];
  onClose: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState({
    company_id: "",
    case_type_id: "",
    life_assured_name: "",
    policy_number: "",
    application_number: "",
    krn_no: "",
    contact_number: "",
    address: "",
    city: "",
    state: "",
    pin_code: "",
    priority: "NORMAL",
    received_at: new Date().toISOString().slice(0, 10),
  });

  const create = useMutation({
    mutationFn: () =>
      api
        .post("/cases", {
          ...form,
          received_at: form.received_at
            ? new Date(form.received_at).toISOString()
            : null,
          policy_number: form.policy_number || null,
          application_number: form.application_number || null,
          krn_no: form.krn_no || null,
          contact_number: form.contact_number || null,
          address: form.address || null,
          city: form.city || null,
          state: form.state || null,
          pin_code: form.pin_code || null,
        })
        .then((r) => r.data as { case_number: string }),
    onSuccess: (data) => {
      toast.success(`Case ${data.case_number} created.`);
      client.invalidateQueries({ queryKey: ["cases"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const set = (key: keyof typeof form, value: string) =>
    setForm((f) => ({ ...f, [key]: value }));

  const valid =
    form.company_id &&
    form.case_type_id &&
    form.life_assured_name.trim().length >= 2;

  return (
    <Modal
      open={open}
      wide
      title="Create case manually"
      subtitle="Most cases arrive through the daily import; use this for one-off assignments."
      onClose={onClose}
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            onClick={() => create.mutate()}
            disabled={create.isPending || !valid}
          >
            {create.isPending ? "Creating…" : "Create case"}
          </button>
        </>
      }
    >
      <Form onSubmit={() => create.mutate()}>
        <FormGrid>
          <Field label="Company" required>
            <SelectInput
              value={form.company_id}
              onChange={(v) => set("company_id", v)}
              options={companies.map((c) => ({
                value: c.id,
                label: c.short_name,
              }))}
            />
          </Field>
          <Field label="Case type" required>
            <SelectInput
              value={form.case_type_id}
              onChange={(v) => set("case_type_id", v)}
              options={caseTypes.map((t) => ({
                value: t.id,
                label: `${t.name} (${titleCase(t.category)})`,
              }))}
            />
          </Field>
          <Field label="Life assured name" required span={2}>
            <TextInput
              value={form.life_assured_name}
              onChange={(v) => set("life_assured_name", v)}
            />
          </Field>
          <Field label="Policy number">
            <TextInput
              value={form.policy_number}
              onChange={(v) => set("policy_number", v)}
            />
          </Field>
          <Field label="Application number">
            <TextInput
              value={form.application_number}
              onChange={(v) => set("application_number", v)}
            />
          </Field>
          <Field label="KRN">
            <TextInput value={form.krn_no} onChange={(v) => set("krn_no", v)} />
          </Field>
          <Field label="Contact number">
            <TextInput
              value={form.contact_number}
              onChange={(v) => set("contact_number", v)}
            />
          </Field>
          <Field label="Address" span={2}>
            <TextArea
              value={form.address}
              onChange={(v) => set("address", v)}
              rows={2}
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
          <Field label="Priority">
            <SelectInput
              value={form.priority}
              onChange={(v) => set("priority", v)}
              options={asOptions(PRIORITIES)}
              allowEmpty={false}
            />
          </Field>
          <Field label="Received date">
            <TextInput
              type="date"
              value={form.received_at}
              onChange={(v) => set("received_at", v)}
            />
          </Field>
        </FormGrid>
      </Form>
    </Modal>
  );
}

function BulkAssignDialog({
  open,
  caseIds,
  onClose,
  onDone,
}: {
  open: boolean;
  caseIds: string[];
  onClose: () => void;
  onDone: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [assignee, setAssignee] = useState("");
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
      api
        .post("/cases/bulk-assign", {
          case_ids: caseIds,
          assigned_to_id: assignee,
          notes: notes || null,
        })
        .then((r) => r.data as { message: string; detail?: string }),
    onSuccess: (data) => {
      toast.success(data.message);
      if (data.detail) toast.info(data.detail);
      client.invalidateQueries({ queryKey: ["cases"] });
      onDone();
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Modal
      open={open}
      title={`Assign ${caseIds.length} case${caseIds.length > 1 ? "s" : ""}`}
      subtitle="Cases that cannot be assigned are reported back and left unchanged."
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
            {assign.isPending ? "Assigning…" : "Assign all"}
          </button>
        </>
      }
    >
      <Form onSubmit={() => assign.mutate()}>
        <FormGrid>
          <Field label="Investigator" required span={2}>
            <SelectInput
              value={assignee}
              onChange={setAssignee}
              placeholder="Select an investigator…"
              options={(staff.data ?? []).map((s) => ({
                value: s.id,
                label: `${s.full_name} — ${s.status_label}, ${s.open_cases} open`,
              }))}
            />
          </Field>
          <Field label="Notes" span={2}>
            <TextArea value={notes} onChange={setNotes} rows={2} />
          </Field>
        </FormGrid>
      </Form>
    </Modal>
  );
}
