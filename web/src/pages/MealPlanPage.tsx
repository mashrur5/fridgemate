import { useEffect, useState } from "react";
import { api } from "../api";
import CookDialog from "../components/CookDialog";
import { ErrorBox, PageTitle, TraceView, errorText, useAsync } from "../components/common";
import { Suggestion, Trace } from "../types";

interface Meal { day: string; slot: number; suggestion: Suggestion | null; outdated?: boolean; }
interface Plan { id: string; start: string; days: number; meals: Meal[]; missing_days: string[]; notes: string[];
  needs_update: boolean; created_at: string; trace?: Trace | null; }

const dayName = (iso: string) => new Date(iso + "T12:00").toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

// F13: the meal-plan agent plans 3 to 5 days so expiring food is eaten in time.
export default function MealPlanPage() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [opts, setOpts] = useState({ days: 3, meals_per_day: 1, max_minutes: "" });
  const [cooking, setCooking] = useState<string | null>(null);
  const { busy, error, setError, run } = useAsync();

  useEffect(() => { api.get<Plan | null>("/api/meal-plan").then(setPlan).catch((e) => setError(errorText(e))); }, [setError]);

  const make = () => run(async () => {
    setPlan(await api.post<Plan>("/api/meal-plan", { ...opts, max_minutes: opts.max_minutes ? +opts.max_minutes : null }));
  });
  const replan = () => run(async () => {
    setPlan(await api.post<Plan>(`/api/meal-plan/replan${opts.max_minutes ? `?max_minutes=${opts.max_minutes}` : ""}`));
  });

  const days = plan ? [...new Set([...plan.meals.map((m) => m.day), ...plan.missing_days])].sort() : [];
  return (
    <>
      <PageTitle title="Waste-rescue meal plan" ids="F13">
        The agent assigns food that expires soon to a day before it expires, with no repeated dishes.
      </PageTitle>
      <div className="card row">
        <label>Days<select value={opts.days} onChange={(e) => setOpts({ ...opts, days: +e.target.value })}>{[3, 4, 5].map((d) => <option key={d}>{d}</option>)}</select></label>
        <label>Meals per day<select value={opts.meals_per_day} onChange={(e) => setOpts({ ...opts, meals_per_day: +e.target.value })}><option>1</option><option>2</option></select></label>
        <label>Max cooking time
          <select value={opts.max_minutes} onChange={(e) => setOpts({ ...opts, max_minutes: e.target.value })}>
            <option value="">Any</option><option value="15">15 min</option><option value="30">30 min</option><option value="60">60 min</option>
          </select>
        </label>
        <button onClick={make} disabled={busy}>{busy ? "Planning… (up to a minute)" : "Plan my meals"}</button>
      </div>
      <ErrorBox error={error} />
      {plan?.needs_update && (
        <div className="banner row">⚠ Your stock changed, so some meals no longer fit. <button onClick={replan} disabled={busy}>Re-plan</button></div>
      )}
      {plan && (
        <>
          <p className="small muted">Planned {plan.created_at.replace("T", " ")}</p>
          {plan.notes.map((n, i) => <div key={i} className="hint" style={{ marginBottom: 6 }}>{n}</div>)}
          <TraceView trace={plan.trace} />
          <div className="calendar">
            {days.map((d) => {
              const meals = plan.meals.filter((m) => m.day === d);
              return (
                <div key={d} className="card day">
                  <h4>{dayName(d)}</h4>
                  {meals.length === 0 && <p className="small warn-text">No meal planned. Check your shopping list.</p>}
                  {meals.map((m) => m.suggestion && (
                    <div key={m.slot} className={`meal ${m.outdated ? "outdated" : ""}`}>
                      <b>{m.suggestion.recipe.name}</b> {m.suggestion.recipe.ai_generated && <span className="tag ai">AI-generated</span>}
                      {m.outdated && <span className="tag bad">no longer fits</span>}
                      <div className="small">
                        Uses: {m.suggestion.checks.filter((c) => c.status === "have" && c.item_name !== "kitchen staple")
                          .map((c) => <span key={c.ingredient} className={c.expiring ? "tag warn" : "tag"}>{c.item_name}</span>)}
                      </div>
                      {m.suggestion.missing_count > 0 && (
                        <div className="small muted">Missing: {m.suggestion.checks.filter((c) => c.status === "missing" || c.status === "short").map((c) => c.ingredient).join(", ")}</div>
                      )}
                      {m.suggestion.explanation && <div className="small muted">{m.suggestion.explanation}</div>}
                      <button className="secondary small-btn" onClick={() => setCooking(m.suggestion!.recipe.id)}>Cook this</button>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
        </>
      )}
      {!plan && !busy && <p className="muted">No plan yet.</p>}
      {cooking && <CookDialog recipeId={cooking} servings={1} onClose={() => setCooking(null)} />}
    </>
  );
}
