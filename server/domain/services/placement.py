"""Strategy pattern for F02 Suggest Storage Location.

Context: PlacementService. Strategy: PlacementStrategy.
Concrete strategies: RuleBasedPlacementStrategy (here) and LLMPlacementStrategy (AI layer).
The LLM strategy is primary; the rule-based one is the fallback when the LLM fails.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from server.domain.model import Location

# keyword -> (location, reason). The first keyword found in the item name wins.
DEFAULT_PLACEMENT_RULES: dict[str, tuple[Location, str]] = {
    "ice cream": (Location.FREEZER, "frozen dessert"),
    "frozen": (Location.FREEZER, "sold frozen"),
    "milk": (Location.FRIDGE, "dairy spoils at room temperature"),
    "yogurt": (Location.FRIDGE, "dairy spoils at room temperature"),
    "cheese": (Location.FRIDGE, "dairy spoils at room temperature"),
    "butter": (Location.FRIDGE, "dairy spoils at room temperature"),
    "egg": (Location.FRIDGE, "eggs last longer cold"),
    "chicken": (Location.FRIDGE, "raw meat must stay cold"),
    "beef": (Location.FRIDGE, "raw meat must stay cold"),
    "pork": (Location.FRIDGE, "raw meat must stay cold"),
    "fish": (Location.FRIDGE, "raw fish must stay cold"),
    "spinach": (Location.FRIDGE, "leafy greens wilt quickly"),
    "lettuce": (Location.FRIDGE, "leafy greens wilt quickly"),
    "berries": (Location.FRIDGE, "soft fruit spoils fast"),
    "rice": (Location.PANTRY, "dry goods keep at room temperature"),
    "pasta": (Location.PANTRY, "dry goods keep at room temperature"),
    "flour": (Location.PANTRY, "dry goods keep at room temperature"),
    "bread": (Location.PANTRY, "bread goes stale faster in the fridge"),
    "onion": (Location.PANTRY, "onions keep best cool and dry"),
    "potato": (Location.PANTRY, "potatoes keep best cool and dark"),
    "banana": (Location.PANTRY, "bananas brown in the cold"),
    "can": (Location.PANTRY, "canned food is shelf stable"),
}


class PlacementStrategy(ABC):
    @abstractmethod
    def choose_location(self, item_name: str) -> tuple[Location, str]:
        """Return the location and a short reason. Raise an exception when unsure."""


class RuleBasedPlacementStrategy(PlacementStrategy):
    def __init__(self, rules: dict[str, tuple[Location, str]] | None = None) -> None:
        self.rules = rules if rules is not None else DEFAULT_PLACEMENT_RULES

    def choose_location(self, item_name: str) -> tuple[Location, str]:
        name = item_name.lower()
        for keyword, answer in self.rules.items():
            if keyword in name:
                return answer
        return Location.FRIDGE, "no rule matched, the fridge is the safest default"


class PlacementService:
    def __init__(self, primary: PlacementStrategy, fallback: PlacementStrategy) -> None:
        self.primary = primary
        self.fallback = fallback

    def suggest_location(self, item_name: str) -> tuple[Location, str]:
        try:
            return self.primary.choose_location(item_name)
        except Exception:
            return self.fallback.choose_location(item_name)
