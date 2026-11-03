from datetime import timedelta

from server.domain.model import Location
from server.domain.services import (
    ExpiryEstimator, ExpiryService, PlacementService, PlacementStrategy,
    RuleBasedExpiryEstimator, RuleBasedPlacementStrategy,
)
from tests.conftest import TODAY


class BrokenPlacement(PlacementStrategy):
    """Stands in for the LLM strategy when Gemini is down."""
    def choose_location(self, item_name):
        raise TimeoutError("LLM unavailable")


class FixedPlacement(PlacementStrategy):
    def choose_location(self, item_name):
        return Location.FREEZER, "the model said so"


class BrokenEstimator(ExpiryEstimator):
    def estimate_days(self, item_name, location):
        raise ValueError("unparseable answer")


class NegativeEstimator(ExpiryEstimator):
    def estimate_days(self, item_name, location):
        return -3


def test_rule_based_placement_uses_keywords():
    rules = RuleBasedPlacementStrategy()
    assert rules.choose_location("2% Milk")[0] is Location.FRIDGE
    assert rules.choose_location("Basmati rice")[0] is Location.PANTRY
    assert rules.choose_location("Vanilla ice cream")[0] is Location.FREEZER
    assert rules.choose_location("Mystery sauce")[0] is Location.FRIDGE  # safe default


def test_placement_service_prefers_primary():
    service = PlacementService(FixedPlacement(), RuleBasedPlacementStrategy())
    assert service.suggest_location("Milk") == (Location.FREEZER, "the model said so")


def test_placement_service_falls_back_when_primary_fails():
    service = PlacementService(BrokenPlacement(), RuleBasedPlacementStrategy())
    location, reason = service.suggest_location("Spinach")
    assert location is Location.FRIDGE and "greens" in reason


def test_rule_based_expiry_depends_on_location():
    rules = RuleBasedExpiryEstimator()
    assert rules.estimate_days("Milk", Location.FRIDGE) == 7
    assert rules.estimate_days("Milk", Location.FREEZER) == 90
    assert rules.estimate_days("Chicken thighs", Location.PANTRY) == 1  # never 0
    assert rules.estimate_days("Unknown thing", Location.PANTRY) == 30


def test_expiry_service_falls_back_on_error_or_bad_value():
    for primary in (BrokenEstimator(), NegativeEstimator()):
        service = ExpiryService(primary, RuleBasedExpiryEstimator())
        assert service.estimate_expiry("Milk", Location.FRIDGE, TODAY) == TODAY + timedelta(days=7)
