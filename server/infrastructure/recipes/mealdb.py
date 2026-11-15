"""Adapter: makes TheMealDB's JSON API look like RecipeSource.

The free key "1" only allows one ingredient per search, so callers search ingredient by ingredient."""
from __future__ import annotations

from typing import Optional

import httpx

from server.domain.model import Recipe, RecipeIngredient
from server.domain.services.unit_converter import UnitConverter
from server.infrastructure.recipes.recipe_source import RecipeSource, RecipeSourceError, RecipeSummary

BASE = "https://www.themealdb.com/api/json/v1/{key}/"
MEALDB_SERVINGS = 4  # TheMealDB recipes don't list servings; most serve about 4


class MealDBRecipeSource(RecipeSource):
    def __init__(self, api_key: str = "1", http: httpx.Client | None = None,
                 converter: UnitConverter | None = None) -> None:
        self.base = BASE.format(key=api_key)
        self.http = http or httpx.Client(timeout=15)
        self.converter = converter or UnitConverter()
        self._recipes: dict[str, Recipe] = {}
        self._area: dict[str, set[str]] = {}

    def _get(self, path: str, **params) -> dict:
        try:
            r = self.http.get(self.base + path, params=params)
            r.raise_for_status()
            return r.json() or {}
        except Exception as e:  # noqa: BLE001
            raise RecipeSourceError("the recipe database is unavailable") from e

    def search_by_ingredient(self, ingredient: str, cuisine: Optional[str] = None) -> list[RecipeSummary]:
        key = ingredient.strip().lower().replace(" ", "_")
        if not key:
            return []
        meals = self._get("filter.php", i=key).get("meals") or []
        if not meals and "_" in key:  # "chicken_thighs" finds nothing, so try the last word ("thighs" -> no) / first
            meals = self._get("filter.php", i=key.split("_")[-1]).get("meals") or []
        results = [RecipeSummary(m["idMeal"], m["strMeal"], m.get("strMealThumb", "")) for m in meals]
        if cuisine:
            allowed = self._cuisine_ids(cuisine)
            results = [r for r in results if r.id in allowed]
        return results

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        if recipe_id in self._recipes:
            return self._recipes[recipe_id]
        if not str(recipe_id).isdigit():
            return None
        meals = self._get("lookup.php", i=recipe_id).get("meals") or []
        if not meals:
            return None
        recipe = self._to_recipe(meals[0])
        self._recipes[recipe_id] = recipe
        return recipe

    def list_cuisines(self) -> list[str]:
        return sorted(a["strArea"] for a in self._get("list.php", a="list").get("meals") or [])

    def _cuisine_ids(self, cuisine: str) -> set[str]:
        key = cuisine.strip().title()
        if key not in self._area:
            self._area[key] = {m["idMeal"] for m in self._get("filter.php", a=key).get("meals") or []}
        return self._area[key]

    def _to_recipe(self, m: dict) -> Recipe:
        ingredients = []
        for n in range(1, 21):
            name = (m.get(f"strIngredient{n}") or "").strip()
            if not name:
                continue
            measure = (m.get(f"strMeasure{n}") or "").strip()
            ingredients.append(RecipeIngredient(name.lower(), self.converter.parse_measure(measure), measure))
        return Recipe(name=m["strMeal"], ingredients=ingredients, id=m["idMeal"], cuisine=m.get("strArea") or "",
                      category=m.get("strCategory") or "", instructions=m.get("strInstructions") or "",
                      image_url=m.get("strMealThumb") or "", servings=MEALDB_SERVINGS)
