"""End-to-end API tests: TestClient -> routers -> facade -> services/agents, with a fake LLM."""
import pytest
from fastapi.testclient import TestClient

from server.api.app import create_app
from server.application.container import build_facade
from server.config import Config
from tests.conftest import TODAY
from tests.fakes import FakeLLMClient, FakeRecipeSource, recipe

RECIPES = [recipe("1", "Spinach Omelette", "French", ("spinach", 100, "g"), ("egg", 2, "pcs"))]


@pytest.fixture
def llm():
    return FakeLLMClient([])


@pytest.fixture
def client(llm):
    facade = build_facade(Config(), llm=llm, recipes=FakeRecipeSource(RECIPES), in_memory=True, today=lambda: TODAY)
    return TestClient(create_app(facade, Config()))


def signup(client, email, name):
    r = client.post("/api/account/register", json={"email": email, "password": "password123", "name": name})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def two(client):
    a = signup(client, "alice@x.com", "Alice")
    home = client.post("/api/household", json={"name": "Apt 4B"}, headers=a).json()
    b = signup(client, "bob@x.com", "Bob")
    assert client.post("/api/household/join", json={"invite_code": home["invite_code"]}, headers=b).status_code == 200
    return a, b, home


def test_auth_errors(client):
    assert client.get("/api/items").status_code == 401
    assert client.get("/api/items", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/account/login", json={"email": "x@x.com", "password": "wrongpass1"}).status_code == 401
    h = signup(client, "c@x.com", "C")
    assert client.get("/api/items", headers=h).status_code == 409  # no household yet
    assert client.post("/api/household/join", json={"invite_code": "BADCODE123"}, headers=h).status_code == 404
    client.post("/api/account/logout", headers=h)
    assert client.get("/api/account/me", headers=h).status_code == 401


def test_add_item_with_ai_fallback_alerts_and_undo(client, two, llm):
    a, b, _ = two
    # F02/F04: the AI is out of scripted replies, so the rule tables answer
    r = client.post("/api/items", json={"name": "Milk", "amount": 1, "unit": "l"}, headers=a)
    assert r.status_code == 201 and r.json()["item"]["location"] == "fridge"
    assert "rule table" in r.json()["location_note"] and r.json()["item"]["expiry_estimated"]
    client.post("/api/items", json={"name": "Spinach", "amount": 200, "unit": "g", "location": "fridge",
                                    "expiry_date": "2026-11-04"}, headers=a)
    alerts = client.get("/api/items/alerts", headers=a).json()
    assert alerts["banner"] == "1 item expires in the next 3 days" or alerts["banner"].startswith("1 item")
    assert [i["name"] for i in client.get("/api/items", headers=b).json()["items"]] == []  # private to Alice
    assert client.post("/api/items", json={"name": "", "amount": 1, "unit": "l"}, headers=a).status_code == 422
    assert client.post("/api/items", json={"name": "X", "amount": 1, "unit": "bucket"}, headers=a).status_code == 400
    assert client.post("/api/items/undo", headers=a).json()["undone"] == "add Spinach"
    assert len(client.get("/api/items", headers=a).json()["items"]) == 1


def test_offer_claim_notifications_and_costs(client, two):
    a, b, home = two
    me = client.get("/api/account/me", headers=a).json()
    alice_id = me["member"]["id"]
    spinach = client.post("/api/items", json={"name": "Spinach", "amount": 1, "unit": "pcs", "location": "fridge",
                                              "expiry_date": "2026-11-05"}, headers=a).json()["item"]
    assert client.post(f"/api/items/{spinach['id']}/offer", json={}, headers=a).status_code == 200
    notes = client.get("/api/notifications", headers=b).json()
    assert notes["unread"] == 1 and "Alice is offering Spinach" in notes["notifications"][0]["message"]
    assert client.post(f"/api/items/{spinach['id']}/claim", headers=b).json()["owner"] == "You"
    r = client.post(f"/api/items/{spinach['id']}/claim", headers=b)
    assert r.status_code == 409 and "already claimed" in r.json()["detail"]
    assert "Bob claimed your Spinach" in client.get("/api/notifications", headers=a).json()["notifications"][0]["message"]
    client.post("/api/items", json={"name": "Rice", "amount": 1, "unit": "kg", "location": "pantry", "owner": "shared",
                                    "price": "12.00", "payer_id": alice_id}, headers=a)
    costs = client.get("/api/costs", headers=b).json()
    assert costs["settlements"][0]["from"] == "Bob" and costs["settlements"][0]["amount"] == "6.00"


def test_recipe_suggest_cook_and_undo(client, two, llm):
    a, _, _ = two
    for body in ({"name": "Spinach", "amount": 200, "unit": "g", "location": "fridge", "expiry_date": "2026-11-04"},
                 {"name": "Eggs", "amount": 6, "unit": "pcs", "location": "fridge", "expiry_date": "2026-11-20"}):
        client.post("/api/items", json=body, headers=a)
    llm.replies += [{"tool": "search_recipes", "args": {"ingredient": "spinach"}},
                    {"final": {"recipes": [{"recipe_id": "1", "estimated_minutes": 15, "weight": "light",
                                            "reason": "spinach expires tomorrow"}]}}]
    r = client.post("/api/recipes/suggest", json={"servings": 2}, headers=a).json()
    assert r["suggestions"][0]["recipe"]["name"] == "Spinach Omelette" and r["suggestions"][0]["expiring_used"] == 1
    assert r["trace"]["steps"][1]["tool"] == "search_recipes"
    preview = client.get("/api/recipes/1/cook?servings=2", headers=a).json()
    assert len(preview["usages"]) == 2
    cooked = client.post("/api/recipes/1/cook", json={"usages": preview["usages"], "leftover_portions": 1}, headers=a)
    assert cooked.status_code == 200
    names = {i["name"]: i for i in client.get("/api/items", headers=a).json()["items"]}
    assert names["Spinach"]["quantity"]["amount"] == 100 and "Leftover Spinach Omelette" in names
    client.post("/api/items/undo", headers=a)
    names = {i["name"]: i for i in client.get("/api/items", headers=a).json()["items"]}
    assert names["Spinach"]["quantity"]["amount"] == 200 and "Leftover Spinach Omelette" not in names


def test_ai_unavailable_gives_503(client, two):
    a, _, _ = two
    client.post("/api/items", json={"name": "Eggs", "amount": 6, "unit": "pcs", "location": "fridge"}, headers=a)
    r = client.post("/api/recipes/suggest", json={}, headers=a)
    assert r.status_code == 503


def test_fridge_command_confirm_and_shopping(client, two, llm):
    a, _, _ = two
    llm.replies += [{"tool": "propose_inventory_change", "args": {"op": "add", "name": "Eggs", "amount": 12, "unit": "pcs",
                                                                  "location": "fridge"}},
                    {"final": {"reply": "Adding 12 eggs.", "question": None}}]
    r = client.post("/api/command", json={"message": "add a dozen eggs"}, headers=a).json()
    assert r["proposal"]["changes"] == ["Add 12 pcs Eggs to the fridge"]
    assert client.get("/api/items", headers=a).json()["items"] == []  # nothing changes before confirm (G4)
    done = client.post(f"/api/command/{r['proposal']['id']}/confirm", headers=a).json()["done"]
    assert done == ["Add 12 pcs Eggs to the fridge"]
    eggs = client.get("/api/items", headers=a).json()["items"][0]
    client.patch(f"/api/items/{eggs['id']}", json={"amount": 2}, headers=a)  # 2 of 12 left -> low
    lst = client.get("/api/shopping", headers=a).json()
    assert lst["sections"]["Dairy and eggs"][0]["reasons"] == ["running low"]
    client.patch(f"/api/items/{eggs['id']}", json={"amount": 1}, headers=a)  # still low: not added twice
    assert client.get("/api/shopping", headers=a).json()["count"] == 1


def test_receipt_parse_and_save(client, two, llm):
    a, b, home = two
    llm.replies += [{"items": [{"name": "Milk", "amount": 2, "unit": "l", "price": 5.49, "food": True},
                               {"name": "Bag", "price": 0.1, "food": False}]}]
    drafts = client.post("/api/receipts/parse-text", json={"text": "MLK 2L 5.49\nBAG 0.10"}, headers=a).json()["items"]
    assert [d["name"] for d in drafts] == ["Milk"] and drafts[0]["price"] == "5.49"
    alice_id = client.get("/api/account/me", headers=a).json()["member"]["id"]
    body = {"items": [{"name": "Milk", "amount": 2, "unit": "l", "location": drafts[0]["location"],
                       "expiry_date": drafts[0]["expiry_date"], "owner": "shared", "price": "5.49"}],
            "payer_id": alice_id}
    assert client.post("/api/receipts/save", json=body, headers=a).json()["message"] == "1 item added"
    assert client.post("/api/receipts/save", json={"items": []}, headers=a).status_code == 400
