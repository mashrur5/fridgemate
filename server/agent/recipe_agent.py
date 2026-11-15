"""F07 / F08 / F10: the recipe agent. The same agent serves F07 and F10 with a different IngredientSource."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from server.agent.agent_trace import AgentTrace
from server.agent.base_agent import BaseAgent
from server.agent.ingredient_source import IngredientSource
from server.agent.response_parser import SchemaError
from server.agent.tools import (
    ConvertUnitsTool, GetExpiringItemsTool, GetInventoryTool, SearchRecipesTool, ToolRegistry, ValidateRecipeTool,
    recipe_from_json,
)
from server.application.request_context import RequestContext
from server.domain.errors import InvalidOperationError
from server.domain.model import FoodItem, Recipe, RecipeRequest, RecipeSuggestion
from server.domain.model.recipe import WEIGHTS
from server.domain.services.household_service import blocked_words, member_allows
from server.domain.services.stock_validator import StockValidator, names_match
from server.domain.services.unit_converter import UnitConverter
from server.infrastructure.llm import LLMClient, Message
from server.infrastructure.recipes import RecipeSource

MAX_RESULTS = 5

ROLE = """You are Fridgemate's recipe agent. You help roommates cook with food they already have,
especially food that expires soon or that a roommate offered, so nothing is wasted."""

TASK = """How to work:
1. Call get_expiring_items (and get_inventory if you need more) to see what can be used.
2. Call search_recipes with the most urgent ingredients, ONE ingredient per search. Use the cuisine if one was chosen.
3. Call validate_recipe on the most promising recipes to see what is missing.
4. If fewer than 3 good recipes exist, write your own using mainly the available items (put them in "generated").
Estimate cooking minutes and meal weight (light, medium, heavy) yourself, since the database has neither.
Skip recipes with ingredients the user must avoid. For "Let AI decide" options, choose and say what you chose.
For missing ingredients you may suggest a substitute, but only an item from the user's inventory."""

FINAL = ('{"recipes": [{"recipe_id": "<id from search_recipes>", "estimated_minutes": 30, "weight": "medium", '
         '"reason": "<why, mention expiring items>", "substitutes": {"<missing ingredient>": "<inventory item name>"}}], '
         '"generated": [{"name": "...", "cuisine": "...", "servings": 2, "estimated_minutes": 20, "weight": "light", '
         '"reason": "...", "ingredients": [{"name": "...", "amount": 200, "unit": "g"}], "instructions": "..."}], '
         '"choices": "<what you decided for Let-AI-decide options>"}')


@dataclass
class RecipeResult:
    suggestions: list[RecipeSuggestion]
    notes: list[str] = field(default_factory=list)
    choices: str = ""
    trace: Optional[AgentTrace] = None


