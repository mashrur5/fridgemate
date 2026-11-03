from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

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

    def is_shared(self) -> bool:
        return self.owner is None

    def is_low(self) -> bool:
        return self.quantity.amount <= self.original_amount * LOW_STOCK_RATIO

    def visible_to(self, member: Member) -> bool:
        """A member can use their own items and Shared items, never a roommate's private item."""
        return self.is_shared() or self.owner.id == member.id
