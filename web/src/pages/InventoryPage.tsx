import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, qs } from "../api";
import { ErrorBox, Modal, PageTitle, errorText, useAsync } from "../components/common";
import { Item, LOCATIONS, Me, UNITS, fmtQty } from "../types";

const FRESH_CLASS: Record<string, string> = { Fresh: "fresh", "Expiring soon": "soon", Expired: "expired" };

// F01 inventory, F02/F04 suggestions in the form, F05 "Use it first" tab, F15 offer / claim.
export default function InventoryPage({ me }: { me: Me }) {
  const [tab, setTab] = useState<"all" | "first">("all");
  const [items, setItems] = useState<Item[]>([]);
  const [alerts, setAlerts] = useState<{ expiring: Item[]; expired: Item[]; banner: string | null }>({ expiring: [], expired: [], banner: null });
  const [filters, setFilters] = useState({ q: "", location: "", owner: "", freshness: "" });
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [editing, setEditing] = useState<Item | "new" | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const { error, setError, run } = useAsync();

  const load = useCallback(async () => {
    try {
      const [list, a] = await Promise.all([api.get(`/api/items${qs(filters)}`), api.get("/api/items/alerts")]);
      setItems(list.items);
      setLastAction(list.last_action);
      setAlerts(a);
    } catch (e) {
      setError(errorText(e));
    }
  }, [filters, setError]);

  useEffect(() => { load(); }, [load]);

  const act = (fn: () => Promise<any>, message?: string) => run(async () => {
    await fn();
    if (message) setFlash(message);
    await load();
  });

  const undo = () => run(async () => {
    const r = await api.post("/api/items/undo");
    setFlash(r.message);
    await load();
  });

  const offer = (i: Item) => {
    const note = window.prompt(`Offer ${i.name} to your roommates. Optional note:`, "");
    if (note === null) return;
    act(() => api.post(`/api/items/${i.id}/offer`, { note }), `Offered ${i.name} to the household.`);
  };

  const row = (i: Item, actions = true) => (
    <tr key={i.id} className={i.freshness === "Expired" ? "dim" : ""}>
      <td>
        <b>{i.name}</b> {i.is_low && <span className="tag warn">low</span>}
        {i.is_offered && <div className="small muted">Offered by {i.offered_by}, expires in {i.days_left} day(s)</div>}
      </td>
      <td>{fmtQty(i.quantity)}</td>
      <td className="hide-sm">{i.location}</td>
      <td>{i.owner}</td>
      <td>
        <span className={`fresh-label ${FRESH_CLASS[i.freshness]}`}>{i.freshness}</span>
        <div className="small muted">{i.expiry_date}{i.expiry_estimated ? " (estimated)" : ""}</div>
      </td>
      {actions && (
        <td className="actions">
          {i.can_claim && <button onClick={() => act(() => api.post(`/api/items/${i.id}/claim`), `You claimed ${i.name}.`)}>Claim</button>}
          {i.can_offer && <button className="secondary" onClick={() => offer(i)}>Offer to household</button>}
          {i.editable && <button className="secondary" onClick={() => setEditing(i)}>Edit</button>}
          {i.editable && <button className="danger" onClick={() => act(() => api.del(`/api/items/${i.id}`), `Removed ${i.name}.`)}>Remove</button>}
        </td>
      )}
    </tr>
  );

  const table = (list: Item[]) => (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th>Item</th><th>Qty</th><th className="hide-sm">Where</th><th>Owner</th><th>Freshness</th><th /></tr></thead>
        <tbody>{list.map((i) => row(i))}</tbody>
      </table>
    </div>
  );

  const byLocation = LOCATIONS.map((l) => [l, items.filter((i) => i.location === l)] as const).filter(([, v]) => v.length);

  return (
    <>
      <PageTitle title="Inventory" ids="F01 F02 F04 F05 F15">Everything you can use: your items, Shared items, and roommates' offers.</PageTitle>
      {alerts.banner && (
        <button className="banner" onClick={() => setTab("first")}>⚠ {alerts.banner}. Open "Use it first".</button>
      )}
      <div className="row">
        <div className="tabs">
          <button className={tab === "all" ? "active" : ""} onClick={() => setTab("all")}>All items</button>
          <button className={tab === "first" ? "active" : ""} onClick={() => setTab("first")}>Use it first ({alerts.expiring.length})</button>
        </div>
        <span className="spacer" />
        {lastAction && <button className="secondary" onClick={undo}>Undo "{lastAction}"</button>}
        <button onClick={() => setEditing("new")}>+ Add item</button>
      </div>
      {flash && <div className="ok" onClick={() => setFlash(null)}>{flash}</div>}
      <ErrorBox error={error} />
      {tab === "all" ? (
        <>
          <div className="filters">
            <input placeholder="Search" value={filters.q} onChange={(e) => setFilters({ ...filters, q: e.target.value })} />
            <select value={filters.location} onChange={(e) => setFilters({ ...filters, location: e.target.value })}>
              <option value="">All locations</option>{LOCATIONS.map((l) => <option key={l}>{l}</option>)}
            </select>
            <select value={filters.owner} onChange={(e) => setFilters({ ...filters, owner: e.target.value })}>
              <option value="">All owners</option><option value="me">Mine</option><option value="shared">Shared</option><option value="offered">Offered</option>
            </select>
            <select value={filters.freshness} onChange={(e) => setFilters({ ...filters, freshness: e.target.value })}>
              <option value="">Any freshness</option><option>Fresh</option><option>Expiring soon</option><option>Expired</option>
            </select>
          </div>
          {items.length === 0 && <p className="muted">No items yet. Add one, import a receipt, or tell the Chat what you bought.</p>}
          {byLocation.map(([loc, list]) => (
            <section key={loc}><h3 className="cap">{loc}</h3>{table(list)}</section>
          ))}
        </>
      ) : (
        <>
          {alerts.expiring.length === 0 ? <p className="muted">Nothing is expiring soon.</p> : table(alerts.expiring)}
          {alerts.expired.length > 0 && <><h3>Expired</h3>{table(alerts.expired)}</>}
        </>
      )}
      {editing && <ItemForm me={me} item={editing === "new" ? null : editing} onClose={() => setEditing(null)}
        onSaved={(m) => { setEditing(null); setFlash(m); load(); }} />}
    </>
  );
}

