"""F11: shopping lists. Observer: low or used-up items are added automatically."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.errors import NotFoundError
from server.domain.model import FoodItem, Quantity, ShoppingList, ShoppingListItem
from server.domain.services.inventory_observer import InventoryObserver
from server.domain.services.stock_validator import normalize
from server.domain.services.unit_converter import UnitConverter
from server.infrastructure.persistence import ShoppingListRepository

SECTIONS: list[tuple[str, list[str]]] = [
    ("Frozen", ["frozen", "ice cream"]),
    ("Dairy and eggs", ["milk", "cheese", "butter", "yogurt", "cream", "egg"]),
    ("Meat and fish", ["chicken", "beef", "pork", "lamb", "fish", "salmon", "tuna", "shrimp", "bacon", "sausage",
                       "turkey", "ham", "mince"]),
    ("Produce", ["onion", "garlic", "potato", "tomato", "lettuce", "spinach", "carrot", "pepper", "apple", "banana",
                 "lemon", "lime", "berries", "berry", "cucumber", "zucchini", "mushroom", "ginger", "herb", "parsley",
                 "coriander", "basil", "avocado", "cabbage", "broccoli", "celery", "fruit", "vegetable"]),
    ("Bakery", ["bread", "bun", "bagel", "tortilla", "pita", "croissant"]),
    ("Pantry", ["rice", "pasta", "flour", "sugar", "oil", "salt", "spice", "sauce", "can", "bean", "lentil",
                "stock", "noodle", "cereal", "oat", "vinegar", "honey", "spaghetti"]),
]


def section_for(name: str) -> str:
    text = name.lower()
    for section, words in SECTIONS:
        if any(w in text for w in words):
            return section
    return "Other"


class ShoppingListService(InventoryObserver):
    def __init__(self, repo: ShoppingListRepository, converter: Optional[UnitConverter] = None) -> None:
        self.repo = repo
        self.converter = converter or UnitConverter()

    # --- Observer: react to inventory changes ---

    def update(self, item: FoodItem, change: str) -> None:
        low = change in ("deducted", "updated") and item.is_low()
        if not (low or change == "used_up"):
            return
        owner_id = None if item.is_shared() else item.owner.id
        key = normalize(item.name)
        if any(not l.checked and l.member_id == owner_id and normalize(l.name) == key and
               ("running low" in l.reasons or "used up" in l.reasons) for l in self.repo.find_by_household(item.household_id)):
            return  # already on the list because of stock, don't add it again on every change
        reason = "used up" if change == "used_up" else "running low"
        self._add(item.household_id, owner_id, item.name, Quantity(item.original_amount, item.quantity.unit), reason)

    # --- user actions ---

    def get_list(self, ctx: RequestContext) -> ShoppingList:
        rows = [i for i in self.repo.find_by_household(ctx.household.id)
                if i.member_id is None or i.member_id == ctx.member.id]
        return ShoppingList(rows)

    def add_item(self, ctx: RequestContext, name: str, quantity: Optional[Quantity], reason: str = "added by hand",
                 shared: bool = False) -> ShoppingListItem:
        if not name.strip():
            raise ValueError("item name cannot be empty")
        return self._add(ctx.household.id, None if shared else ctx.member.id, name.strip(), quantity, reason)

    def set_checked(self, ctx: RequestContext, item_id: UUID, checked: bool) -> ShoppingListItem:
        line = self._own(ctx, item_id)
        line.checked = checked
        self.repo.save(line)
        return line

    def remove(self, ctx: RequestContext, item_id: UUID) -> None:
        self.repo.delete(self._own(ctx, item_id).id)

    def clear_checked(self, ctx: RequestContext) -> int:
        done = [i for i in self.get_list(ctx).items if i.checked]
        for line in done:
            self.repo.delete(line.id)
        return len(done)

    # --- merging ---

    def _add(self, household_id: UUID, member_id: Optional[UUID], name: str, quantity: Optional[Quantity],
             reason: str) -> ShoppingListItem:
        key = normalize(name)
        for line in self.repo.find_by_household(household_id):
            if line.checked or line.member_id != member_id or normalize(line.name) != key:
                continue
            merged = self._merge(line.quantity, quantity, name)
            if merged is False:
                continue  # units can't be merged ("2 cans" and "400 g"), so keep separate lines
            line.quantity = merged
            if reason not in line.reasons:
                line.reasons.append(reason)
            self.repo.save(line)
            return line
        line = ShoppingListItem(household_id=household_id, name=name, quantity=quantity, section=section_for(name),
                                reasons=[reason], member_id=member_id)
        self.repo.save(line)
        return line

    def _merge(self, current: Optional[Quantity], extra: Optional[Quantity], name: str):
        if current is None or extra is None:
            return current or extra
        converted = self.converter.convert(extra, current.unit, name)
        if converted is None:
            return False
        total = Quantity(current.amount + converted.amount, current.unit)
        if total.unit == "g" and total.amount >= 1000:
            total = total.to("kg")
        elif total.unit == "ml" and total.amount >= 1000:
            total = total.to("l")
        return total

    def _own(self, ctx: RequestContext, item_id: UUID) -> ShoppingListItem:
        line = next((i for i in self.get_list(ctx).items if i.id == item_id), None)
        if line is None:
            raise NotFoundError("shopping list item not found")
        return line
