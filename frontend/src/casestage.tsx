import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, MapPin, RotateCcw, Send } from "lucide-react";
import { api, errorMessage } from "./api";
import { useAuth } from "./auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  Online,
  Status,
  fmtDateTime,
} from "./components";
import { Field, Modal, SelectInput, TextArea, TextInput, useToast } from "./ui";
import { FIELD_STAGE_OVER } from "./types";
import type { CaseDetail, StageAssignment } from "./types";

const VISIT_STATES = [
  { value: "NOT_STARTED", label: "Not started" },
  { value: "VISIT_SCHEDULED", label: "Visit scheduled" },
  { value: "VISIT_IN_PROGRESS", label: "Visit in progress" },
  { value: "VISITED", label: "Visited" },
  { value: "INFORMATION_COLLECTED", label: "Information collected" },
  { value: "FORM_COMPLETED", label: "Form completed" },
];

const OUTCOMES = [
  { value: "POSITIVE", label: "Positive" },
  { value: "NEGATIVE", label: "Negative" },
  { value: "SUSPICIOUS", label: "Suspicious" },
];

/**
 * The workflow tab: where the case is, who has held it, and what happens next.
 *
 * The two stages are shown as a track rather than a single "assigned to"
 * field, because the client's process has two owners in sequence and losing
 * the first one when the second arrives was exactly what they asked us to
 * avoid.
 */
