"""F09: cook a recipe, deduct the ingredients and optionally add leftovers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional
from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.errors import InvalidOperationError
from server.domain.model import FoodItem, Location, Quantity, Recipe
from server.domain.services.expiry import ExpiryService
from server.domain.services.inventory_service import InventoryService
from server.domain.services.stock_validator import CheckResult, StockValidator


@dataclass
class Usage:
    """Take `amount` from item `item_id` (amount may be in any convertible unit)."""

    item_id: UUID
    amount: Quantity


@dataclass
class Leftovers:
    portions: int
    location: Location = Location.FRIDGE


class CookingService:
    def __init__(self, inventory: InventoryService, validator: StockValidator, expiry: ExpiryService,
                 today: Callable[[], date] = date.today) -> None:
        self.inventory = inventory
        self.validator = validator
        self.expiry = expiry
        self._today = today

    def preview(self, ctx: RequestContext, recipe: Recipe, scale: float = 1.0) -> tuple[CheckResult, list[Usage]]:
        """What would be taken from which item. Only the member's own and Shared items are used."""
        items = [i for i in self.inventory.get_items(ctx) if i.visible_to(ctx.member)]
        result = self.validator.check(recipe, items, scale)
        usages = [Usage(a.item_id, a.amount) for allocs in result.allocations.values() for a in allocs]
        return result, usages

    def check_usages(self, ctx: RequestContext, usages: list[Usage]) -> None:
        """Every item must still exist, be ours or Shared, and have enough left. Raises with the problem."""
        totals: dict[UUID, float] = {}
        for u in usages:
            item = self.inventory.get_item(ctx, u.item_id)
            if not item.visible_to(ctx.member):
                raise InvalidOperationError(f"{item.name} belongs to another member")
            if not item.quantity.can_convert(u.amount.unit):
                raise InvalidOperationError(f"enter the amount of {item.name} in {item.quantity.unit}")
            totals[item.id] = totals.get(item.id, 0) + u.amount.to(item.quantity.unit).amount
            if totals[item.id] > item.quantity.amount + 1e-9:
                raise InvalidOperationError(f"not enough {item.name}: only {item.quantity.amount:g} "
                                            f"{item.quantity.unit} left")

    def make_leftovers(self, ctx: RequestContext, recipe_name: str, leftovers: Leftovers) -> FoodItem:
        if leftovers.portions <= 0:
            raise ValueError("portions must be at least 1")
        today = self._today()
        return FoodItem(name=f"Leftover {recipe_name}", quantity=Quantity(leftovers.portions, "pcs"),
                        location=leftovers.location, household_id=ctx.household.id,
                        expiry_date=self.expiry.estimate_expiry("leftover " + recipe_name, leftovers.location, today),
                        added_on=today, owner=ctx.member, expiry_estimated=True)
