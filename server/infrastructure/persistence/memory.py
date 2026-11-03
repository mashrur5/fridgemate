from __future__ import annotations

import threading
from typing import Optional
from uuid import UUID

from server.domain.model import FoodItem, Member
from server.infrastructure.persistence.item_repository import ItemRepository


class InMemoryItemRepository(ItemRepository):
    """Keeps items in a dict. Used by the tests and for running the app without a database."""

    def __init__(self) -> None:
        self._items: dict[UUID, FoodItem] = {}
        self._lock = threading.Lock()

    def save(self, item: FoodItem) -> None:
        self._items[item.id] = item

    def find_by_id(self, item_id: UUID) -> Optional[FoodItem]:
        return self._items.get(item_id)

    def find_by_household(self, household_id: UUID) -> list[FoodItem]:
        return [i for i in self._items.values() if i.household_id == household_id]

    def find_by_owner(self, owner_id: UUID) -> list[FoodItem]:
        return [i for i in self._items.values() if i.owner is not None and i.owner.id == owner_id]

    def claim_if_unclaimed(self, item_id: UUID, member: Member) -> bool:
        with self._lock:  # same guarantee as the single conditional UPDATE in Postgres
            item = self._items.get(item_id)
            if item is None or not item.is_offered:
                return False
            item.owner = member
            item.is_offered = False
            item.offered_by = None
            return True

    def delete(self, item_id: UUID) -> None:
        self._items.pop(item_id, None)
