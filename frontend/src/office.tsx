import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, CircleDot, Clock, UserRoundCheck } from "lucide-react";
import { api, errorMessage } from "./api";
import { Loading } from "./components";
import { Field, Modal, TextArea, useDebounced, useToast } from "./ui";
import type { AssignableStaff } from "./types";

/**
 * The staff picker used by both assignment stages.
 *
 * It shows presence and clock state side by side on purpose: they answer
 * different questions. Online means the person is at a screen; clocked in
 * means they are on shift. Neither blocks assignment — a manager may well
 * queue work for someone who starts in the morning — but seeing both stops
 * the common mistake of handing an urgent case to someone who has gone home.
 */
export function StaffPicker({
  stage,
  value,
  onChange,
}: {
  stage: "FIELD_INVESTIGATION" | "OFFICE_PROCESSING";
  value: string;
  onChange: (id: string) => void;
}) {
  const [search, setSearch] = useState("");
  const debounced = useDebounced(search);

  const query = useQuery({
    queryKey: ["assignable-staff", stage, debounced],
    queryFn: () =>
      api
        .get<AssignableStaff[]>("/cases/assignable-staff", {
          params: { stage, search: debounced || undefined },
        })
        .then((r) => r.data),
  });

  if (query.isLoading) return <Loading label="Loading staff…" />;
  const rows = query.data ?? [];

  return (
    <>
      <Field label="Find someone">
        <input
          placeholder="Search by name or email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </Field>
      {!rows.length ? (
        <p className="muted">
          Nobody has permission for this stage yet. Grant the{" "}
          {stage === "FIELD_INVESTIGATION"
            ? "Investigation"
            : "Office processing"}{" "}
          permission to a role under Administration.
        </p>
      ) : (
        <div className="assign-list">
          {rows.map((person) => (
            <button
              key={person.id}
              type="button"
              className={person.id === value ? "assign-row picked" : "assign-row"}
              onClick={() => onChange(person.id)}
            >
              <div className="who">
                <b>{person.full_name}</b>
                <small>{person.roles.join(", ") || person.email}</small>
              </div>
              <div className="load">
                <div>
                  <b>{person.active_cases}</b>
                  <small>Active</small>
                </div>
                <div>
                  <b>{person.pending_cases}</b>
                  <small>Pending</small>
                </div>
                <div>
                  <b>{person.completed_this_month}</b>
                  <small>Done</small>
                </div>
                <div>
                  <b>{person.overdue_cases}</b>
                  <small>Overdue</small>
                </div>
              </div>
              <div className="assign-badges">
                <span className={person.is_online ? "pill on" : "pill off"}>
                  <CircleDot /> {person.is_online ? "Online" : "Offline"}
                </span>
                <span
                  className={
                    person.clock_state === "CLOCKED_IN" ? "pill on" : "pill off"
                  }
                >
                  <Clock />
                  {person.clock_state === "CLOCKED_IN" ? "On shift" : "Off shift"}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </>
  );
}

/** Stage B assignment for one case, or for a selection of cases. */
export function OfficeAssignDialog({
  open,
  caseId,
  caseIds,
  onClose,
  onDone,
}: {
  open: boolean;
  caseId?: string;
  caseIds?: string[];
  onClose: () => void;
  onDone?: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [staffId, setStaffId] = useState("");
  const [notes, setNotes] = useState("");
  const bulk = !caseId && (caseIds?.length ?? 0) > 0;

  const assign = useMutation({
    mutationFn: async () => {
      const url = bulk
        ? "/cases/bulk-assign-office"
        : `/cases/${caseId}/assign-office`;
      const body: Record<string, unknown> = {
        office_staff_id: staffId,
        notes: notes || undefined,
      };
      if (bulk) body.case_ids = caseIds;
      const response = await api.post<{ message: string; detail?: string }>(
        url,
        body,
      );
      return response.data;
    },
    onSuccess: (data) => {
      toast.success(data.detail ? `${data.message} ${data.detail}` : data.message);
      client.invalidateQueries({ queryKey: ["cases"] });
      client.invalidateQueries({ queryKey: ["case"] });
      client.invalidateQueries({ queryKey: ["navigation"] });
      setStaffId("");
      setNotes("");
      onDone?.();
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Assign for office processing"
      subtitle={
        bulk
          ? `${caseIds?.length} case(s) will move to Office Processing.`
          : "The field assignment is kept — this adds the back-office owner."
      }
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={!staffId || assign.isPending}
            onClick={() => assign.mutate()}
          >
            <Building2 /> Assign to office
          </button>
        </>
      }
    >
      <StaffPicker
        stage="OFFICE_PROCESSING"
        value={staffId}
        onChange={setStaffId}
      />
      <Field label="Instructions (optional)">
        <TextArea
          value={notes}
          onChange={setNotes}
          rows={3}
          placeholder="What should the office check or prepare?"
        />
      </Field>
    </Modal>
  );
}

/** Stage A assignment, reused by the case list and the case detail page. */
export function FieldAssignDialog({
  open,
  caseId,
  onClose,
}: {
  open: boolean;
  caseId: string;
  onClose: () => void;
}) {
  const client = useQueryClient();
  const toast = useToast();
  const [staffId, setStaffId] = useState("");
  const [notes, setNotes] = useState("");

  const assign = useMutation({
    mutationFn: () =>
      api.post(`/cases/${caseId}/assign`, {
        assigned_to_id: staffId,
        notes: notes || undefined,
      }),
    onSuccess: () => {
      toast.success("Assigned to the investigator.");
      client.invalidateQueries({ queryKey: ["cases"] });
      client.invalidateQueries({ queryKey: ["case"] });
      client.invalidateQueries({ queryKey: ["navigation"] });
      setStaffId("");
      setNotes("");
      onClose();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Assign to a field investigator"
      subtitle="Stage 1 of 2. The office stage is assigned after the visit is submitted."
      footer={
        <>
          <button className="secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="primary"
            disabled={!staffId || assign.isPending}
            onClick={() => assign.mutate()}
          >
            <UserRoundCheck /> Assign
          </button>
        </>
      }
    >
      <StaffPicker
        stage="FIELD_INVESTIGATION"
        value={staffId}
        onChange={setStaffId}
      />
      <Field label="Instructions (optional)">
        <TextArea
          value={notes}
          onChange={setNotes}
          rows={3}
          placeholder="Anything the investigator should know before the visit?"
        />
      </Field>
    </Modal>
  );
}
