import { useEffect, useState } from "react";
import { api } from "../api";
import { Check, LOCATIONS, Recipe } from "../types";
import { ErrorBox, Modal, errorText, useAsync } from "./common";

interface Usage { item_id: string; item_name: string; amount: number; unit: string; }

// F09: review the amounts taken from each item, optional leftovers, then cook (one undoable command).
export default function CookDialog({ recipeId, servings, onClose }: { recipeId: string; servings: number; onClose: () => void }) {
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [checks, setChecks] = useState<Check[]>([]);
  const [usages, setUsages] = useState<Usage[]>([]);
  const [leftovers, setLeftovers] = useState(false);
  const [portions, setPortions] = useState(1);
  const [location, setLocation] = useState("fridge");
  const [done, setDone] = useState<string | null>(null);
  const { busy, error, setError, run } = useAsync();

  useEffect(() => {
    api.get(`/api/recipes/${recipeId}/cook?servings=${servings}`)
      .then((p) => { setRecipe(p.recipe); setChecks(p.checks); setUsages(p.usages); })
      .catch((e) => setError(errorText(e)));
  }, [recipeId, servings, setError]);

  const cook = () => run(async () => {
    const r = await api.post(`/api/recipes/${recipeId}/cook`, {
      usages: usages.filter((u) => u.amount > 0).map(({ item_id, amount, unit }) => ({ item_id, amount, unit })),
      leftover_portions: leftovers ? portions : null, leftover_location: location,
    });
    setDone(r.message);
  });

  const undo = () => run(async () => {
    const r = await api.post("/api/items/undo");
    setDone(r.message);
  });

  const missing = checks.filter((c) => c.status === "missing" || c.status === "short");
  return (
    <Modal title={`Cook ${recipe?.name ?? ""}`} onClose={onClose}>
      <ErrorBox error={error} />
      {done ? (
        <>
          <div className="ok">{done}</div>
          <div className="row"><button className="secondary" onClick={undo} disabled={busy}>Undo</button><button onClick={onClose}>Close</button></div>
        </>
      ) : (
        <>
          {usages.length === 0 && recipe && <p>None of this recipe's ingredients are in your inventory.</p>}
          <table className="table">
            <thead><tr><th>From item</th><th>Amount taken</th></tr></thead>
            <tbody>
              {usages.map((u, i) => (
                <tr key={i}>
                  <td>{u.item_name}</td>
                  <td>
                    <input type="number" min={0} step="any" value={u.amount} style={{ width: 90 }}
                      onChange={(e) => setUsages(usages.map((x, j) => (j === i ? { ...x, amount: +e.target.value } : x)))} /> {u.unit}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {missing.length > 0 && <p className="small warn-text">Not in stock: {missing.map((c) => c.ingredient).join(", ")}</p>}
          <label className="check"><input type="checkbox" checked={leftovers} onChange={(e) => setLeftovers(e.target.checked)} /> Any leftovers?</label>
          {leftovers && (
            <div className="row">
              <label>Portions <input type="number" min={1} max={20} value={portions} onChange={(e) => setPortions(+e.target.value)} style={{ width: 70 }} /></label>
              <label>Keep in <select value={location} onChange={(e) => setLocation(e.target.value)}>{LOCATIONS.map((l) => <option key={l}>{l}</option>)}</select></label>
            </div>
          )}
          <div className="row">
            <button onClick={cook} disabled={busy || (usages.length === 0 && !leftovers)}>{busy ? "Cooking…" : "Confirm cooking"}</button>
            <button className="secondary" onClick={onClose}>Cancel</button>
          </div>
        </>
      )}
    </Modal>
  );
}
