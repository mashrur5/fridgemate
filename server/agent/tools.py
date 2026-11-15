"""The agent's tools (G1: tools only call services, so ownership and expiry rules can't be skipped)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import TYPE_CHECKING, Any, Callable, Optional
from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.model import UNITS, FoodItem, Location, ProposedChange, ProposedChanges, Quantity, Recipe, RecipeIngredient
from server.domain.services.household_service import member_allows
from server.domain.services.stock_validator import StockValidator, names_match
from server.domain.services.unit_converter import UnitConverter
from server.infrastructure.recipes import RecipeSource, RecipeSourceError

if TYPE_CHECKING:
    from server.agent.ingredient_source import IngredientSource

MAX_SEARCH_RESULTS = 12


class Tool(ABC):
    name: str
    description: str
    args_help: str = "{}"

    @abstractmethod
    def run(self, ctx: RequestContext, args: dict) -> Any: ...


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self.tools = {t.name: t for t in tools}

    def describe(self) -> str:
        return "\n".join(f"- {t.name}: {t.description} Args: {t.args_help}" for t in self.tools.values())

    def run(self, name: str, ctx: RequestContext, args: dict) -> Any:
        tool = self.tools.get(name)
        if tool is None:
            return {"error": f"unknown tool '{name}'. Use one of: {', '.join(self.tools)}"}
        try:
            return tool.run(ctx, args if isinstance(args, dict) else {})
        except RecipeSourceError as e:
            return {"error": str(e)}
        except (ValueError, KeyError, TypeError) as e:
            return {"error": f"bad arguments: {e}"}


def item_view(item: FoodItem, ctx: RequestContext, today: date) -> dict:
    if item.is_shared():
        owner = "shared"
    elif item.owner.id == ctx.member.id:
        owner = "yours"
    else:
        owner = f"offered by {item.owner.name}"
    return {"id": str(item.id), "name": item.name, "amount": round(item.quantity.amount, 2), "unit": item.quantity.unit,
            "location": item.location.value, "days_left": (item.expiry_date - today).days,
            "freshness": item.freshness_label(), "owner": owner}


class GetInventoryTool(Tool):
    name = "get_inventory"
    description = "List the food you are allowed to use (yours, Shared, and items roommates offered)."

    def __init__(self, items: Callable[[RequestContext], list[FoodItem]], today: Callable[[], date] = date.today):
        self.items, self.today = items, today

    def run(self, ctx, args):
        return [item_view(i, ctx, self.today()) for i in self.items(ctx)]


class GetExpiringItemsTool(Tool):
    name = "get_expiring_items"
    description = "List usable items that expire within 3 days or were offered by roommates, most urgent first."

    def __init__(self, items: Callable[[RequestContext], list[FoodItem]], today: Callable[[], date] = date.today):
        self.items, self.today = items, today

    def run(self, ctx, args):
        urgent = [i for i in self.items(ctx) if i.alert_priority() == 1 or i.is_offered]
        return [item_view(i, ctx, self.today()) for i in sorted(urgent, key=lambda i: i.expiry_date)]


class SearchRecipesTool(Tool):
    name = "search_recipes"
    description = "Search the recipe database by ONE ingredient name, optionally limited to a cuisine (e.g. Italian)."
    args_help = '{"ingredient": "chicken", "cuisine": "Indian or null"}'

    def __init__(self, source: RecipeSource) -> None:
        self.source = source

    def run(self, ctx, args):
        ingredient = str(args["ingredient"])
        cuisine = args.get("cuisine") or None
        found = self.source.search_by_ingredient(ingredient, cuisine)
        if not found and cuisine:
            return {"results": [], "note": f"nothing with {ingredient} in {cuisine} cuisine; try without cuisine"}
        return {"results": [{"recipe_id": r.id, "name": r.name} for r in found[:MAX_SEARCH_RESULTS]]}


class ConvertUnitsTool(Tool):
    name = "convert_units"
    description = "Convert an amount between units (g, kg, ml, l, tsp, tbsp, cup, oz, lb, pcs)."
    args_help = '{"amount": 2, "from": "cup", "to": "ml", "ingredient": "milk"}'

    def __init__(self, converter: UnitConverter) -> None:
        self.converter = converter

    def run(self, ctx, args):
        q = Quantity(float(args["amount"]), str(args["from"]))
        out = self.converter.convert(q, str(args["to"]), str(args.get("ingredient", "")))
        return {"error": "these units can't be converted"} if out is None else {"amount": round(out.amount, 3), "unit": out.unit}


def recipe_from_json(data: dict, converter: UnitConverter) -> Recipe:
    """An AI-written recipe: {"name", "ingredients": [{"name", "amount", "unit"}], "instructions"}."""
    ingredients = []
    for line in data.get("ingredients") or []:
        if not isinstance(line, dict) or not str(line.get("name", "")).strip():
            continue
        qty = None
        unit = converter.normalize_unit(str(line.get("unit") or "pcs"))
        try:
            amount = float(line.get("amount"))
            if amount > 0 and unit:
                qty = Quantity(amount, unit)
        except (TypeError, ValueError):
            pass
        ingredients.append(RecipeIngredient(str(line["name"]).strip().lower(), qty,
                                            f"{line.get('amount', '')} {line.get('unit', '')}".strip()))
    if not ingredients:
        raise ValueError("the recipe has no ingredients")
    return Recipe(name=str(data.get("name") or "AI recipe").strip()[:80], ingredients=ingredients,
                  cuisine=str(data.get("cuisine") or ""), instructions=str(data.get("instructions") or ""),
                  servings=int(data.get("servings") or 2), ai_generated=True)


class ValidateRecipeTool(Tool):
    """G3: check a recipe against the real stock and the member's preferences."""

    name = "validate_recipe"
    description = ("Check a recipe against the usable stock and the user's preferences. Pass a recipe_id from "
                   "search_recipes, or a recipe you wrote yourself as {\"recipe\": {name, ingredients:[{name, amount, unit}]}}.")
    args_help = '{"recipe_id": "52772"}'

    def __init__(self, find_recipe: Callable[[str], Optional[Recipe]], validator: StockValidator,
                 source: "IngredientSource", servings: int, converter: UnitConverter) -> None:
        self.find_recipe, self.validator, self.source = find_recipe, validator, source
        self.servings, self.converter = servings, converter

    def run(self, ctx, args):
        if args.get("recipe"):
            recipe = recipe_from_json(args["recipe"], self.converter)
        else:
            recipe = self.find_recipe(str(args.get("recipe_id", "")))
            if recipe is None:
                return {"error": "no recipe with that id; use an id from search_recipes"}
        items = self.source.get_items(ctx)
        result = self.validator.check(recipe, items, self.servings / max(recipe.servings, 1),
                                      ignore_amounts=not self.source.amounts_known)
        by = lambda s: [c.ingredient.name for c in result.checks if c.status == s]  # noqa: E731
        return {"recipe": recipe.name, "cuisine": recipe.cuisine, "category": recipe.category,
                "ingredients": [f"{i.raw_measure} {i.name}".strip() for i in recipe.ingredients],
                "have": by("have"), "short": by("short"), "missing": by("missing"), "check_amount": by("check amount"),
                "uses_expiring": [c.item_name for c in result.checks if c.expiring and c.status == "have"],
                "not_allowed_for_user": [i.name for i in recipe.ingredients if not member_allows(ctx.member, i.name)]}


