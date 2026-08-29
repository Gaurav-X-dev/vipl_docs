import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";

/* ------------------------------------------------------------------ *
 * Modal
 * ------------------------------------------------------------------ */
export function Modal({
  open,
  title,
  subtitle,
  onClose,
  children,
  footer,
  wide,
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-root" role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal-backdrop" onClick={onClose} />
      <div className={wide ? "modal wide" : "modal"}>
        <header className="modal-head">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  danger,
  busy,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <button className="secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            className={danger ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working…" : confirmLabel}
          </button>
        </>
      }
    >
      <p className="confirm-message">{message}</p>
    </Modal>
  );
}

/* ------------------------------------------------------------------ *
 * Form primitives
 * ------------------------------------------------------------------ */
export type Option = { value: string; label: string };

export function Field({
  label,
  required,
  hint,
  error,
  span,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  span?: 1 | 2;
  children: ReactNode;
}) {
  return (
    <label className={span === 2 ? "field span-2" : "field"}>
      <span className="field-label">
        {label}
        {required && <i aria-hidden="true"> *</i>}
      </span>
      {children}
      {error ? (
        <small className="field-error">{error}</small>
      ) : (
        hint && <small className="field-hint">{hint}</small>
      )}
    </label>
  );
}

export function TextInput({
  value,
  onChange,
  type = "text",
  placeholder,
  disabled,
  readOnly,
  min,
  max,
}: {
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
  readOnly?: boolean;
  min?: string | number;
  max?: string | number;
}) {
  return (
    <input
      type={type}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      readOnly={readOnly}
      min={min}
      max={max}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function TextArea({
  value,
  onChange,
  rows = 4,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  rows?: number;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <textarea
      rows={rows}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function SelectInput({
  value,
  onChange,
  options,
  placeholder = "Select…",
  disabled,
  allowEmpty = true,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  placeholder?: string;
  disabled?: boolean;
  allowEmpty?: boolean;
}) {
  return (
    <select
      // Lets the stylesheet highlight a filter that is actually narrowing
      // the list, so an active filter is visible at a glance.
      data-empty={value ? "false" : "true"}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {allowEmpty && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label className="checkbox">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  );
}

export function FormGrid({ children }: { children: ReactNode }) {
  return <div className="form-grid">{children}</div>;
}

export function Form({
  onSubmit,
  children,
}: {
  onSubmit: () => void;
  children: ReactNode;
}) {
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };
  return <form onSubmit={submit}>{children}</form>;
}

/* ------------------------------------------------------------------ *
 * Tabs
 * ------------------------------------------------------------------ */
export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; count?: number }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          className={active === t.key ? "active" : ""}
          onClick={() => onChange(t.key)}
        >
          {t.label}
          {t.count !== undefined && <em>{t.count}</em>}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ *
 * Toasts
 * ------------------------------------------------------------------ */
type Toast = { id: number; kind: "success" | "error" | "info"; message: string };
type ToastValue = {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
};

const ToastContext = createContext<ToastValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const seq = useRef(0);

  const push = useCallback((kind: Toast["kind"], message: string) => {
    const id = ++seq.current;
    setItems((list) => [...list, { id, kind, message }]);
    window.setTimeout(
      () => setItems((list) => list.filter((t) => t.id !== id)),
      kind === "error" ? 7000 : 4000,
    );
  }, []);

  const value = useMemo<ToastValue>(
    () => ({
      success: (m) => push("success", m),
      error: (m) => push("error", m),
      info: (m) => push("info", m),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {items.map((t) => (
          <div className={`toast ${t.kind}`} key={t.id}>
            {t.kind === "success" ? (
              <CheckCircle2 />
            ) : t.kind === "error" ? (
              <AlertTriangle />
            ) : (
              <Info />
            )}
            <span>{t.message}</span>
            <button
              className="icon-button"
              aria-label="Dismiss"
              onClick={() => setItems((l) => l.filter((x) => x.id !== t.id))}
            >
              <X />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error("ToastProvider missing");
  return value;
}

/* ------------------------------------------------------------------ *
 * Misc helpers
 * ------------------------------------------------------------------ */
export function useDebounced<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}

export function PermissionDenied({ what }: { what: string }) {
  return (
    <div className="state error">
      <AlertTriangle />
      <strong>Permission denied</strong>
      <span>You do not have access to {what}. Contact your administrator.</span>
    </div>
  );
}

export function SectionTitle({
  title,
  action,
}: {
  title: string;
  action?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="section-title">
      <h2 id={id}>{title}</h2>
      {action}
    </div>
  );
}
