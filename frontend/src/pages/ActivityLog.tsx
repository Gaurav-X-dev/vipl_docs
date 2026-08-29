import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { FilterX, Search } from "lucide-react";
import { api, errorMessage, toParams } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Pagination,
  fmtDateTime,
} from "../components";
import { Field, SelectInput, TextInput, useDebounced } from "../ui";
import type { ActivityActionOption, ActivityRow, Page, StaffStatus } from "../types";

/**
 * The Super Admin's user activity log.
 *
 * Deliberately distinct from the Audit Log: the audit log records what data
 * changed, this records what people did. Opening a case changes nothing but
 * still matters when you are asking how someone spent their day.
 *
 * Without activity.view_all the server forces the filter to the caller's own
 * rows, so this same screen is also a person's own timeline.
 */
export default function ActivityLog() {
  const { can, user } = useAuth();
  const canSeeAll = can("activity.view_all");

  const [filters, setFilters] = useState({
    user_id: "",
    action: "",
    module: "",
    date_from: "",
    date_to: "",
    search: "",
  });
  const [page, setPage] = useState(1);
  const debounced = useDebounced(filters.search);

  const staff = useQuery({
    queryKey: ["staff", "status", "activity"],
    queryFn: () =>
      api
        .get<StaffStatus[]>("/staff/status", { params: { only_assignable: false } })
        .then((r) => r.data),
    enabled: canSeeAll && can("staff.view"),
  });

  const actions = useQuery({
    queryKey: ["activity", "actions"],
    queryFn: () =>
      api.get<ActivityActionOption[]>("/activity/actions").then((r) => r.data),
  });

  const modules = useQuery({
    queryKey: ["activity", "modules"],
    queryFn: () => api.get<string[]>("/activity/modules").then((r) => r.data),
  });

  const params = toParams({
    user_id: filters.user_id || undefined,
    action: filters.action || undefined,
    module: filters.module || undefined,
    date_from: filters.date_from || undefined,
    date_to: filters.date_to || undefined,
    search: debounced || undefined,
    page,
    page_size: 40,
  });

  const query = useQuery({
    queryKey: ["activity", "list", params],
    queryFn: () =>
      api.get<Page<ActivityRow>>("/activity", { params }).then((r) => r.data),
  });

  const set = (key: keyof typeof filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  const active = Object.values(filters).filter(Boolean).length;
  const rows = query.data?.items ?? [];

  return (
    <>
      <PageHeader
        title={canSeeAll ? "User activity log" : "My activity"}
        subtitle={
          canSeeAll
            ? "Every action taken inside the application, by whom and when."
            : `Everything you have done in the application, ${user?.full_name}.`
        }
      />
      <Card>
        <div className="filters">
          <div className="search">
            <Search />
            <input
              placeholder="Search a case number, action or person…"
              value={filters.search}
              onChange={(e) => set("search", e.target.value)}
            />
          </div>
          {canSeeAll && (
            <SelectInput
              value={filters.user_id}
              onChange={(v) => set("user_id", v)}
              placeholder="Everyone"
              options={(staff.data ?? []).map((s) => ({
                value: s.id,
                label: s.full_name,
              }))}
            />
          )}
          <SelectInput
            value={filters.module}
            onChange={(v) => set("module", v)}
            placeholder="All modules"
            options={(modules.data ?? []).map((m) => ({ value: m, label: m }))}
          />
          <SelectInput
            value={filters.action}
            onChange={(v) => set("action", v)}
            placeholder="All actions"
            options={(actions.data ?? []).map((a) => ({
              value: a.value,
              label: a.label,
            }))}
          />
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
          {active > 0 && (
            <button
              className="secondary"
              onClick={() => {
                setFilters({
                  user_id: "",
                  action: "",
                  module: "",
                  date_from: "",
                  date_to: "",
                  search: "",
                });
                setPage(1);
              }}
            >
              <FilterX /> Clear ({active})
            </button>
          )}
        </div>

        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !rows.length ? (
          <Empty
            title="No activity matches these filters"
            detail="Widen the date range, or clear the filters to see everything."
          />
        ) : (
          <>
            <div className="activity-feed">
              {rows.map((row) => (
                <div className="activity-line" key={row.id}>
                  <time>{fmtDateTime(row.created_at)}</time>
                  <div className="body">
                    <b>{row.user_label ?? "Unknown user"}</b>
                    <span>
                      {row.case_id ? (
                        <Link to={`/cases/${row.case_id}`}>
                          {row.summary ?? row.activity_type}
                        </Link>
                      ) : (
                        (row.summary ?? row.activity_type)
                      )}
                    </span>
                    {row.detail && <small>{row.detail}</small>}
                  </div>
                  <span className="pill stage">{row.module}</span>
                </div>
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
    </>
  );
}
