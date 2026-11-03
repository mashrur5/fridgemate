import pytest

from server.domain.model import Member, Quantity


def test_quantity_converts_within_same_kind():
    assert Quantity(1.5, "kg").to("g") == Quantity(1500, "g")
    assert Quantity(250, "ml").to("l") == Quantity(0.25, "l")


def test_quantity_refuses_mixed_kinds():
    with pytest.raises(ValueError):
        Quantity(200, "g").to("ml")
    assert not Quantity(200, "g").can_convert("pcs")


def test_quantity_rejects_bad_input():
    with pytest.raises(ValueError):
        Quantity(1, "cups")
    with pytest.raises(ValueError):
        Quantity(-1, "g")


def test_member_allows_respects_restrictions_and_dislikes():
    m = Member(auth0_id="a", name="A", email="a@x.com",
               dietary_restrictions=["pork"], disliked_ingredients=["Cilantro"])
    assert not m.allows("pork belly")
    assert not m.allows("fresh cilantro")
    assert m.allows("chicken")


def test_new_item_remembers_original_amount(make_item):
    item = make_item(amount=2)
    assert item.original_amount == 2


def test_item_rejects_empty_name_and_zero_quantity(make_item):
    with pytest.raises(ValueError):
        make_item(name="  ")
    with pytest.raises(ValueError):
        make_item(amount=0)


def test_shared_and_private_visibility(make_item, alice, bob):
    shared = make_item()
    private = make_item(owner=alice)
    assert shared.is_shared() and shared.visible_to(bob)
    assert private.visible_to(alice) and not private.visible_to(bob)


def test_is_low_at_a_quarter_left(make_item):
    item = make_item(amount=4, unit="pcs")
    item.quantity = Quantity(1, "pcs")
    assert item.is_low()
    item.quantity = Quantity(2, "pcs")
    assert not item.is_low()
