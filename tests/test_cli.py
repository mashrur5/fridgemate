"""CLI tests: typer's CliRunner drives the real commands against the API through TestClient."""
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

import cli.main as cli_main
from cli.client import FridgemateClient
from cli.token_store import TokenStore
from server.api.app import create_app
from server.application.container import build_facade
from server.config import Config
from tests.conftest import TODAY
from tests.fakes import FakeLLMClient, FakeRecipeSource, recipe

runner = CliRunner()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    llm = FakeLLMClient([])
    facade = build_facade(Config(), llm=llm, recipes=FakeRecipeSource(
        [recipe("1", "Spinach Omelette", "French", ("spinach", 100, "g"), ("egg", 2, "pcs"))]),
        in_memory=True, today=lambda: TODAY)
    http = TestClient(create_app(facade, Config()))

    def as_user(name):
        monkeypatch.setattr(cli_main, "client", FridgemateClient("http://testserver", TokenStore(tmp_path / name / "t.json"), http))
        return lambda *args, input=None: runner.invoke(cli_main.app, list(args), input=input)

    return as_user, llm


def test_cli_flow(setup):
    as_user, llm = setup
    alice = as_user("alice")
    assert "Welcome, Alice" in alice("register", "--email", "a@x.com", "--name", "Alice", "--password", "password123").output
    out = alice("household", "create", "Apt").output
    code = out.split("Invite code: ")[1].strip()
    assert "Added Spinach" in alice("items", "add", "Spinach", "200", "g", "--location", "fridge",
                                    "--expiry", "2026-11-04").output
    assert "rule table" in alice("items", "add", "Eggs", "6", "pcs").output
    assert "Spinach" in alice("alerts").output
    llm.replies += [{"tool": "propose_inventory_change", "args": {"op": "add", "name": "Milk", "amount": 1, "unit": "l"}},
                    {"final": {"reply": "Adding milk.", "question": None}}]
    out = alice("do", "bought milk", input="y\n").output
    assert "Add 1 l Milk" in out and "done" in out
    llm.replies += [{"final": {"recipes": [{"recipe_id": "1", "estimated_minutes": 10, "reason": "spinach"}]}}]
    assert "Spinach Omelette" in alice("recipes", "suggest").output
    out = alice("cook", "1", input="y\n").output
    assert "Cooked Spinach Omelette" in out
    assert "Undid: cook Spinach Omelette" in alice("undo").output
    bob = as_user("bob")
    bob("register", "--email", "b@x.com", "--name", "Bob", "--password", "password123")
    assert "Joined Apt" in bob("household", "join", code).output
    alice = as_user("alice")
    assert "Offered Spinach" in alice("offer", "spinach", "--note", "half a bag").output
    bob = as_user("bob")
    assert '"half a bag"' in bob("notifications").output
    assert "You claimed Spinach" in bob("claim", "spinach").output
    r = bob("claim", "spinach")
    assert r.exit_code == 1 and "already claimed" in r.output


def test_cli_errors(setup):
    as_user, _ = setup
    u = as_user("x")
    r = u("items", "list")
    assert r.exit_code == 1 and "not logged in" in r.output
    u("register", "--email", "x@x.com", "--name", "X", "--password", "password123")
    assert "create or join a household" in u("items", "list").output
    assert "no household was found" in u("household", "join", "NOPE000000").output
