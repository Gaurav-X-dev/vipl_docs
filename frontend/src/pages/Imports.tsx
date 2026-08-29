import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  FileSpreadsheet,
  RotateCcw,
  UploadCloud,
  XCircle,
} from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, download, errorMessage } from "../api";
import { useAuth } from "../auth";
import {
  Card,
  Empty,
  ErrorState,
  Loading,
  PageHeader,
  Pagination,
  Status,
  fmtDateTime,
  num,
} from "../components";
import {
  Checkbox,
  ConfirmDialog,
  PermissionDenied,
  Tabs,
  useToast,
} from "../ui";
import type {
  ImportBatch,
  ImportPreview,
  ImportPreviewRow,
  Page,
} from "../types";

export default function Imports() {
  const { can } = useAuth();
  const client = useQueryClient();
  const toast = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [rowTab, setRowTab] = useState("all");
  const [page, setPage] = useState(1);
  const [rollingBack, setRollingBack] = useState<ImportBatch | null>(null);
  // Off by default: the client's Status column tracks their progress, not
  // ours, and honouring it creates cases that arrive already closed.
  const [applyFileStatus, setApplyFileStatus] = useState(false);

  const canImport = can("import.create");
  const canRollback = can("import.rollback");

  const list = useQuery({
    queryKey: ["imports", page],
    enabled: can("import.view"),
    queryFn: () =>
      api
        .get<Page<ImportBatch>>("/imports", {
          params: { page, page_size: 15 },
        })
        .then((r) => r.data),
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const data = new FormData();
      data.append("file", file);
      return api
        .post<ImportPreview>("/imports/upload", data)
        .then((r) => r.data);
    },
    onSuccess: (data) => {
      setPreview(data);
      setRowTab("all");
      client.invalidateQueries({ queryKey: ["imports"] });
      toast.success(
        `${data.summary.total_rows} rows read · ${data.summary.valid} ready to import.`,
      );
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const commit = useMutation({
    mutationFn: (id: string) =>
      api
        .post(`/imports/${id}/commit`, {
          skip_duplicates: true,
          auto_assign: true,
          apply_file_status: applyFileStatus,
        })
        .then((r) => r.data as { message: string }),
    onSuccess: (data) => {
      toast.success(data.message);
      setPreview(null);
      client.invalidateQueries({ queryKey: ["imports"] });
      client.invalidateQueries({ queryKey: ["cases"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  const rollback = useMutation({
    mutationFn: (id: string) =>
      api.post(`/imports/${id}/rollback`).then((r) => r.data as { message: string }),
    onSuccess: (data) => {
      toast.success(data.message);
      client.invalidateQueries({ queryKey: ["imports"] });
      client.invalidateQueries({ queryKey: ["cases"] });
      setRollingBack(null);
    },
    onError: (e) => {
      toast.error(errorMessage(e));
      setRollingBack(null);
    },
  });

  if (!can("import.view") && !canImport)
    return <PermissionDenied what="case imports" />;

  async function downloadErrors(batch: ImportBatch) {
    try {
      await download(
        `/imports/${batch.id}/errors/download`,
        `${batch.batch_number}_rejected_rows.xlsx`,
      );
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  const rows: ImportPreviewRow[] = preview
    ? preview.rows.filter((row) => {
        if (rowTab === "all") return true;
        if (rowTab === "errors") return row.status === "ERROR";
        if (rowTab === "duplicates") return row.status === "DUPLICATE";
        if (rowTab === "warnings") return row.status === "WARNING";
        return row.status === "VALID";
      })
    : [];

  return (
    <>
      <PageHeader
        title="Daily case import"
        subtitle="Upload the client file, validate every row, then create cases in one controlled transaction."
      />

      {canImport && (
        <Card className="upload-card">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,.csv"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
              e.target.value = "";
            }}
          />
          <button
            className="dropzone"
            onClick={() => fileRef.current?.click()}
            disabled={upload.isPending}
          >
            <UploadCloud />
            <b>
              {upload.isPending
                ? "Reading and validating…"
                : "Choose Excel or CSV file"}
            </b>
            <span>Supports .xlsx, .xlsm and .csv · up to 40 MB</span>
          </button>
          <p className="card-note">
            The exact same file cannot be imported twice — a checksum check
            blocks it. Column headers are matched case-insensitively against the
            configured mapping.
          </p>
        </Card>
      )}

      {preview && (
        <Card
          title={`Validation preview · ${preview.batch.batch_number}`}
          action={<Status value={preview.batch.status} />}
        >
          <div className="summary-strip">
            <span>
              <b>{num(preview.summary.total_rows)}</b>Total rows
            </span>
            <span className="success">
              <CheckCircle2 />
              <b>{num(preview.summary.valid)}</b>Valid
            </span>
            <span className="warn">
              <AlertTriangle />
              <b>{num(preview.summary.warnings)}</b>Warnings
            </span>
            <span className="danger">
              <XCircle />
              <b>{num(preview.summary.errors)}</b>Errors
            </span>
            <span>
              <Copy />
              <b>{num(preview.summary.duplicates)}</b>Duplicates
            </span>
          </div>

          {preview.unmapped_headers.length > 0 && (
            <div className="banner warning">
              <AlertTriangle />
              <div>
                <b>{preview.unmapped_headers.length} column(s) not mapped</b>
                <span>
                  {preview.unmapped_headers.join(", ")} — these are kept in the
                  row snapshot but not written to the case.
                </span>
              </div>
            </div>
          )}

          <details className="mapping-details">
            <summary>Column mapping applied to this file</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Spreadsheet column</th>
                    <th>Internal field</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(preview.mapping).map(([header, field]) => (
                    <tr key={header}>
                      <td>{header}</td>
                      <td>
                        {field ? (
                          <code>{field}</code>
                        ) : (
                          <span className="muted">not mapped</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>

          <Tabs
            tabs={[
              { key: "all", label: "All rows", count: preview.rows.length },
              { key: "valid", label: "Valid" },
              { key: "warnings", label: "Warnings" },
              { key: "errors", label: "Errors", count: preview.summary.errors },
              {
                key: "duplicates",
                label: "Duplicates",
                count: preview.summary.duplicates,
              },
            ]}
            active={rowTab}
            onChange={setRowTab}
          />

          {!rows.length ? (
            <Empty title="No rows in this view" />
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Status</th>
                    <th>Company</th>
                    <th>Case type</th>
                    <th>Life assured</th>
                    <th>Policy / KRN</th>
                    <th>Validation</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.row_number}>
                      <td>{row.row_number}</td>
                      <td>
                        <Status value={row.status} />
                      </td>
                      <td>{String(row.parsed.company_code ?? "—")}</td>
                      <td>{String(row.parsed.case_type_code ?? "—")}</td>
                      <td>{String(row.parsed.life_assured_name ?? "—")}</td>
                      <td>
                        {String(
                          row.parsed.policy_number ?? row.parsed.krn_no ?? "—",
                        )}
                      </td>
                      <td className="validation wrap">
                        {row.errors.length
                          ? row.errors.join(" · ")
                          : row.warnings.length
                            ? row.warnings.join(" · ")
                            : "Ready"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="import-options">
            <Checkbox
              checked={applyFileStatus}
              onChange={setApplyFileStatus}
              label="Use the Status column from the file"
            />
            <small>
              Leave this off for the daily file. The client's Status column is
              their own tracking note — applying it would create cases that
              arrive already closed and cannot be worked. Every new case starts
              as Imported and is kept as a note on the case.
            </small>
          </div>

          <div className="actions end">
            {preview.summary.errors > 0 && (
              <button
                className="secondary"
                onClick={() => downloadErrors(preview.batch)}
              >
                <FileSpreadsheet /> Download rejected rows
              </button>
            )}
            <button className="secondary" onClick={() => setPreview(null)}>
              Cancel
            </button>
            <button
              className="primary"
              disabled={commit.isPending || preview.summary.valid === 0}
              onClick={() => commit.mutate(preview.batch.id)}
            >
              {commit.isPending
                ? "Creating cases…"
                : `Confirm & create ${preview.summary.valid} case${preview.summary.valid === 1 ? "" : "s"}`}
            </button>
          </div>
        </Card>
      )}

      <Card title="Import history">
        {list.isLoading ? (
          <Loading />
        ) : list.isError ? (
          <ErrorState message={errorMessage(list.error)} />
        ) : !list.data?.items.length ? (
          <Empty
            title="No imports yet"
            detail="Upload the client's daily file to create cases automatically."
          />
        ) : (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>File</th>
                    <th>Status</th>
                    <th>Rows</th>
                    <th>Imported</th>
                    <th>Errors</th>
                    <th>Duplicates</th>
                    <th>Uploaded by</th>
                    <th>When</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody>
                  {list.data.items.map((b) => (
                    <tr key={b.id}>
                      <td>
                        <b>{b.batch_number}</b>
                      </td>
                      <td>
                        <FileSpreadsheet className="table-icon" />
                        {b.original_filename}
                      </td>
                      <td>
                        <Status value={b.status} />
                      </td>
                      <td>{num(b.total_rows)}</td>
                      <td>
                        {b.imported_rows > 0 ? (
                          <Link to={`/cases?import_batch_id=${b.id}`}>
                            <b>{num(b.imported_rows)}</b>
                          </Link>
                        ) : (
                          num(b.imported_rows)
                        )}
                      </td>
                      <td className={b.error_rows ? "danger-text" : ""}>
                        {num(b.error_rows)}
                      </td>
                      <td>{num(b.duplicate_rows)}</td>
                      <td>{b.uploaded_by?.full_name || "—"}</td>
                      <td>{fmtDateTime(b.created_at)}</td>
                      <td className="row-actions">
                        {b.error_rows > 0 && (
                          <button
                            className="icon-button"
                            title="Download rejected rows"
                            onClick={() => downloadErrors(b)}
                          >
                            <FileSpreadsheet />
                          </button>
                        )}
                        {canRollback &&
                          ["COMPLETED", "COMPLETED_WITH_ERRORS"].includes(
                            b.status,
                          ) && (
                            <button
                              className="icon-button danger"
                              title="Roll this batch back"
                              onClick={() => setRollingBack(b)}
                            >
                              <RotateCcw />
                            </button>
                          )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              page={list.data.meta.page}
              totalPages={list.data.meta.total_pages}
              onPage={setPage}
            />
          </>
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(rollingBack)}
        title={`Roll back ${rollingBack?.batch_number}?`}
        message={`Every case created by this import will be deleted. This is refused if work has already started on any of them. ${rollingBack?.imported_rows ?? 0} case(s) would be removed.`}
        confirmLabel="Roll back import"
        danger
        busy={rollback.isPending}
        onConfirm={() => rollingBack && rollback.mutate(rollingBack.id)}
        onClose={() => setRollingBack(null)}
      />
    </>
  );
}
