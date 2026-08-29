import { useQuery } from "@tanstack/react-query";
import { Download, FileSpreadsheet } from "lucide-react";
import { useState } from "react";
import { api, download, errorMessage, toParams } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  Online,
  PageHeader,
  Status,
  fmtDateTime,
  num,
} from "../components";
import {
  Field,
  PermissionDenied,
  SelectInput,
  Tabs,
  TextInput,
  useToast,
} from "../ui";
import type {
  CaseType,
  Company,
  CompanyPerformance,
  DistributionItem,
  ImportReportRow,
  StaffPerformance,
} from "../types";

const daysAgo = (n: number) =>
  new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);
const today = () => new Date().toISOString().slice(0, 10);

export default function Reports() {
  const { can } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState("cases");
  const [filters, setFilters] = useState({
    date_from: daysAgo(30),
    date_to: today(),
    company_id: "",
    case_type_id: "",
    category: "",
  });

  const companies = useQuery({
    queryKey: ["companies", "all"],
    queryFn: () => api.get<Company[]>("/companies").then((r) => r.data),
  });
  const caseTypes = useQuery({
    queryKey: ["case-types", "all"],
    queryFn: () => api.get<CaseType[]>("/case-types").then((r) => r.data),
  });

  if (!can("reports.view")) return <PermissionDenied what="reports" />;
  const canExport = can("reports.export");

  const params = toParams(filters);
  const set = (key: keyof typeof filters, value: string) =>
    setFilters((f) => ({ ...f, [key]: value }));

  async function exportTo(path: string, name: string) {
    try {
      await download(path, name);
      toast.success("Export downloaded.");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Case, company, investigator and import performance — every figure computed in the database."
        actions={
          canExport && (
            <button
              className="secondary"
              onClick={() =>
                exportTo(
                  `/reports/cases/export?${new URLSearchParams(
                    params as Record<string, string>,
                  )}&format=xlsx`,
                  "case_report.xlsx",
                )
              }
            >
              <FileSpreadsheet /> Export case report
            </button>
          )
        }
      />

      <Card>
        <div className="filters">
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
          <Field label="Company">
            <SelectInput
              value={filters.company_id}
              onChange={(v) => set("company_id", v)}
              placeholder="All companies"
              options={(companies.data ?? []).map((c) => ({
                value: c.id,
                label: c.short_name,
              }))}
            />
          </Field>
          <Field label="Case type">
            <SelectInput
              value={filters.case_type_id}
              onChange={(v) => set("case_type_id", v)}
              placeholder="All case types"
              options={(caseTypes.data ?? []).map((c) => ({
                value: c.id,
                label: c.name,
              }))}
            />
          </Field>
          <Field label="Module">
            <SelectInput
              value={filters.category}
              onChange={(v) => set("category", v)}
              placeholder="All modules"
              options={[
                { value: "INVESTIGATION", label: "Investigation" },
                { value: "DEATH_CLAIM", label: "Death Claim" },
              ]}
            />
          </Field>
        </div>
      </Card>

      <Tabs
        tabs={[
          { key: "cases", label: "Case status" },
          { key: "company", label: "Company" },
          { key: "investigator", label: "Investigator" },
          { key: "imports", label: "Imports" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "cases" && <CaseStatusReport params={params} />}
      {tab === "company" && (
        <CompanyReport
          params={params}
          canExport={canExport}
          onExport={() =>
            exportTo(
              `/reports/company/export?${new URLSearchParams(
                params as Record<string, string>,
              )}`,
              "company_report.xlsx",
            )
          }
        />
      )}
      {tab === "investigator" && (
        <InvestigatorReport
          params={params}
          canExport={canExport}
          onExport={() =>
            exportTo(
              `/reports/investigator/export?${new URLSearchParams(
                params as Record<string, string>,
              )}`,
              "staff_performance.xlsx",
            )
          }
        />
      )}
      {tab === "imports" && (
        <ImportReport
          canExport={canExport}
          onExport={() =>
            exportTo("/reports/imports/export", "import_report.xlsx")
          }
        />
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
function CaseStatusReport({ params }: { params: Record<string, unknown> }) {
  const query = useQuery({
    queryKey: ["report", "case-status", params],
    queryFn: () =>
      api
        .get<DistributionItem[]>("/reports/case-status", { params })
        .then((r) => r.data),
  });

  if (query.isLoading) return <Loading />;
  if (query.isError) return <ErrorState message={errorMessage(query.error)} />;
  if (!query.data?.length) return <Empty title="No cases in this range" />;

  const total = query.data.reduce((a, x) => a + x.value, 0);

  return (
    <Card title={`Case status distribution · ${num(total)} cases`}>
      <div className="bar-report">
        {query.data.map((row) => (
          <div className="bar-row" key={row.key}>
            <span className="bar-label">{row.label}</span>
            <div className="bar-track">
              <div
                className={`bar-fill tone-${row.key.toLowerCase()}`}
                style={{ width: `${Math.max(row.percent, 1.5)}%` }}
              />
            </div>
            <span className="bar-value">
              <b>{num(row.value)}</b>
              <small>{row.percent}%</small>
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function CompanyReport({
  params,
  canExport,
  onExport,
}: {
  params: Record<string, unknown>;
  canExport: boolean;
  onExport: () => void;
}) {
  const query = useQuery({
    queryKey: ["report", "company", params],
    queryFn: () =>
      api
        .get<CompanyPerformance[]>("/reports/company", { params })
        .then((r) => r.data),
  });

  return (
    <Card
      title="Company performance"
      action={
        canExport && (
          <button className="secondary" onClick={onExport}>
            <Download /> Export
          </button>
        )
      }
    >
      {query.isLoading ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} />
      ) : !query.data?.length ? (
        <Empty title="No data for this range" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Total</th>
                <th>Unassigned</th>
                <th>WIP</th>
                <th>RIP</th>
                <th>Completed</th>
                <th>Overdue</th>
                <th>Positive</th>
                <th>Negative</th>
                <th>Suspicious</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((row) => (
                <tr key={row.company_id}>
                  <td>
                    <b>{row.company_name}</b>
                    <small>{row.company_code}</small>
                  </td>
                  <td>{num(row.total)}</td>
                  <td>{num(row.unassigned)}</td>
                  <td>{num(row.wip)}</td>
                  <td>{num(row.rip)}</td>
                  <td>{num(row.completed)}</td>
                  <td className={row.overdue ? "danger-text" : ""}>
                    {num(row.overdue)}
                  </td>
                  <td>{num(row.positive)}</td>
                  <td>{num(row.negative)}</td>
                  <td>{num(row.suspicious)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function InvestigatorReport({
  params,
  canExport,
  onExport,
}: {
  params: Record<string, unknown>;
  canExport: boolean;
  onExport: () => void;
}) {
  const query = useQuery({
    queryKey: ["report", "investigator", params],
    queryFn: () =>
      api
        .get<StaffPerformance[]>("/reports/investigator", { params })
        .then((r) => r.data),
  });

  return (
    <Card
      title="Investigator performance"
      action={
        canExport && (
          <button className="secondary" onClick={onExport}>
            <Download /> Export
          </button>
        )
      }
    >
      {query.isLoading ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} />
      ) : !query.data?.length ? (
        <Empty title="No assigned cases in this range" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Investigator</th>
                <th>Availability</th>
                <th>Assigned</th>
                <th>WIP</th>
                <th>RIP</th>
                <th>Pending</th>
                <th>Completed</th>
                <th>Overdue</th>
                <th>Completion</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((row) => (
                <tr key={row.staff_id}>
                  <td>
                    <b>{row.full_name}</b>
                    <small>{row.staff_category.replace("_", " ")}</small>
                  </td>
                  <td>
                    <Online online={row.is_online} />
                  </td>
                  <td>{num(row.assigned)}</td>
                  <td>{num(row.in_progress)}</td>
                  <td>{num(row.report_in_progress)}</td>
                  <td>{num(row.pending)}</td>
                  <td>{num(row.completed)}</td>
                  <td className={row.overdue ? "danger-text" : ""}>
                    {num(row.overdue)}
                  </td>
                  <td>
                    <div className="mini-meter">
                      <div
                        className="mini-fill"
                        style={{ width: `${row.completion_rate}%` }}
                      />
                    </div>
                    <small>{row.completion_rate}%</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function ImportReport({
  canExport,
  onExport,
}: {
  canExport: boolean;
  onExport: () => void;
}) {
  const query = useQuery({
    queryKey: ["report", "imports"],
    queryFn: () =>
      api.get<ImportReportRow[]>("/reports/imports").then((r) => r.data),
  });

  return (
    <Card
      title="Import history"
      action={
        canExport && (
          <button className="secondary" onClick={onExport}>
            <Download /> Export
          </button>
        )
      }
    >
      {query.isLoading ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} />
      ) : !query.data?.length ? (
        <Empty title="No imports yet" />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Batch</th>
                <th>File</th>
                <th>Uploaded by</th>
                <th>When</th>
                <th>Rows</th>
                <th>Imported</th>
                <th>Errors</th>
                <th>Duplicates</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {query.data.map((row) => (
                <tr key={row.batch_number}>
                  <td>
                    <b>{row.batch_number}</b>
                  </td>
                  <td>{row.filename}</td>
                  <td>{row.uploaded_by || "—"}</td>
                  <td>{fmtDateTime(row.created_at)}</td>
                  <td>{num(row.total_rows)}</td>
                  <td>{num(row.imported_rows)}</td>
                  <td className={row.error_rows ? "danger-text" : ""}>
                    {num(row.error_rows)}
                  </td>
                  <td>{num(row.duplicate_rows)}</td>
                  <td>
                    <Status value={row.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
