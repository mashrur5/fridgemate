import threading
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from server.domain.model import (
    Household, MealPlan, Member, Notification, Payment, Purchase, Quantity, ShoppingListItem,
)
from server.domain.services import InventoryService
from server.infrastructure.persistence.sqlite import (
    Database, SqliteAccountRepository, SqliteCostRepository, SqliteHouseholdRepository, SqliteItemRepository,
    SqliteMealPlanRepository, SqliteMemberRepository, SqliteNotificationRepository, SqliteShoppingListRepository,
)
from server.application.request_context import RequestContext
from tests.conftest import TODAY


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def setup(db, household, alice, bob):
    homes, people = SqliteHouseholdRepository(db), SqliteMemberRepository(db)
    homes.save(household)
    for m in (alice, bob):
        m.household_id = household.id
        people.save(m)
    return people, SqliteItemRepository(db, people)


def test_members_households_and_accounts_round_trip(db, setup, household, alice):
    people, _ = setup
    alice.dietary_restrictions = ["vegan"]
    people.save(alice)
    loaded = people.find_by_account("alice")
    assert loaded.id == alice.id and loaded.dietary_restrictions == ["vegan"] and loaded.household_id == household.id
    assert SqliteHouseholdRepository(db).find_by_invite_code("fridge42").id == household.id
    acc = SqliteAccountRepository(db)
    acc.save_credentials("alice", "h", "s")
    acc.save_session("tok", "alice", datetime(2026, 11, 10))
    assert acc.find_credentials("alice") == ("h", "s") and acc.find_session("tok")[0] == "alice"
    acc.delete_session("tok")
    assert acc.find_session("tok") is None


def test_items_round_trip_and_service_works_on_sqlite(setup, household, alice, make_item):
    _, items = setup
    inv = InventoryService(items, today=lambda: TODAY)
    ctx = RequestContext(alice, household)
    item = make_item("Milk", 2, "l", owner=alice)
    item.price, item.payer = Decimal("4.99"), alice
    inv.add(ctx, item)
    loaded = items.find_by_id(item.id)
    assert loaded.owner.id == alice.id and loaded.price == Decimal("4.99") and loaded.quantity == Quantity(2, "l")
    inv.deduct(ctx, item.id, Quantity(500, "ml"))
    assert items.find_by_id(item.id).quantity.amount == 1.5 and items.find_by_id(item.id).original_amount == 2


def test_claim_is_atomic(setup, household, alice, bob, make_item):
    _, items = setup
    item = make_item("Spinach", 1, "pcs", days_left=1, owner=alice)
    item.is_offered, item.offered_by = True, alice
    items.save(item)
    wins = []
    threads = [threading.Thread(target=lambda: wins.append(items.claim_if_unclaimed(item.id, bob))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert wins.count(True) == 1
    assert items.find_by_id(item.id).owner.id == bob.id


def test_other_repositories_round_trip(db, household, alice):
    shop = SqliteShoppingListRepository(db)
    line = ShoppingListItem(household.id, "Flour", Quantity(1, "kg"), "Pantry", ["low"], alice.id)
    shop.save(line)
    assert shop.find_by_household(household.id)[0].quantity == Quantity(1, "kg")
    costs = SqliteCostRepository(db)
    costs.save_purchase(Purchase(household.id, line.id, "Flour", Decimal("3.50"), alice.id, TODAY))
    costs.save_payment(Payment(household.id, alice.id, alice.id, Decimal("1.00"), TODAY))
    assert costs.purchases(household.id)[0].price == Decimal("3.50") and len(costs.payments(household.id)) == 1
    notes = SqliteNotificationRepository(db)
    notes.save(Notification(alice.id, "hi", line.id, "offer"))
    assert notes.find_by_member(alice.id)[0].message == "hi"
    notes.delete_for_item(line.id)
    assert notes.find_by_member(alice.id) == []
    plans = SqliteMealPlanRepository(db)
    plans.save(MealPlan(alice.id, household.id, TODAY, 3, notes=["x"]))
    assert plans.latest_for_member(alice.id).notes == ["x"]
