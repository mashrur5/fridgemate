"""Turns domain objects into plain JSON for the clients."""
from __future__ import annotations

from datetime import date
from typing import Optional

from server.application.request_context import RequestContext
from server.domain.model import (
    CostSummary, FoodItem, Household, IngredientCheck, MealPlan, Member, Notification, PlannedMeal, ProposedChanges,
    Quantity, Recipe, RecipeSuggestion, ShoppingList, ShoppingListItem,
)


def qty(q: Optional[Quantity]) -> Optional[dict]:
    return {"amount": round(q.amount, 3), "unit": q.unit} if q else None


def member(m: Member) -> dict:
    return {"id": str(m.id), "name": m.name, "email": m.email, "household_id": str(m.household_id) if m.household_id else None,
            "dietary_restrictions": m.dietary_restrictions, "disliked_ingredients": m.disliked_ingredients}


def household(h: Household, members: list[Member]) -> dict:
    return {"id": str(h.id), "name": h.name, "invite_code": h.invite_code,
            "members": [{"id": str(m.id), "name": m.name} for m in members]}


def item(i: FoodItem, ctx: RequestContext, today: date) -> dict:
    if i.is_shared():
        owner = "Shared"
    elif i.owner.id == ctx.member.id:
        owner = "You"
    else:
        owner = i.owner.name
    return {"id": str(i.id), "name": i.name, "quantity": qty(i.quantity), "location": i.location.value,
            "expiry_date": i.expiry_date.isoformat(), "days_left": (i.expiry_date - today).days,
            "expiry_estimated": i.expiry_estimated, "freshness": i.freshness_label(), "owner": owner,
            "owner_id": str(i.owner.id) if i.owner else None, "mine": bool(i.owner and i.owner.id == ctx.member.id),
            "editable": i.visible_to(ctx.member), "is_low": i.is_low(),
            "price": str(i.price) if i.price is not None else None, "payer": i.payer.name if i.payer else None,
            "is_offered": i.is_offered, "offered_by": i.offered_by.name if i.offered_by else None,
            "can_offer": i.can_offer() and bool(i.owner and i.owner.id == ctx.member.id) and not i.is_offered,
            "can_claim": i.is_offered and not (i.offered_by and i.offered_by.id == ctx.member.id)}


def check(c: IngredientCheck) -> dict:
    return {"ingredient": c.ingredient.name, "measure": c.ingredient.raw_measure, "status": c.status,
            "item_id": c.item_id, "item_name": c.item_name, "expiring": c.expiring, "substitute": c.substitute}


def recipe(r: Recipe) -> dict:
    return {"id": r.id, "name": r.name, "cuisine": r.cuisine, "category": r.category, "image_url": r.image_url,
            "instructions": r.instructions, "ai_generated": r.ai_generated, "servings": r.servings,
            "ingredients": [{"name": i.name, "measure": i.raw_measure, "quantity": qty(i.quantity)} for i in r.ingredients]}


def suggestion(s: RecipeSuggestion) -> dict:
    return {"recipe": recipe(s.recipe), "estimated_minutes": s.estimated_minutes, "weight": s.weight,
            "explanation": s.explanation, "checks": [check(c) for c in s.checks],
            "expiring_used": s.expiring_used, "missing_count": len(s.missing)}


def meal(m: PlannedMeal) -> dict:
    return {"day": m.day.isoformat(), "slot": m.slot, "suggestion": suggestion(m.suggestion) if m.suggestion else None,
            "note": m.note}


def meal_plan(p: MealPlan, outdated: list[PlannedMeal]) -> dict:
    bad = {(m.day, m.slot) for m in outdated}
    meals = []
    for m in p.meals:
        d = meal(m)
        d["outdated"] = (m.day, m.slot) in bad
        meals.append(d)
    return {"id": str(p.id), "start": p.start.isoformat(), "days": p.days, "meals": meals,
            "missing_days": [d.isoformat() for d in p.missing_days], "notes": p.notes,
            "needs_update": bool(outdated), "created_at": p.created_at.isoformat(timespec="minutes")}


def shopping_item(i: ShoppingListItem) -> dict:
    return {"id": str(i.id), "name": i.name, "quantity": qty(i.quantity), "section": i.section, "reasons": i.reasons,
            "shared": i.member_id is None, "checked": i.checked}


def shopping_list(lst: ShoppingList) -> dict:
    return {"sections": {k: [shopping_item(i) for i in v] for k, v in lst.by_section().items()},
            "count": len(lst.items)}


def notification(n: Notification) -> dict:
    return {"id": str(n.id), "message": n.message, "item_id": str(n.item_id) if n.item_id else None, "kind": n.kind,
            "read": n.read, "created_at": n.created_at.isoformat(timespec="minutes")}


def proposal(p: ProposedChanges) -> Optional[dict]:
    if not p.changes:
        return None
    return {"id": str(p.id), "changes": [c.describe() for c in p.changes], "rejected": p.rejected}


def costs(s: CostSummary, members: list[Member], missing: list[FoodItem]) -> dict:
    names = {m.id: m.name for m in members}
    return {
        "purchases": [{"item": p.item_name, "price": str(p.price), "payer": names.get(p.payer_id, "?"),
                       "date": p.bought_on.isoformat()} for p in s.purchases],
        "members": [{"id": str(m.id), "name": m.name, "paid": str(s.paid.get(m.id, 0)), "share": str(s.share.get(m.id, 0)),
                     "balance": str(s.balance.get(m.id, 0))} for m in members],
        "settlements": [{"from_id": str(x.from_id), "from": names.get(x.from_id, "?"), "to_id": str(x.to_id),
                         "to": names.get(x.to_id, "?"), "amount": str(x.amount)} for x in s.settlements],
        "payments": [{"id": str(p.id), "from": names.get(p.from_id, "?"), "to": names.get(p.to_id, "?"),
                      "amount": str(p.amount), "date": p.paid_on.isoformat()} for p in s.payments],
        "missing_price": [{"id": str(i.id), "name": i.name} for i in missing],
    }
