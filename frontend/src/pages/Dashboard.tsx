import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BriefcaseBusiness,
  CircleCheckBig,
  Clock3,
  FileClock,
  ShieldAlert,
  Users,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { api, errorMessage } from "../api";
import {
  Card,
  ErrorState,
  Loading,
  Online,
  PageHeader,
  Status,
  fmtDate,
  num,
} from "../components";
import type { CaseItem, Dict } from "../types";

const get = <T,>(path: string) => api.get<T>(path).then((r) => r.data);
export default function Dashboard() {
  const summary = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => get<Dict>("/dashboard/summary"),
  });
  const outcome = useQuery({
    queryKey: ["outcomes"],
    queryFn: () => get<Dict[]>("/dashboard/outcome-distribution"),
  });
  const recent = useQuery({
    queryKey: ["recent"],
    queryFn: () => get<CaseItem[]>("/dashboard/recent-cases"),
  });
  const staff = useQuery({
    queryKey: ["dash-staff"],
    queryFn: () => get<Dict[]>("/dashboard/staff-status"),
  });
  if (summary.isLoading) return <Loading />;
  if (summary.isError)
    return (
      <ErrorState
        message={errorMessage(summary.error)}
        retry={() => summary.refetch()}
      />
    );
  const s = summary.data || {};
  const kpis: [string, string, LucideIcon, string][] = [
    ["Total assignments", "total_assignment", BriefcaseBusiness, "navy"],
    ["Work in progress", "wip_cases", Clock3, "amber"],
    ["Report in progress", "rip_cases", FileClock, "purple"],
    ["Completed", "completed_cases", CircleCheckBig, "green"],
  ];
  const outcomes = (outcome.data || []).map((x, i) => ({
    name: String(x.label || x.outcome || ""),
    value: Number(x.count || 0),
    fill: ["#159a78", "#e05858", "#e7a63b"][i % 3],
  }));
  return (
    <>
      <PageHeader
        title="Operations dashboard"
        subtitle="A live view of assignments, outcomes, TAT, and team availability."
        actions={
          <Link className="primary" to="/imports">
            Import daily cases
          </Link>
        }
      />
      <div className="kpi-grid">
        {kpis.map(([label, key, Icon, tone]) => (
          <Card className={`kpi ${tone}`} key={String(key)}>
            <div className="kpi-icon">
              <Icon />
            </div>
            <div>
              <span>{label}</span>
              <strong>{num(s[String(key)])}</strong>
              <small>Current case volume</small>
            </div>
          </Card>
        ))}
      </div>
      <div className="dashboard-grid">
        <Card title="Investigation outcomes" className="outcome-card">
          {outcomes.length ? (
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height={230}>
                <PieChart>
                  <Pie
                    data={outcomes}
                    dataKey="value"
                    innerRadius={62}
                    outerRadius={92}
                    paddingAngle={3}
                  >
                    {outcomes.map((x, i) => (
                      <Cell key={i} fill={x.fill} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
              <div className="chart-center">
                <strong>
                  {num(outcomes.reduce((a, x) => a + x.value, 0))}
                </strong>
                <span>decided</span>
              </div>
            </div>
          ) : (
            <div className="mini-empty">No outcomes recorded yet</div>
          )}
          <div className="legend">
            {outcomes.map((x) => (
              <span key={x.name}>
                <i style={{ background: x.fill }} />
                {x.name}
                <b>{x.value}</b>
              </span>
            ))}
          </div>
        </Card>
        <Card title="Turnaround time" className="tat-card">
          <div className="tat-main">
            <ShieldAlert />
            <div>
              <strong>{num(s.in_tat)}</strong>
              <span>Cases within TAT</span>
            </div>
          </div>
          <div className="tat-row">
            <span>
              <i className="dot on" />
              In TAT
            </span>
            <b>{num(s.in_tat)}</b>
          </div>
          <div className="tat-row">
            <span>
              <i className="dot warn" />
              About to breach
            </span>
            <b>{num(s.tat_about_to_breach)}</b>
          </div>
          <div className="tat-row">
            <span>
              <i className="dot danger" />
              Out of TAT
            </span>
            <b>{num(s.out_of_tat)}</b>
          </div>
          <Link to="/cases" className="text-link">
            Review all cases <ArrowRight />
          </Link>
        </Card>
        <Card
          title="Team availability"
          className="team-card"
          action={<Link to="/staff">View staff</Link>}
        >
          <div className="team-summary">
            <div>
              <Users />
              <span>
                <strong>{num(s.active_investigators)}</strong> Active
                investigators
              </span>
            </div>
            <div>
              <span>
                <strong>{num(s.active_back_office)}</strong> Back office online
              </span>
            </div>
          </div>
          <div className="people">
            {(staff.data || []).slice(0, 5).map((x, i) => (
              <div className="person" key={String(x.id || i)}>
                <span className="avatar small">
                  {String(x.full_name || "?")
                    .split(" ")
                    .map((y) => y[0])
                    .slice(0, 2)
                    .join("")}
                </span>
                <span>
                  <b>{String(x.full_name || "Staff")}</b>
                  <small>
                    {String(x.role || x.staff_category || "Team member")}
                  </small>
                </span>
                <Online online={Boolean(x.is_online)} />
              </div>
            ))}
          </div>
        </Card>
        <Card
          title="Recent cases"
          className="recent-card"
          action={<Link to="/cases">View all</Link>}
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Life assured</th>
                  <th>Company</th>
                  <th>Status</th>
                  <th>Received</th>
                </tr>
              </thead>
              <tbody>
                {(recent.data || []).slice(0, 7).map((c) => (
                  <tr key={c.id}>
                    <td>
                      <Link to={`/cases/${c.id}`}>
                        <b>{c.case_number}</b>
                      </Link>
                      <small>{c.case_type_name}</small>
                    </td>
                    <td>{c.life_assured_name}</td>
                    <td>{c.company_code}</td>
                    <td>
                      <Status value={c.status} label={c.status_label} />
                    </td>
                    <td>{fmtDate(c.received_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}
