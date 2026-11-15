"""G3: every recipe is checked against the real stock before it is shown (F08)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from server.domain.model import FoodItem, IngredientCheck, Quantity, Recipe
from server.domain.services.unit_converter import UnitConverter

SYNONYMS: dict[str, str] = {
    "scallion": "green onion", "spring onion": "green onion", "cilantro": "coriander",
    "minced beef": "ground beef", "beef mince": "ground beef", "courgette": "zucchini",
    "aubergine": "eggplant", "capsicum": "bell pepper", "chickpeas": "chickpea",
    "garbanzo": "chickpea", "prawn": "shrimp", "curd": "yogurt", "yoghurt": "yogurt",
}
# assumed to be in every kitchen, so they never count as missing
STAPLES = {"water", "salt", "pepper", "black pepper", "ice"}


def normalize(name: str) -> str:
    text = re.sub(r"[^a-z ]", " ", name.lower())
    text = " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in text.split())
    for word, canonical in SYNONYMS.items():
        text = text.replace(word.rstrip("s"), canonical)
    return text.strip()


def names_match(ingredient: str, item_name: str) -> bool:
    """True when all words of one name appear in the other ('chicken' matches 'chicken breast')."""
    a, b = set(normalize(ingredient).split()), set(normalize(item_name).split())
    return bool(a and b) and (a <= b or b <= a)


@dataclass
class Allocation:
    """Which item an ingredient is taken from, and how much (in the item's own unit)."""

    item_id: object
    amount: Quantity


@dataclass
class CheckResult:
    checks: list[IngredientCheck] = field(default_factory=list)
    allocations: dict[str, list[Allocation]] = field(default_factory=dict)


class StockValidator:
    def __init__(self, converter: Optional[UnitConverter] = None) -> None:
        self.converter = converter or UnitConverter()

    def check(self, recipe: Recipe, items: list[FoodItem], scale: float = 1.0,
              available: Optional[dict] = None) -> CheckResult:
        """Mark every ingredient as have / short / missing / check amount.

        Only items that can be used in a recipe (not expired) are considered. `available` maps
        item id -> amount left; the meal planner passes one in so the same food is not counted twice.
        """
        usable = [i for i in items if i.can_use_in_recipe()]
        left = available if available is not None else {}
        result = CheckResult()
        for ing in recipe.ingredients:
            if normalize(ing.name) in STAPLES:
                result.checks.append(IngredientCheck(ing, "have", item_name="kitchen staple"))
                continue
            matches = [i for i in usable if names_match(ing.name, i.name)]
            if not matches:
                result.checks.append(IngredientCheck(ing, "missing"))
                continue
            matches.sort(key=lambda i: i.expiry_date)  # use the most urgent item first
            first = matches[0]
            expiring = first.alert_priority() == 1 or first.is_offered
            if ing.quantity is None:
                result.checks.append(IngredientCheck(ing, "check amount", str(first.id), first.name, expiring))
                continue
            need = Quantity(ing.quantity.amount * scale, ing.quantity.unit)
            allocations, short, unconvertible = self._allocate(ing.name, need, matches, left)
            if unconvertible and not allocations:
                result.checks.append(IngredientCheck(ing, "check amount", str(first.id), first.name, expiring))
                continue
            status = "short" if short else "have"
            result.checks.append(IngredientCheck(ing, status, str(first.id), first.name, expiring))
            if not short:
                result.allocations[ing.name] = allocations
                for a in allocations:
                    left[a.item_id] = left[a.item_id] - a.amount.amount
        return result

    def _allocate(self, name: str, need: Quantity, matches: list[FoodItem], left: dict):
        allocations: list[Allocation] = []
        remaining = need
        unconvertible = False
        for item in matches:
            have = left.setdefault(item.id, item.quantity.amount)
            if have <= 1e-9:
                continue
            wanted = self.converter.convert(remaining, item.quantity.unit, name)
            if wanted is None:
                unconvertible = True
                continue
            take = min(wanted.amount, have)
            allocations.append(Allocation(item.id, Quantity(take, item.quantity.unit)))
            if wanted.amount - take <= 1e-9:
                return allocations, False, unconvertible
            rest = Quantity(wanted.amount - take, item.quantity.unit)
            back = self.converter.convert(rest, need.unit, name)
            remaining = back if back is not None else rest
        return allocations, True, unconvertible
