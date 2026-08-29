import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Building2, Inbox, MapPin, RotateCcw } from "lucide-react";
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
  fmtDate,
} from "../components";
import { Tabs } from "../ui";
import type { CaseItem, Page, Sidebar } from "../types";

/**
 * One screen for whichever desk the signed-in user works.
 *
 * A field investigator and a back-office processor both open "My Cases", but
 * a case reaches them at different points in its life, so the tabs are framed
 * by stage rather than by status: work to do in the field, work to do at a
 * desk, and work that has come back for correction.
 */
const TABS = [
  { key: "field", label: "Field work" },
  { key: "office", label: "Office processing" },
  { key: "correction", label: "Correction required" },
  { key: "completed", label: "Completed" },
];

export default function MyCases() {
  const { user } = useAuth();
  const [tab, setTab] = useState("field");
  const [page, setPage] = useState(1);

  const nav = useQuery({
    queryKey: ["navigation", "sidebar"],
    queryFn: () => api.get<Sidebar>("/navigation/sidebar").then((r) => r.data),
  });

  const scope =
    tab === "field"
      ? { assigned_to_id: user?.id, bucket: "in_progress" }
      : tab === "office"
        ? { office_staff_id: user?.id, bucket: "office" }
        : tab === "correction"
          ? { assigned_to_id: user?.id, bucket: "correction" }
          : { my_desk: true, bucket: "completed" };

  const params = toParams({ ...scope, page, page_size: 20 });
  const query = useQuery({
    queryKey: ["cases", "mine", params],
    queryFn: () =>
      api.get<Page<CaseItem>>("/cases", { params }).then((r) => r.data),
  });

  const desk = nav.data?.my_desk;
  const items = query.data?.items ?? [];

  return (
    <>
      <PageHeader
        title="My cases"
        subtitle="Everything currently on your desk, at either stage of the workflow."
      />

      <div className="stat-strip">
        <div className="stat-tile">
          <b>{desk?.field_open ?? 0}</b>
          <span>Field work open</span>
        </div>
        <div className="stat-tile">
          <b>{desk?.office_open ?? 0}</b>
          <span>Office work open</span>
        </div>
        <div className={desk?.correction_required ? "stat-tile warn" : "stat-tile"}>
          <b>{desk?.correction_required ?? 0}</b>
          <span>Correction required</span>
        </div>
        <div className="stat-tile good">
          <b>{desk?.completed ?? 0}</b>
          <span>Completed</span>
        </div>
      </div>

      <Card>
        <Tabs tabs={TABS} active={tab} onChange={(k) => { setTab(k); setPage(1); }} />

        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !items.length ? (
          <Empty
            title="Nothing here right now"
            detail={
              tab === "correction"
                ? "No case has been returned to you for correction."
                : "New work will appear here as soon as it is assigned to you."
            }
          />
        ) : (
          <>
            <div className="table-scroll">
              <table className="case-table">
                <thead>
                  <tr>
                    <th>Case reference</th>
                    <th>Customer / LA</th>
                    <th>Company</th>
                    <th>Status</th>
                    <th>Visit</th>
                    <th>Due</th>
                    <th>TAT</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/cases/${c.id}`}>
                          <b>{c.case_number}</b>
                        </Link>
                        <small>{c.case_type_name}</small>
                      </td>
                      <td>
                        <b>{c.life_assured_name}</b>
                        <small>{c.policy_number || c.krn_no || "No reference"}</small>
                      </td>
                      <td>
                        <span className="company-chip">{c.company_code}</span>
                      </td>
                      <td>
                        <Status value={c.status} label={c.status_label} />
                      </td>
                      <td>
                        {c.visit_status_label ? (
                          <span className="pill stage">
                            <MapPin /> {c.visit_status_label}
                          </span>
                        ) : (
                          <span className="muted">—</span>
                        )}
                      </td>
                      <td>{c.due_at ? fmtDate(c.due_at) : "—"}</td>
                      <td>
                        <Status value={c.tat_state} />
                        <small>{c.aging_days} days aging</small>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
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

      <Card title="How work reaches you">
        <p className="muted">
          The same case passes two desks before it is finished.
        </p>
        <div className="stage-track">
          <div className="stage-step done">
            <small>Stage 1</small>
            <b>
              <Inbox /> Field investigation
            </b>
            <span>
              You visit, complete the form, upload evidence and submit to the
              office. Submitting does not close the case.
            </span>
          </div>
          <div className="stage-step current">
            <small>Stage 2</small>
            <b>
              <Building2 /> Office processing
            </b>
            <span>
              A manager assigns the submitted case to office staff, who verify
              it and prepare the client document.
            </span>
          </div>
          <div className="stage-step">
            <small>If needed</small>
            <b>
              <RotateCcw /> Correction
            </b>
            <span>
              The office can return a case with a reason. It comes back to the
              investigator and is resubmitted.
            </span>
          </div>
        </div>
      </Card>
    </>
  );
}
