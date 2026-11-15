import { ReactNode, useEffect, useState } from "react";
import { ApiError } from "../api";
import { Trace } from "../types";

export function errorText(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  return e instanceof Error ? e.message : String(e);
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error" role="alert">{error}</div> : null;
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-label={title}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="link" onClick={onClose} aria-label="Close">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function PageTitle({ title, ids, children }: { title: string; ids: string; children?: ReactNode }) {
  return (
    <div className="page-title">
      <h2>{title} <span className="ids">{ids}</span></h2>
      {children && <p className="muted">{children}</p>}
    </div>
  );
}

export function TraceView({ trace }: { trace: Trace | null | undefined }) {
  const [open, setOpen] = useState(false);
  if (!trace) return null;
  return (
    <div className="trace">
      <button className="link small" onClick={() => setOpen(!open)}>
        {open ? "Hide" : "Show"} agent steps ({trace.steps.filter((s) => s.kind === "tool").length} tool calls)
      </button>
      {open && (
        <ol>
          {trace.steps.map((s, i) => (
            <li key={i}><b>{s.kind}</b>{s.tool ? ` ${s.tool}` : ""}: <span className="muted">{s.detail}</span></li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function useAsync() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(errorText(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  };
  return { busy, error, setError, run };
}
