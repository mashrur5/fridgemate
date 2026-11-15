"""Loads demo data through the API WITHOUT using any AI quota (every item has a location and a date).

Before running: start the server, register alice@test.com and bob@test.com (password123),
and have Bob join Alice's household. Then run:  python docs/stage2/demo/seed_demo.py
"""
import os
from datetime import date, timedelta

import httpx

URL = os.getenv("FRIDGEMATE_URL", "http://127.0.0.1:8000")
today = date.today()


def login(email: str) -> httpx.Client:
    c = httpx.Client(base_url=URL, timeout=30)
    r = c.post("/api/account/login", json={"email": email, "password": "password123"})
    r.raise_for_status()
    c.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return c


def add(c: httpx.Client, name, amount, unit, location, days, owner="me", price=None, payer=None):
    body = {"name": name, "amount": amount, "unit": unit, "location": location,
            "expiry_date": (today + timedelta(days=days)).isoformat(), "owner": owner,
            "price": price, "payer_id": payer}
    c.post("/api/items", json=body).raise_for_status()
    print("added", name)


alice, bob = login("alice@test.com"), login("bob@test.com")
alice_id = alice.get("/api/account/me").json()["member"]["id"]
bob_id = bob.get("/api/account/me").json()["member"]["id"]

# Alice's own food: spinach and tomatoes expire soon (good for recipes, meal plan and offers)
add(alice, "Spinach", 200, "g", "fridge", 1)
add(alice, "Tomato", 4, "pcs", "fridge", 2)
add(alice, "Chicken breast", 500, "g", "fridge", 2)
add(alice, "Greek yogurt", 500, "g", "fridge", 9)
add(alice, "Old milk", 1, "l", "fridge", -2)          # already expired
# Shared food with prices (cost split F14)
add(alice, "Eggs", 12, "pcs", "fridge", 14, "shared", "5.99", alice_id)
add(alice, "Rice", 2, "kg", "pantry", 300, "shared", "12.00", alice_id)
add(alice, "Onion", 3, "pcs", "pantry", 20, "shared", "2.49", alice_id)
add(alice, "Garlic", 6, "pcs", "pantry", 30, "shared")  # no price -> "Missing price" on Costs page
add(bob, "Olive oil", 500, "ml", "pantry", 365, "shared", "9.99", bob_id)
add(bob, "Pasta", 500, "g", "pantry", 365, "shared", "3.49", bob_id)
# Bob's private food (Alice must never see it)
add(bob, "Bob's steak", 300, "g", "fridge", 3)
add(bob, "Cheddar cheese", 200, "g", "fridge", 20)
print("done")
