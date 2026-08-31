import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  Bell,
  Building2,
  ChevronRight,
  ClipboardList,
  Clock,
  FileInput,
  FileText,
  Gauge,
  HeartPulse,
  Inbox,
  LogIn,
  LogOut,
  Menu,
  Settings,
  ShieldCheck,
  Users,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { api, errorMessage } from "./api";
import { playNotificationChime, setSoundEnabled, soundEnabled } from "./notify";
import { useAuth } from "./auth";
import { fmtDateTime } from "./components";
import { useToast } from "./ui";
import type { ClockStatus, NavCategory, Notification, Sidebar } from "./types";

type NavItem = {
  label: string;
  to: string;
  icon: typeof Gauge;
  permission?: string;
};

/**
 * Fixed menu entries. The Investigation and Death Claim branches are *not*
 * here — they are generated from the companies that actually have cases, so
 * a new client appears in the menu the moment their first import lands.
 */
const STATIC_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: "People",
    items: [
      { label: "Staff", to: "/staff", icon: Users, permission: "staff.view" },
      {
        label: "Attendance",
        to: "/attendance",
        icon: Clock,
        permission: "attendance.self",
      },
      {
        label: "Activity Log",
        to: "/activity",
        icon: Activity,
        permission: "activity.view_self",
      },
      { label: "HR Records", to: "/hr", icon: Users, permission: "hr.view" },
    ],
  },
  {
    label: "Management",
    items: [
      {
        label: "Companies",
        to: "/companies",
        icon: Building2,
        permission: "company.view",
      },
      {
        label: "Templates",
        to: "/templates",
        icon: FileText,
        permission: "template.view",
      },
      { label: "Reports", to: "/reports", icon: Gauge, permission: "reports.view" },
      {
        label: "Audit Logs",
        to: "/audit",
        icon: ShieldCheck,
        permission: "audit.view",
      },
      {
        label: "Administration",
        to: "/admin",
        icon: Settings,
        permission: "users.manage",
      },
    ],
  },
];

const CATEGORY_ICONS: Record<string, typeof Gauge> = {
  "shield-check": ShieldCheck,
  "heart-pulse": HeartPulse,
};

