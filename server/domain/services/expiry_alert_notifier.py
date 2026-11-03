from __future__ import annotations

from server.application.request_context import RequestContext
from server.domain.model import FoodItem
from server.domain.services.inventory_observer import InventoryObserver
from server.domain.services.inventory_service import InventoryService


class ExpiryAlertNotifier(InventoryObserver):
    """F05: builds the expiry alert list. As an observer it counts changes, so the
    web client knows when its alert banner is out of date."""

    def __init__(self, inventory: InventoryService) -> None:
        self.inventory = inventory
        self.changes_seen = 0

    def update(self, item: FoodItem, change: str) -> None:
        self.changes_seen += 1

    def get_alerts(self, ctx: RequestContext) -> list[FoodItem]:
        """Expiring-soon items first (fewest days left first), then expired items.
        Only items the member owns or that are Shared appear."""
        items = [i for i in self.inventory.get_items(ctx) if i.visible_to(ctx.member)]
        flagged = [i for i in items if i.alert_priority() > 0]
        expiring = sorted((i for i in flagged if i.alert_priority() == 1), key=lambda i: i.expiry_date)
        expired = sorted((i for i in flagged if i.alert_priority() == 2), key=lambda i: i.expiry_date)
        return expiring + expired
