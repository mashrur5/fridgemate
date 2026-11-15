"""Test doubles. Tests never call a real LLM or web API."""
from __future__ import annotations

import json
from typing import Optional

from server.domain.model import Recipe, RecipeIngredient, Quantity
from server.infrastructure.llm import LLMClient, LLMResponse, LLMUnavailableError, UsageMeter
from server.infrastructure.recipes import RecipeSource, RecipeSummary


class FakeLLMClient(LLMClient):
    """Replies with a scripted list of answers (dicts are sent as JSON) and records every prompt."""

    name = "fake"

    def __init__(self, replies: list) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, list]] = []
        self.usage = UsageMeter()

    def generate(self, system, messages, json_mode=True, images=None) -> LLMResponse:
        self.calls.append((system, list(messages)))
        if not self.replies:
            raise LLMUnavailableError("no scripted reply left")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        r = LLMResponse(reply if isinstance(reply, str) else json.dumps(reply), 10, 5)
        self.usage.record(r)
        return r


class FakeRecipeSource(RecipeSource):
    def __init__(self, recipes: list[Recipe]) -> None:
        self.recipes = {r.id: r for r in recipes}
        self.searches: list[str] = []

    def search_by_ingredient(self, ingredient, cuisine=None):
        self.searches.append(ingredient)
        return [RecipeSummary(r.id, r.name) for r in self.recipes.values()
                if any(ingredient.lower() in i.name for i in r.ingredients)
                and (not cuisine or r.cuisine.lower() == cuisine.lower())]

    def get_recipe(self, recipe_id) -> Optional[Recipe]:
        return self.recipes.get(recipe_id)

    def list_cuisines(self):
        return sorted({r.cuisine for r in self.recipes.values()})


def recipe(rid, name, cuisine, *lines, servings=2):
    return Recipe(name=name, id=rid, cuisine=cuisine, servings=servings,
                  ingredients=[RecipeIngredient(n, Quantity(a, u) if a else None, f"{a or ''} {u or ''}".strip())
                               for n, a, u in lines])
