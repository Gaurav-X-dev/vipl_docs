import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleDot, Clock, LogIn, LogOut, TriangleAlert } from "lucide-react";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  fmtDate,
  fmtDateTime,
} from "../components";
import { Field, Tabs, TextInput, useToast } from "../ui";
import type {
  AttendanceDashboard,
  AttendanceSessionRow,
  ClockStatus,
  LiveUserRow,
} from "../types";

const todayISO = () => new Date().toISOString().slice(0, 10);

/**
 * Attendance is a record of shifts, not of logins.
 *
 * The distinction runs through this whole screen: a person can be Online and
 * Clocked Out (signed in from home) or Offline and Clocked In (out on a
 * visit). Both facts are shown, and neither is inferred from the other.
 */
export default function Attendance() {
  const { can } = useAuth();
  const canSeeAll = can("attendance.view_all");
  const [tab, setTab] = useState(canSeeAll ? "team" : "me");

  const tabs = [
    ...(canSeeAll ? [{ key: "team", label: "Team today" }] : []),
    { key: "me", label: "My attendance" },
    ...(canSeeAll ? [{ key: "live", label: "Who is working now" }] : []),
  ];

  return (
    <>
      <PageHeader
        title="Attendance"
        subtitle="Clock in and out. Working hours come only from shifts, never from logins."
      />
      <Card>
        <Tabs tabs={tabs} active={tab} onChange={setTab} />
        {tab === "me" && <MyAttendance />}
        {tab === "team" && canSeeAll && <TeamAttendance />}
        {tab === "live" && canSeeAll && <LiveMonitor />}
      </Card>
    </>
  );
}