class RecipeAgent(BaseAgent):
    def __init__(self, llm: LLMClient, recipes: RecipeSource, validator: StockValidator | None = None,
                 converter: UnitConverter | None = None, today: Callable[[], date] = date.today, **kw) -> None:
        super().__init__(llm, **kw)
        self.recipes = recipes
        self.validator = validator or StockValidator()
        self.converter = converter or UnitConverter()
        self.today = today
        self.generated: dict[str, Recipe] = {}  # AI-written recipes, so "Cook this" can find them later

    def find_recipe(self, recipe_id: str) -> Optional[Recipe]:
        return self.generated.get(recipe_id) or self.recipes.get_recipe(recipe_id)

    def remember_generated(self, recipe: Recipe) -> Recipe:
        if not recipe.id:
            recipe.id = "ai-" + uuid.uuid4().hex[:8]
        self.generated[recipe.id] = recipe
        return recipe

    def tools_for(self, source: IngredientSource, servings: int) -> ToolRegistry:
        return ToolRegistry([
            GetInventoryTool(source.get_items, self.today), GetExpiringItemsTool(source.get_items, self.today),
            SearchRecipesTool(self.recipes), ValidateRecipeTool(self.find_recipe, self.validator, source, servings,
                                                                self.converter),
            ConvertUnitsTool(self.converter)])

    def suggest(self, ctx: RequestContext, request: RecipeRequest, source: IngredientSource) -> RecipeResult:
        trace = AgentTrace("RecipeAgent")
        items = source.get_items(ctx)  # G2 happens inside the source
        if not items:
            raise InvalidOperationError("you have no usable ingredients; try the Quick Finder or your shopping list")
        trace.add("note", f"{len(items)} usable items after ownership and expiry filtering")
        options = {
            "cuisine": request.cuisine or "Let AI decide",
            "max_cooking_minutes": request.max_minutes or "Let AI decide",
            "meal_weight": request.weight or "Let AI decide",
            "servings": request.servings,
            "ingredients_must_avoid": blocked_words(ctx.member),
            "ingredient_source": "the user's fridge" if source.amounts_known else "a list the user typed (amounts unknown)",
        }
        registry = self.tools_for(source, request.servings)
        system = self.prompts.tool_system_prompt(ROLE, TASK, registry, FINAL, self.max_steps)
        loop = self.run_tool_loop(ctx, system, [Message("user", self.prompts.as_data("options", options))], registry,
                                  trace, validate_final=self._valid_final)
        notes = ["The agent reached its step limit, so these are the best results it found."] if loop.hit_limit else []
        suggestions = self.build_suggestions(ctx, request, items, loop.final, source, notes)
        if not suggestions:
            notes.append("No recipe fit your options and ingredients. Try other options or the Quick Finder.")
        return RecipeResult(suggestions, notes, str(loop.final.get("choices") or ""), trace)

    @staticmethod
    def _valid_final(final: dict) -> dict:
        for key in ("recipes", "generated"):
            final.setdefault(key, [])
            if not isinstance(final[key], list):
                raise SchemaError(f"'{key}' must be a list")
        return final

    def build_suggestions(self, ctx: RequestContext, request: RecipeRequest, items: list[FoodItem], final: dict,
                          source: IngredientSource, notes: list[str]) -> list[RecipeSuggestion]:
        """Deterministic checks on everything the LLM proposed (G3): stock, preferences, options."""
        picks: list[tuple[Recipe, dict]] = []
        seen: set[str] = set()
        for pick in final.get("recipes", []):
            if not isinstance(pick, dict):
                continue
            recipe = self.find_recipe(str(pick.get("recipe_id", "")))
            if recipe is None:
                notes.append(f"Skipped a recipe the AI named that doesn't exist ({pick.get('recipe_id')}).")
            elif recipe.id not in seen:
                seen.add(recipe.id)
                picks.append((recipe, pick))
        for gen in final.get("generated", []):
            try:
                recipe = self.remember_generated(recipe_from_json(gen, self.converter))
                picks.append((recipe, gen))
            except (ValueError, TypeError, AttributeError):
                notes.append("Skipped an AI-written recipe that had no usable ingredients.")
        results = []
        for recipe, pick in picks:
            blocked = [i.name for i in recipe.ingredients if not member_allows(ctx.member, i.name)]
            if blocked:
                notes.append(f"Removed {recipe.name}: it contains {', '.join(blocked)} (your preferences).")
                continue
            scale = request.servings / max(recipe.servings, 1)
            check = self.validator.check(recipe, items, scale, ignore_amounts=not source.amounts_known)
            if not check.checks or not any(c.status == "have" and c.item_name != "kitchen staple" for c in check.checks):
                notes.append(f"Removed {recipe.name}: it uses none of your ingredients.")
                continue
            self._apply_substitutes(ctx, check.checks, pick.get("substitutes"), items)
            minutes = self._int(pick.get("estimated_minutes"))
            weight = str(pick.get("weight") or "").lower() or None
            weight = weight if weight in WEIGHTS else None
            s = RecipeSuggestion(recipe, check.checks, minutes, weight, str(pick.get("reason") or "")[:400])
            misfits = []
            if request.max_minutes and minutes and minutes > request.max_minutes:
                misfits.append(f"takes about {minutes} min (you asked for {request.max_minutes})")
            if request.weight and weight and weight != request.weight:
                misfits.append(f"is a {weight} meal (you asked for {request.weight})")
            if request.cuisine and recipe.cuisine and recipe.cuisine.lower() != request.cuisine.lower():
                misfits.append(f"is {recipe.cuisine} (you asked for {request.cuisine})")
            if misfits:
                s.explanation = (s.explanation + " Note: this " + " and ".join(misfits) + ".").strip()
            s.score = 3 * s.expiring_used + len(s.used) - 1.5 * len(s.missing) - 5 * len(misfits)
            results.append(s)
        results.sort(key=lambda s: s.score, reverse=True)
        return results[:MAX_RESULTS]

    def _apply_substitutes(self, ctx, checks, subs, items) -> None:
        """F08: keep a substitute only if it is a usable item the member is allowed to eat."""
        if not isinstance(subs, dict):
            return
        for c in checks:
            if c.status not in ("missing", "short"):
                continue
            proposed = subs.get(c.ingredient.name)
            if not isinstance(proposed, str):
                continue
            match = next((i for i in items if names_match(proposed, i.name)), None)
            if match is not None and member_allows(ctx.member, match.name):
                c.substitute = match.name

    @staticmethod
    def _int(value) -> Optional[int]:
        try:
            v = int(float(value))
            return v if 1 <= v <= 600 else None
        except (TypeError, ValueError):
            return None
