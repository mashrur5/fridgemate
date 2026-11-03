from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from server.domain.model.freshness import FreshnessState
from server.domain.model.location import Location
from server.domain.model.member import Member
from server.domain.model.quantity import Quantity

# An item counts as "low" when a quarter or less of the original amount is left.
LOW_STOCK_RATIO = 0.25


@dataclass
class FoodItem:
    """One item in a household's inventory.

    owner = None means the item is Shared, so every member may use it.
    """

    name: str
    quantity: Quantity
    location: Location
    household_id: UUID
    expiry_date: date
    added_on: date = field(default_factory=date.today)
    owner: Optional[Member] = None
    original_amount: Optional[float] = None
    expiry_estimated: bool = False
    price: Optional[Decimal] = None
    payer: Optional[Member] = None
    is_offered: bool = False
    offered_by: Optional[Member] = None
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("item name cannot be empty")
        if self.quantity.amount <= 0:
            raise ValueError("quantity must be greater than 0")
        if self.original_amount is None:
            self.original_amount = self.quantity.amount
        self._state: FreshnessState = FreshnessState.for_dates(self.expiry_date, self.added_on)

    # --- State pattern: FoodItem is the context and delegates to its FreshnessState ---

    def refresh_state(self, today: date) -> None:
        """Pick the state from the expiry date. Called whenever alerts or recipes need fresh data."""
        self._state = FreshnessState.for_dates(self.expiry_date, today)

    @property
    def state(self) -> FreshnessState:
        return self._state

    def can_use_in_recipe(self) -> bool:
        return self._state.can_use_in_recipe()

    def can_offer(self) -> bool:
        return self._state.can_offer()

    def alert_priority(self) -> int:
        return self._state.alert_priority()

    def freshness_label(self) -> str:
        return self._state.label()

    def is_shared(self) -> bool:
        return self.owner is None

    def is_low(self) -> bool:
        return self.quantity.amount <= self.original_amount * LOW_STOCK_RATIO

    def visible_to(self, member: Member) -> bool:
        """A member can use their own items and Shared items, never a roommate's private item."""
        return self.is_shared() or self.owner.id == member.id