function ItemForm({ me, item, onClose, onSaved }: { me: Me; item: Item | null; onClose: () => void; onSaved: (msg: string) => void }) {
  const [f, setF] = useState({
    name: item?.name ?? "", amount: String(item?.quantity?.amount ?? ""), unit: item?.quantity?.unit ?? "pcs",
    location: item?.location ?? "", expiry_date: item && !item.expiry_estimated ? item.expiry_date : "",
    owner: item ? (item.owner === "Shared" ? "shared" : item.mine ? "me" : item.owner_id ?? "me") : "me",
    price: item?.price ?? "", paid: !!item?.payer,
  });
  const [hint, setHint] = useState<any>(null);
  const { busy, error, run } = useAsync();

  // F02 + F04: show the suggestion once a name is typed and Location is "Suggest for me".
  useEffect(() => {
    if (item || f.name.trim().length < 2) { setHint(null); return; }
    const t = setTimeout(() => {
      api.get(`/api/items/suggest${qs({ name: f.name, location: f.location })}`).then(setHint).catch(() => setHint(null));
    }, 600);
    return () => clearTimeout(t);
  }, [f.name, f.location, item]);

  const save = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      const body: any = {
        name: f.name, amount: +f.amount, unit: f.unit, location: f.location || null, expiry_date: f.expiry_date || null,
        owner: f.owner, price: f.price === "" ? null : f.price, payer_id: f.price !== "" && f.paid ? me.member.id : null,
      };
      if (item) {
        await api.patch(`/api/items/${item.id}`, body);
        onSaved(`Updated ${f.name}.`);
      } else {
        const r = await api.post("/api/items", body);
        onSaved([`Added ${r.item.name} to the ${r.item.location}.`, r.location_note, r.expiry_note].filter(Boolean).join(" "));
      }
    });
  };

  const others = me.household!.members.filter((m) => m.id !== me.member.id);
  return (
    <Modal title={item ? `Edit ${item.name}` : "Add item"} onClose={onClose}>
      <form onSubmit={save} className="form">
        <label>Name<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required maxLength={80} autoFocus /></label>
        <div className="row">
          <label>Quantity<input type="number" min="0.01" step="any" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} required /></label>
          <label>Unit<select value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}>{UNITS.map((u) => <option key={u}>{u}</option>)}</select></label>
        </div>
        <label>Location
          <select value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })}>
            {!item && <option value="">Suggest for me</option>}
            {LOCATIONS.map((l) => <option key={l}>{l}</option>)}
          </select>
        </label>
        {hint && !f.location && <div className="hint">💡 {hint.location}: {hint.reason} <span className="muted">({hint.location_source === "ai" ? "AI" : "rule table"})</span></div>}
        <label>Expiry date<input type="date" value={f.expiry_date} onChange={(e) => setF({ ...f, expiry_date: e.target.value })} /></label>
        {hint && !f.expiry_date && <div className="hint">📅 Estimated {hint.expiry_date} <span className="muted">({hint.expiry_source === "ai" ? "AI" : "rule table"}), leave empty to use it</span></div>}
        <label>Owner
          <select value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })}>
            <option value="me">Me</option><option value="shared">Shared</option>
            {others.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
        </label>
        <div className="row">
          <label>Price ($)<input type="number" min="0" step="0.01" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} /></label>
          <label className="check"><input type="checkbox" checked={f.paid} onChange={(e) => setF({ ...f, paid: e.target.checked })} /> I paid</label>
        </div>
        <ErrorBox error={error} />
        <div className="row"><button disabled={busy}>{busy ? "Saving…" : "Save"}</button><button type="button" className="secondary" onClick={onClose}>Cancel</button></div>
      </form>
    </Modal>
  );
}
