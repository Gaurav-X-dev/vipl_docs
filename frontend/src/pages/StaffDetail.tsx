import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, KeyRound, Power, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
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
  fmtDateTime,
} from "../components";
import { ConfirmDialog, Tabs, useToast } from "../ui";
import { titleCase } from "../types";
import type {
  CaseItem,
  Page,
  StaffDetail as StaffDetailType,
  StaffPerformance,
} from "../types";

type SessionRow = {
  id: string;
  ip_address?: string;
  device_label?: string;
  started_at: string;
  last_seen_at: string;
  ended_at?: string;
  is_active: boolean;
};

type LoginAttemptRow = {
  id: string;
  email: string;
  successful: boolean;
  failure_reason?: string;
  ip_address?: string;
  created_at: string;
};

export default function StaffDetail() {
  const { id = "" } = useParams();
  const { can } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState("overview");
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<"disable" | "enable" | "reset" | null>(
    null,
  );

  const detail = useQuery({
    queryKey: ["staff", id],
    queryFn: () =>
      api.get<StaffDetailType>(`/staff/${id}`).then((r) => r.data),
  });

  const cases = useQuery({
    queryKey: ["staff", id, "cases", page],
    enabled: tab === "cases",
    queryFn: () =>
      api
        .get<Page<CaseItem>>(`/staff/${id}/cases`, {
          params: { page, page_size: 15 },
        })
        .then((r) => r.data),
  });

  const performance = useQuery({
    queryKey: ["staff", id, "performance"],
    enabled: tab === "performance",
    queryFn: () =>
      api
        .get<StaffPerformance>(`/staff/${id}/performance`)
        .then((r) => r.data),
  });

  const sessions = useQuery({
    queryKey: ["staff", id, "activity"],
    enabled: tab === "activity",
    queryFn: () =>
      api.get<SessionRow[]>(`/staff/${id}/activity`).then((r) => r.data),
  });

  const attempts = useQuery({
    queryKey: ["staff", id, "attempts"],
    enabled: tab === "activity",
    queryFn: () =>
      api
        .get<LoginAttemptRow[]>(`/staff/${id}/login-attempts`)
        .then((r) => r.data),
  });

  const toggle = useMutation({
    mutationFn: (action: "disable" | "enable") =>
      api.post(`/staff/${id}/${action}`).then((r) => r.data),
    onSuccess: () => {
      toast.success("Account updated.");
      client.invalidateQueries({ queryKey: ["staff"] });
      setConfirm(null);
    },
    onError: (e) => {
      toast.error(errorMessage(e));
      setConfirm(null);
    },
  });

  const reset = useMutation({
    mutationFn: () =>
      api
        .post(`/staff/${id}/reset-password`, {
          user_id: detail.data?.user_id,
          require_change_on_login: true,
        })
        .then((r) => r.data as { message: string; detail?: string }),
    onSuccess: (data) => {
      toast.success(data.detail || data.message);
      setConfirm(null);
    },
    onError: (e) => {
      toast.error(errorMessage(e));
      setConfirm(null);
    },
  });

  if (detail.isLoading) return <Loading />;
  if (detail.isError || !detail.data)
    return <ErrorState message={errorMessage(detail.error)} />;

  const s = detail.data;
  const canEdit = can("staff.edit");
  const canDisable = can("staff.disable");

  return (
    <>
      <Link to="/staff" className="back">
        <ArrowLeft /> Back to staff
      </Link>
      <PageHeader
        title={s.full_name}
        subtitle={`${s.employee_code} · ${s.designation || titleCase(s.staff_category)}`}
        actions={
          <>
            {canEdit && (
              <button
                className="secondary"
                onClick={() => setConfirm("reset")}
                disabled={!s.user_id}
              >
                <KeyRound /> Reset password
              </button>
            )}
            {canDisable && (
              <button
                className={s.is_active ? "danger" : "primary"}
                onClick={() => setConfirm(s.is_active ? "disable" : "enable")}
              >
                <Power /> {s.is_active ? "Disable account" : "Enable account"}
              </button>
            )}
          </>
        }
      />

      <div className="case-hero">
        <div>
          <span className="company-logo">
            {s.full_name
              .split(" ")
              .map((x) => x[0])
              .slice(0, 2)
              .join("")}
          </span>
          <span>
            <b>{s.email || "No email"}</b>
            <small>{s.mobile || "No mobile"}</small>
          </span>
        </div>
        <Online online={s.is_online} label={s.status_label} />
        <div>
          <span>Open cases</span>
          <b>{s.open_cases}</b>
        </div>
        <div>
          <span>Completed</span>
          <b>{s.completed_cases}</b>
        </div>
        <div>
          <span>Overdue</span>
          <b className={s.overdue_cases ? "danger-text" : ""}>
            {s.overdue_cases}
          </b>
        </div>
      </div>

      <Tabs
        tabs={[
          { key: "overview", label: "Overview" },
          { key: "cases", label: "Cases" },
          { key: "performance", label: "Performance" },
          { key: "activity", label: "Login activity" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" && (
        <div className="detail-grid">
          <Card title="Employment">
            <dl className="details">
              {[
                ["Employee code", s.employee_code],
                ["Department", s.department],
                ["Designation", s.designation],
                ["Category", titleCase(s.staff_category)],
                ["Employment status", titleCase(s.employment_status)],
                ["Reporting manager", s.reporting_manager],
                ["Joining date", fmtDate(s.joining_date)],
                ["Exit date", s.exit_date ? fmtDate(s.exit_date) : null],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt>{k}</dt>
                  <dd>{v || "—"}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card title="Contact & location">
            <dl className="details">
              {[
                ["Email", s.email],
                ["Mobile", s.mobile],
                ["Alternate mobile", s.alternate_mobile],
                ["Address", [s.address_line1, s.address_line2].filter(Boolean).join(", ")],
                ["City / State", [s.city, s.state].filter(Boolean).join(", ")],
                ["PIN code", s.pin_code],
                ["Base location", [s.base_city, s.base_state].filter(Boolean).join(", ")],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt>{k}</dt>
                  <dd>{v || "—"}</dd>
                </div>
              ))}
            </dl>
          </Card>
          <Card title="Access">
            <dl className="details">
              <div>
                <dt>Roles</dt>
                <dd>{s.roles.join(", ") || "No role assigned"}</dd>
              </div>
              <div>
                <dt>Login enabled</dt>
                <dd>{s.login_enabled ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt>Must change password</dt>
                <dd>{s.must_change_password ? "Yes" : "No"}</dd>
              </div>
              <div>
                <dt>Last login</dt>
                <dd>{fmtDateTime(s.last_login_at)}</dd>
              </div>
              <div>
                <dt>Last activity</dt>
                <dd>{fmtDateTime(s.last_activity_at)}</dd>
              </div>
              <div>
                <dt>Last logout</dt>
                <dd>{fmtDateTime(s.last_logout_at)}</dd>
              </div>
              <div>
                <dt>Last login IP</dt>
                <dd>{s.last_login_ip || "—"}</dd>
              </div>
            </dl>
          </Card>
          {s.notes && (
            <Card title="Notes" className="wide">
              <p className="wrap">{s.notes}</p>
            </Card>
          )}
        </div>
      )}

      {tab === "cases" && (
        <Card title="Assigned cases">
          {cases.isLoading ? (
            <Loading />
          ) : cases.isError ? (
            <ErrorState message={errorMessage(cases.error)} />
          ) : !cases.data?.items.length ? (
            <Empty title="No cases assigned" />
          ) : (
            <>
              <div className="table-scroll">
                <table className="case-table">
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>Life assured</th>
                      <th>Company</th>
                      <th>Status</th>
                      <th>TAT</th>
                      <th>Received</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.data.items.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <Link to={`/cases/${c.id}`}>
                            <b>{c.case_number}</b>
                          </Link>
                          <small>{c.case_type_name}</small>
                        </td>
                        <td>{c.life_assured_name}</td>
                        <td>
                          <span className="company-chip">{c.company_code}</span>
                        </td>
                        <td>
                          <Status value={c.status} label={c.status_label} />
                        </td>
                        <td>
                          <Status value={c.tat_state} />
                        </td>
                        <td>{fmtDate(c.received_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination
                page={cases.data.meta.page}
                totalPages={cases.data.meta.total_pages}
                onPage={setPage}
              />
            </>
          )}
        </Card>
      )}

      {tab === "performance" && (
        <Card title="Performance">
          {performance.isLoading ? (
            <Loading />
          ) : performance.isError ? (
            <ErrorState message={errorMessage(performance.error)} />
          ) : performance.data ? (
            <div className="kpi-grid compact">
              {[
                ["Assigned", performance.data.assigned],
                ["Work in progress", performance.data.in_progress],
                ["Report in progress", performance.data.report_in_progress],
                ["Pending", performance.data.pending],
                ["Completed", performance.data.completed],
                ["Overdue", performance.data.overdue],
                ["Positive", performance.data.positive],
                ["Negative", performance.data.negative],
                ["Suspicious", performance.data.suspicious],
                ["Completion rate", `${performance.data.completion_rate}%`],
              ].map(([label, value]) => (
                <Card className="kpi" key={String(label)}>
                  <div>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <Empty title="No performance data" />
          )}
        </Card>
      )}

      {tab === "activity" && (
        <>
          <Card title="Sessions">
            {sessions.isLoading ? (
              <Loading />
            ) : !sessions.data?.length ? (
              <Empty title="No sessions recorded" />
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Started</th>
                      <th>Last seen</th>
                      <th>Ended</th>
                      <th>Device</th>
                      <th>IP</th>
                      <th>State</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.data.map((row) => (
                      <tr key={row.id}>
                        <td>{fmtDateTime(row.started_at)}</td>
                        <td>{fmtDateTime(row.last_seen_at)}</td>
                        <td>{fmtDateTime(row.ended_at)}</td>
                        <td>{row.device_label || "—"}</td>
                        <td>{row.ip_address || "—"}</td>
                        <td>
                          <Status value={row.is_active ? "ACTIVE" : "ENDED"} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card title="Login attempts">
            {attempts.isLoading ? (
              <Loading />
            ) : !attempts.data?.length ? (
              <Empty title="No login attempts recorded" />
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Result</th>
                      <th>Reason</th>
                      <th>IP</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attempts.data.map((row) => (
                      <tr key={row.id}>
                        <td>{fmtDateTime(row.created_at)}</td>
                        <td>
                          <Status
                            value={row.successful ? "SUCCESS" : "FAILED"}
                          />
                        </td>
                        <td>{row.failure_reason || "—"}</td>
                        <td>{row.ip_address || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <p className="audit-footnote">
            <ShieldCheck /> The green online indicator is driven by the activity
            heartbeat, not by a sticky flag set at login.
          </p>
        </>
      )}

      <ConfirmDialog
        open={confirm === "disable"}
        title="Disable this account?"
        message={`${s.full_name} will be signed out and will not be able to log in. Their case history is retained.`}
        confirmLabel="Disable account"
        danger
        busy={toggle.isPending}
        onConfirm={() => toggle.mutate("disable")}
        onClose={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === "enable"}
        title="Enable this account?"
        message={`${s.full_name} will be able to sign in again.`}
        confirmLabel="Enable account"
        busy={toggle.isPending}
        onConfirm={() => toggle.mutate("enable")}
        onClose={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === "reset"}
        title="Reset password?"
        message="A temporary password is generated and shown once. All of this user's sessions are ended immediately."
        confirmLabel="Reset password"
        busy={reset.isPending}
        onConfirm={() => reset.mutate()}
        onClose={() => setConfirm(null)}
      />
    </>
  );
}
