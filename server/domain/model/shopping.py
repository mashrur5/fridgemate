from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4

from server.domain.model.quantity import Quantity


@dataclass
class ShoppingListItem:
    """One line of a shopping list. member_id None means the line is on the Shared list."""

    household_id: UUID
    name: str
    quantity: Optional[Quantity]
    section: str
    reasons: list[str] = field(default_factory=list)
    member_id: Optional[UUID] = None
    checked: bool = False
    id: UUID = field(default_factory=uuid4)


@dataclass
class ShoppingList:
    """What one member sees: their own lines plus the Shared lines, grouped by store section."""

    items: list[ShoppingListItem]

    def by_section(self) -> dict[str, list[ShoppingListItem]]:
        groups: dict[str, list[ShoppingListItem]] = {}
        for item in sorted(self.items, key=lambda i: (i.section, i.name)):
            groups.setdefault(item.section, []).append(item)
        return groups
