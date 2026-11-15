from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from server.domain.model.quantity import Quantity

WEIGHTS = ("light", "medium", "heavy")


@dataclass
class RecipeIngredient:
    """One line of a recipe. quantity is None when the amount can't be measured ("a pinch")."""

    name: str
    quantity: Optional[Quantity] = None
    raw_measure: str = ""


@dataclass
class Recipe:
    name: str
    ingredients: list[RecipeIngredient]
    id: str = ""
    cuisine: str = ""
    category: str = ""
    instructions: str = ""
    image_url: str = ""
    servings: int = 2
    ai_generated: bool = False


@dataclass
class RecipeRequest:
    """F07/F10 options. None means "Let AI decide"."""

    cuisine: Optional[str] = None
    max_minutes: Optional[int] = None
    weight: Optional[str] = None
    servings: int = 2

    def __post_init__(self) -> None:
        if self.weight is not None:
            self.weight = self.weight.lower()
            if self.weight not in WEIGHTS:
                raise ValueError("weight must be light, medium or heavy")
        if not 1 <= self.servings <= 10:
            raise ValueError("servings must be between 1 and 10")
        if self.max_minutes is not None and self.max_minutes <= 0:
            raise ValueError("cooking time must be positive")


@dataclass
class IngredientCheck:
    """F08: the result of checking one recipe ingredient against the stock."""

    ingredient: RecipeIngredient
    status: str  # "have", "short", "missing" or "check amount"
    item_id: Optional[str] = None
    item_name: Optional[str] = None
    expiring: bool = False
    substitute: Optional[str] = None


@dataclass
class RecipeSuggestion:
    recipe: Recipe
    checks: list[IngredientCheck] = field(default_factory=list)
    estimated_minutes: Optional[int] = None
    weight: Optional[str] = None
    explanation: str = ""
    score: float = 0.0

    @property
    def missing(self) -> list[IngredientCheck]:
        return [c for c in self.checks if c.status in ("missing", "short")]

    @property
    def used(self) -> list[IngredientCheck]:
        return [c for c in self.checks if c.status == "have"]

    @property
    def expiring_used(self) -> int:
        return sum(1 for c in self.used if c.expiring)
