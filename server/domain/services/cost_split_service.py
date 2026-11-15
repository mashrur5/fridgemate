"""F14: split Shared purchases equally and find the fewest payments to settle up."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.errors import InvalidOperationError
from server.domain.model import CostSummary, FoodItem, Payment, Purchase, Settlement
from server.domain.services.inventory_observer import InventoryObserver
from server.infrastructure.persistence import CostRepository, ItemRepository, MemberRepository

CENT = Decimal("0.01")


class CostSplitService(InventoryObserver):
    """Observer: records a Purchase when a Shared item with a price and payer is added."""

    def __init__(self, costs: CostRepository, members: MemberRepository, items: ItemRepository,
                 today: Callable[[], date] = date.today) -> None:
        self.costs = costs
        self.members = members
        self.items = items
        self._today = today

    def update(self, item: FoodItem, change: str) -> None:
        if change == "added" and item.is_shared() and item.price and item.payer is not None:
            self.costs.delete_purchase_for_item(item.id)
            self.costs.save_purchase(Purchase(item.household_id, item.id, item.name, Decimal(item.price),
                                              item.payer.id, item.added_on))
        elif change == "removed" and abs(item.quantity.amount - item.original_amount) < 1e-9:
            # removed before any of it was used: an undone add or a mistake, so it was never really bought
            self.costs.delete_purchase_for_item(item.id)

    def summarize(self, ctx: RequestContext, month: Optional[str] = None) -> CostSummary:
        """month is 'YYYY-MM'; the current month by default."""
        month = month or self._today().strftime("%Y-%m")
        members = self.members.find_by_household(ctx.household.id)
        ids = [m.id for m in members]
        purchases = sorted((p for p in self.costs.purchases(ctx.household.id)
                            if p.bought_on.strftime("%Y-%m") == month), key=lambda p: p.bought_on)
        payments = [p for p in self.costs.payments(ctx.household.id) if p.paid_on.strftime("%Y-%m") == month]
        paid = {i: Decimal("0.00") for i in ids}
        share = {i: Decimal("0.00") for i in ids}
        for p in purchases:
            if p.payer_id not in paid:
                continue
            paid[p.payer_id] += p.price
            each = (p.price / len(ids)).quantize(CENT, rounding="ROUND_DOWN")
            for i in ids:
                share[i] += each
            share[p.payer_id] += p.price - each * len(ids)  # extra cents go to the payer, so totals match
        balance = {i: paid[i] - share[i] for i in ids}
        for pay in payments:
            if pay.from_id in balance and pay.to_id in balance:
                balance[pay.from_id] += pay.amount
                balance[pay.to_id] -= pay.amount
        return CostSummary(purchases, paid, share, balance, self.settle(balance), payments)

    @staticmethod
    def settle(balance: dict[UUID, Decimal]) -> list[Settlement]:
        """Greedy: the member who owes the most pays the member owed the most, until all are settled."""
        owed = {k: v for k, v in balance.items() if v > 0}
        owes = {k: -v for k, v in balance.items() if v < 0}
        result = []
        while owed and owes:
            creditor = max(owed, key=owed.get)
            debtor = max(owes, key=owes.get)
            amount = min(owed[creditor], owes[debtor])
            result.append(Settlement(debtor, creditor, amount.quantize(CENT)))
            owed[creditor] -= amount
            owes[debtor] -= amount
            if owed[creditor] <= 0:
                del owed[creditor]
            if owes[debtor] <= 0:
                del owes[debtor]
        return result

    def missing_price(self, ctx: RequestContext) -> list[FoodItem]:
        return [i for i in self.items.find_by_household(ctx.household.id)
                if i.is_shared() and (not i.price or i.payer is None)]

    def mark_paid(self, ctx: RequestContext, from_id: UUID, to_id: UUID, amount: Decimal) -> Payment:
        ids = {m.id for m in self.members.find_by_household(ctx.household.id)}
        if from_id not in ids or to_id not in ids or from_id == to_id:
            raise InvalidOperationError("payments are between two different members of your household")
        if ctx.member.id not in (from_id, to_id):
            raise InvalidOperationError("you can only record payments you sent or received")
        if amount <= 0:
            raise ValueError("amount must be positive")
        payment = Payment(ctx.household.id, from_id, to_id, Decimal(amount).quantize(CENT), self._today())
        self.costs.save_payment(payment)
        return payment

    def remove_payment(self, ctx: RequestContext, payment_id: UUID) -> None:
        self.costs.delete_payment(payment_id)
