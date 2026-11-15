from __future__ import annotations

import threading
from typing import Optional
from uuid import UUID

from datetime import datetime

from server.domain.model import (
    FoodItem, Household, MealPlan, Member, Notification, Payment, Purchase, ShoppingListItem,
)
from server.infrastructure.persistence.item_repository import ItemRepository
from server.infrastructure.persistence.repositories import (
    AccountRepository, CostRepository, HouseholdRepository, MealPlanRepository, MemberRepository,
    NotificationRepository, ShoppingListRepository,
)


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


class InMemoryMemberRepository(MemberRepository):
    def __init__(self) -> None:
        self._rows: dict[UUID, Member] = {}

    def save(self, member: Member) -> None:
        self._rows[member.id] = member

    def find_by_id(self, member_id: UUID) -> Optional[Member]:
        return self._rows.get(member_id)

    def find_by_account(self, account_id: str) -> Optional[Member]:
        return next((m for m in self._rows.values() if m.account_id == account_id), None)

    def find_by_household(self, household_id: UUID) -> list[Member]:
        return [m for m in self._rows.values() if m.household_id == household_id]


class InMemoryHouseholdRepository(HouseholdRepository):
    def __init__(self) -> None:
        self._rows: dict[UUID, Household] = {}

    def save(self, household: Household) -> None:
        self._rows[household.id] = household

    def find_by_id(self, household_id: UUID) -> Optional[Household]:
        return self._rows.get(household_id)

    def find_by_invite_code(self, code: str) -> Optional[Household]:
        return next((h for h in self._rows.values() if h.invite_code == code.strip().upper()), None)


class InMemoryAccountRepository(AccountRepository):
    def __init__(self) -> None:
        self._creds: dict[str, tuple[str, str]] = {}
        self._sessions: dict[str, tuple[str, datetime]] = {}

    def save_credentials(self, account_id: str, password_hash: str, salt: str) -> None:
        self._creds[account_id] = (password_hash, salt)

    def find_credentials(self, account_id: str) -> Optional[tuple[str, str]]:
        return self._creds.get(account_id)

    def save_session(self, token: str, account_id: str, expires_at: datetime) -> None:
        self._sessions[token] = (account_id, expires_at)

    def find_session(self, token: str) -> Optional[tuple[str, datetime]]:
        return self._sessions.get(token)

    def delete_session(self, token: str) -> None:
        self._sessions.pop(token, None)


class InMemoryShoppingListRepository(ShoppingListRepository):
    def __init__(self) -> None:
        self._rows: dict[UUID, ShoppingListItem] = {}

    def save(self, item: ShoppingListItem) -> None:
        self._rows[item.id] = item

    def find_by_household(self, household_id: UUID) -> list[ShoppingListItem]:
        return [i for i in self._rows.values() if i.household_id == household_id]

    def delete(self, item_id: UUID) -> None:
        self._rows.pop(item_id, None)


class InMemoryCostRepository(CostRepository):
    def __init__(self) -> None:
        self._purchases: dict[UUID, Purchase] = {}
        self._payments: dict[UUID, Payment] = {}

    def save_purchase(self, purchase: Purchase) -> None:
        self._purchases[purchase.id] = purchase

    def delete_purchase_for_item(self, item_id: UUID) -> None:
        for key in [k for k, p in self._purchases.items() if p.item_id == item_id]:
            del self._purchases[key]

    def purchases(self, household_id: UUID) -> list[Purchase]:
        return [p for p in self._purchases.values() if p.household_id == household_id]

    def save_payment(self, payment: Payment) -> None:
        self._payments[payment.id] = payment

    def delete_payment(self, payment_id: UUID) -> None:
        self._payments.pop(payment_id, None)

    def payments(self, household_id: UUID) -> list[Payment]:
        return [p for p in self._payments.values() if p.household_id == household_id]


class InMemoryNotificationRepository(NotificationRepository):
    def __init__(self) -> None:
        self._rows: dict[UUID, Notification] = {}

    def save(self, notification: Notification) -> None:
        self._rows[notification.id] = notification

    def find_by_member(self, member_id: UUID) -> list[Notification]:
        return sorted((n for n in self._rows.values() if n.member_id == member_id),
                      key=lambda n: n.created_at, reverse=True)

    def delete_for_item(self, item_id: UUID) -> None:
        for key in [k for k, n in self._rows.items() if n.item_id == item_id and n.kind == "offer"]:
            del self._rows[key]


class InMemoryMealPlanRepository(MealPlanRepository):
    def __init__(self) -> None:
        self._rows: dict[UUID, MealPlan] = {}

    def save(self, plan: MealPlan) -> None:
        self._rows[plan.id] = plan

    def latest_for_member(self, member_id: UUID) -> Optional[MealPlan]:
        plans = [p for p in self._rows.values() if p.member_id == member_id]
        return max(plans, key=lambda p: p.created_at) if plans else None
