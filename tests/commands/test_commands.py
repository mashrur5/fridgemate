import copy

from server.domain.commands import (
    AddItemCommand, ClaimItemCommand, CommandHistory, OfferItemCommand, RemoveItemCommand, UpdateItemCommand,
)
from server.domain.model import Quantity


def test_add_then_undo_removes_item(inventory, ctx_alice, repo, make_item):
    history = CommandHistory()
    item = make_item(name="Eggs")
    history.run(ctx_alice, AddItemCommand(inventory, ctx_alice, item))
    assert repo.find_by_id(item.id) is not None
    assert history.undo_last(ctx_alice) is True
    assert repo.find_by_id(item.id) is None


def test_remove_then_undo_restores_item(inventory, ctx_alice, repo, make_item):
    history = CommandHistory()
    item = inventory.add(ctx_alice, make_item(name="Cheese"))
    history.run(ctx_alice, RemoveItemCommand(inventory, ctx_alice, item.id))
    assert repo.find_by_id(item.id) is None
    history.undo_last(ctx_alice)
    assert repo.find_by_id(item.id).name == "Cheese"


def test_update_then_undo_restores_old_values(inventory, ctx_alice, repo, make_item):
    history = CommandHistory()
    item = inventory.add(ctx_alice, make_item(name="Milk", amount=1))
    edited = copy.copy(item)
    edited.quantity = Quantity(0.5, "l")
    history.run(ctx_alice, UpdateItemCommand(inventory, ctx_alice, edited))
    assert repo.find_by_id(item.id).quantity == Quantity(0.5, "l")
    history.undo_last(ctx_alice)
    assert repo.find_by_id(item.id).quantity == Quantity(1, "l")


def test_undo_stacks_are_per_member(inventory, ctx_alice, ctx_bob, make_item):
    history = CommandHistory()
    history.run(ctx_alice, AddItemCommand(inventory, ctx_alice, make_item()))
    assert history.undo_last(ctx_bob) is False
    assert history.last_description(ctx_alice) == "add Milk"
    assert history.undo_last(ctx_alice) is True
    assert history.undo_last(ctx_alice) is False


def test_offer_undo_withdraws_offer(inventory, ctx_alice, alice, make_item):
    history = CommandHistory()
    item = inventory.add(ctx_alice, make_item(name="Spinach", days_left=1, owner=alice))
    history.run(ctx_alice, OfferItemCommand(inventory, ctx_alice, item.id, "free"))
    assert item.is_offered
    history.undo_last(ctx_alice)
    assert not item.is_offered


def test_claim_is_final_and_not_in_history(inventory, ctx_alice, ctx_bob, alice, bob, make_item):
    history = CommandHistory()
    item = inventory.add(ctx_alice, make_item(days_left=1, owner=alice))
    inventory.mark_offered(ctx_alice, item.id)
    claim = ClaimItemCommand(inventory, ctx_bob, item.id)
    history.run(ctx_bob, claim)
    assert claim.succeeded and item.owner == bob
    assert history.undo_last(ctx_bob) is False
