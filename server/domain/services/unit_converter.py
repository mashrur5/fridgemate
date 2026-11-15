"""Turns recipe measures ("1 1/2 cups", "200g", "2 cloves") into Quantity objects and converts
between units, including a few ingredient-specific conversions (1 egg is about 50 g)."""
from __future__ import annotations

import re
from typing import Optional

from server.domain.model import Quantity

_UNIT_WORDS: dict[str, str] = {
    "g": "g", "gram": "g", "grams": "g", "gr": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg", "kgs": "kg",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml", "millilitres": "ml", "milliliters": "ml",
    "l": "l", "litre": "l", "liter": "l", "litres": "l", "liters": "l",
    "tsp": "tsp", "teaspoon": "tsp", "teaspoons": "tsp", "tsps": "tsp",
    "tbsp": "tbsp", "tablespoon": "tbsp", "tablespoons": "tbsp", "tbs": "tbsp", "tbsps": "tbsp", "tblsp": "tbsp",
    "cup": "cup", "cups": "cup",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",
    "pcs": "pcs", "pc": "pcs", "piece": "pcs", "pieces": "pcs", "whole": "pcs", "large": "pcs",
    "medium": "pcs", "small": "pcs", "clove": "pcs", "cloves": "pcs", "slice": "pcs", "slices": "pcs",
    "can": "pcs", "cans": "pcs", "x": "pcs", "unit": "pcs", "units": "pcs", "bunch": "pcs",
}

# grams per piece, used to convert "2 eggs" into grams and back
PIECE_GRAMS: dict[str, float] = {
    "egg": 50, "onion": 150, "garlic": 5, "potato": 200, "tomato": 120, "banana": 120,
    "carrot": 70, "apple": 180, "lemon": 100, "lime": 60, "pepper": 150, "chicken breast": 200,
    "chicken thigh": 120, "bread": 30, "avocado": 170, "cucumber": 300, "zucchini": 200,
    # one bunch / head, as TheMealDB writes "1 bunch spinach"
    "spinach": 250, "lettuce": 400, "cabbage": 900, "broccoli": 300, "cauliflower": 600, "kale": 200,
    "parsley": 50, "coriander": 50, "basil": 30, "mint": 30, "celery": 40, "green onion": 15,
    "mushroom": 20, "shallot": 30, "ginger": 30, "chilli": 15, "chili": 15,
}
# grams per millilitre, for volume <-> mass
DENSITY: dict[str, float] = {
    "milk": 1.03, "water": 1.0, "oil": 0.92, "flour": 0.53, "sugar": 0.85, "rice": 0.85,
    "butter": 0.96, "cream": 1.0, "yogurt": 1.03, "honey": 1.4, "stock": 1.0, "broth": 1.0,
}
_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125}


def _lookup(table: dict[str, float], name: str) -> Optional[float]:
    name = name.lower()
    for key in sorted(table, key=len, reverse=True):
        if key in name:
            return table[key]
    return None


class UnitConverter:
    def normalize_unit(self, word: str) -> Optional[str]:
        return _UNIT_WORDS.get(word.strip().lower().rstrip("."))

    def parse_measure(self, raw: str) -> Optional[Quantity]:
        """'1 1/2 cups' -> 1.5 cup. Returns None for amounts like 'a pinch' or 'to taste'."""
        text = (raw or "").strip().lower()
        for symbol, value in _FRACTIONS.items():
            text = text.replace(symbol, f" {value}")
        frac = re.match(r"^\s*(?:(\d+(?:\.\d+)?)\s+)?(\d+)/(\d+)\s*([a-z]+)?", text)
        plain = re.match(r"^\s*(\d+(?:\.\d+)?)(?:\s+(\d+(?:\.\d+)?))?\s*([a-z]+)?", text)
        if frac and float(frac.group(3)) != 0:
            whole, num, den, word = frac.groups()
            amount = (float(whole) if whole else 0.0) + float(num) / float(den)
        elif plain:
            first, second, word = plain.groups()
            amount = float(first) + (float(second) if second else 0.0)  # "1 0.5 cup" after ½ replacement
        else:
            return None
        if amount <= 0:
            return None
        unit = self.normalize_unit(word) if word else "pcs"
        if unit is None:
            unit = "pcs"  # "2 eggs": the word is the ingredient itself, so it is a count
        return Quantity(amount, unit)

    def convert(self, quantity: Quantity, unit: str, ingredient: str = "") -> Optional[Quantity]:
        """Convert, using ingredient-specific weights when the unit kinds differ. None if impossible."""
        unit = unit.strip().lower()
        if quantity.can_convert(unit):
            return quantity.to(unit)
        grams = self._to_grams(quantity, ingredient)
        if grams is None:
            return None
        return self._from_grams(grams, unit, ingredient)

    def can_convert(self, quantity: Quantity, unit: str, ingredient: str = "") -> bool:
        return self.convert(quantity, unit, ingredient) is not None

    def _to_grams(self, q: Quantity, ingredient: str) -> Optional[float]:
        if q.can_convert("g"):
            return q.to("g").amount
        if q.can_convert("ml"):
            density = _lookup(DENSITY, ingredient)
            return q.to("ml").amount * density if density else None
        piece = _lookup(PIECE_GRAMS, ingredient)
        return q.amount * piece if piece else None

    def _from_grams(self, grams: float, unit: str, ingredient: str) -> Optional[Quantity]:
        probe = Quantity(1, unit)
        if probe.can_convert("g"):
            return Quantity(grams, "g").to(unit)
        if probe.can_convert("ml"):
            density = _lookup(DENSITY, ingredient)
            return Quantity(grams / density, "ml").to(unit) if density else None
        piece = _lookup(PIECE_GRAMS, ingredient)
        return Quantity(grams / piece, unit) if piece else None
