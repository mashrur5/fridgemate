"""Strategy: where the recipe agent gets its ingredients from.

FridgeIngredientSource (F07) uses the real inventory; ManualIngredientSource (F10) uses a typed list.
G2: ownership and expiry are filtered here, by regular code, before anything reaches the LLM."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, timedelta

from server.application.request_context import RequestContext
from server.domain.model import FoodItem, Location, Quantity
from server.domain.services.inventory_service import InventoryService


class IngredientSource(ABC):
    amounts_known: bool = True

    @abstractmethod
    def get_items(self, ctx: RequestContext) -> list[FoodItem]:
        """Usable items only: the member's own, Shared, or offered by a roommate, and not expired."""


class FridgeIngredientSource(IngredientSource):
    def __init__(self, inventory: InventoryService) -> None:
        self.inventory = inventory

    def get_items(self, ctx: RequestContext) -> list[FoodItem]:
        items = self.inventory.get_items(ctx)
        usable = [i for i in items if (i.visible_to(ctx.member) or i.is_offered) and i.can_use_in_recipe()]
        # most urgent first: offered and expiring-soon items, then by expiry date
        return sorted(usable, key=lambda i: (-(i.alert_priority() == 1 or i.is_offered), i.expiry_date))


class ManualIngredientSource(IngredientSource):
    """F10: ingredients typed by the user. Amounts are unknown, so only names are compared."""

    amounts_known = False

    def __init__(self, names: list[str]) -> None:
        cleaned = []
        for n in names:
            n = re.sub(r"[^\w\s\-']", "", n).strip().lower()[:40]
            if n and n not in cleaned:
                cleaned.append(n)
        self.names = cleaned

    def get_items(self, ctx: RequestContext) -> list[FoodItem]:
        today = date.today()
        return [FoodItem(name=n, quantity=Quantity(1, "pcs"), location=Location.PANTRY, household_id=ctx.household.id,
                         expiry_date=today + timedelta(days=30), added_on=today, owner=ctx.member) for n in self.names]