class ProposeInventoryChangeTool(Tool):
    """F12 + G4: records a proposed change after checking it. Nothing is changed until the user confirms."""

    name = "propose_inventory_change"
    description = ("Propose ONE inventory change for the user to confirm. op is add, use, remove, move or set. "
                   "use/remove/move/set need the item_id from get_inventory. add needs name, amount and unit. "
                   "move needs location (fridge, freezer, pantry). set gives the new amount.")
    args_help = '{"op": "use", "item_id": "...", "name": "milk", "amount": 1, "unit": "l", "location": null, "owner": "me or shared"}'

    def __init__(self, items: Callable[[RequestContext], list[FoodItem]], proposal: ProposedChanges,
                 converter: UnitConverter) -> None:
        self.items, self.proposal, self.converter = items, proposal, converter

    def run(self, ctx, args):
        op = str(args.get("op", "")).lower()
        if op not in ("add", "use", "remove", "move", "set"):
            return {"error": "op must be add, use, remove, move or set"}
        name = str(args.get("name") or "").strip()
        amount, unit = args.get("amount"), args.get("unit")
        if amount is not None:
            try:
                amount = float(amount)
            except (TypeError, ValueError):
                return {"error": "amount must be a number"}
            if amount <= 0:
                return {"error": "amount must be greater than 0; ask the user to correct it"}
        if unit is not None:
            unit = self.converter.normalize_unit(str(unit))
            if unit is None or unit not in UNITS:
                return {"error": f"unsupported unit; use one of {', '.join(UNITS)}"}
        location = args.get("location")
        if location:
            location = str(location).lower()
            if location not in [l.value for l in Location]:
                return {"error": "location must be fridge, freezer or pantry"}
        if op == "add":
            if not name or amount is None or unit is None:
                return {"error": "add needs name, amount and unit"}
            change = ProposedChange("add", name, None, amount, unit, location,
                                    "shared" if str(args.get("owner", "me")).lower() == "shared" else "me")
            self.proposal.changes.append(change)
            return {"ok": True, "proposed": change.describe()}
        try:
            item_id = UUID(str(args.get("item_id")))
        except ValueError:
            return {"error": "item_id is required; get it from get_inventory"}
        everything = {i.id: i for i in self.items(ctx)}
        item = everything.get(item_id)
        if item is None:
            return {"error": "no item with that id in the inventory"}
        if not item.visible_to(ctx.member):
            self.proposal.rejected.append(f"{item.name} belongs to {item.owner.name}, so it can't be changed")
            return {"error": f"{item.name} belongs to {item.owner.name}; you can't change a roommate's item. Tell the user."}
        if op == "move" and not location:
            return {"error": "move needs a location"}
        if op in ("use", "set"):
            if amount is None:
                return {"error": f"{op} needs an amount"}
            unit = unit or item.quantity.unit
            if self.converter.convert(Quantity(amount, unit), item.quantity.unit, item.name) is None:
                return {"error": f"{item.name} is measured in {item.quantity.unit}; use a compatible unit"}
            if op == "use":
                have = item.quantity.amount
                need = self.converter.convert(Quantity(amount, unit), item.quantity.unit, item.name).amount
                if need > have + 1e-9:
                    return {"error": f"only {have:g} {item.quantity.unit} of {item.name} left"}
        change = ProposedChange(op, item.name, item.id, amount, unit, location)
        self.proposal.changes = [c for c in self.proposal.changes if c.item_id != item.id]  # latest wins
        self.proposal.changes.append(change)
        return {"ok": True, "proposed": change.describe()}
