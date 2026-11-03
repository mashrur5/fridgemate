from __future__ import annotations

from datetime import date
from typing import Callable
from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.errors import InvalidOperationError, NotFoundError, PermissionDeniedError
from server.domain.model import FoodItem, Quantity
from server.domain.services.inventory_observer import InventoryObserver
from server.infrastructure.persistence import ItemRepository


class InventoryService:
    """Holds the inventory rules (household, ownership, freshness) and is the Observer subject."""

    def __init__(self, items: ItemRepository, today: Callable[[], date] = date.today) -> None:
        self.items = items
        self.observers: list[InventoryObserver] = []
        self._today = today

    # --- Observer pattern: subject side ---

    def attach(self, observer: InventoryObserver) -> None:
        if observer not in self.observers:
            self.observers.append(observer)

    def detach(self, observer: InventoryObserver) -> None:
        if observer in self.observers:
            self.observers.remove(observer)

    def notify_observers(self, item: FoodItem, change: str) -> None:
        for observer in list(self.observers):
            observer.update(item, change)

    # --- queries ---

    def get_items(self, ctx: RequestContext) -> list[FoodItem]:
        """The member's own items, Shared items, and roommates' items that are on offer."""
        today = self._today()
        result = []
        for item in self.items.find_by_household(ctx.household.id):
            if item.visible_to(ctx.member) or item.is_offered:
                item.refresh_state(today)
                result.append(item)
        return sorted(result, key=lambda i: i.expiry_date)

    def get_item(self, ctx: RequestContext, item_id: UUID) -> FoodItem:
        item = self.items.find_by_id(item_id)
        if item is None or item.household_id != ctx.household.id:
            raise NotFoundError("item not found")
        item.refresh_state(self._today())
        return item

    # --- commands (each one tells the observers) ---

    def add(self, ctx: RequestContext, item: FoodItem) -> FoodItem:
        if item.household_id != ctx.household.id:
            raise PermissionDeniedError("items can only be added to your own household")
        item.refresh_state(self._today())
        self.items.save(item)
        self.notify_observers(item, "added")
        return item

    def update(self, ctx: RequestContext, item: FoodItem) -> FoodItem:
        self._editable(ctx, item.id)
        item.refresh_state(self._today())
        self.items.save(item)
        self.notify_observers(item, "updated")
        return item

    def remove(self, ctx: RequestContext, item_id: UUID) -> FoodItem:
        item = self._editable(ctx, item_id)
        self.items.delete(item_id)
        self.notify_observers(item, "removed")
        return item

    def deduct(self, ctx: RequestContext, item_id: UUID, amount: Quantity) -> FoodItem:
        """Use up part of an item (cooking). An item that reaches zero is removed."""
        item = self._editable(ctx, item_id)
        if not item.quantity.can_convert(amount.unit):
            raise InvalidOperationError(f"cannot take {amount.unit} from an item measured in {item.quantity.unit}")
        used = amount.to(item.quantity.unit).amount
        if used > item.quantity.amount + 1e-9:
            raise InvalidOperationError(f"only {item.quantity.amount:g} {item.quantity.unit} of {item.name} left")
        left = item.quantity.amount - used
        if left <= 1e-9:
            self.items.delete(item_id)
            self.notify_observers(item, "removed")
            return item
        item.quantity = Quantity(left, item.quantity.unit)
        self.items.save(item)
        self.notify_observers(item, "deducted")
        return item

    def mark_offered(self, ctx: RequestContext, item_id: UUID, note: str = "") -> FoodItem:
        """F15: the owner offers an expiring item to the household."""
        item = self.get_item(ctx, item_id)
        if item.owner is None or item.owner.id != ctx.member.id:
            raise PermissionDeniedError("only the owner can offer an item")
        if not item.can_offer():
            raise InvalidOperationError("items can be offered within 3 days of expiry")
        item.is_offered = True
        item.offered_by = ctx.member
        self.items.save(item)
        self.notify_observers(item, "offered")
        return item

    def withdraw_offer(self, ctx: RequestContext, item_id: UUID) -> FoodItem:
        item = self.get_item(ctx, item_id)
        if not item.is_offered or item.offered_by is None or item.offered_by.id != ctx.member.id:
            raise InvalidOperationError("there is no offer of yours to withdraw")
        item.is_offered = False
        item.offered_by = None
        self.items.save(item)
        self.notify_observers(item, "updated")
        return item

    def claim(self, ctx: RequestContext, item_id: UUID) -> bool:
        """F15: a roommate claims an offered item. Returns False if someone else got it first."""
        item = self.get_item(ctx, item_id)
        if item.offered_by is not None and item.offered_by.id == ctx.member.id:
            raise InvalidOperationError("you cannot claim your own offer")
        if not self.items.claim_if_unclaimed(item_id, ctx.member):
            return False
        self.notify_observers(self.items.find_by_id(item_id), "claimed")
        return True

    # --- rules ---

    def _editable(self, ctx: RequestContext, item_id: UUID) -> FoodItem:
        item = self.get_item(ctx, item_id)
        if not item.visible_to(ctx.member):
            raise PermissionDeniedError("this item belongs to another member")
        return item
