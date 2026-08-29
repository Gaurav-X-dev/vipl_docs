import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, Plus, RefreshCw, X } from "lucide-react";
import { useState } from "react";
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
import {
  Checkbox,
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
import {
  ATTENDANCE_STATUSES,
  LEAVE_TYPES,
  asOptions,
  titleCase,
  type AttendanceRow,
  type Department,
  type Designation,
  type LeaveRow,
  type Page,
  type Staff,
} from "../types";

const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n: number) =>
  new Date(Date.now() - n * 86400000).toISOString().slice(0, 10);

export default function HR() {
  const { can } = useAuth();
  const [tab, setTab] = useState("employees");

  if (!can("hr.view")) return <PermissionDenied what="HR records" />;
  const canManage = can("hr.manage");

  return (
    <>
      <PageHeader
        title="Human resources"
        subtitle="Employees, org structure, attendance and leave — kept separate from application user administration."
      />
      <Tabs
        tabs={[
          { key: "employees", label: "Employees" },
          { key: "departments", label: "Departments" },
          { key: "designations", label: "Designations" },
          { key: "attendance", label: "Attendance" },
          { key: "leaves", label: "Leave" },
        ]}
        active={tab}
        onChange={setTab}
      />
      {tab === "employees" && <EmployeesTab />}
      {tab === "departments" && <DepartmentsTab canManage={canManage} />}
      {tab === "designations" && <DesignationsTab canManage={canManage} />}
      {tab === "attendance" && <AttendanceTab canManage={canManage} />}
      {tab === "leaves" && <LeavesTab canManage={canManage} />}
    </>
  );
}