export function AppLayout() {
  const { user, logout, can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    setOpen(false);
  }, [location]);

  useEffect(() => {
    // Minutes only, so a quarter-minute tick is enough to stay accurate
    // without re-rendering the header once a second all day.
    const id = setInterval(() => setNow(new Date()), 15000);
    return () => clearInterval(id);
  }, []);

  const nav = useQuery({
    queryKey: ["navigation", "sidebar"],
    queryFn: () => api.get<Sidebar>("/navigation/sidebar").then((r) => r.data),
    // Counts move as cases move; a minute is fresh enough for a menu.
    refetchInterval: 60000,
    staleTime: 30000,
  });

  const groups = STATIC_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter(
      (item) =>
        !item.permission ||
        can(item.permission) ||
        (item.to === "/admin" && (can("roles.manage") || can("settings.manage"))),
    ),
  })).filter((group) => group.items.length > 0);

  const desk = nav.data?.my_desk;
  const myOpen = (desk?.field_open ?? 0) + (desk?.office_open ?? 0);

  return (
    <div className="shell">
      <aside className={open ? "sidebar open" : "sidebar"}>
        <div className="brand">
          <div className="brand-mark">V</div>
          <div>
            <b>VIPL</b>
            <span>Case Management</span>
          </div>
          <button
            className="mobile-close"
            onClick={() => setOpen(false)}
            aria-label="Close menu"
          >
            <X />
          </button>
        </div>

        <nav>
          <div className="nav-group">
            <small>Workspace</small>
            {can("dashboard.view") && (
              <NavLink to="/" end className={({ isActive }) => (isActive ? "active" : "")}>
                <Gauge />
                <span>Dashboard</span>
              </NavLink>
            )}
            {can("case.view") && (
              <>
                <NavLink
                  to="/my-cases"
                  className={({ isActive }) => (isActive ? "active" : "")}
                >
                  <Inbox />
                  <span>My Cases</span>
                  {myOpen > 0 && <em className="nav-count">{myOpen}</em>}
                </NavLink>
                <NavLink
                  to="/cases"
                  end
                  className={({ isActive }) => (isActive ? "active" : "")}
                >
                  <ClipboardList />
                  <span>All Cases</span>
                </NavLink>
              </>
            )}
            {can("import.view") && (
              <NavLink
                to="/imports"
                className={({ isActive }) => (isActive ? "active" : "")}
              >
                <FileInput />
                <span>Import Cases</span>
              </NavLink>
            )}
          </div>

          {(nav.data?.categories ?? []).map((category) => (
            <CategoryBranch key={category.category} category={category} />
          ))}

          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <small>{group.label}</small>
              {group.items.map(({ label, to, icon: Icon }) => (
                <NavLink
                  key={label}
                  to={to}
                  className={({ isActive }) => (isActive ? "active" : "")}
                >
                  <Icon />
                  <span>{label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <div className="security">
            <ShieldCheck />
            <span>
              <b>Secure session</b>
              <small>Activity monitored and audit logged</small>
            </span>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <button className="menu" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu />
          </button>
          <div className="live-time">
            <b>
              {now.toLocaleTimeString("en-IN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </b>
            <span>
              {now.toLocaleDateString("en-IN", {
                weekday: "long",
                day: "2-digit",
                month: "short",
                year: "numeric",
              })}
            </span>
          </div>
          <div className="top-spacer" />
          <ClockWidget />
          <NotificationBell />
          <button className="user-menu">
            <span className="avatar">
              {user?.full_name
                ?.split(" ")
                .map((x) => x[0])
                .slice(0, 2)
                .join("")}
            </span>
            <span>
              <b>{user?.full_name}</b>
              <small>
                {user?.is_super_admin ? "Super Admin" : user?.roles?.[0]?.name || "No role"}
              </small>
            </span>
          </button>
          <button
            className="icon-button"
            title="Sign out"
            aria-label="Sign out"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            <LogOut />
          </button>
        </header>
        <main>
          <Outlet />
        </main>
      </div>
      {open && <div className="backdrop" onClick={() => setOpen(false)} />}
    </div>
  );
}

/**
 * One dynamic branch: Investigation or Death Claim, then the client list.
 *
 * Deliberately just names and counts. The status filters live on the case
 * list where they belong — a menu that also carries eight status rows per
 * company becomes a wall of text nobody reads, and the people using this all
 * day navigate by client first.
 */
function CategoryBranch({ category }: { category: NavCategory }) {
  const location = useLocation();
  const { can } = useAuth();
  const base = `/${category.slug}`;
  const onBranch = location.pathname.startsWith(base);
  const [expanded, setExpanded] = useState(onBranch);

  useEffect(() => {
    if (onBranch) setExpanded(true);
  }, [onBranch]);

  const Icon = CATEGORY_ICONS[category.icon] ?? ShieldCheck;
  const search = new URLSearchParams(location.search);
  const activeCompany = search.get("company_id");
  const activeCaseType = search.get("case_type_id");

  // These links are told apart by their query string, and NavLink matches on
  // pathname only — it would mark every form in the branch as active at once.
  // So the current one is worked out here and plain Links carry the class.
  //
  // One flat list of every form, named the way the agency names them. Nesting
  // them under company headings made the menu ragged — some companies had
  // children, most did not — and buried the forms people actually click.
  const forms = category.companies.flatMap((company) =>
    company.forms.map((form) => ({ ...form, company })),
  );

  return (
    <div className="nav-group nav-tree">
      <button
        className={expanded ? "nav-branch open" : "nav-branch"}
        onClick={() => setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <Icon />
        <span>{category.label}</span>
        {category.total > 0 && <em className="nav-count">{category.total}</em>}
        <ChevronRight className="chevron" />
      </button>

      {expanded && (
        <div className="nav-children">
          <Link
            to={base}
            className={
              onBranch && !activeCompany ? "nav-leaf active" : "nav-leaf"
            }
          >
            <span>All {category.label.toLowerCase()} cases</span>
            {category.total > 0 && <em>{category.total}</em>}
          </Link>

          {/* Each queue imports its own sheet: the two arrive from different
              desks in different layouts, and mixing them was how rows ended
              up filed under the wrong kind of case. */}
          {can("import.create") && (
            <Link
              to={`/imports/${category.slug}`}
              className={
                location.pathname === `/imports/${category.slug}`
                  ? "nav-leaf active"
                  : "nav-leaf"
              }
            >
              <span>Import {category.label.toLowerCase()} cases</span>
            </Link>
          )}

          {forms.map((form) => {
            const active =
              activeCompany === form.company.id &&
              activeCaseType === form.case_type_id;
            return (
              <Link
                key={`${form.company.id}:${form.case_type_id}`}
                to={`${base}?company_id=${form.company.id}&case_type_id=${form.case_type_id}`}
                className={active ? "nav-form active" : "nav-form"}
                title={`${form.name} — ${form.company.name}`}
                aria-current={active ? "page" : undefined}
              >
                <span>
                  <b>{form.name}</b>
                  <small>{form.company.short_name}</small>
                </span>
                {form.count > 0 && <em>{form.count}</em>}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Clock in / clock out.
 *
 * Kept visually separate from the green online dot elsewhere in the app,
 * because they are different facts: online means the browser is active,
 * clocked in means the person is on shift.
 */
function ClockWidget() {
  const { can } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const [tick, setTick] = useState(0);

  const status = useQuery({
    queryKey: ["attendance", "me"],
    queryFn: () => api.get<ClockStatus>("/attendance/me").then((r) => r.data),
    enabled: can("attendance.self"),
    refetchInterval: 120000,
  });

  // Local ticker so the running duration counts up without polling the API.
  useEffect(() => {
    if (status.data?.state !== "CLOCKED_IN") return;
    const id = setInterval(() => setTick((t) => t + 1), 30000);
    return () => clearInterval(id);
  }, [status.data?.state]);

  const act = useMutation({
    mutationFn: (action: "clock-in" | "clock-out") =>
      api.post<ClockStatus>(`/attendance/${action}`, {}).then((r) => r.data),
    onSuccess: (data, action) => {
      client.setQueryData(["attendance", "me"], data);
      client.invalidateQueries({ queryKey: ["attendance"] });
      toast.success(
        action === "clock-in"
          ? "Clocked in. Have a good shift."
          : `Clocked out. Total today: ${data.worked_display}.`,
      );
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  if (!can("attendance.self") || !status.data) return null;

  const live = status.data.state === "CLOCKED_IN";
  const running = live
    ? liveDuration(status.data.clock_in_at, status.data.worked_minutes_today, tick)
    : status.data.worked_display;

  return (
    <div className={live ? "clock-widget live" : "clock-widget"}>
      <div className="clock-read">
        <b>{running}</b>
        <small>{live ? "On shift" : "Clocked out"}</small>
      </div>
      <button
        className={live ? "clock-button out" : "clock-button in"}
        disabled={act.isPending}
        onClick={() => act.mutate(live ? "clock-out" : "clock-in")}
      >
        {live ? <LogOut /> : <LogIn />}
        <span>{live ? "Clock Out" : "Clock In"}</span>
      </button>
    </div>
  );
}

/** Worked time including the shift still running, without asking the server. */
function liveDuration(
  clockInAt: string | null | undefined,
  closedMinutes: number,
  _tick: number,
) {
  if (!clockInAt) return "00:00";
  const started = new Date(clockInAt).getTime();
  const elapsed = Math.max(0, Math.floor((Date.now() - started) / 60000));
  const total = closedMinutes + elapsed;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function NotificationBell() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const [sound, setSound] = useState(soundEnabled);

  const count = useQuery({
    queryKey: ["notifications", "count"],
    queryFn: () =>
      api.get<{ unread: number; total: number }>("/notifications/count").then((r) => r.data),
    // A case moving through the workflow should be audible within seconds,
    // not at the next minute boundary.
    refetchInterval: 20000,
    refetchIntervalInBackground: true,
  });

  const list = useQuery({
    queryKey: ["notifications", "list"],
    enabled: open,
    queryFn: () =>
      api.get<Notification[]>("/notifications", { params: { limit: 20 } }).then((r) => r.data),
  });

  const markRead = useMutation({
    mutationFn: () => api.post("/notifications/read", {}),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const unread = count.data?.unread ?? 0;

  // Ring only when the number actually grows. The first reading after a
  // sign-in establishes the baseline, so a backlog of unread items does not
  // announce itself the moment the app opens.
  const known = useRef<number | null>(null);
  useEffect(() => {
    if (count.data === undefined) return;
    const previous = known.current;
    known.current = unread;
    if (previous !== null && unread > previous) playNotificationChime();
  }, [unread, count.data]);

  return (
    <div className="notification-wrap" ref={ref}>
      <button
        className="icon-button"
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell />
        {unread > 0 && <span className="badge-count">{unread}</span>}
      </button>
      {open && (
        <div className="notification-panel">
          <header>
            <b>Notifications</b>
            <button
              className="text-link"
              onClick={() => {
                const next = !sound;
                setSound(next);
                setSoundEnabled(next);
                if (next) playNotificationChime();
              }}
              aria-pressed={sound}
              aria-label={
                sound ? "Turn notification sound off" : "Turn notification sound on"
              }
              title={sound ? "Sound is on" : "Sound is off"}
            >
              {sound ? <Volume2 /> : <VolumeX />}
            </button>
            {unread > 0 && (
              <button
                className="text-link"
                onClick={() => markRead.mutate()}
                disabled={markRead.isPending}
              >
                Mark all read
              </button>
            )}
          </header>
          <div className="notification-list">
            {list.isLoading ? (
              <p className="muted">Loading…</p>
            ) : !list.data?.length ? (
              <p className="muted">Nothing new right now.</p>
            ) : (
              list.data.map((n) => (
                <button
                  key={n.id}
                  className={n.is_read ? "notification" : "notification unread"}
                  onClick={() => {
                    setOpen(false);
                    if (n.link) navigate(n.link);
                  }}
                >
                  <b>{n.title}</b>
                  {n.body && <span>{n.body}</span>}
                  <small>{fmtDateTime(n.created_at)}</small>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
