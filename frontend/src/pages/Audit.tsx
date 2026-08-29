import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Search, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api, errorMessage, toParams } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Pagination,
  Status,
  fmtDateTime,
} from "../components";
import {
  Field,
  Modal,
  PermissionDenied,
  SelectInput,
  TextInput,
  useDebounced,
} from "../ui";
import { titleCase, type AuditLog, type Page } from "../types";

const ACTIONS = [
  "LOGIN",
  "LOGIN_FAILED",
  "LOGOUT",
  "PASSWORD_CHANGED",
  "CASE_CREATED",
  "CASE_IMPORTED",
  "CASE_UPDATED",
  "CASE_ASSIGNED",
  "CASE_REASSIGNED",
  "CASE_STATUS_CHANGED",
  "CASE_DELETED",
  "FORM_UPDATED",
  "FORM_SUBMITTED",
  "DOCUMENT_UPLOADED",
  "DOCUMENT_DELETED",
  "DOCUMENT_GENERATED",
  "IMPORT_CREATED",
  "IMPORT_COMMITTED",
  "IMPORT_ROLLED_BACK",
  "STAFF_CREATED",
  "STAFF_UPDATED",
  "STAFF_DISABLED",
  "ROLE_CHANGED",
  "PERMISSION_CHANGED",
  "SETTINGS_CHANGED",
  "COMPANY_CHANGED",
  "TEMPLATE_CHANGED",
  "EXPORT_RUN",
  "DATA_PURGED",
];

export default function Audit() {
  const { can } = useAuth();
  const [filters, setFilters] = useState({
    action: "",
    module: "",
    date_from: "",
    date_to: "",
    search: "",
  });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<AuditLog | null>(null);
  const debouncedSearch = useDebounced(filters.search);

  const modules = useQuery({
    queryKey: ["audit", "modules"],
    queryFn: () => api.get<string[]>("/audit-logs/modules").then((r) => r.data),
    enabled: can("audit.view"),
  });

  const query = useQuery({
    queryKey: ["audit", filters.action, filters.module, filters.date_from, filters.date_to, debouncedSearch, page],
    enabled: can("audit.view"),
    queryFn: () =>
      api
        .get<Page<AuditLog>>("/audit-logs", {
          params: toParams({
            action: filters.action,
            module: filters.module,
            date_from: filters.date_from,
            date_to: filters.date_to,
            search: debouncedSearch,
            page,
            page_size: 30,
          }),
        })
        .then((r) => r.data),
  });

  if (!can("audit.view")) return <PermissionDenied what="audit logs" />;

  const set = (key: keyof typeof filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  return (
    <>
      <PageHeader
        title="Audit log"
        subtitle="Every login, assignment, status change, import and document generation. Passwords and tokens are never recorded."
      />

      <Card>
        <div className="filters">
          <div className="search">
            <Search />
            <input
              placeholder="Search entity, actor or remark…"
              value={filters.search}
              onChange={(e) => set("search", e.target.value)}
            />
          </div>
          <Field label="Action">
            <SelectInput
              value={filters.action}
              onChange={(v) => set("action", v)}
              placeholder="All actions"
              options={ACTIONS.map((a) => ({ value: a, label: titleCase(a) }))}
            />
          </Field>
          <Field label="Module">
            <SelectInput
              value={filters.module}
              onChange={(v) => set("module", v)}
              placeholder="All modules"
              options={(modules.data ?? []).map((m) => ({
                value: m,
                label: m,
              }))}
            />
          </Field>
          <Field label="From">
            <TextInput
              type="date"
              value={filters.date_from}
              onChange={(v) => set("date_from", v)}
            />
          </Field>
          <Field label="To">
            <TextInput
              type="date"
              value={filters.date_to}
              onChange={(v) => set("date_to", v)}
            />
          </Field>
        </div>

        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !query.data?.items.length ? (
          <Empty
            title="No audit entries"
            detail="Nothing matches these filters."
          />
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Module</th>
                    <th>Entity</th>
                    <th>Remarks</th>
                    <th aria-label="Details" />
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((row) => (
                    <tr key={row.id}>
                      <td>{fmtDateTime(row.created_at)}</td>
                      <td>
                        <b>{row.actor_label || "System"}</b>
                        {row.ip_address && <small>{row.ip_address}</small>}
                      </td>
                      <td>
                        <Status value={row.action} label={titleCase(row.action)} />
                      </td>
                      <td>{row.module}</td>
                      <td>
                        {row.entity_label || row.entity_type || "—"}
                        {row.entity_type && row.entity_label && (
                          <small>{row.entity_type}</small>
                        )}
                      </td>
                      <td className="wrap">{row.remarks || "—"}</td>
                      <td>
                        <button
                          className="icon-button"
                          title="View change detail"
                          onClick={() => setSelected(row)}
                        >
                          <ChevronRight />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={query.data.meta.page}
              totalPages={query.data.meta.total_pages}
              onPage={setPage}
            />
          </>
        )}
      </Card>

      <Modal
        open={Boolean(selected)}
        wide
        title={selected ? titleCase(selected.action) : "Audit entry"}
        subtitle={
          selected
            ? `${selected.actor_label || "System"} · ${fmtDateTime(selected.created_at)}`
            : undefined
        }
        onClose={() => setSelected(null)}
      >
        {selected && (
          <div className="audit-detail">
            <dl className="details">
              <div>
                <dt>Module</dt>
                <dd>{selected.module}</dd>
              </div>
              <div>
                <dt>Entity</dt>
                <dd>
                  {selected.entity_label || "—"}
                  {selected.entity_type ? ` (${selected.entity_type})` : ""}
                </dd>
              </div>
              <div>
                <dt>Request</dt>
                <dd>
                  {selected.request_method || "—"} {selected.request_path || ""}
                </dd>
              </div>
              <div>
                <dt>IP address</dt>
                <dd>{selected.ip_address || "—"}</dd>
              </div>
            </dl>
            {selected.remarks && (
              <p className="audit-remark">{selected.remarks}</p>
            )}
            <div className="diff-grid">
              <div>
                <h4>Before</h4>
                <pre>
                  {selected.old_values
                    ? JSON.stringify(selected.old_values, null, 2)
                    : "—"}
                </pre>
              </div>
              <div>
                <h4>After</h4>
                <pre>
                  {selected.new_values
                    ? JSON.stringify(selected.new_values, null, 2)
                    : "—"}
                </pre>
              </div>
            </div>
            <p className="audit-footnote">
              <ShieldCheck /> Passwords, tokens and session secrets are stripped
              before an entry is written.
            </p>
          </div>
        )}
      </Modal>
    </>
  );
}
