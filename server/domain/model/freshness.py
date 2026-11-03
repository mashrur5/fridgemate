"""State pattern: an item's behaviour depends on how fresh it is.

Context: FoodItem. State: FreshnessState.
Concrete states: FreshState, ExpiringSoonState, ExpiredState.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

# "Expiring soon" means the item expires within this many days (Stage 1, F05).
EXPIRING_SOON_DAYS = 3


class FreshnessState(ABC):
    @abstractmethod
    def can_use_in_recipe(self) -> bool: ...

    @abstractmethod
    def can_offer(self) -> bool: ...

    @abstractmethod
    def alert_priority(self) -> int:
        """0 = no alert. Higher numbers are shown first."""

    @abstractmethod
    def label(self) -> str: ...

    @staticmethod
    def for_dates(expiry_date: date, today: date) -> FreshnessState:
        days_left = (expiry_date - today).days
        if days_left < 0:
            return ExpiredState()
        if days_left <= EXPIRING_SOON_DAYS:
            return ExpiringSoonState()
        return FreshState()


class FreshState(FreshnessState):
    def can_use_in_recipe(self) -> bool:
        return True

    def can_offer(self) -> bool:
        return False  # only expiring items can be offered to roommates (F15)

    def alert_priority(self) -> int:
        return 0

    def label(self) -> str:
        return "Fresh"


class ExpiringSoonState(FreshnessState):
    def can_use_in_recipe(self) -> bool:
        return True

    def can_offer(self) -> bool:
        return True

    def alert_priority(self) -> int:
        return 1

    def label(self) -> str:
        return "Expiring soon"


class ExpiredState(FreshnessState):
    def can_use_in_recipe(self) -> bool:
        return False  # never suggest cooking with expired food

    def can_offer(self) -> bool:
        return False

    def alert_priority(self) -> int:
        return 2

    def label(self) -> str:
        return "Expired"
