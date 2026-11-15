import { KeyboardEvent, useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, TraceView, useAsync } from "../components/common";
import RecipeCard from "../components/RecipeCard";
import RecipeOptions, { Opts, defaultOpts, toBody } from "../components/RecipeOptions";
import { RecipeResult } from "../types";

// F10: the same recipe agent, but the ingredients come from a typed list instead of the fridge.
export default function QuickFinderPage() {
  const [typed, setTyped] = useState("");
  const [ingredients, setIngredients] = useState<string[]>([]);
  const [opts, setOpts] = useState<Opts>(defaultOpts);
  const [result, setResult] = useState<RecipeResult | null>(null);
  const { busy, error, run } = useAsync();

  const add = () => {
    const parts = typed.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
    setIngredients([...new Set([...ingredients, ...parts])]);
    setTyped("");
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { e.preventDefault(); add(); }
  };

  const find = () => run(async () => {
    setResult(null);
    setResult(await api.post<RecipeResult>("/api/recipes/find", { ...toBody(opts), ingredients }));
  });

  return (
    <>
      <PageTitle title="Quick Finder" ids="F10">
        Type ingredients you have (for example while shopping) and get recipes. Your fridge isn't used here.
      </PageTitle>
      <div className="card form">
        <label>Ingredients (press Enter after each)
          <input value={typed} onChange={(e) => setTyped(e.target.value)} onKeyDown={onKey} onBlur={() => typed && add()} placeholder="chicken" />
        </label>
        <div>
          {ingredients.map((i) => (
            <span key={i} className="tag">{i} <button className="link small" onClick={() => setIngredients(ingredients.filter((x) => x !== i))} aria-label={`Remove ${i}`}>✕</button></span>
          ))}
        </div>
        <RecipeOptions value={opts} onChange={setOpts} />
        <div><button onClick={find} disabled={busy || ingredients.length === 0}>{busy ? "Searching…" : "Find recipes"}</button></div>
      </div>
      <ErrorBox error={error} />
      {result && (
        <>
          {result.notes.map((n, i) => <div key={i} className="hint" style={{ marginTop: 8 }}>{n}</div>)}
          {result.choices && <p className="small"><b>The AI decided:</b> {result.choices}</p>}
          <TraceView trace={result.trace} />
          <div className="cards">
            {result.suggestions.map((s) => <RecipeCard key={s.recipe.id} s={s} canCook={false} servings={opts.servings} />)}
          </div>
        </>
      )}
    </>
  );
}
