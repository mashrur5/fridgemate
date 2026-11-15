from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from server.domain.model import Recipe


class RecipeSourceError(Exception):
    """The recipe database could not be reached."""


@dataclass
class RecipeSummary:
    id: str
    name: str
    image_url: str = ""


class RecipeSource(ABC):
    """Adapter target: where recipes come from."""

    @abstractmethod
    def search_by_ingredient(self, ingredient: str, cuisine: Optional[str] = None) -> list[RecipeSummary]: ...

    @abstractmethod
    def get_recipe(self, recipe_id: str) -> Optional[Recipe]: ...

    @abstractmethod
    def list_cuisines(self) -> list[str]: ...
