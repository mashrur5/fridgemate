"""Strategy pattern for F04 Estimate Expiry.

Context: ExpiryService. Strategy: ExpiryEstimator.
Concrete strategies: RuleBasedExpiryEstimator (here) and LLMExpiryEstimator (AI layer).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta

from server.domain.model import Location

# keyword -> days it lasts in (fridge, freezer, pantry)
DEFAULT_SHELF_LIFE: dict[str, tuple[int, int, int]] = {
    "milk": (7, 90, 1),
    "yogurt": (14, 60, 1),
    "cheese": (21, 180, 2),
    "egg": (28, 120, 7),
    "chicken": (2, 270, 0),
    "beef": (3, 270, 0),
    "fish": (2, 180, 0),
    "spinach": (5, 240, 1),
    "lettuce": (7, 0, 1),
    "berries": (5, 240, 1),
    "bread": (7, 90, 5),
    "rice": (5, 180, 365),
    "pasta": (5, 60, 365),
    "banana": (7, 60, 5),
    "onion": (30, 240, 30),
    "potato": (21, 300, 30),
}
DEFAULT_DAYS = {Location.FRIDGE: 7, Location.FREEZER: 90, Location.PANTRY: 30}
_INDEX = {Location.FRIDGE: 0, Location.FREEZER: 1, Location.PANTRY: 2}


class ExpiryEstimator(ABC):
    @abstractmethod
    def estimate_days(self, item_name: str, location: Location) -> int:
        """How many days the item lasts where it is stored. Raise an exception when unsure."""


class RuleBasedExpiryEstimator(ExpiryEstimator):
    def __init__(self, rules: dict[str, tuple[int, int, int]] | None = None) -> None:
        self.rules = rules if rules is not None else DEFAULT_SHELF_LIFE

    def estimate_days(self, item_name: str, location: Location) -> int:
        name = item_name.lower()
        for keyword, days in self.rules.items():
            if keyword in name:
                value = days[_INDEX[location]]
                # 0 means "do not store it there"; still give a short, safe estimate
                return max(value, 1)
        return DEFAULT_DAYS[location]


class ExpiryService:
    def __init__(self, primary: ExpiryEstimator, fallback: ExpiryEstimator) -> None:
        self.primary = primary
        self.fallback = fallback

    def estimate_expiry(self, item_name: str, location: Location, added_on: date) -> date:
        """The estimated expiry date. Items using it are marked expiry_estimated=True by the caller."""
        try:
            days = self.primary.estimate_days(item_name, location)
            if days <= 0:
                raise ValueError("estimate must be positive")
        except Exception:
            days = self.fallback.estimate_days(item_name, location)
        return added_on + timedelta(days=days)
