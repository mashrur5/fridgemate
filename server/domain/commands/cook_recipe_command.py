from __future__ import annotations

import copy
from typing import Optional

from server.application.request_context import RequestContext
from server.domain.commands.inventory_command import InventoryCommand
from server.domain.model import FoodItem
from server.domain.services.cooking_service import CookingService, Leftovers, Usage
from server.domain.services.inventory_service import InventoryService


class CookRecipeCommand(InventoryCommand):
    """F09: one command for the whole cooking action, so a single undo restores every quantity
    and removes the leftovers item."""

    def __init__(self, inventory: InventoryService, cooking: CookingService, ctx: RequestContext,
                 recipe_name: str, usages: list[Usage], leftovers: Optional[Leftovers] = None) -> None:
        self.inventory, self.cooking, self.ctx = inventory, cooking, ctx
        self.recipe_name, self.usages, self.leftovers = recipe_name, usages, leftovers
        self.before: list[FoodItem] = []
        self.leftover_item: Optional[FoodItem] = None
        self.description = f"cook {recipe_name}"

    def execute(self) -> None:
        self.cooking.check_usages(self.ctx, self.usages)  # nothing changes unless every item has enough
        seen = set()
        for u in self.usages:
            if u.item_id not in seen:
                seen.add(u.item_id)
                self.before.append(copy.copy(self.inventory.get_item(self.ctx, u.item_id)))
        for u in self.usages:
            self.inventory.deduct(self.ctx, u.item_id, u.amount)
        if self.leftovers is not None:
            self.leftover_item = self.cooking.make_leftovers(self.ctx, self.recipe_name, self.leftovers)
            self.inventory.add(self.ctx, self.leftover_item)

    def undo(self) -> None:
        if self.leftover_item is not None:
            try:
                self.inventory.remove(self.ctx, self.leftover_item.id)
            except Exception:
                pass  # already eaten or removed
        for item in self.before:
            if self.inventory.items.find_by_id(item.id) is None:
                self.inventory.add(self.ctx, copy.copy(item))
            else:
                self.inventory.update(self.ctx, copy.copy(item))
