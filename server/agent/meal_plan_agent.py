"""F13: plans several days of meals so expiring food is used in time."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Callable, Optional

from server.agent.agent_trace import AgentTrace
from server.agent.base_agent import BaseAgent
from server.agent.ingredient_source import FridgeIngredientSource
from server.agent.recipe_agent import RecipeAgent
from server.agent.response_parser import SchemaError
from server.agent.tools import recipe_from_json
from server.application.request_context import RequestContext
from server.domain.errors import InvalidOperationError
from server.domain.model import FoodItem, MealPlan, PlannedMeal, Recipe, RecipeSuggestion
from server.domain.services.household_service import blocked_words, member_allows
from server.infrastructure.llm import LLMClient, Message
from server.infrastructure.persistence import MealPlanRepository

ROLE = """You are Fridgemate's meal planning agent. You plan the next few days of meals for one person
so that food is eaten before it expires. Each expiring item should be used on a day BEFORE it expires."""

TASK = """How to work:
1. Call get_expiring_items to see what must be used first (days_left tells you the deadline).
2. Call search_recipes for those ingredients (ONE ingredient per search) and validate_recipe for candidates.
3. Assign one recipe to every meal slot. Never repeat a dish. Use the most urgent items on the earliest days.
4. If there aren't enough different recipes, write your own in "generated" form inside the meal.
Respect the maximum cooking time and the ingredients the user must avoid."""

FINAL = ('{"meals": [{"day": 1, "slot": 1, "recipe_id": "<id from search_recipes, or null>", '
         '"generated": null, "estimated_minutes": 25, "reason": "<which expiring items it uses>"}], '
         '"notes": "<anything the user should know>"}')


class MealPlanAgent(BaseAgent):
    def __init__(self, llm: LLMClient, recipe_agent: RecipeAgent, source: FridgeIngredientSource,
                 plans: MealPlanRepository, today: Callable[[], date] = date.today, **kw) -> None:
        super().__init__(llm, **kw)
        self.recipe_agent = recipe_agent
        self.source = source
        self.plans = plans
        self.today = today
        self.last_trace: Optional[AgentTrace] = None

    def plan(self, ctx: RequestContext, days: int, meals_per_day: int = 1, max_minutes: Optional[int] = None,
             keep: Optional[list[PlannedMeal]] = None) -> MealPlan:
        if not 3 <= days <= 5:
            raise ValueError("plan 3 to 5 days")
        if meals_per_day not in (1, 2):
            raise ValueError("meals per day must be 1 or 2")
        items = self.source.get_items(ctx)
        if not items:
            raise InvalidOperationError("you have no usable food to plan with; add items or check your shopping list")
        trace = AgentTrace("MealPlanAgent")
        self.last_trace = trace
        start = self.today()
        keep = keep or []
        slots = [(d, s) for d in range(1, days + 1) for s in range(1, meals_per_day + 1)
                 if not any(k.day == start + timedelta(days=d - 1) and k.slot == s for k in keep)]
        request = {"days": days, "meals_per_day": meals_per_day, "max_cooking_minutes": max_minutes or "any",
                   "today": start.isoformat(), "slots_to_fill": [{"day": d, "slot": s} for d, s in slots],
                   "already_planned": [k.suggestion.recipe.name for k in keep if k.suggestion],
                   "ingredients_must_avoid": blocked_words(ctx.member)}
        registry = self.recipe_agent.tools_for(self.source, servings=1)
        system = self.prompts.tool_system_prompt(ROLE, TASK, registry, FINAL, self.max_steps)
        convo = [Message("user", self.prompts.as_data("plan_request", request))]
        loop = self.run_tool_loop(ctx, system, convo, registry, trace, validate_final=self._valid_final)
        plan = MealPlan(ctx.member.id, ctx.household.id, start, days)
        if loop.hit_limit:
            plan.notes.append("The agent reached its step limit, so the plan may be partial.")
        meals, problems = self._check(ctx, start, loop.final, items, keep, max_minutes)
        if problems:
            # re-plan only the rejected slots, once, continuing the same conversation
            reasons = [text for _, _, text in problems]
            trace.add("note", "re-planning: " + "; ".join(reasons))
            feedback = ("These meals were rejected by the stock check: " + "; ".join(reasons) +
                        ". Reply with a final answer that replaces ONLY those slots (same JSON shape).")
            retry = self.run_tool_loop(ctx, system, loop.conversation + [Message("user", feedback)], registry, trace,
                                       max_steps=2, validate_final=self._valid_final)
            fixed, still = self._check(ctx, start, retry.final, items, keep + meals, max_minutes)
            meals += fixed
            filled = {(m.day, m.slot) for m in fixed}
            plan.notes += [f"Couldn't fill: {text}" for (d, s, text) in problems + still
                           if (start + timedelta(days=d - 1), s) not in filled]
        plan.meals = sorted(keep + meals, key=lambda m: (m.day, m.slot))
        filled = {m.day for m in plan.meals if m.suggestion}
        plan.missing_days = [start + timedelta(days=d) for d in range(days) if start + timedelta(days=d) not in filled]
        if loop.final.get("notes"):
            plan.notes.append(str(loop.final["notes"])[:300])
        self.plans.save(plan)
        return plan

    @staticmethod
    def _valid_final(final: dict) -> dict:
        if not isinstance(final.get("meals"), list):
            raise SchemaError("'meals' must be a list")
        return final

    def _check(self, ctx, start, final, items: list[FoodItem], fixed: list[PlannedMeal], max_minutes):
        """Check the whole plan in day order with one shared stock map, so nothing is counted twice."""
        available: dict = {}
        used_names = {m.suggestion.recipe.name.lower() for m in fixed if m.suggestion}
        for m in sorted(fixed, key=lambda m: (m.day, m.slot)):  # stock already promised to kept meals
            if m.suggestion:
                self.recipe_agent.validator.check(m.suggestion.recipe, items, 1 / max(m.suggestion.recipe.servings, 1),
                                                  available)
        taken = {(m.day, m.slot) for m in fixed}
        good, problems = [], []
        rows = sorted((m for m in final.get("meals", []) if isinstance(m, dict)),
                      key=lambda m: (self._int(m.get("day")) or 99, self._int(m.get("slot")) or 9))
        for row in rows:
            d, s = self._int(row.get("day")), self._int(row.get("slot")) or 1
            if not d:
                continue
            day = start + timedelta(days=d - 1)
            label = f"day {d} meal {s}"
            if (day, s) in taken:
                continue
            recipe = self._recipe(row)
            if recipe is None:
                problems.append((d, s, f"{label}: recipe not found"))
                continue
            if recipe.name.lower() in used_names:
                problems.append((d, s, f"{label}: {recipe.name} is repeated"))
                continue
            blocked = [i.name for i in recipe.ingredients if not member_allows(ctx.member, i.name)]
            if blocked:
                problems.append((d, s, f"{label}: {recipe.name} contains {', '.join(blocked)}"))
                continue
            minutes = self.recipe_agent._int(row.get("estimated_minutes"))
            if max_minutes and minutes and minutes > max_minutes:
                problems.append((d, s, f"{label}: {recipe.name} takes {minutes} min, over the {max_minutes} min limit"))
                continue
            result = self.recipe_agent.validator.check(recipe, items, 1 / max(recipe.servings, 1), available)
            late = [i.name for i in items for c in result.checks
                    if c.status == "have" and c.item_id == str(i.id) and i.expiry_date < day]
            if late:
                problems.append((d, s, f"{label}: {', '.join(late)} expires before that day"))
                continue
            if not any(c.status == "have" and c.item_name != "kitchen staple" for c in result.checks):
                problems.append((d, s, f"{label}: {recipe.name} uses none of your food"))
                continue
            used_names.add(recipe.name.lower())
            taken.add((day, s))
            good.append(PlannedMeal(day, s, RecipeSuggestion(recipe, result.checks, minutes, None,
                                                             str(row.get("reason") or "")[:300])))
        return good, problems

    def _recipe(self, row: dict) -> Optional[Recipe]:
        if row.get("generated"):
            try:
                return self.recipe_agent.remember_generated(recipe_from_json(row["generated"], self.recipe_agent.converter))
            except (ValueError, TypeError, AttributeError):
                return None
        return self.recipe_agent.find_recipe(str(row.get("recipe_id") or ""))

    @staticmethod
    def _int(v) -> Optional[int]:
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def latest(self, ctx: RequestContext) -> Optional[MealPlan]:
        return self.plans.latest_for_member(ctx.member.id)

    def outdated_meals(self, ctx: RequestContext, plan: MealPlan) -> list[PlannedMeal]:
        """Meals that no longer fit the current stock (an item was used, removed or expired)."""
        items = self.source.get_items(ctx)
        available: dict = {}
        bad = []
        for m in sorted(plan.meals, key=lambda m: (m.day, m.slot)):
            if m.suggestion is None or m.day < self.today():
                continue
            before = {c.ingredient.name for c in m.suggestion.checks if c.status == "have"}
            now = self.recipe_agent.validator.check(m.suggestion.recipe, items,
                                                    1 / max(m.suggestion.recipe.servings, 1), available)
            have_now = {c.ingredient.name for c in now.checks if c.status == "have"}
            late = any(c.status == "have" and i.expiry_date < m.day for c in now.checks for i in items
                       if c.item_id == str(i.id))
            if not before <= have_now or late:
                bad.append(m)
        return bad

    def replan(self, ctx: RequestContext, plan: MealPlan, max_minutes: Optional[int] = None) -> MealPlan:
        bad = self.outdated_meals(ctx, plan)
        keep = [m for m in plan.meals if m not in bad and m.day >= self.today() and m.suggestion]
        meals_per_day = max((m.slot for m in plan.meals), default=1)
        days_left = max(3, min(5, (plan.start + timedelta(days=plan.days) - self.today()).days))
        return self.plan(ctx, days_left, meals_per_day, max_minutes, keep=keep)
