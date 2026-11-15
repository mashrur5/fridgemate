from datetime import timedelta

import pytest

from server.domain.model import Quantity, Recipe, RecipeIngredient
from server.domain.services.stock_validator import StockValidator, names_match
from server.domain.services.unit_converter import UnitConverter
from tests.conftest import TODAY


@pytest.fixture
def conv():
    return UnitConverter()


@pytest.mark.parametrize("raw,amount,unit", [
    ("200g", 200, "g"), ("1 1/2 cups", 1.5, "cup"), ("1/2 tsp", 0.5, "tsp"), ("2 cloves", 2, "pcs"),
    ("3", 3, "pcs"), ("1 kg", 1, "kg"), ("½ cup", 0.5, "cup"), ("2 large", 2, "pcs"), ("2 eggs", 2, "pcs"),
])
def test_parse_measure(conv, raw, amount, unit):
    q = conv.parse_measure(raw)
    assert q.unit == unit and q.amount == pytest.approx(amount)


@pytest.mark.parametrize("raw", ["a pinch", "to taste", "", "Dash"])
def test_unmeasurable_amounts(conv, raw):
    assert conv.parse_measure(raw) is None


def test_convert_same_kind_and_ingredient_specific(conv):
    assert conv.convert(Quantity(1, "cup"), "ml").amount == pytest.approx(240)
    assert conv.convert(Quantity(2, "pcs"), "g", "egg").amount == pytest.approx(100)
    assert conv.convert(Quantity(100, "ml"), "g", "milk").amount == pytest.approx(103)
    assert conv.convert(Quantity(2, "pcs"), "g", "mystery") is None
    assert conv.convert(Quantity(1, "pcs"), "g", "spinach").amount == 250  # "1 bunch spinach"


def test_names_match():
    assert names_match("chicken breast", "Chicken")
    assert names_match("Eggs", "egg")
    assert names_match("scallions", "green onion")
    assert not names_match("salt", "salted butter")


def recipe(*lines):
    return Recipe(name="Test", ingredients=[RecipeIngredient(n, q) for n, q in lines])


def test_have_short_missing(make_item):
    milk = make_item("Milk", 1, "l")
    eggs = make_item("Eggs", 2, "pcs", days_left=2)
    for i in (milk, eggs):
        i.refresh_state(TODAY)
    r = recipe(("milk", Quantity(250, "ml")), ("eggs", Quantity(3, "pcs")), ("flour", Quantity(100, "g")),
               ("salt", None), ("butter", None))
    res = StockValidator().check(r, [milk, eggs])
    statuses = {c.ingredient.name: c.status for c in res.checks}
    assert statuses == {"milk": "have", "eggs": "short", "flour": "missing", "salt": "have", "butter": "missing"}
    assert res.allocations["milk"][0].amount.amount == pytest.approx(0.25)


def test_expired_items_are_never_used(make_item):
    old = make_item("Milk", 1, "l", days_left=-1)
    old.refresh_state(TODAY)
    res = StockValidator().check(recipe(("milk", Quantity(100, "ml"))), [old])
    assert res.checks[0].status == "missing"


def test_shared_available_map_prevents_double_counting(make_item):
    eggs = make_item("Eggs", 3, "pcs")
    eggs.refresh_state(TODAY)
    left = {}
    v = StockValidator()
    assert v.check(recipe(("egg", Quantity(2, "pcs"))), [eggs], available=left).checks[0].status == "have"
    assert v.check(recipe(("egg", Quantity(2, "pcs"))), [eggs], available=left).checks[0].status == "short"
