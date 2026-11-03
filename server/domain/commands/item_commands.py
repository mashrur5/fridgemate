from __future__ import annotations

import copy
from typing import Optional
from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.commands.inventory_command import InventoryCommand
from server.domain.model import FoodItem
from server.domain.services.inventory_service import InventoryService


class AddItemCommand(InventoryCommand):
    def __init__(self, inventory: InventoryService, ctx: RequestContext, item: FoodItem) -> None:
        self.inventory, self.ctx, self.item = inventory, ctx, item
        self.description = f"add {item.name}"

    def execute(self) -> None:
        self.inventory.add(self.ctx, self.item)

    def undo(self) -> None:
        self.inventory.remove(self.ctx, self.item.id)


class UpdateItemCommand(InventoryCommand):
    def __init__(self, inventory: InventoryService, ctx: RequestContext, item: FoodItem) -> None:
        self.inventory, self.ctx, self.item = inventory, ctx, item
        self.before: Optional[FoodItem] = None
        self.description = f"update {item.name}"

    def execute(self) -> None:
        # keep a copy of the stored version so undo can put it back
        self.before = copy.copy(self.inventory.get_item(self.ctx, self.item.id))
        self.inventory.update(self.ctx, self.item)

    def undo(self) -> None:
        if self.before is not None:
            self.inventory.update(self.ctx, self.before)


class RemoveItemCommand(InventoryCommand):
    def __init__(self, inventory: InventoryService, ctx: RequestContext, item_id: UUID) -> None:
        self.inventory, self.ctx, self.item_id = inventory, ctx, item_id
        self.removed: Optional[FoodItem] = None
        self.description = "remove item"

    def execute(self) -> None:
        self.removed = self.inventory.remove(self.ctx, self.item_id)
        self.description = f"remove {self.removed.name}"

    def undo(self) -> None:
        if self.removed is not None:
            self.inventory.add(self.ctx, self.removed)


class OfferItemCommand(InventoryCommand):
    """F15: undoing an offer withdraws it."""

    def __init__(self, inventory: InventoryService, ctx: RequestContext, item_id: UUID, note: str = "") -> None:
        self.inventory, self.ctx, self.item_id, self.note = inventory, ctx, item_id, note
        self.description = "offer item"

    def execute(self) -> None:
        item = self.inventory.mark_offered(self.ctx, self.item_id, self.note)
        self.description = f"offer {item.name}"

    def undo(self) -> None:
        self.inventory.withdraw_offer(self.ctx, self.item_id)


class ClaimItemCommand(InventoryCommand):
    """F15: claims are final, so this command is run directly and never put in the undo history."""

    def __init__(self, inventory: InventoryService, ctx: RequestContext, item_id: UUID) -> None:
        self.inventory, self.ctx, self.item_id = inventory, ctx, item_id
        self.succeeded = False
        self.description = "claim item"

    def execute(self) -> None:
        self.succeeded = self.inventory.claim(self.ctx, self.item_id)

    def undo(self) -> None:
        raise NotImplementedError("claims cannot be undone")

    def undoable(self) -> bool:
        return False
