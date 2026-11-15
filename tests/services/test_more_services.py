from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from server.application.request_context import RequestContext
from server.domain.commands import AddItemCommand, CommandHistory, CookRecipeCommand, OfferItemCommand
from server.domain.errors import InvalidOperationError, NotFoundError
from server.domain.model import Location, Member, Quantity, Recipe, RecipeIngredient
from server.domain.services.account_service import AccountService, AuthError
from server.domain.services.cooking_service import CookingService, Leftovers
from server.domain.services.cost_split_service import CostSplitService
from server.domain.services.expiry import ExpiryService, RuleBasedExpiryEstimator
from server.domain.services.household_service import HouseholdService, member_allows
from server.domain.services.notification_service import HouseholdNotifier, NotificationService
from server.domain.services.shopping_list_service import ShoppingListService
from server.domain.services.stock_validator import StockValidator
from server.infrastructure.persistence import (
    InMemoryAccountRepository, InMemoryCostRepository, InMemoryHouseholdRepository, InMemoryMemberRepository,
    InMemoryNotificationRepository, InMemoryShoppingListRepository,
)
from tests.conftest import TODAY


@pytest.fixture
def members(alice, bob, household):
    repo = InMemoryMemberRepository()
    for m in (alice, bob):
        m.household_id = household.id
        repo.save(m)
    return repo


# --- F06 household ---

def test_create_and_join_household():
    homes, people = InMemoryHouseholdRepository(), InMemoryMemberRepository()
    svc = HouseholdService(homes, people)
    a, b = Member("a", "A", "a@x.com"), Member("b", "B", "b@x.com")
    home = svc.create_household(a, "Apt 1")
    assert len(home.invite_code) == 10 and a.household_id == home.id
    assert svc.join_household(b, home.invite_code.lower()).id == home.id
    with pytest.raises(InvalidOperationError):
        svc.join_household(b, home.invite_code)
    with pytest.raises(NotFoundError):
        svc.join_household(Member("c", "C", "c@x.com"), "WRONGCODE1")
    assert [m.name for m in svc.get_members(RequestContext(a, home))] == ["A", "B"]


def test_preferences_filter_ingredients(alice):
    svc = HouseholdService(InMemoryHouseholdRepository(), InMemoryMemberRepository())
    svc.update_preferences(alice, ["Vegetarian"], ["Mushroom "])
    assert not member_allows(alice, "chicken breast")
    assert not member_allows(alice, "button mushrooms")
    assert member_allows(alice, "rice")
    with pytest.raises(ValueError):
        svc.update_preferences(alice, ["keto"], [])


# --- UC16 accounts ---

def test_register_login_and_sessions():
    now = [datetime(2026, 11, 3, 12)]
    svc = AccountService(InMemoryAccountRepository(), InMemoryMemberRepository(), InMemoryHouseholdRepository(),
                         now=lambda: now[0])
    member = svc.register("Sam@Example.com", "password123", "Sam")
    with pytest.raises(InvalidOperationError):
        svc.register("sam@example.com", "password123", "Sam")
    with pytest.raises(ValueError):
        svc.register("x@y.com", "short", "X")
    with pytest.raises(AuthError):
        svc.login("sam@example.com", "wrong-password")
    token = svc.login("sam@example.com", "password123")
    assert svc.load_context(token)[0].id == member.id
    svc.change_password(member, "password123", "newpassword1")
    assert svc.login("sam@example.com", "newpassword1")
    now[0] += timedelta(days=8)
    with pytest.raises(AuthError):
        svc.load_context(token)


# --- F15 notifications ---

def test_offer_and_claim_notify_the_right_people(inventory, ctx_alice, ctx_bob, alice, bob, members, make_item):
    notes = NotificationService(InMemoryNotificationRepository())
    inventory.attach(HouseholdNotifier(notes, members, today=lambda: TODAY))
    item = inventory.add(ctx_alice, make_item("Spinach", 200, "g", days_left=2, owner=alice))
    inventory.mark_offered(ctx_alice, item.id)
    assert "Alice is offering Spinach (expires in 2 days)" in notes.get_for(bob)[0].message
    assert notes.get_for(alice) == []
    assert inventory.claim(ctx_bob, item.id)
    assert notes.get_for(alice)[0].message == "Bob claimed your Spinach."
    assert notes.get_for(bob) == []  # the offer notification is closed after the claim


# --- F11 shopping list ---