export function WorkflowTab({
  c,
  onAssignOffice,
  onSubmitToOffice,
  onUpdateVisit,
}: {
  c: CaseDetail;
  onAssignOffice: () => void;
  onSubmitToOffice: () => void;
  onUpdateVisit: () => void;
}) {
  const { can } = useAuth();
  const query = useQuery({
    queryKey: ["case-stages", c.id],
    queryFn: () =>
      api
        .get<StageAssignment[]>(`/cases/${c.id}/stage-assignments`)
        .then((r) => r.data),
  });

  const fieldDone =
    Boolean(c.field_submitted_at) || FIELD_STAGE_OVER.includes(c.status);
  const officeStarted = Boolean(c.office_assigned_at);
  const finished = ["COMPLETED", "VERIFIED"].includes(c.status);

  const canSubmit =
    can("investigation.edit") &&
    !fieldDone &&
    !finished &&
    c.status !== "IMPORTED" &&
    c.status !== "UNASSIGNED";

  return (
    <>
      <Card title="Where this case is">
        <div className="stage-track">
          <div className={fieldDone ? "stage-step done" : "stage-step current"}>
            <small>Stage 1 · Field</small>
            <b>{c.assigned_to?.full_name ?? "Not assigned"}</b>
            <span>
              {fieldDone
                ? `Submitted to office ${fmtDateTime(c.field_submitted_at)}`
                : `Visit status: ${c.visit_status_label ?? "Not started"}`}
            </span>
          </div>
          <div
            className={
              finished
                ? "stage-step done"
                : officeStarted
                  ? "stage-step current"
                  : "stage-step"
            }
          >
            <small>Stage 2 · Office</small>
            <b>{c.office_staff?.full_name ?? "Not assigned"}</b>
            <span>
              {officeStarted
                ? `Assigned ${fmtDateTime(c.office_assigned_at)}`
                : fieldDone
                  ? "Waiting for a manager to assign office staff"
                  : "Starts once the investigator submits"}
            </span>
          </div>
          <div className={finished ? "stage-step done" : "stage-step"}>
            <small>Stage 3 · Review</small>
            <b>{c.reviewed_by?.full_name ?? "Not reviewed"}</b>
            <span>
              {finished
                ? `Completed ${fmtDateTime(c.completed_at)}`
                : "Approval and client document generation"}
            </span>
          </div>
        </div>

        <div className="row-actions" style={{ marginTop: 14 }}>
          {canSubmit && (
            <button className="primary" onClick={onSubmitToOffice}>
              <Send /> Submit to office
            </button>
          )}
          {can("case.assign_office") && fieldDone && !finished && (
            <button className="secondary" onClick={onAssignOffice}>
              <Building2 />
              {c.office_staff ? "Reassign office staff" : "Assign to office"}
            </button>
          )}
          {can("investigation.edit") && !fieldDone && !finished && (
            <button className="secondary" onClick={onUpdateVisit}>
              <MapPin /> Update visit status
            </button>
          )}
        </div>
      </Card>

      <Card title="Assignment history">
        <p className="card-note">
          Nothing is overwritten. Reassigning a case closes the previous record
          and opens a new one, so every holder stays on file.
        </p>
        {query.isLoading ? (
          <Loading />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            retry={() => query.refetch()}
          />
        ) : !query.data?.length ? (
          <Empty
            title="Not assigned yet"
            detail="Assign an investigator to start the field stage."
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Stage</th>
                  <th>Assigned to</th>
                  <th>By</th>
                  <th>State</th>
                  <th>From</th>
                  <th>Closed</th>
                  <th>Notes</th>
                </tr>
              </thead>
              <tbody>
                {query.data.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <span className="pill stage">
                        {row.stage === "FIELD_INVESTIGATION"
                          ? "Field"
                          : row.stage === "OFFICE_PROCESSING"
                            ? "Office"
                            : "Review"}
                      </span>
                    </td>
                    <td>
                      {row.assigned_to ? (
                        <>
                          <b>{row.assigned_to.full_name}</b>
                          <Online online={row.assigned_to.is_online} />
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>{row.assigned_by?.full_name ?? "System"}</td>
                    <td>
                      <Status value={row.state} />
                      {row.is_reassignment && <small>reassignment</small>}
                    </td>
                    <td>{fmtDateTime(row.created_at)}</td>
                    <td>
                      {fmtDateTime(row.completed_at ?? row.released_at ?? undefined) ||
                        "—"}
                    </td>
                    <td>
                      <small>{row.notes ?? "—"}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}

/** Investigator's hand-off. Queues the case; never completes it. */
export function SubmitToOfficeDialog({
  open,
  caseId,
  currentOutcome,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  currentOutcome?: string | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const client = useQueryClient();
  const [outcome, setOutcome] = useState(currentOutcome ?? "");
  const [remarks, setRemarks] = useState("");

  const submit = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/submit-to-office`, {
        outcome: outcome || undefined,
        remarks: remarks || undefined,
      }),
    onSuccess: () => {
      toast.success("Submitted. The case is now awaiting office assignment.");
      client.invalidateQueries({ queryKey: ["navigation"] });
      setRemarks("");
      onDone();
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Submit to office"
      subtitle="This hands the case to the back office. It does not complete it."
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={!outcome || submit.isPending}
            onClick={() => submit.mutate()}
          >
            <Send /> Submit
          </button>
        </>
      }
    >
      <Field label="Outcome" hint="Required before a report leaves the field.">
        <SelectInput value={outcome} onChange={setOutcome} options={OUTCOMES} />
      </Field>
      <Field label="Remarks for the office">
        <TextArea
          value={remarks}
          onChange={setRemarks}
          rows={4}
          placeholder="What did you find? Anything the office should check?"
        />
      </Field>
    </Modal>
  );
}

/** Field-visit progress, tracked separately from the case status. */
export function VisitDialog({
  open,
  caseId,
  current,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  current?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [status, setStatus] = useState(current ?? "NOT_STARTED");
  const [scheduled, setScheduled] = useState("");
  const [remarks, setRemarks] = useState("");

  const save = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/visit`, {
        visit_status: status,
        visit_scheduled_at: scheduled ? new Date(scheduled).toISOString() : undefined,
        remarks: remarks || undefined,
      }),
    onSuccess: () => {
      toast.success("Visit status updated.");
      setRemarks("");
      onDone();
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Update visit status"
      subtitle="Visit progress is recorded apart from the case status."
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={save.isPending}
            onClick={() => save.mutate()}
          >
            <MapPin /> Save
          </button>
        </>
      }
    >
      <Field label="Visit status">
        <SelectInput value={status} onChange={setStatus} options={VISIT_STATES} />
      </Field>
      {status === "VISIT_SCHEDULED" && (
        <Field label="Scheduled for">
          <TextInput
            type="datetime-local"
            value={scheduled}
            onChange={setScheduled}
          />
        </Field>
      )}
      <Field label="Remarks">
        <TextArea value={remarks} onChange={setRemarks} rows={3} />
      </Field>
    </Modal>
  );
}

/**
 * Reopen a case that was closed by mistake.
 *
 * Most often that is a case whose imported file carried the client's own
 * "Completed" status. Without this the case is a dead end: read-only form,
 * no way forward.
 */
export function ReopenDialog({
  open,
  caseId,
  currentStatus,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId: string;
  currentStatus?: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const client = useQueryClient();
  const [reason, setReason] = useState("");

  const reopen = useMutation({
    mutationFn: async () => {
      const response = await api.post<{ message: string; detail?: string }>(
        `/cases/${caseId}/reopen`,
        { reason },
      );
      return response.data;
    },
    onSuccess: (data) => {
      toast.success(data.detail ? `${data.message} ${data.detail}` : data.message);
      client.invalidateQueries({ queryKey: ["navigation"] });
      setReason("");
      onDone();
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Reopen this case"
      subtitle={`It is currently ${currentStatus ?? "closed"}. Reopening is recorded.`}
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={reason.trim().length < 5 || reopen.isPending}
            onClick={() => reopen.mutate()}
          >
            <RotateCcw /> Reopen
          </button>
        </>
      }
    >
      <Field
        label="Why is this case being reopened?"
        hint="Saved to the case timeline and the audit log."
      >
        <TextArea
          value={reason}
          onChange={setReason}
          rows={4}
          placeholder="e.g. The imported file carried the client's own status; this case still needs to be worked."
        />
      </Field>
      <p className="card-note">
        The case goes back to whoever last held it — office staff if it reached
        the office, otherwise the investigator.
      </p>
    </Modal>
  );
}
