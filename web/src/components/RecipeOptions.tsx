import { useEffect, useState } from "react";
import { api } from "../api";

export interface Opts { cuisine: string; max_minutes: string; weight: string; servings: number; }
export const defaultOpts: Opts = { cuisine: "", max_minutes: "", weight: "", servings: 2 };

export function toBody(o: Opts) {
  return { cuisine: o.cuisine || null, max_minutes: o.max_minutes ? +o.max_minutes : null, weight: o.weight || null,
    servings: o.servings };
}

// The four F07/F10 options. Each one has "Let AI decide".
export default function RecipeOptions({ value, onChange }: { value: Opts; onChange: (o: Opts) => void }) {
  const [cuisines, setCuisines] = useState<string[]>([]);
  useEffect(() => {
    api.get<string[]>("/api/recipes/cuisines").then(setCuisines).catch(() => setCuisines([]));
  }, []);
  return (
    <div className="grid4">
      <label>Cuisine
        <select value={value.cuisine} onChange={(e) => onChange({ ...value, cuisine: e.target.value })}>
          <option value="">Let AI decide</option>
          {cuisines.map((c) => <option key={c}>{c}</option>)}
        </select>
      </label>
      <label>Cooking time
        <select value={value.max_minutes} onChange={(e) => onChange({ ...value, max_minutes: e.target.value })}>
          <option value="">Let AI decide</option>
          <option value="15">Under 15 min</option>
          <option value="30">15 to 30 min</option>
          <option value="60">30 to 60 min</option>
          <option value="600">Over 60 min</option>
        </select>
      </label>
      <label>Meal weight
        <select value={value.weight} onChange={(e) => onChange({ ...value, weight: e.target.value })}>
          <option value="">Let AI decide</option>
          <option value="light">Light</option>
          <option value="medium">Medium</option>
          <option value="heavy">Heavy</option>
        </select>
      </label>
      <label>Servings
        <input type="number" min={1} max={10} value={value.servings}
          onChange={(e) => onChange({ ...value, servings: Math.max(1, Math.min(10, +e.target.value || 1)) })} />
      </label>
    </div>
  );
}
