import { useState } from "react";
import { api } from "../api";
import { Suggestion } from "../types";
import CookDialog from "./CookDialog";
import { errorText } from "./common";

export default function RecipeCard({ s, canCook, servings }: { s: Suggestion; canCook: boolean; servings: number }) {
  const [why, setWhy] = useState(false);
  const [cooking, setCooking] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const have = s.checks.filter((c) => c.status === "have");
  const missing = s.checks.filter((c) => c.status === "missing" || c.status === "short");
  const check = s.checks.filter((c) => c.status === "check amount");

  const addMissing = async () => {
    try {
      const r = await api.post(`/api/recipes/${s.recipe.id}/missing-to-shopping?servings=${servings}`);
      setMsg(r.added.length ? `Added ${r.added.length} item(s) to your shopping list.` : "You already have everything.");
    } catch (e) {
      setMsg(errorText(e));
    }
  };

  return (
    <div className="card recipe">
      {s.recipe.image_url && <img src={s.recipe.image_url + "/preview"} alt="" loading="lazy" />}
      <div className="recipe-body">
        <h3>
          {s.recipe.name} {s.recipe.ai_generated && <span className="tag ai">AI-generated</span>}
        </h3>
        <div className="muted small">
          {[s.recipe.cuisine, s.estimated_minutes && `~${s.estimated_minutes} min (est.)`, s.weight && `${s.weight} (est.)`]
            .filter(Boolean).join(" · ")}
        </div>
        <div className="small">
          <b>You have:</b>{" "}
          {have.map((c) => (
            <span key={c.ingredient} className={c.expiring ? "tag warn" : "tag"}>{c.ingredient}</span>
          ))}
        </div>
        {missing.length > 0 && (
          <div className="small">
            <b>Missing:</b>{" "}
            {missing.map((c) => (
              <span key={c.ingredient} className="tag bad">
                {c.ingredient}{c.status === "short" ? " (short)" : ""}
                {c.substitute && !accepted[c.ingredient] && (
                  <> · use {c.substitute}? <button className="link small" onClick={() => setAccepted({ ...accepted, [c.ingredient]: true })}>Accept</button></>
                )}
                {accepted[c.ingredient] && <> → {c.substitute} ✓</>}
              </span>
            ))}
          </div>
        )}
        {check.length > 0 && <div className="small muted">Check amount: {check.map((c) => c.ingredient).join(", ")}</div>}
        {why && <p className="small explain">{s.explanation || "No explanation given."}</p>}
        <div className="row">
          <button className="secondary" onClick={() => setWhy(!why)}>Why this recipe?</button>
          {canCook && <button onClick={() => setCooking(true)}>Cook this</button>}
          {missing.length > 0 && <button className="secondary" onClick={addMissing}>Add missing to shopping list</button>}
        </div>
        {msg && <div className="ok small">{msg}</div>}
      </div>
      {cooking && <CookDialog recipeId={s.recipe.id} servings={servings} onClose={() => setCooking(false)} />}
    </div>
  );
}
