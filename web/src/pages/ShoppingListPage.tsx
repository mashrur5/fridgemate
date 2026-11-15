import { FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, errorText, useAsync } from "../components/common";
import { Qty, UNITS, fmtQty } from "../types";

interface Line { id: string; name: string; quantity: Qty; section: string; reasons: string[]; shared: boolean; checked: boolean; }

// F11: low and used-up items appear automatically; recipe cards add missing ingredients; duplicates merge.
export default function ShoppingListPage() {
  const [sections, setSections] = useState<Record<string, Line[]>>({});
  const [f, setF] = useState({ name: "", amount: "", unit: "pcs", shared: false });
  const { busy, error, setError, run } = useAsync();

  const load = useCallback(() => {
    api.get("/api/shopping").then((r) => setSections(r.sections)).catch((e) => setError(errorText(e)));
  }, [setError]);
  useEffect(load, [load]);

  const add = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api.post("/api/shopping", { name: f.name, amount: f.amount ? +f.amount : null, unit: f.amount ? f.unit : null, shared: f.shared });
      setF({ ...f, name: "", amount: "" });
      load();
    });
  };
  const toggle = (l: Line) => run(async () => { await api.patch(`/api/shopping/${l.id}`, { checked: !l.checked }); load(); });
  const remove = (l: Line) => run(async () => { await api.del(`/api/shopping/${l.id}`); load(); });
  const clear = () => run(async () => { await api.del("/api/shopping/checked"); load(); });

  const all = Object.values(sections).flat();
  return (
    <>
      <PageTitle title="Shopping list" ids="F11">
        Items running low (a quarter or less left) are added automatically. Shared items appear on everyone's list.
      </PageTitle>
      <form className="card row" onSubmit={add}>
        <label style={{ flex: 3 }}>Item<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required maxLength={80} placeholder="flour" /></label>
        <label>Amount<input type="number" min="0.01" step="any" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></label>
        <label>Unit<select value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}>{UNITS.map((u) => <option key={u}>{u}</option>)}</select></label>
        <label className="check"><input type="checkbox" checked={f.shared} onChange={(e) => setF({ ...f, shared: e.target.checked })} /> Shared</label>
        <button disabled={busy}>Add</button>
      </form>
      <ErrorBox error={error} />
      {all.length === 0 && <p className="muted">Your shopping list is empty.</p>}
      {Object.entries(sections).map(([section, lines]) => (
        <section key={section}>
          <h3>{section}</h3>
          <div className="card list">
            {lines.map((l) => (
              <div key={l.id} className={`line ${l.checked ? "done" : ""}`}>
                <label className="check"><input type="checkbox" checked={l.checked} onChange={() => toggle(l)} /> <b>{l.name}</b> {fmtQty(l.quantity)}</label>
                <span className="small muted">{l.reasons.join(", ")}{l.shared ? " · Shared" : ""}</span>
                <span className="spacer" />
                <button className="link small" onClick={() => remove(l)} aria-label={`Remove ${l.name}`}>✕</button>
              </div>
            ))}
          </div>
        </section>
      ))}
      {all.some((l) => l.checked) && <button className="secondary" onClick={clear} style={{ marginTop: 10 }}>Clear checked items</button>}
    </>
  );
}
