"""SQLite repositories (replace the Stage 1 Neon/Postgres ones, see docs/design-changes.md #9)."""
from __future__ import annotations

import json
import pickle
import sqlite3
import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional
from uuid import UUID

from server.domain.model import (
    FoodItem, Household, Location, MealPlan, Member, Notification, Payment, Purchase, Quantity, ShoppingListItem,
)
from server.infrastructure.persistence.item_repository import ItemRepository
from server.infrastructure.persistence.repositories import (
    AccountRepository, CostRepository, HouseholdRepository, MealPlanRepository, MemberRepository,
    NotificationRepository, ShoppingListRepository,
)

SCHEMA = Path(__file__).with_name("schema.sql")


class Database:
    """One shared connection guarded by a lock (the API serves requests from several threads)."""

    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA.read_text())

    def run(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, params)

    def all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchone()


def _id(value) -> Optional[str]:
    return str(value) if value is not None else None


def _uuid(value) -> Optional[UUID]:
    return UUID(value) if value else None


class SqliteMemberRepository(MemberRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, m: Member) -> None:
        self.db.run("INSERT OR REPLACE INTO members VALUES (?,?,?,?,?,?,?)",
                    (str(m.id), m.account_id, m.name, m.email, _id(m.household_id),
                     json.dumps(m.dietary_restrictions), json.dumps(m.disliked_ingredients)))

    @staticmethod
    def _row(r) -> Member:
        return Member(account_id=r["account_id"], name=r["name"], email=r["email"], id=UUID(r["id"]),
                      household_id=_uuid(r["household_id"]), dietary_restrictions=json.loads(r["dietary_restrictions"]),
                      disliked_ingredients=json.loads(r["disliked_ingredients"]))

    def find_by_id(self, member_id: UUID) -> Optional[Member]:
        r = self.db.one("SELECT * FROM members WHERE id=?", (str(member_id),))
        return self._row(r) if r else None

    def find_by_account(self, account_id: str) -> Optional[Member]:
        r = self.db.one("SELECT * FROM members WHERE account_id=?", (account_id,))
        return self._row(r) if r else None

    def find_by_household(self, household_id: UUID) -> list[Member]:
        return [self._row(r) for r in self.db.all("SELECT * FROM members WHERE household_id=?", (str(household_id),))]


class SqliteHouseholdRepository(HouseholdRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, h: Household) -> None:
        self.db.run("INSERT OR REPLACE INTO households VALUES (?,?,?)", (str(h.id), h.name, h.invite_code))

    @staticmethod
    def _row(r) -> Household:
        return Household(name=r["name"], invite_code=r["invite_code"], id=UUID(r["id"]))

    def find_by_id(self, household_id: UUID) -> Optional[Household]:
        r = self.db.one("SELECT * FROM households WHERE id=?", (str(household_id),))
        return self._row(r) if r else None

    def find_by_invite_code(self, code: str) -> Optional[Household]:
        r = self.db.one("SELECT * FROM households WHERE invite_code=?", (code.strip().upper(),))
        return self._row(r) if r else None


class SqliteAccountRepository(AccountRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_credentials(self, account_id, password_hash, salt) -> None:
        self.db.run("INSERT OR REPLACE INTO credentials VALUES (?,?,?)", (account_id, password_hash, salt))

    def find_credentials(self, account_id):
        r = self.db.one("SELECT password_hash, salt FROM credentials WHERE account_id=?", (account_id,))
        return (r[0], r[1]) if r else None

    def save_session(self, token, account_id, expires_at) -> None:
        self.db.run("INSERT OR REPLACE INTO sessions VALUES (?,?,?)", (token, account_id, expires_at.isoformat()))

    def find_session(self, token):
        r = self.db.one("SELECT account_id, expires_at FROM sessions WHERE token=?", (token,))
        return (r[0], datetime.fromisoformat(r[1])) if r else None

    def delete_session(self, token) -> None:
        self.db.run("DELETE FROM sessions WHERE token=?", (token,))


class SqliteItemRepository(ItemRepository):
    def __init__(self, db: Database, members: MemberRepository) -> None:
        self.db = db
        self.members = members

    def save(self, i: FoodItem) -> None:
        self.db.run("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            str(i.id), str(i.household_id), i.name, i.quantity.amount, i.quantity.unit, i.original_amount,
            i.location.value, i.expiry_date.isoformat(), i.added_on.isoformat(), _id(i.owner and i.owner.id),
            int(i.expiry_estimated), str(i.price) if i.price is not None else None, _id(i.payer and i.payer.id),
            int(i.is_offered), _id(i.offered_by and i.offered_by.id)))

    def _member(self, member_id, cache: dict) -> Optional[Member]:
        if not member_id:
            return None
        if member_id not in cache:
            cache[member_id] = self.members.find_by_id(UUID(member_id))
        return cache[member_id]

    def _row(self, r, cache: dict) -> FoodItem:
        return FoodItem(
            name=r["name"], quantity=Quantity(r["amount"], r["unit"]), location=Location(r["location"]),
            household_id=UUID(r["household_id"]), expiry_date=date.fromisoformat(r["expiry_date"]),
            added_on=date.fromisoformat(r["added_on"]), owner=self._member(r["owner_id"], cache),
            original_amount=r["original_amount"], expiry_estimated=bool(r["expiry_estimated"]),
            price=Decimal(r["price"]) if r["price"] is not None else None, payer=self._member(r["payer_id"], cache),
            is_offered=bool(r["is_offered"]), offered_by=self._member(r["offered_by_id"], cache), id=UUID(r["id"]))

    def find_by_id(self, item_id: UUID) -> Optional[FoodItem]:
        r = self.db.one("SELECT * FROM items WHERE id=?", (str(item_id),))
        return self._row(r, {}) if r else None

    def find_by_household(self, household_id: UUID) -> list[FoodItem]:
        cache: dict = {}
        return [self._row(r, cache) for r in self.db.all("SELECT * FROM items WHERE household_id=?", (str(household_id),))]

    def find_by_owner(self, owner_id: UUID) -> list[FoodItem]:
        cache: dict = {}
        return [self._row(r, cache) for r in self.db.all("SELECT * FROM items WHERE owner_id=?", (str(owner_id),))]

    def claim_if_unclaimed(self, item_id: UUID, member: Member) -> bool:
        """One conditional UPDATE: only the first claim changes a row, so only the first claim wins."""
        cur = self.db.run("UPDATE items SET owner_id=?, is_offered=0, offered_by_id=NULL WHERE id=? AND is_offered=1",
                          (str(member.id), str(item_id)))
        return cur.rowcount == 1

    def delete(self, item_id: UUID) -> None:
        self.db.run("DELETE FROM items WHERE id=?", (str(item_id),))


