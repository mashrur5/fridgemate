from __future__ import annotations

from datetime import date
from typing import Callable, Optional
from uuid import UUID

from server.domain.model import FoodItem, Member, Notification
from server.domain.services.inventory_observer import InventoryObserver
from server.infrastructure.persistence import MemberRepository, NotificationRepository


class NotificationService:
    def __init__(self, notifications: NotificationRepository) -> None:
        self.notifications = notifications

    def notify(self, member_id: UUID, message: str, item_id: Optional[UUID] = None, kind: str = "info") -> None:
        self.notifications.save(Notification(member_id=member_id, message=message, item_id=item_id, kind=kind))

    def get_for(self, member: Member) -> list[Notification]:
        return self.notifications.find_by_member(member.id)

    def mark_all_read(self, member: Member) -> None:
        for n in self.notifications.find_by_member(member.id):
            if not n.read:
                n.read = True
                self.notifications.save(n)

    def close_offer(self, item_id: UUID) -> None:
        self.notifications.delete_for_item(item_id)


class HouseholdNotifier(InventoryObserver):
    """Observer (F15): tells roommates about offers, and tells the offerer who claimed."""

    def __init__(self, notifications: NotificationService, members: MemberRepository,
                 today: Callable[[], date] = date.today) -> None:
        self.notifications = notifications
        self.members = members
        self._today = today

    def update(self, item: FoodItem, change: str) -> None:
        if change == "offered" and item.offered_by is not None:
            days = (item.expiry_date - self._today()).days
            when = "today" if days <= 0 else f"in {days} day{'s' if days != 1 else ''}"
            for m in self.members.find_by_household(item.household_id):
                if m.id != item.offered_by.id:
                    self.notifications.notify(
                        m.id, f"{item.offered_by.name} is offering {item.name} (expires {when})"
                        + (f': "{item.offer_note}"' if item.offer_note else "") + ". First to claim gets it.",
                        item.id, "offer")
        elif change == "claimed":
            self.notifications.close_offer(item.id)
            if item.claimed_from is not None and item.owner is not None:
                self.notifications.notify(item.claimed_from.id, f"{item.owner.name} claimed your {item.name}.",
                                          item.id, "claim")
        elif change in ("removed", "used_up") or (change == "updated" and not item.is_offered):
            self.notifications.close_offer(item.id)
