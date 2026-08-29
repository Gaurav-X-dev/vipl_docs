import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, UserPlus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
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
} from "../components";
import {
  Field,
  Form,
  FormGrid,
  Modal,
  PermissionDenied,
  SelectInput,
  TextInput,
  useDebounced,
  useToast,
} from "../ui";
import {
  STAFF_CATEGORIES,
  asOptions,
  type Department,
  type Designation,
  type Page,
  type Role,
  type Staff,
} from "../types";

type StaffForm = {
  employee_code: string;
  first_name: string;
  last_name: string;
  email: string;
  mobile: string;
  password: string;
  staff_category: string;
  department_id: string;
  designation_id: string;
  city: string;
  state: string;
  joining_date: string;
  role_id: string;
};

const empty: StaffForm = {
  employee_code: "",
  first_name: "",
  last_name: "",
  email: "",
  mobile: "",
  password: "",
  staff_category: "FIELD",
  department_id: "",
  designation_id: "",
  city: "",
  state: "",
  joining_date: new Date().toISOString().slice(0, 10),
  role_id: "",
};

export default function StaffPage() {
  const { can } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [online, setOnline] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<StaffForm>(empty);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const debounced = useDebounced(search);

  const canView = can("staff.view");
  const canCreate = can("staff.create");

  const departments = useQuery({
    queryKey: ["hr", "departments"],
    queryFn: () => api.get<Department[]>("/hr/departments").then((r) => r.data),
    enabled: canCreate,
  });
  const designations = useQuery({
    queryKey: ["hr", "designations"],
    queryFn: () =>
      api.get<Designation[]>("/hr/designations").then((r) => r.data),
    enabled: canCreate,
  });
  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles").then((r) => r.data),
    enabled: canCreate && can("roles.manage"),
  });

  const query = useQuery({
    queryKey: ["staff", debounced, category, online, page],
    enabled: canView,
    queryFn: () =>
      api
        .get<Page<Staff>>("/staff", {
          params: {
            search: debounced || undefined,
            staff_category: category || undefined,
            online: online === "" ? undefined : online === "online",
            page,
            page_size: 24,
          },
        })
        .then((r) => r.data),
  });

  const create = useMutation({
    mutationFn: () =>
      api
        .post("/staff", {
          employee_code: form.employee_code,
          first_name: form.first_name,
          last_name: form.last_name || null,
          email: form.email,
          mobile: form.mobile || null,
          password: form.password || null,
          staff_category: form.staff_category,
          department_id: form.department_id || null,
          designation_id: form.designation_id || null,
          city: form.city || null,
          state: form.state || null,
          joining_date: form.joining_date || null,
          role_ids: form.role_id ? [form.role_id] : [],
          login_enabled: true,
        })
        .then((r) => r.data as { message: string }),
    onSuccess: (data) => {
      toast.success(data.message);
      client.invalidateQueries({ queryKey: ["staff"] });
      setOpen(false);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (!canView) return <PermissionDenied what="staff records" />;

  const set = <K extends keyof StaffForm>(key: K, value: StaffForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  function submit() {
    const next: Record<string, string> = {};
    if (!form.employee_code.trim()) next.employee_code = "Required.";
    if (!form.first_name.trim()) next.first_name = "Required.";
    if (!form.email.trim()) next.email = "Required.";
    if (form.password && form.password.length < 8)
      next.password = "Must be at least 8 characters, or leave blank.";
    setErrors(next);
    if (Object.keys(next).length) return;
    create.mutate();
  }

  const items = query.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Staff management"
        subtitle="Team access, availability, workload and performance in one place."
        actions={
          canCreate && (
            <button
              className="primary"
              onClick={() => {
                setForm(empty);
                setErrors({});
                setOpen(true);
              }}
            >
              <UserPlus /> Add staff
            </button>
          )
        }
      />

      <div className="kpi-grid compact">
        <Card className="kpi green">
          <div>
            <span>Online now</span>
            <strong>{items.filter((x) => x.is_online).length}</strong>
          </div>
        </Card>
        <Card className="kpi navy">
          <div>
            <span>Active staff</span>
            <strong>{items.filter((x) => x.is_active).length}</strong>
          </div>
        </Card>
        <Card className="kpi amber">
          <div>
            <span>Open workload</span>
            <strong>{items.reduce((a, x) => a + x.open_cases, 0)}</strong>
          </div>
        </Card>
        <Card className="kpi">
          <div>
            <span>Overdue cases</span>
            <strong>{items.reduce((a, x) => a + x.overdue_cases, 0)}</strong>
          </div>
        </Card>
      </div>

      <Card>
        <div className="filters">
          <div className="search">
            <Search />
            <input
              placeholder="Search employee, email or code…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          <SelectInput
            value={category}
            onChange={(v) => {
              setCategory(v);
              setPage(1);
            }}
            placeholder="All categories"
            options={asOptions(STAFF_CATEGORIES)}
          />
          <SelectInput
            value={online}
            onChange={(v) => {
              setOnline(v);
              setPage(1);
            }}
            placeholder="Any availability"
            options={[
              { value: "online", label: "Online only" },
              { value: "offline", label: "Offline only" },
            ]}
          />
        </div>

        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !items.length ? (
          <Empty
            title="No staff found"
            detail="Adjust the filters, or add your first team member."
          />
        ) : (
          <>
            <div className="staff-grid">
              {items.map((s) => (
                <article className="staff-card" key={s.id}>
                  <div className="staff-top">
                    <span className="avatar">
                      {s.full_name
                        .split(" ")
                        .map((x) => x[0])
                        .slice(0, 2)
                        .join("")}
                    </span>
                    <Online online={s.is_online} label={s.status_label} />
                  </div>
                  <h3>{s.full_name}</h3>
                  <p>{s.designation || s.staff_category.replace("_", " ")}</p>
                  <span className="employee-code">{s.employee_code}</span>
                  <div className="staff-stats">
                    <span>
                      <b>{s.open_cases}</b>Open
                    </span>
                    <span>
                      <b>{s.completed_cases}</b>Completed
                    </span>
                    <span>
                      <b>{s.overdue_cases}</b>Overdue
                    </span>
                  </div>
                  <div className="staff-foot">
                    <Status value={s.is_active ? "ACTIVE" : "INACTIVE"} />
                    <Link className="text-link" to={`/staff/${s.id}`}>
                      View profile
                    </Link>
                  </div>
                </article>
              ))}
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

      <Modal
        open={open}
        wide
        title="Add staff member"
        subtitle="Creates the login account and the HR employee record together."
        onClose={() => setOpen(false)}
        footer={
          <>
            <button className="secondary" onClick={() => setOpen(false)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={submit}
              disabled={create.isPending}
            >
              {create.isPending ? "Creating…" : "Create staff"}
            </button>
          </>
        }
      >
        <Form onSubmit={submit}>
          <FormGrid>
            <Field label="Employee code" required error={errors.employee_code}>
              <TextInput
                value={form.employee_code}
                onChange={(v) => set("employee_code", v.toUpperCase())}
                placeholder="EMP1008"
              />
            </Field>
            <Field label="Category">
              <SelectInput
                value={form.staff_category}
                onChange={(v) => set("staff_category", v)}
                options={asOptions(STAFF_CATEGORIES)}
                allowEmpty={false}
              />
            </Field>
            <Field label="First name" required error={errors.first_name}>
              <TextInput
                value={form.first_name}
                onChange={(v) => set("first_name", v)}
              />
            </Field>
            <Field label="Last name">
              <TextInput
                value={form.last_name}
                onChange={(v) => set("last_name", v)}
              />
            </Field>
            <Field label="Email" required error={errors.email}>
              <TextInput
                type="email"
                value={form.email}
                onChange={(v) => set("email", v)}
              />
            </Field>
            <Field label="Mobile">
              <TextInput value={form.mobile} onChange={(v) => set("mobile", v)} />
            </Field>
            <Field
              label="Password"
              error={errors.password}
              hint="Leave blank to generate a temporary password."
            >
              <TextInput
                type="password"
                value={form.password}
                onChange={(v) => set("password", v)}
              />
            </Field>
            <Field label="Role">
              <SelectInput
                value={form.role_id}
                onChange={(v) => set("role_id", v)}
                placeholder="No role yet"
                options={(roles.data ?? []).map((r) => ({
                  value: r.id,
                  label: r.name,
                }))}
              />
            </Field>
            <Field label="Department">
              <SelectInput
                value={form.department_id}
                onChange={(v) => set("department_id", v)}
                placeholder="Unassigned"
                options={(departments.data ?? []).map((d) => ({
                  value: d.id,
                  label: d.name,
                }))}
              />
            </Field>
            <Field label="Designation">
              <SelectInput
                value={form.designation_id}
                onChange={(v) => set("designation_id", v)}
                placeholder="Unassigned"
                options={(designations.data ?? []).map((d) => ({
                  value: d.id,
                  label: d.name,
                }))}
              />
            </Field>
            <Field label="Base city">
              <TextInput value={form.city} onChange={(v) => set("city", v)} />
            </Field>
            <Field label="State">
              <TextInput value={form.state} onChange={(v) => set("state", v)} />
            </Field>
            <Field label="Joining date">
              <TextInput
                type="date"
                value={form.joining_date}
                onChange={(v) => set("joining_date", v)}
              />
            </Field>
          </FormGrid>
        </Form>
      </Modal>
    </>
  );
}