/* ---------------------------------------------------------- Employees */
function EmployeesTab() {
  const [search, setSearch] = useState("");
  const [department, setDepartment] = useState("");
  const [page, setPage] = useState(1);

  const departments = useQuery({
    queryKey: ["hr", "departments"],
    queryFn: () => api.get<Department[]>("/hr/departments").then((r) => r.data),
  });

  const query = useQuery({
    queryKey: ["hr", "employees", search, department, page],
    queryFn: () =>
      api
        .get<Page<Staff>>("/hr/employees", {
          params: {
            search: search || undefined,
            department_id: department || undefined,
            page,
            page_size: 25,
          },
        })
        .then((r) => r.data),
  });

  return (
    <Card>
      <div className="filters">
        <div className="search">
          <input
            placeholder="Search employee, code or email…"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>
        <SelectInput
          value={department}
          onChange={(v) => {
            setDepartment(v);
            setPage(1);
          }}
          placeholder="All departments"
          options={(departments.data ?? []).map((d) => ({
            value: d.id,
            label: d.name,
          }))}
        />
      </div>
      {query.isLoading ? (
        <Loading />
      ) : query.isError ? (
        <ErrorState message={errorMessage(query.error)} />
      ) : !query.data?.items.length ? (
        <Empty title="No employees found" />
      ) : (
        <>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Department</th>
                  <th>Designation</th>
                  <th>Category</th>
                  <th>Joined</th>
                  <th>Employment</th>
                  <th>Availability</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <b>{e.full_name}</b>
                      <small>
                        {e.employee_code} · {e.email || "no email"}
                      </small>
                    </td>
                    <td>{e.department || "—"}</td>
                    <td>{e.designation || "—"}</td>
                    <td>{titleCase(e.staff_category)}</td>
                    <td>{fmtDate(e.joining_date)}</td>
                    <td>
                      <Status value={e.employment_status} />
                    </td>
                    <td>
                      <Online online={e.is_online} label={e.status_label} />
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
  );
}

/* -------------------------------------------------------- Departments */
function DepartmentsTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Department | null>(null);
  const [form, setForm] = useState({
    code: "",
    name: "",
    description: "",
    is_active: true,
  });

  const query = useQuery({
    queryKey: ["hr", "departments"],
    queryFn: () => api.get<Department[]>("/hr/departments").then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: () =>
      editing
        ? api.patch(`/hr/departments/${editing.id}`, form)
        : api.post("/hr/departments", form),
    onSuccess: () => {
      toast.success(editing ? "Department updated." : "Department created.");
      client.invalidateQueries({ queryKey: ["hr", "departments"] });
      setOpen(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <Card>
        {canManage && (
          <div className="filters">
            <div className="filters-note">
              <span>Departments group employees for reporting and HR views.</span>
            </div>
            <button
              className="primary"
              onClick={() => {
                setEditing(null);
                setForm({ code: "", name: "", description: "", is_active: true });
                setOpen(true);
              }}
            >
              <Plus /> Add department
            </button>
          </div>
        )}
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty title="No departments" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Employees</th>
                  <th>Status</th>
                  {canManage && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {query.data.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <b>{d.code}</b>
                    </td>
                    <td>
                      {d.name}
                      {d.description && <small>{d.description}</small>}
                    </td>
                    <td>{d.employee_count}</td>
                    <td>
                      <Status value={d.is_active ? "ACTIVE" : "INACTIVE"} />
                    </td>
                    {canManage && (
                      <td>
                        <button
                          className="icon-button"
                          title="Edit"
                          onClick={() => {
                            setEditing(d);
                            setForm({
                              code: d.code,
                              name: d.name,
                              description: d.description ?? "",
                              is_active: d.is_active,
                            });
                            setOpen(true);
                          }}
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
        title={editing ? `Edit ${editing.name}` : "Add department"}
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => save.mutate()}
              disabled={save.isPending || !form.code || !form.name}
            >
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </>
        }
      >
        <Form onSubmit={() => save.mutate()}>
          <FormGrid>
            <Field label="Code" required>
              <TextInput
                value={form.code}
                onChange={(v) =>
                  setForm((f) => ({ ...f, code: v.toUpperCase() }))
                }
                disabled={Boolean(editing)}
              />
            </Field>
            <Field label="Name" required>
              <TextInput
                value={form.name}
                onChange={(v) => setForm((f) => ({ ...f, name: v }))}
              />
            </Field>
            <Field label="Description" span={2}>
              <TextArea
                value={form.description}
                onChange={(v) => setForm((f) => ({ ...f, description: v }))}
                rows={2}
              />
            </Field>
            <Field label="Status" span={2}>
              <Checkbox
                checked={form.is_active}
                onChange={(v) => setForm((f) => ({ ...f, is_active: v }))}
                label="Active"
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}

/* ------------------------------------------------------- Designations */
function DesignationsTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Designation | null>(null);
  const [form, setForm] = useState({
    code: "",
    name: "",
    grade: "",
    description: "",
    is_active: true,
  });

  const query = useQuery({
    queryKey: ["hr", "designations"],
    queryFn: () =>
      api.get<Designation[]>("/hr/designations").then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: () => {
      const body = { ...form, grade: form.grade || null };
      return editing
        ? api.patch(`/hr/designations/${editing.id}`, body)
        : api.post("/hr/designations", body);
    },
    onSuccess: () => {
      toast.success(editing ? "Designation updated." : "Designation created.");
      client.invalidateQueries({ queryKey: ["hr", "designations"] });
      setOpen(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <Card>
        {canManage && (
          <div className="filters">
            <div className="filters-note">
              <span>Designations describe the role a person holds.</span>
            </div>
            <button
              className="primary"
              onClick={() => {
                setEditing(null);
                setForm({
                  code: "",
                  name: "",
                  grade: "",
                  description: "",
                  is_active: true,
                });
                setOpen(true);
              }}
            >
              <Plus /> Add designation
            </button>
          </div>
        )}
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty title="No designations" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Grade</th>
                  <th>Employees</th>
                  <th>Status</th>
                  {canManage && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {query.data.map((d) => (
                  <tr key={d.id}>
                    <td>
                      <b>{d.code}</b>
                    </td>
                    <td>{d.name}</td>
                    <td>{d.grade || "—"}</td>
                    <td>{d.employee_count}</td>
                    <td>
                      <Status value={d.is_active ? "ACTIVE" : "INACTIVE"} />
                    </td>
                    {canManage && (
                      <td>
                        <button
                          className="icon-button"
                          title="Edit"
                          onClick={() => {
                            setEditing(d);
                            setForm({
                              code: d.code,
                              name: d.name,
                              grade: d.grade ?? "",
                              description: d.description ?? "",
                              is_active: d.is_active,
                            });
                            setOpen(true);
                          }}
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
        title={editing ? `Edit ${editing.name}` : "Add designation"}
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => save.mutate()}
              disabled={save.isPending || !form.code || !form.name}
            >
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </>
        }
      >
        <Form onSubmit={() => save.mutate()}>
          <FormGrid>
            <Field label="Code" required>
              <TextInput
                value={form.code}
                onChange={(v) =>
                  setForm((f) => ({ ...f, code: v.toUpperCase() }))
                }
                disabled={Boolean(editing)}
              />
            </Field>
            <Field label="Name" required>
              <TextInput
                value={form.name}
                onChange={(v) => setForm((f) => ({ ...f, name: v }))}
              />
            </Field>
            <Field label="Grade">
              <TextInput
                value={form.grade}
                onChange={(v) => setForm((f) => ({ ...f, grade: v }))}
              />
            </Field>
            <Field label="Description" span={2}>
              <TextArea
                value={form.description}
                onChange={(v) => setForm((f) => ({ ...f, description: v }))}
                rows={2}
              />
            </Field>
            <Field label="Status" span={2}>
              <Checkbox
                checked={form.is_active}
                onChange={(v) => setForm((f) => ({ ...f, is_active: v }))}
                label="Active"
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}

/* --------------------------------------------------------- Attendance */
function AttendanceTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [from, setFrom] = useState(daysAgo(7));
  const [to, setTo] = useState(today());
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    employee_id: "",
    work_date: today(),
    status: "PRESENT",
    remarks: "",
  });

  const employees = useQuery({
    queryKey: ["hr", "employees", "picker"],
    queryFn: () =>
      api
        .get<Page<Staff>>("/hr/employees", { params: { page_size: 200 } })
        .then((r) => r.data.items),
  });

  const query = useQuery({
    queryKey: ["hr", "attendance", from, to],
    queryFn: () =>
      api
        .get<AttendanceRow[]>("/hr/attendance", {
          params: { from_date: from, to_date: to },
        })
        .then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: () =>
      api.post("/hr/attendance", {
        ...form,
        remarks: form.remarks || null,
      }),
    onSuccess: () => {
      toast.success("Attendance recorded.");
      client.invalidateQueries({ queryKey: ["hr", "attendance"] });
      setOpen(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const sync = useMutation({
    mutationFn: (day: string) =>
      api
        .post(`/hr/attendance/sync-from-logins`, null, {
          params: { work_date: day },
        })
        .then((r) => r.data as { message: string }),
    onSuccess: (data) => {
      toast.success(data.message);
      client.invalidateQueries({ queryKey: ["hr", "attendance"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <Card>
        <div className="filters">
          <Field label="From">
            <TextInput type="date" value={from} onChange={setFrom} />
          </Field>
          <Field label="To">
            <TextInput type="date" value={to} onChange={setTo} />
          </Field>
          {canManage && (
            <>
              <button
                className="secondary"
                onClick={() => sync.mutate(to)}
                disabled={sync.isPending}
                title="Derive attendance from the login and heartbeat trail"
              >
                <RefreshCw /> {sync.isPending ? "Syncing…" : "Sync from logins"}
              </button>
              <button
                className="primary"
                onClick={() => {
                  setForm({
                    employee_id: "",
                    work_date: today(),
                    status: "PRESENT",
                    remarks: "",
                  });
                  setOpen(true);
                }}
              >
                <Plus /> Mark attendance
              </button>
            </>
          )}
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty
            title="No attendance in this range"
            detail="Mark attendance manually, or derive it from the login trail."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Employee</th>
                  <th>Status</th>
                  <th>Check in</th>
                  <th>Check out</th>
                  <th>Hours</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((a) => (
                  <tr key={a.id}>
                    <td>{fmtDate(a.work_date)}</td>
                    <td>{a.employee_name || "—"}</td>
                    <td>
                      <Status value={a.status} />
                    </td>
                    <td>{fmtDateTime(a.check_in_at)}</td>
                    <td>{fmtDateTime(a.check_out_at)}</td>
                    <td>{a.worked_hours ?? "—"}</td>
                    <td>
                      <small>
                        {a.derived_from_login ? "Login trail" : "Manual entry"}
                      </small>
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
        title="Mark attendance"
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => save.mutate()}
              disabled={save.isPending || !form.employee_id}
            >
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </>
        }
      >
        <Form onSubmit={() => save.mutate()}>
          <FormGrid>
            <Field label="Employee" required span={2}>
              <SelectInput
                value={form.employee_id}
                onChange={(v) => setForm((f) => ({ ...f, employee_id: v }))}
                placeholder="Select employee…"
                options={(employees.data ?? []).map((e) => ({
                  value: e.id,
                  label: `${e.full_name} (${e.employee_code})`,
                }))}
              />
            </Field>
            <Field label="Date" required>
              <TextInput
                type="date"
                value={form.work_date}
                onChange={(v) => setForm((f) => ({ ...f, work_date: v }))}
              />
            </Field>
            <Field label="Status">
              <SelectInput
                value={form.status}
                onChange={(v) => setForm((f) => ({ ...f, status: v }))}
                options={asOptions(ATTENDANCE_STATUSES)}
                allowEmpty={false}
              />
            </Field>
            <Field label="Remarks" span={2}>
              <TextArea
                value={form.remarks}
                onChange={(v) => setForm((f) => ({ ...f, remarks: v }))}
                rows={2}
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}

/* -------------------------------------------------------------- Leave */
function LeavesTab({ canManage }: { canManage: boolean }) {
  const client = useQueryClient();
  const toast = useToast();
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    employee_id: "",
    leave_type: "CASUAL",
    from_date: today(),
    to_date: today(),
    days: "1",
    reason: "",
  });

  const employees = useQuery({
    queryKey: ["hr", "employees", "picker"],
    queryFn: () =>
      api
        .get<Page<Staff>>("/hr/employees", { params: { page_size: 200 } })
        .then((r) => r.data.items),
  });

  const query = useQuery({
    queryKey: ["hr", "leaves", status],
    queryFn: () =>
      api
        .get<LeaveRow[]>("/hr/leaves", {
          params: { status: status || undefined },
        })
        .then((r) => r.data),
  });

  const apply = useMutation({
    mutationFn: () =>
      api.post("/hr/leaves", {
        ...form,
        days: Number(form.days) || 1,
        reason: form.reason || null,
      }),
    onSuccess: () => {
      toast.success("Leave request submitted.");
      client.invalidateQueries({ queryKey: ["hr", "leaves"] });
      setOpen(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: string }) =>
      api.post(`/hr/leaves/${id}/decision`, { status: decision }),
    onSuccess: () => {
      toast.success("Leave decision recorded.");
      client.invalidateQueries({ queryKey: ["hr", "leaves"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <Card>
        <div className="filters">
          <SelectInput
            value={status}
            onChange={setStatus}
            placeholder="All statuses"
            options={[
              { value: "PENDING", label: "Pending" },
              { value: "APPROVED", label: "Approved" },
              { value: "REJECTED", label: "Rejected" },
              { value: "CANCELLED", label: "Cancelled" },
            ]}
          />
          <button
            className="primary"
            onClick={() => {
              setForm({
                employee_id: "",
                leave_type: "CASUAL",
                from_date: today(),
                to_date: today(),
                days: "1",
                reason: "",
              });
              setOpen(true);
            }}
          >
            <Plus /> Apply leave
          </button>
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.length ? (
          <Empty title="No leave records" />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Type</th>
                  <th>From</th>
                  <th>To</th>
                  <th>Days</th>
                  <th>Reason</th>
                  <th>Status</th>
                  {canManage && <th aria-label="Actions" />}
                </tr>
              </thead>
              <tbody>
                {query.data.map((l) => (
                  <tr key={l.id}>
                    <td>{l.employee_name || "—"}</td>
                    <td>{titleCase(l.leave_type)}</td>
                    <td>{fmtDate(l.from_date)}</td>
                    <td>{fmtDate(l.to_date)}</td>
                    <td>{l.days}</td>
                    <td className="wrap">{l.reason || "—"}</td>
                    <td>
                      <Status value={l.status} />
                    </td>
                    {canManage && (
                      <td className="row-actions">
                        {l.status === "PENDING" ? (
                          <>
                            <button
                              className="icon-button success"
                              title="Approve"
                              disabled={decide.isPending}
                              onClick={() =>
                                decide.mutate({
                                  id: l.id,
                                  decision: "APPROVED",
                                })
                              }
                            >
                              <Check />
                            </button>
                            <button
                              className="icon-button danger"
                              title="Reject"
                              disabled={decide.isPending}
                              onClick={() =>
                                decide.mutate({
                                  id: l.id,
                                  decision: "REJECTED",
                                })
                              }
                            >
                              <X />
                            </button>
                          </>
                        ) : (
                          <small>{fmtDate(l.approved_at)}</small>
                        )}
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
        title="Apply for leave"
        subtitle="HR can approve or reject from the list once submitted."
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => apply.mutate()}
              disabled={apply.isPending || !form.employee_id}
            >
              {apply.isPending ? "Submitting…" : "Submit request"}
            </button>
          </>
        }
      >
        <Form onSubmit={() => apply.mutate()}>
          <FormGrid>
            <Field label="Employee" required span={2}>
              <SelectInput
                value={form.employee_id}
                onChange={(v) => setForm((f) => ({ ...f, employee_id: v }))}
                placeholder="Select employee…"
                options={(employees.data ?? []).map((e) => ({
                  value: e.id,
                  label: `${e.full_name} (${e.employee_code})`,
                }))}
              />
            </Field>
            <Field label="Leave type">
              <SelectInput
                value={form.leave_type}
                onChange={(v) => setForm((f) => ({ ...f, leave_type: v }))}
                options={asOptions(LEAVE_TYPES)}
                allowEmpty={false}
              />
            </Field>
            <Field label="Days">
              <TextInput
                type="number"
                min={0.5}
                value={form.days}
                onChange={(v) => setForm((f) => ({ ...f, days: v }))}
              />
            </Field>
            <Field label="From">
              <TextInput
                type="date"
                value={form.from_date}
                onChange={(v) => setForm((f) => ({ ...f, from_date: v }))}
              />
            </Field>
            <Field label="To">
              <TextInput
                type="date"
                value={form.to_date}
                onChange={(v) => setForm((f) => ({ ...f, to_date: v }))}
              />
            </Field>
            <Field label="Reason" span={2}>
              <TextArea
                value={form.reason}
                onChange={(v) => setForm((f) => ({ ...f, reason: v }))}
                rows={2}
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}
