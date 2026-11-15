"""Repository interfaces for everything except food items (see item_repository.py).

The domain depends on these interfaces; SQLite and in-memory classes implement them
(Dependency Inversion)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from uuid import UUID

from server.domain.model import (
    Household, MealPlan, Member, Notification, Payment, Purchase, ShoppingListItem,
)


class MemberRepository(ABC):
    @abstractmethod
    def save(self, member: Member) -> None: ...

    @abstractmethod
    def find_by_id(self, member_id: UUID) -> Optional[Member]: ...

    @abstractmethod
    def find_by_account(self, account_id: str) -> Optional[Member]: ...

    @abstractmethod
    def find_by_household(self, household_id: UUID) -> list[Member]: ...


class HouseholdRepository(ABC):
    @abstractmethod
    def save(self, household: Household) -> None: ...

    @abstractmethod
    def find_by_id(self, household_id: UUID) -> Optional[Household]: ...

    @abstractmethod
    def find_by_invite_code(self, code: str) -> Optional[Household]: ...


class AccountRepository(ABC):
    """Login data: password hashes and session tokens. Kept apart from Member on purpose."""

    @abstractmethod
    def save_credentials(self, account_id: str, password_hash: str, salt: str) -> None: ...

    @abstractmethod
    def find_credentials(self, account_id: str) -> Optional[tuple[str, str]]: ...

    @abstractmethod
    def save_session(self, token: str, account_id: str, expires_at: datetime) -> None: ...

    @abstractmethod
    def find_session(self, token: str) -> Optional[tuple[str, datetime]]: ...

    @abstractmethod
    def delete_session(self, token: str) -> None: ...


class ShoppingListRepository(ABC):
    @abstractmethod
    def save(self, item: ShoppingListItem) -> None: ...

    @abstractmethod
    def find_by_household(self, household_id: UUID) -> list[ShoppingListItem]: ...

    @abstractmethod
    def delete(self, item_id: UUID) -> None: ...


class CostRepository(ABC):
    @abstractmethod
    def save_purchase(self, purchase: Purchase) -> None: ...

    @abstractmethod
    def delete_purchase_for_item(self, item_id: UUID) -> None: ...

    @abstractmethod
    def purchases(self, household_id: UUID) -> list[Purchase]: ...

    @abstractmethod
    def save_payment(self, payment: Payment) -> None: ...

    @abstractmethod
    def delete_payment(self, payment_id: UUID) -> None: ...

    @abstractmethod
    def payments(self, household_id: UUID) -> list[Payment]: ...


class NotificationRepository(ABC):
    @abstractmethod
    def save(self, notification: Notification) -> None: ...

    @abstractmethod
    def find_by_member(self, member_id: UUID) -> list[Notification]: ...

    @abstractmethod
    def delete_for_item(self, item_id: UUID) -> None: ...


class MealPlanRepository(ABC):
    @abstractmethod
    def save(self, plan: MealPlan) -> None: ...

    @abstractmethod
    def latest_for_member(self, member_id: UUID) -> Optional[MealPlan]: ...