def test_low_items_are_added_and_merged(inventory, ctx_alice, ctx_bob, alice, make_item):
    shopping = ShoppingListService(InMemoryShoppingListRepository())
    inventory.attach(shopping)
    flour = inventory.add(ctx_alice, make_item("Flour", 1, "kg", days_left=100))  # Shared
    inventory.deduct(ctx_alice, flour.id, Quantity(800, "g"))
    lines = shopping.get_list(ctx_bob).items
    assert len(lines) == 1 and lines[0].reasons == ["running low"] and lines[0].section == "Pantry"
    shopping.add_item(ctx_alice, "flour", Quantity(200, "g"), "for Pancakes", shared=True)
    line = shopping.get_list(ctx_alice).items[0]
    assert line.quantity == Quantity(1.2, "kg") and line.reasons == ["running low", "for Pancakes"]
    shopping.add_item(ctx_alice, "Flour", Quantity(2, "pcs"), shared=True)  # can't merge units
    assert len(shopping.get_list(ctx_alice).items) == 2
    mine = shopping.add_item(ctx_alice, "Eggs", Quantity(6, "pcs"))
    assert mine not in shopping.get_list(ctx_bob).items
    shopping.set_checked(ctx_alice, mine.id, True)
    assert shopping.clear_checked(ctx_alice) == 1


# --- F14 cost split ---

def test_cost_split_rounding_and_settlements(inventory, ctx_alice, ctx_bob, alice, bob, repo, members, make_item):
    costs = CostSplitService(InMemoryCostRepository(), members, repo, today=lambda: TODAY)
    inventory.attach(costs)
    a = make_item("Rice", 1, "kg")
    a.price, a.payer = Decimal("10.01"), alice
    inventory.add(ctx_alice, a)
    private = make_item("Chocolate", 1, "pcs", owner=bob)
    private.price, private.payer = Decimal("5"), bob
    inventory.add(ctx_bob, private)  # not Shared, so not split
    s = costs.summarize(ctx_alice)
    assert s.share[alice.id] == Decimal("5.01") and s.share[bob.id] == Decimal("5.00")
    assert s.balance[bob.id] == Decimal("-5.00")
    assert [(x.from_id, x.to_id, x.amount) for x in s.settlements] == [(bob.id, alice.id, Decimal("5.00"))]
    costs.mark_paid(ctx_bob, bob.id, alice.id, Decimal("5.00"))
    assert costs.summarize(ctx_alice).settlements == []
    with pytest.raises(InvalidOperationError):
        costs.mark_paid(ctx_alice, alice.id, alice.id, Decimal("1"))


def test_settle_uses_few_payments():
    from uuid import uuid4
    a, b, c = uuid4(), uuid4(), uuid4()
    result = CostSplitService.settle({a: Decimal("20"), b: Decimal("-15"), c: Decimal("-5")})
    assert {(r.from_id, r.to_id, r.amount) for r in result} == {(b, a, Decimal("15.00")), (c, a, Decimal("5.00"))}


# --- F09 cooking ---

def test_cook_deducts_adds_leftovers_and_undo_restores(inventory, ctx_alice, alice, make_item):
    cooking = CookingService(inventory, StockValidator(),
                             ExpiryService(RuleBasedExpiryEstimator(), RuleBasedExpiryEstimator()), today=lambda: TODAY)
    eggs = inventory.add(ctx_alice, make_item("Eggs", 3, "pcs", owner=alice))
    milk = inventory.add(ctx_alice, make_item("Milk", 1, "l"))
    recipe = Recipe("Omelette", [RecipeIngredient("egg", Quantity(3, "pcs")), RecipeIngredient("milk", Quantity(1, "cup"))])
    result, usages = cooking.preview(ctx_alice, recipe)
    assert all(c.status == "have" for c in result.checks)
    history = CommandHistory()
    history.run(ctx_alice, CookRecipeCommand(inventory, cooking, ctx_alice, recipe.name, usages, Leftovers(2)))
    names = {i.name: i for i in inventory.get_items(ctx_alice)}
    assert "Eggs" not in names and names["Milk"].quantity.amount == pytest.approx(0.76)
    assert names["Leftover Omelette"].expiry_date == TODAY + timedelta(days=4)
    assert history.undo_last(ctx_alice)
    names = {i.name: i for i in inventory.get_items(ctx_alice)}
    assert set(names) == {"Eggs", "Milk"} and names["Milk"].quantity.amount == 1


def test_cook_refuses_when_stock_changed(inventory, ctx_alice, make_item):
    cooking = CookingService(inventory, StockValidator(),
                             ExpiryService(RuleBasedExpiryEstimator(), RuleBasedExpiryEstimator()), today=lambda: TODAY)
    eggs = inventory.add(ctx_alice, make_item("Eggs", 2, "pcs"))
    from server.domain.services.cooking_service import Usage
    with pytest.raises(InvalidOperationError):
        CookRecipeCommand(inventory, cooking, ctx_alice, "x", [Usage(eggs.id, Quantity(3, "pcs"))]).execute()
    assert inventory.get_item(ctx_alice, eggs.id).quantity.amount == 2
