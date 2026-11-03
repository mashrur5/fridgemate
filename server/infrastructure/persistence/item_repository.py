from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from server.domain.model import FoodItem, Member


class ItemRepository(ABC):
    """Storage for food items. Services depend on this interface, not on a database (Dependency Inversion)."""

    @abstractmethod
    def save(self, item: FoodItem) -> None: ...

    @abstractmethod
    def find_by_id(self, item_id: UUID) -> Optional[FoodItem]: ...

    @abstractmethod
    def find_by_household(self, household_id: UUID) -> list[FoodItem]: ...

    @abstractmethod
    def find_by_owner(self, owner_id: UUID) -> list[FoodItem]: ...

    @abstractmethod
    def claim_if_unclaimed(self, item_id: UUID, member: Member) -> bool:
        """Give an offered item to member in one step. Only the first claim wins."""

    @abstractmethod
    def delete(self, item_id: UUID) -> None: ...
