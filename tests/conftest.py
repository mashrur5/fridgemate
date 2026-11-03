from datetime import date, timedelta
from uuid import uuid4

import pytest

from server.domain.model import FoodItem, Household, Location, Member, Quantity

TODAY = date(2026, 11, 3)


@pytest.fixture
def household():
    return Household(name="Apt 4B", invite_code="FRIDGE42")


@pytest.fixture
def alice():
    return Member(auth0_id="auth0|alice", name="Alice", email="alice@example.com")


@pytest.fixture
def bob():
    return Member(auth0_id="auth0|bob", name="Bob", email="bob@example.com")


@pytest.fixture
def make_item(household):
    def _make(name="Milk", amount=1.0, unit="l", days_left=7, owner=None, location=Location.FRIDGE):
        return FoodItem(
            name=name,
            quantity=Quantity(amount, unit),
            location=location,
            household_id=household.id,
            expiry_date=TODAY + timedelta(days=days_left),
            added_on=TODAY,
            owner=owner,
        )
    return _make


@pytest.fixture
def repo():
    from server.infrastructure.persistence import InMemoryItemRepository
    return InMemoryItemRepository()


@pytest.fixture
def inventory(repo):
    from server.domain.services import InventoryService
    return InventoryService(repo, today=lambda: TODAY)


@pytest.fixture
def ctx_alice(alice, household):
    from server.application.request_context import RequestContext
    return RequestContext(member=alice, household=household)


@pytest.fixture
def ctx_bob(bob, household):
    from server.application.request_context import RequestContext
    return RequestContext(member=bob, household=household)
