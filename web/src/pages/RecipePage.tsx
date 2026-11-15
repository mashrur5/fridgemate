import { useState } from "react";
import { api } from "../api";
import { ErrorBox, PageTitle, TraceView, useAsync } from "../components/common";
import RecipeCard from "../components/RecipeCard";
import RecipeOptions, { Opts, defaultOpts, toBody } from "../components/RecipeOptions";
import { RecipeResult } from "../types";

// F07 recipe agent from the fridge, F08 missing ingredients and substitutes on each card, F09 "Cook this".
export default function RecipePage() {
  const [opts, setOpts] = useState<Opts>(defaultOpts);
  const [result, setResult] = useState<RecipeResult | null>(null);
  const { busy, error, run } = useAsync();

  const go = () => run(async () => {
    setResult(null);
    setResult(await api.post<RecipeResult>("/api/recipes/suggest", toBody(opts)));
  });

  return (
    <>
      <PageTitle title="Recipe suggestions" ids="F07 F08 F09">
        The recipe agent picks recipes you can make with your own and Shared food, using what expires soonest first.
      </PageTitle>
      <div className="card">
        <RecipeOptions value={opts} onChange={setOpts} />
        <button onClick={go} disabled={busy}>{busy ? "The agent is working… (up to a minute)" : "Get recipes"}</button>
      </div>
      <ErrorBox error={error} />
      {result && (
        <>
          {result.notes.map((n, i) => <div key={i} className="hint" style={{ marginTop: 8 }}>{n}</div>)}
          {result.choices && <p className="small"><b>The AI decided:</b> {result.choices}</p>}
          <TraceView trace={result.trace} />
          <div className="cards">
            {result.suggestions.map((s) => <RecipeCard key={s.recipe.id} s={s} canCook servings={opts.servings} />)}
          </div>
          {result.suggestions.length > 0 && <p className="small muted">Yellow tags are items that expire soon or were offered by a roommate.</p>}
        </>
      )}
    </>
  );
}