class SqliteShoppingListRepository(ShoppingListRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, i: ShoppingListItem) -> None:
        self.db.run("INSERT OR REPLACE INTO shopping_items VALUES (?,?,?,?,?,?,?,?,?)", (
            str(i.id), str(i.household_id), _id(i.member_id), i.name, i.quantity.amount if i.quantity else None,
            i.quantity.unit if i.quantity else None, i.section, json.dumps(i.reasons), int(i.checked)))

    def find_by_household(self, household_id: UUID) -> list[ShoppingListItem]:
        return [ShoppingListItem(
            household_id=UUID(r["household_id"]), name=r["name"],
            quantity=Quantity(r["amount"], r["unit"]) if r["unit"] else None, section=r["section"],
            reasons=json.loads(r["reasons"]), member_id=_uuid(r["member_id"]), checked=bool(r["checked"]),
            id=UUID(r["id"])) for r in self.db.all("SELECT * FROM shopping_items WHERE household_id=?",
                                                    (str(household_id),))]

    def delete(self, item_id: UUID) -> None:
        self.db.run("DELETE FROM shopping_items WHERE id=?", (str(item_id),))


class SqliteCostRepository(CostRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save_purchase(self, p: Purchase) -> None:
        self.db.run("INSERT OR REPLACE INTO purchases VALUES (?,?,?,?,?,?,?)", (
            str(p.id), str(p.household_id), str(p.item_id), p.item_name, str(p.price), str(p.payer_id),
            p.bought_on.isoformat()))

    def delete_purchase_for_item(self, item_id: UUID) -> None:
        self.db.run("DELETE FROM purchases WHERE item_id=?", (str(item_id),))

    def purchases(self, household_id: UUID) -> list[Purchase]:
        return [Purchase(UUID(r["household_id"]), UUID(r["item_id"]), r["item_name"], Decimal(r["price"]),
                         UUID(r["payer_id"]), date.fromisoformat(r["bought_on"]), UUID(r["id"]))
                for r in self.db.all("SELECT * FROM purchases WHERE household_id=?", (str(household_id),))]

    def save_payment(self, p: Payment) -> None:
        self.db.run("INSERT OR REPLACE INTO payments VALUES (?,?,?,?,?,?)", (
            str(p.id), str(p.household_id), str(p.from_id), str(p.to_id), str(p.amount), p.paid_on.isoformat()))

    def delete_payment(self, payment_id: UUID) -> None:
        self.db.run("DELETE FROM payments WHERE id=?", (str(payment_id),))

    def payments(self, household_id: UUID) -> list[Payment]:
        return [Payment(UUID(r["household_id"]), UUID(r["from_id"]), UUID(r["to_id"]), Decimal(r["amount"]),
                        date.fromisoformat(r["paid_on"]), UUID(r["id"]))
                for r in self.db.all("SELECT * FROM payments WHERE household_id=?", (str(household_id),))]


class SqliteNotificationRepository(NotificationRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, n: Notification) -> None:
        self.db.run("INSERT OR REPLACE INTO notifications VALUES (?,?,?,?,?,?,?)", (
            str(n.id), str(n.member_id), n.message, _id(n.item_id), n.kind, int(n.read), n.created_at.isoformat()))

    def find_by_member(self, member_id: UUID) -> list[Notification]:
        return [Notification(UUID(r["member_id"]), r["message"], _uuid(r["item_id"]), r["kind"], bool(r["read"]),
                             datetime.fromisoformat(r["created_at"]), UUID(r["id"]))
                for r in self.db.all("SELECT * FROM notifications WHERE member_id=? ORDER BY created_at DESC",
                                     (str(member_id),))]

    def delete_for_item(self, item_id: UUID) -> None:
        self.db.run("DELETE FROM notifications WHERE item_id=? AND kind='offer'", (str(item_id),))


class SqliteMealPlanRepository(MealPlanRepository):
    """The plan is stored as one pickled blob: it is only ever read back whole by this app."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, plan: MealPlan) -> None:
        self.db.run("INSERT OR REPLACE INTO meal_plans VALUES (?,?,?,?)",
                    (str(plan.id), str(plan.member_id), plan.created_at.isoformat(), pickle.dumps(plan)))

    def latest_for_member(self, member_id: UUID) -> Optional[MealPlan]:
        r = self.db.one("SELECT data FROM meal_plans WHERE member_id=? ORDER BY created_at DESC LIMIT 1",
                        (str(member_id),))
        return pickle.loads(r["data"]) if r else None
