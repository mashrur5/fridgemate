import { useState } from "react";
import { api } from "../api";
import { ErrorBox, Modal, PageTitle, useAsync } from "../components/common";
import { Item, LOCATIONS, Me, UNITS } from "../types";

interface Draft { key: number; name: string; amount: number; unit: string; location: string; expiry_date: string;
  owner: string; price: string; note: string; }

const MAX_BYTES = 8 * 1024 * 1024;

// F03: photo (or pasted text) -> AI parse -> review popup with an owner dropdown per item -> save. No undo.
export default function ReceiptImportPage({ me }: { me: Me }) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [payer, setPayer] = useState(me.member.id);
  const [drafts, setDrafts] = useState<Draft[] | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const { busy, error, setError, run } = useAsync();
  const members = me.household!.members;

  const toDrafts = (items: Item[]) => items.map((i, n) => ({
    key: n, name: i.name, amount: i.quantity?.amount ?? 1, unit: i.quantity?.unit ?? "pcs", location: i.location,
    expiry_date: i.expiry_date, owner: "me", price: i.price ?? "", note: i.note ?? "",
  }));

  const pick = (f: File | null) => {
    setError(null);
    if (f && !["image/jpeg", "image/png", "image/webp"].includes(f.type)) return setError("Please choose a JPG, PNG or WEBP photo.");
    if (f && f.size > MAX_BYTES) return setError("The photo is too large (max 8 MB).");
    setFile(f);
  };

  const parse = () => run(async () => {
    setDone(null);
    let r;
    if (file) {
      const form = new FormData();
      form.append("photo", file);
      r = await api.upload("/api/receipts/parse", form);
    } else {
      r = await api.post("/api/receipts/parse-text", { text });
    }
    setDrafts(toDrafts(r.items));
  });

  const update = (key: number, patch: Partial<Draft>) => setDrafts(drafts!.map((d) => (d.key === key ? { ...d, ...patch } : d)));

  const save = () => run(async () => {
    const items = drafts!.map((d) => ({
      name: d.name, amount: +d.amount, unit: d.unit, location: d.location, expiry_date: d.expiry_date || null,
      owner: d.owner, price: d.price === "" ? null : d.price,
    }));
    const r = await api.post("/api/receipts/save", { items, payer_id: payer || null });
    setDrafts(null);
    setFile(null);
    setText("");
    setDone(`${r.message}. They're on the Inventory page.`);
  });

  return (
    <>
      <PageTitle title="Import receipt" ids="F03">
        Upload a photo of a grocery receipt. The AI reads it, and you review every item before anything is saved.
      </PageTitle>
      {done && <div className="ok">{done}</div>}
      <ErrorBox error={error} />
      <div className="card form">
        <label>Receipt photo (JPG, PNG or WEBP, max 8 MB)
          <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => pick(e.target.files?.[0] ?? null)} />
        </label>
        {!file && (
          <label>…or paste the receipt text
            <textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} placeholder={"GRN ONIO 1.29\nMLK 2% 2L 5.49"} />
          </label>
        )}
        <label>Who paid?
          <select value={payer} onChange={(e) => setPayer(e.target.value)}>
            {members.map((m) => <option key={m.id} value={m.id}>{m.id === me.member.id ? "Me" : m.name}</option>)}
            <option value="">Nobody / don't split</option>
          </select>
        </label>
        <div><button onClick={parse} disabled={busy || (!file && !text.trim())}>{busy && !drafts ? "Reading the receipt…" : "Read receipt"}</button></div>
      </div>

      {drafts && (
        <Modal title={`Review ${drafts.length} item(s)`} onClose={() => setDrafts(null)}>
          <p className="small muted">Set the owner of each item, fix anything wrong, remove lines that aren't yours. Nothing is saved until you press Save.</p>
          {drafts.map((d) => (
            <div key={d.key} className="draft">
              {d.note.startsWith("Check this") && <div className="small warn-text">⚠ Check this line, it was hard to read.</div>}
              <div className="row">
                <label style={{ flex: 3 }}>Name<input value={d.name} onChange={(e) => update(d.key, { name: e.target.value })} /></label>
                <label>Owner
                  <select value={d.owner} onChange={(e) => update(d.key, { owner: e.target.value })}>
                    <option value="me">Mine</option><option value="shared">Shared</option>
                    {members.filter((m) => m.id !== me.member.id).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                  </select>
                </label>
                <button className="danger" onClick={() => setDrafts(drafts.filter((x) => x.key !== d.key))} aria-label="Remove">✕</button>
              </div>
              <div className="row">
                <label>Qty<input type="number" min="0.01" step="any" value={d.amount} onChange={(e) => update(d.key, { amount: +e.target.value })} /></label>
                <label>Unit<select value={d.unit} onChange={(e) => update(d.key, { unit: e.target.value })}>{UNITS.map((u) => <option key={u}>{u}</option>)}</select></label>
                <label>Where<select value={d.location} onChange={(e) => update(d.key, { location: e.target.value })}>{LOCATIONS.map((l) => <option key={l}>{l}</option>)}</select></label>
                <label>Expires<input type="date" value={d.expiry_date} onChange={(e) => update(d.key, { expiry_date: e.target.value })} /></label>
                <label>Price<input type="number" min="0" step="0.01" value={d.price} onChange={(e) => update(d.key, { price: e.target.value })} /></label>
              </div>
            </div>
          ))}
          <button className="secondary" onClick={() => setDrafts([...drafts, { key: Date.now(), name: "", amount: 1, unit: "pcs",
            location: "fridge", expiry_date: "", owner: "me", price: "", note: "" }])}>+ Add a missing item</button>
          <ErrorBox error={error} />
          <div className="row">
            <button onClick={save} disabled={busy || drafts.length === 0 || drafts.some((d) => !d.name.trim())}>
              Save {drafts.length} item(s)
            </button>
            <button className="secondary" onClick={() => setDrafts(null)}>Close without saving</button>
          </div>
          <p className="small muted">Receipt imports can't be undone; edit items later on the Inventory page.</p>
        </Modal>
      )}
    </>
  );
}
