from __future__ import annotations

from abc import ABC, abstractmethod

from server.domain.model import FoodItem


class InventoryObserver(ABC):
    """Observer pattern: anything that must react when the inventory changes.

    Subject: InventoryService. Concrete observers: ExpiryAlertNotifier,
    ShoppingListService and HouseholdNotifier.
    """

    @abstractmethod
    def update(self, item: FoodItem, change: str) -> None:
        """change is one of: added, updated, removed, deducted, offered, claimed."""
