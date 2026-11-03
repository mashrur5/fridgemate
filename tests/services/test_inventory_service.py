from uuid import uuid4

import pytest

from server.domain.errors import InvalidOperationError, NotFoundError, PermissionDeniedError
from server.domain.model import FoodItem, Location, Quantity
from server.domain.services import ExpiryAlertNotifier, InventoryObserver
from tests.conftest import TODAY


class Recorder(InventoryObserver):
    def __init__(self):
        self.events = []

    def update(self, item, change):
        self.events.append((item.name, change))


def test_observers_hear_every_change(inventory, ctx_alice, make_item):
    rec = Recorder()
    inventory.attach(rec)
    item = inventory.add(ctx_alice, make_item(name="Eggs", amount=12, unit="pcs"))
    inventory.deduct(ctx_alice, item.id, Quantity(2, "pcs"))
    inventory.remove(ctx_alice, item.id)
    assert rec.events == [("Eggs", "added"), ("Eggs", "deducted"), ("Eggs", "removed")]
    inventory.detach(rec)
    inventory.add(ctx_alice, make_item())
    assert len(rec.events) == 3


def test_get_items_hides_roommates_private_items(inventory, ctx_alice, ctx_bob, alice, make_item):
    inventory.add(ctx_alice, make_item(name="Alice yogurt", owner=alice))
    inventory.add(ctx_alice, make_item(name="Shared milk"))
    assert [i.name for i in inventory.get_items(ctx_bob)] == ["Shared milk"]
    assert len(inventory.get_items(ctx_alice)) == 2


def test_cannot_change_someone_elses_item(inventory, ctx_alice, ctx_bob, alice, make_item):
    item = inventory.add(ctx_alice, make_item(owner=alice))
    with pytest.raises(PermissionDeniedError):
        inventory.remove(ctx_bob, item.id)


def test_cannot_add_to_another_household(inventory, ctx_alice, make_item):
    item = make_item()
    item.household_id = uuid4()
    with pytest.raises(PermissionDeniedError):
        inventory.add(ctx_alice, item)


def test_deduct_converts_units_and_removes_empty_items(inventory, ctx_alice, repo, make_item):
    milk = inventory.add(ctx_alice, make_item(name="Milk", amount=1, unit="l"))
    inventory.deduct(ctx_alice, milk.id, Quantity(250, "ml"))
    assert repo.find_by_id(milk.id).quantity == Quantity(0.75, "l")
    inventory.deduct(ctx_alice, milk.id, Quantity(750, "ml"))
    assert repo.find_by_id(milk.id) is None


def test_deduct_rejects_too_much_or_wrong_unit(inventory, ctx_alice, make_item):
    rice = inventory.add(ctx_alice, make_item(name="Rice", amount=500, unit="g"))
    with pytest.raises(InvalidOperationError):
        inventory.deduct(ctx_alice, rice.id, Quantity(1, "kg"))
    with pytest.raises(InvalidOperationError):
        inventory.deduct(ctx_alice, rice.id, Quantity(1, "l"))


def test_unknown_item_is_not_found(inventory, ctx_alice):
    with pytest.raises(NotFoundError):
        inventory.remove(ctx_alice, uuid4())


def test_offer_and_claim_flow(inventory, ctx_alice, ctx_bob, alice, bob, make_item):
    item = inventory.add(ctx_alice, make_item(name="Spinach", days_left=2, owner=alice))
    inventory.mark_offered(ctx_alice, item.id, "use it tonight")
    assert item.id in [i.id for i in inventory.get_items(ctx_bob)]
    assert inventory.claim(ctx_bob, item.id) is True
    assert item.owner == bob and not item.is_offered
    assert inventory.claim(ctx_alice, item.id) is False  # nothing left to claim


def test_only_expiring_items_can_be_offered(inventory, ctx_alice, alice, make_item):
    fresh = inventory.add(ctx_alice, make_item(days_left=10, owner=alice))
    with pytest.raises(InvalidOperationError):
        inventory.mark_offered(ctx_alice, fresh.id)


def test_alerts_sorted_and_private_items_hidden(inventory, ctx_alice, ctx_bob, alice, make_item):
    alerts = ExpiryAlertNotifier(inventory)
    inventory.attach(alerts)
    inventory.add(ctx_alice, make_item(name="Old bread", days_left=-1))
    inventory.add(ctx_alice, make_item(name="Cheese", days_left=3))
    inventory.add(ctx_alice, make_item(name="Berries", days_left=1))
    inventory.add(ctx_alice, make_item(name="Alice tofu", days_left=0, owner=alice))
    inventory.add(ctx_alice, make_item(name="Rice", days_left=200))
    assert [i.name for i in alerts.get_alerts(ctx_alice)] == ["Alice tofu", "Berries", "Cheese", "Old bread"]
    assert [i.name for i in alerts.get_alerts(ctx_bob)] == ["Berries", "Cheese", "Old bread"]
    assert alerts.changes_seen == 5
