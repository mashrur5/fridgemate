export type Qty = { amount: number; unit: string } | null;

export interface Item {
  id: string; name: string; quantity: Qty; location: string; expiry_date: string; days_left: number;
  expiry_estimated: boolean; freshness: string; owner: string; owner_id: string | null; mine: boolean;
  editable: boolean; is_low: boolean; price: string | null; payer: string | null; is_offered: boolean;
  offered_by: string | null; can_offer: boolean; can_claim: boolean; note?: string;
}

export interface Member { id: string; name: string; email: string; household_id: string | null;
  dietary_restrictions: string[]; disliked_ingredients: string[]; }
export interface Household { id: string; name: string; invite_code: string; members: { id: string; name: string }[]; }
export interface Me { member: Member; household: Household | null; ai: { provider: string; calls: number;
  input_tokens: number; output_tokens: number }; }

export interface Check { ingredient: string; measure: string; status: string; item_id: string | null;
  item_name: string | null; expiring: boolean; substitute: string | null; }
export interface Recipe { id: string; name: string; cuisine: string; category: string; image_url: string;
  instructions: string; ai_generated: boolean; servings: number;
  ingredients: { name: string; measure: string }[]; }
export interface Suggestion { recipe: Recipe; estimated_minutes: number | null; weight: string | null;
  explanation: string; checks: Check[]; expiring_used: number; missing_count: number; }
export interface TraceStep { kind: string; detail: string; tool: string | null; }
export interface Trace { agent: string; steps: TraceStep[]; }
export interface RecipeResult { suggestions: Suggestion[]; notes: string[]; choices: string; trace: Trace | null; }

export const fmtQty = (q: Qty) => (q ? `${+q.amount.toFixed(2)} ${q.unit}` : "");
export const UNITS = ["g", "kg", "ml", "l", "pcs"];
export const LOCATIONS = ["fridge", "freezer", "pantry"];
