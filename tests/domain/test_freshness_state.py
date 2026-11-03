from datetime import timedelta

import pytest

from server.domain.model import ExpiredState, ExpiringSoonState, FreshState
from tests.conftest import TODAY


@pytest.mark.parametrize("days_left, state", [
    (10, FreshState), (4, FreshState),
    (3, ExpiringSoonState), (0, ExpiringSoonState),
    (-1, ExpiredState),
])
def test_state_chosen_from_days_left(make_item, days_left, state):
    item = make_item(days_left=days_left)
    item.refresh_state(TODAY)
    assert isinstance(item.state, state)


def test_fresh_item_behaviour(make_item):
    item = make_item(days_left=10)
    assert item.can_use_in_recipe() and not item.can_offer()
    assert item.alert_priority() == 0 and item.freshness_label() == "Fresh"


def test_expiring_item_can_be_offered_and_cooked(make_item):
    item = make_item(days_left=2)
    assert item.can_offer() and item.can_use_in_recipe()
    assert item.alert_priority() == 1


def test_expired_item_is_blocked(make_item):
    item = make_item(days_left=-2)
    assert not item.can_use_in_recipe() and not item.can_offer()
    assert item.alert_priority() == 2


def test_state_changes_as_time_passes(make_item):
    item = make_item(days_left=5)
    assert isinstance(item.state, FreshState)
    item.refresh_state(TODAY + timedelta(days=3))
    assert isinstance(item.state, ExpiringSoonState)
    item.refresh_state(TODAY + timedelta(days=6))
    assert isinstance(item.state, ExpiredState)