function MyAttendance() {
  const client = useQueryClient();
  const toast = useToast();
  const [note, setNote] = useState("");

  const status = useQuery({
    queryKey: ["attendance", "me"],
    queryFn: () => api.get<ClockStatus>("/attendance/me").then((r) => r.data),
  });

  const sessions = useQuery({
    queryKey: ["attendance", "me", "sessions"],
    queryFn: () =>
      api
        .get<AttendanceSessionRow[]>("/attendance/me/sessions", {
          params: { limit: 60 },
        })
        .then((r) => r.data),
  });

  const act = useMutation({
    mutationFn: (action: "clock-in" | "clock-out") =>
      api
        .post<ClockStatus>(`/attendance/${action}`, { note: note || undefined })
        .then((r) => r.data),
    onSuccess: (data, action) => {
      client.setQueryData(["attendance", "me"], data);
      client.invalidateQueries({ queryKey: ["attendance"] });
      setNote("");
      toast.success(
        action === "clock-in"
          ? "Clocked in."
          : `Clocked out. Total today: ${data.worked_display}.`,
      );
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  if (status.isLoading) return <Loading />;
  if (status.isError)
    return (
      <ErrorState
        message={errorMessage(status.error)}
        retry={() => status.refetch()}
      />
    );

  const live = status.data?.state === "CLOCKED_IN";

  return (
    <>
      <div className="stat-strip">
        <div className={live ? "stat-tile good" : "stat-tile"}>
          <b>{status.data?.worked_display}</b>
          <span>Worked today</span>
        </div>
        <div className="stat-tile">
          <b>{status.data?.sessions_today ?? 0}</b>
          <span>Shifts today</span>
        </div>
        <div className="stat-tile">
          <b>
            {status.data?.clock_in_at
              ? new Date(status.data.clock_in_at).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"}
          </b>
          <span>First clock in</span>
        </div>
        <div className="stat-tile">
          <b>
            {status.data?.clock_out_at
              ? new Date(status.data.clock_out_at).toLocaleTimeString("en-IN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : "—"}
          </b>
          <span>Last clock out</span>
        </div>
      </div>

      <div className="filters">
        <Field label={live ? "Note before clocking out" : "Note (optional)"}>
          <TextInput
            value={note}
            onChange={setNote}
            placeholder={live ? "e.g. Field visits complete" : "e.g. Starting shift"}
          />
        </Field>
        <button
          className={live ? "danger" : "primary"}
          disabled={act.isPending}
          onClick={() => act.mutate(live ? "clock-out" : "clock-in")}
        >
          {live ? <LogOut /> : <LogIn />}
          {live ? "Clock out" : "Clock in"}
        </button>
      </div>

      {sessions.isLoading ? (
        <Loading label="Loading your shifts…" />
      ) : !sessions.data?.length ? (
        <Empty
          title="No shifts recorded yet"
          detail="Clock in when you start work and out when you finish."
        />
      ) : (
        <div className="table-scroll">
          <table className="case-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Clock in</th>
                <th>Clock out</th>
                <th>Worked</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {sessions.data.map((row) => (
                <tr key={row.id}>
                  <td>
                    <b>{fmtDate(row.work_date)}</b>
                  </td>
                  <td>{fmtDateTime(row.clock_in_at)}</td>
                  <td>
                    {row.is_open ? (
                      <span className="pill on">
                        <Clock /> Still on shift
                      </span>
                    ) : (
                      fmtDateTime(row.clock_out_at ?? undefined)
                    )}
                  </td>
                  <td>
                    <b>{row.worked_display}</b>
                    {row.auto_closed && (
                      <small className="locked-note">
                        <TriangleAlert /> Closed automatically
                      </small>
                    )}
                  </td>
                  <td>
                    <small>
                      {[row.clock_in_note, row.clock_out_note]
                        .filter(Boolean)
                        .join(" · ") || "—"}
                    </small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function TeamAttendance() {
  const [day, setDay] = useState(todayISO());
  const query = useQuery({
    queryKey: ["attendance", "dashboard", day],
    queryFn: () =>
      api
        .get<AttendanceDashboard>("/attendance/dashboard", {
          params: { work_date: day },
        })
        .then((r) => r.data),
  });

  if (query.isLoading) return <Loading />;
  if (query.isError)
    return (
      <ErrorState message={errorMessage(query.error)} retry={() => query.refetch()} />
    );

  const totals = query.data?.totals;
  const rows = query.data?.rows ?? [];

  return (
    <>
      <div className="filters">
        <Field label="Date">
          <TextInput type="date" value={day} onChange={setDay} />
        </Field>
      </div>

      <div className="stat-strip">
        <div className="stat-tile">
          <b>{totals?.total_staff ?? 0}</b>
          <span>Active staff</span>
        </div>
        <div className="stat-tile good">
          <b>{totals?.clocked_in ?? 0}</b>
          <span>Clocked in now</span>
        </div>
        <div className="stat-tile">
          <b>{totals?.present_today ?? 0}</b>
          <span>Worked this day</span>
        </div>
        <div className="stat-tile warn">
          <b>{totals?.not_clocked_in ?? 0}</b>
          <span>No shift recorded</span>
        </div>
        <div className="stat-tile">
          <b>{totals?.total_worked_display ?? "00:00"}</b>
          <span>Total hours</span>
        </div>
      </div>

      {!rows.length ? (
        <Empty
          title="Nobody clocked in on this date"
          detail="Pick another date, or ask staff to use the Clock In button in the header."
        />
      ) : (
        <div className="table-scroll">
          <table className="case-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Clock in</th>
                <th>Clock out</th>
                <th>Working hours</th>
                <th>Presence</th>
                <th>Shift</th>
                <th>Current activity</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.user_id}>
                  <td>
                    <b>{row.user_name}</b>
                    <small>{row.email}</small>
                  </td>
                  <td>{fmtDateTime(row.first_clock_in)}</td>
                  <td>
                    {row.clock_state === "CLOCKED_IN"
                      ? "—"
                      : fmtDateTime(row.last_clock_out)}
                  </td>
                  <td>
                    <b>{row.worked_display}</b>
                    <small>
                      {row.sessions} shift{row.sessions === 1 ? "" : "s"}
                    </small>
                  </td>
                  <td>
                    <span className={row.is_online ? "pill on" : "pill off"}>
                      <CircleDot /> {row.is_online ? "Online" : "Offline"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={
                        row.clock_state === "CLOCKED_IN" ? "pill on" : "pill off"
                      }
                    >
                      <Clock />
                      {row.clock_state === "CLOCKED_IN"
                        ? "Clocked in"
                        : "Clocked out"}
                    </span>
                  </td>
                  <td>
                    <small>{row.current_activity ?? "No activity recorded"}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function LiveMonitor() {
  const query = useQuery({
    queryKey: ["attendance", "live"],
    queryFn: () => api.get<LiveUserRow[]>("/attendance/live").then((r) => r.data),
    refetchInterval: 30000,
  });

  if (query.isLoading) return <Loading />;
  if (query.isError)
    return (
      <ErrorState message={errorMessage(query.error)} retry={() => query.refetch()} />
    );

  const rows = query.data ?? [];

  return (
    <>
      <p className="muted">
        "Currently" is each person's most recently recorded action, not live
        observation — nothing is shown here that was not logged.
      </p>
      <div className="table-scroll">
        <table className="case-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Presence</th>
              <th>Shift</th>
              <th>Worked today</th>
              <th>Open cases</th>
              <th>Last activity</th>
              <th>Currently</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.user.id}>
                <td>
                  <b>{row.user.full_name}</b>
                  <small>{row.user.email}</small>
                </td>
                <td>
                  <span className={row.is_online ? "pill on" : "pill off"}>
                    <CircleDot /> {row.is_online ? "Online" : "Offline"}
                  </span>
                </td>
                <td>
                  <span
                    className={
                      row.clock_state === "CLOCKED_IN" ? "pill on" : "pill off"
                    }
                  >
                    <Clock />
                    {row.clock_state === "CLOCKED_IN" ? "On shift" : "Off shift"}
                  </span>
                </td>
                <td>
                  <b>{row.worked_display}</b>
                </td>
                <td>{row.active_cases}</td>
                <td>
                  <small>{fmtDateTime(row.last_activity_at) || "Never"}</small>
                </td>
                <td>
                  <small>{row.current_action ?? "—"}</small>
                  {row.current_module && (
                    <small className="muted"> · {row.current_module}</small>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
