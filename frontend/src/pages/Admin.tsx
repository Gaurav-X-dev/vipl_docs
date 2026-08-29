import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save, Search, ShieldCheck, UserCog } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
  fmtDateTime,
} from "../components";
import {
  Checkbox,
  Field,
  Form,
  FormGrid,
  Modal,
  PermissionDenied,
  Tabs,
  TextArea,
  TextInput,
  useToast,
} from "../ui";
import {
  titleCase,
  type AdminUser,
  type AppSetting,
  type Page,
  type Permission,
  type Role,
} from "../types";

export default function Admin() {
  const { can } = useAuth();
  const tabs = [
    can("users.manage") && { key: "users", label: "Users" },
    can("roles.manage") && { key: "roles", label: "Roles & permissions" },
    can("settings.manage") && { key: "settings", label: "Settings" },
  ].filter(Boolean) as { key: string; label: string }[];

  const [tab, setTab] = useState(tabs[0]?.key ?? "");

  if (!tabs.length) return <PermissionDenied what="administration" />;

  return (
    <>
      <PageHeader
        title="Administration"
        subtitle="User accounts, the role-permission matrix, and application settings."
      />
      <Tabs tabs={tabs} active={tab} onChange={setTab} />
      {tab === "users" && <UsersTab />}
      {tab === "roles" && <RolesTab />}
      {tab === "settings" && <SettingsTab />}
    </>
  );
}

