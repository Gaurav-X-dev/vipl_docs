import type { ReactNode } from "react";
import { AlertTriangle, Search } from "lucide-react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      <div className="actions">{actions}</div>
    </header>
  );
}
export function Card({
  children,
  className = "",
  title,
  action,
}: {
  children: ReactNode;
  className?: string;
  title?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-head">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
/**
 * A spinner tells you to wait; a skeleton tells you what is coming. Rows are
 * the shape of the table that is about to replace them, so the page does not
 * jump when the data lands.
 */
export function Loading({
  label = "Loading data…",
  rows = 5,
}: {
  label?: string;
  rows?: number;
}) {
  return (
    <div className="skeleton" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index}>
          <span style={{ width: "22%" }} />
          <span style={{ width: "30%" }} />
          <span style={{ width: "14%" }} />
          <span style={{ width: "18%" }} />
        </div>
      ))}
      <span className="sr-only">{label}</span>
    </div>
  );
}
export function ErrorState({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="state error">
      <AlertTriangle />
      <strong>Could not load</strong>
      <span>{message}</span>
      {retry && <button onClick={retry}>Try again</button>}
    </div>
  );
}
export function Empty({
  title = "No records found",
  detail = "Try changing your filters or add a new record.",
}: {
  title?: string;
  detail?: string;
}) {
  return (
    <div className="state empty">
      <Search />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}
export function Status({ value, label }: { value: string; label?: string }) {
  const key = value.toLowerCase().replaceAll("_", "-");
  return (
    <span className={`badge badge-${key}`}>
      {label || value.replaceAll("_", " ")}
    </span>
  );
}
export function Online({ online, label }: { online: boolean; label?: string }) {
  return (
    <span className="online">
      <i className={online ? "dot on" : "dot"} />
      {label || (online ? "Online" : "Offline")}
    </span>
  );
}
export function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (p: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="pagination">
      <button disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {totalPages}
      </span>
      <button disabled={page >= totalPages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </div>
  );
}
export const fmtDate = (value?: string) =>
  value
    ? new Intl.DateTimeFormat("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(new Date(value))
    : "—";
export const fmtDateTime = (value?: string) =>
  value
    ? new Intl.DateTimeFormat("en-IN", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
export const num = (value: unknown) =>
  new Intl.NumberFormat("en-IN").format(Number(value || 0));
