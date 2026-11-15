from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass
class Purchase:
    """F14: a Shared item someone paid for. Recorded when the item is added."""

    household_id: UUID
    item_id: UUID
    item_name: str
    price: Decimal
    payer_id: UUID
    bought_on: date
    id: UUID = field(default_factory=uuid4)


@dataclass
class Payment:
    """A settlement that a member marked as paid."""

    household_id: UUID
    from_id: UUID
    to_id: UUID
    amount: Decimal
    paid_on: date
    id: UUID = field(default_factory=uuid4)


@dataclass
class Settlement:
    """A suggested payment: from_id pays to_id."""

    from_id: UUID
    to_id: UUID
    amount: Decimal


@dataclass
class CostSummary:
    purchases: list[Purchase]
    paid: dict[UUID, Decimal]
    share: dict[UUID, Decimal]
    balance: dict[UUID, Decimal]
    settlements: list[Settlement]
    payments: list[Payment]