/* -------------------------------------------------------------- Users */
function UsersTab() {
  const client = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [selectedRoles, setSelectedRoles] = useState<string[]>([]);

  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles").then((r) => r.data),
  });

  const query = useQuery({
    queryKey: ["users", search, page],
    queryFn: () =>
      api
        .get<Page<AdminUser>>("/users", {
          params: { search: search || undefined, page, page_size: 25 },
        })
        .then((r) => r.data),
  });

  const save = useMutation({
    mutationFn: () =>
      api.put(`/users/${editing?.id}/roles`, { role_ids: selectedRoles }),
    onSuccess: () => {
      toast.success("Roles updated.");
      client.invalidateQueries({ queryKey: ["users"] });
      setEditing(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  function openEdit(user: AdminUser) {
    const ids = (roles.data ?? [])
      .filter((r) => user.roles.includes(r.name))
      .map((r) => r.id);
    setSelectedRoles(ids);
    setEditing(user);
  }

  return (
    <>
      <Card>
        <div className="filters">
          <div className="search">
            <Search />
            <input
              placeholder="Search name or email…"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
        </div>
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState message={errorMessage(query.error)} />
        ) : !query.data?.items.length ? (
          <Empty title="No users found" />
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Category</th>
                    <th>Roles</th>
                    <th>Availability</th>
                    <th>Last login</th>
                    <th>Account</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <b>{u.full_name}</b>
                        <small>{u.email}</small>
                      </td>
                      <td>{titleCase(u.staff_category)}</td>
                      <td className="wrap">
                        {u.is_super_admin ? (
                          <span className="inline-ok">
                            <ShieldCheck /> Super Admin
                          </span>
                        ) : (
                          u.roles.join(", ") || "—"
                        )}
                      </td>
                      <td>
                        <Online online={u.is_online} />
                      </td>
                      <td>{fmtDateTime(u.last_login_at)}</td>
                      <td>
                        <Status
                          value={
                            u.is_active && u.login_enabled
                              ? "ACTIVE"
                              : "INACTIVE"
                          }
                        />
                      </td>
                      <td>
                        {!u.is_super_admin && (
                          <button
                            className="icon-button"
                            title="Change roles"
                            onClick={() => openEdit(u)}
                          >
                            <UserCog />
                          </button>
                        )}
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
        open={Boolean(editing)}
        title={editing ? `Roles for ${editing.full_name}` : "Roles"}
        subtitle="Permissions are the union of every assigned role."
        onClose={() => setEditing(null)}
        footer={
          <>
            <button className="secondary" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => save.mutate()}
              disabled={save.isPending}
            >
              {save.isPending ? "Saving…" : "Save roles"}
            </button>
          </>
        }
      >
        <div className="checkbox-list">
          {(roles.data ?? []).map((role) => (
            <Checkbox
              key={role.id}
              checked={selectedRoles.includes(role.id)}
              onChange={(checked) =>
                setSelectedRoles((list) =>
                  checked
                    ? [...list, role.id]
                    : list.filter((id) => id !== role.id),
                )
              }
              label={`${role.name} — ${role.description}`}
            />
          ))}
        </div>
      </Modal>
    </>
  );
}

/* -------------------------------------------------------------- Roles */
function RolesTab() {
  const client = useQueryClient();
  const toast = useToast();
  const [editing, setEditing] = useState<Role | null>(null);
  const [granted, setGranted] = useState<string[]>([]);

  const roles = useQuery({
    queryKey: ["roles"],
    queryFn: () => api.get<Role[]>("/roles").then((r) => r.data),
  });
  const permissions = useQuery({
    queryKey: ["permissions"],
    queryFn: () => api.get<Permission[]>("/permissions").then((r) => r.data),
  });

  const grouped = useMemo(() => {
    const map = new Map<string, Permission[]>();
    for (const p of permissions.data ?? []) {
      map.set(p.module, [...(map.get(p.module) ?? []), p]);
    }
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [permissions.data]);

  const save = useMutation({
    mutationFn: () =>
      api.put(`/roles/${editing?.id}/permissions`, {
        permission_codes: granted,
      }),
    onSuccess: () => {
      toast.success("Permissions updated.");
      client.invalidateQueries({ queryKey: ["roles"] });
      setEditing(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <>
      <Card>
        {roles.isLoading ? (
          <Loading />
        ) : roles.isError ? (
          <ErrorState message={errorMessage(roles.error)} />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Description</th>
                  <th>Users</th>
                  <th>Permissions</th>
                  <th>Type</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {(roles.data ?? []).map((role) => (
                  <tr key={role.id}>
                    <td>
                      <b>{role.name}</b>
                      <small>{role.code}</small>
                    </td>
                    <td className="wrap">{role.description}</td>
                    <td>{role.user_count}</td>
                    <td>{role.permissions.length}</td>
                    <td>
                      <Status value={role.is_system ? "SYSTEM" : "CUSTOM"} />
                    </td>
                    <td>
                      {role.code !== "SUPER_ADMIN" && (
                        <button
                          className="text-link"
                          onClick={() => {
                            setEditing(role);
                            setGranted(role.permissions);
                          }}
                        >
                          Edit permissions
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        open={Boolean(editing)}
        wide
        title={editing ? `Permissions for ${editing.name}` : "Permissions"}
        subtitle="Enforced on the server for every request — hiding a button is not authorisation."
        onClose={() => setEditing(null)}
        footer={
          <>
            <button className="secondary" onClick={() => setEditing(null)}>
              Cancel
            </button>
            <button
              className="primary"
              onClick={() => save.mutate()}
              disabled={save.isPending}
            >
              {save.isPending ? "Saving…" : `Save ${granted.length} permissions`}
            </button>
          </>
        }
      >
        <div className="permission-matrix">
          {grouped.map(([module, list]) => {
            const codes = list.map((p) => p.code);
            const allOn = codes.every((c) => granted.includes(c));
            return (
              <section key={module}>
                <header>
                  <h4>{module}</h4>
                  <button
                    className="text-link"
                    onClick={() =>
                      setGranted((current) =>
                        allOn
                          ? current.filter((c) => !codes.includes(c))
                          : [...new Set([...current, ...codes])],
                      )
                    }
                  >
                    {allOn ? "Clear all" : "Select all"}
                  </button>
                </header>
                {list.map((p) => (
                  <Checkbox
                    key={p.code}
                    checked={granted.includes(p.code)}
                    onChange={(checked) =>
                      setGranted((current) =>
                        checked
                          ? [...current, p.code]
                          : current.filter((c) => c !== p.code),
                      )
                    }
                    label={`${p.description} (${p.code})`}
                  />
                ))}
              </section>
            );
          })}
        </div>
      </Modal>
    </>
  );
}

/* ----------------------------------------------------------- Settings */
function SettingsTab() {
  const client = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState<Record<string, string>>({});

  const query = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.get<AppSetting[]>("/settings").then((r) => r.data),
  });

  useEffect(() => {
    if (!query.data) return;
    setDraft(
      Object.fromEntries(query.data.map((s) => [s.key, s.value ?? ""])),
    );
  }, [query.data]);

  const save = useMutation({
    mutationFn: () => {
      const changed: Record<string, string> = {};
      for (const setting of query.data ?? []) {
        const next = draft[setting.key] ?? "";
        if (next !== (setting.value ?? "")) changed[setting.key] = next;
      }
      return api.put("/settings", { values: changed });
    },
    onSuccess: () => {
      toast.success("Settings saved.");
      client.invalidateQueries({ queryKey: ["settings"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (query.isLoading) return <Loading />;
  if (query.isError) return <ErrorState message={errorMessage(query.error)} />;

  const groups = new Map<string, AppSetting[]>();
  for (const setting of query.data ?? []) {
    groups.set(setting.group, [...(groups.get(setting.group) ?? []), setting]);
  }

  const dirty = (query.data ?? []).some(
    (s) => (draft[s.key] ?? "") !== (s.value ?? ""),
  );

  return (
    <>
      {[...groups.entries()].map(([group, list]) => (
        <Card key={group} title={group}>
          <Form onSubmit={() => save.mutate()}>
            <FormGrid>
              {list.map((setting) => (
                <Field
                  key={setting.key}
                  label={setting.label}
                  hint={setting.description}
                  span={setting.value_type === "string" && setting.key.includes("address") ? 2 : 1}
                >
                  {setting.value_type === "bool" ? (
                    <Checkbox
                      checked={
                        (draft[setting.key] ?? "").toLowerCase() === "true"
                      }
                      disabled={!setting.is_editable}
                      onChange={(checked) =>
                        setDraft((d) => ({
                          ...d,
                          [setting.key]: checked ? "true" : "false",
                        }))
                      }
                      label="Enabled"
                    />
                  ) : setting.key.includes("address") ? (
                    <TextArea
                      rows={2}
                      value={draft[setting.key] ?? ""}
                      disabled={!setting.is_editable}
                      onChange={(v) =>
                        setDraft((d) => ({ ...d, [setting.key]: v }))
                      }
                    />
                  ) : (
                    <TextInput
                      type={setting.value_type === "int" ? "number" : "text"}
                      value={draft[setting.key] ?? ""}
                      disabled={!setting.is_editable}
                      onChange={(v) =>
                        setDraft((d) => ({ ...d, [setting.key]: v }))
                      }
                    />
                  )}
                </Field>
              ))}
            </FormGrid>
          </Form>
        </Card>
      ))}

      <div className="sticky-save">
        <span>
          {dirty
            ? "You have unsaved changes. Every change is audit logged."
            : "All settings saved."}
        </span>
        <button
          className="primary"
          onClick={() => save.mutate()}
          disabled={save.isPending || !dirty}
        >
          <Save /> {save.isPending ? "Saving…" : "Save settings"}
        </button>
      </div>
    </>
  );
}
