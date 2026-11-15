"""F01, F02, F04, F05, F15: inventory items, suggestions, alerts, offers, claims and undo."""
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade
from server.application.facade import ItemInput
from server.domain.model import Location

router = APIRouter(prefix="/api/items", tags=["inventory"])


class ItemBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0)
    unit: str
    location: Optional[str] = None
    expiry_date: Optional[date] = None
    owner: str = "me"
    price: Optional[Decimal] = Field(default=None, ge=0)
    payer_id: Optional[UUID] = None

    def to_input(self) -> ItemInput:
        return ItemInput(self.name, self.amount, self.unit, self.location, self.expiry_date, self.owner, self.price,
                         self.payer_id)


class UpdateBody(BaseModel):
    name: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    unit: Optional[str] = None
    location: Optional[str] = None
    expiry_date: Optional[date] = None
    owner: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    payer_id: Optional[UUID] = None


class OfferBody(BaseModel):
    note: str = ""


@router.get("")
def list_items(ctx: Ctx, facade: Facade, location: Optional[str] = None, owner: Optional[str] = None,
               freshness: Optional[str] = None, q: Optional[str] = None):
    today = facade.today()
    return {"items": [s.item(i, ctx, today) for i in facade.list_items(ctx, location, owner, freshness, q)],
            "last_action": facade.last_action(ctx)}


@router.post("", status_code=201)
def add_item(body: ItemBody, ctx: Ctx, facade: Facade):
    result = facade.add_item(ctx, body.to_input())
    return {"item": s.item(result.item, ctx, facade.today()), "location_note": result.location_note,
            "expiry_note": result.expiry_note}


@router.get("/suggest")
def suggest(name: str, facade: Facade, location: Optional[str] = None):
    """F02 + F04 preview for the Add Item form: where to store it and when it expires."""
    loc, reason, source = facade.suggest_location(name)
    chosen = Location(location) if location else loc
    expiry, expiry_source = facade.estimate_expiry(name, chosen)
    return {"location": loc.value, "reason": reason, "location_source": source,
            "expiry_date": expiry.isoformat(), "expiry_source": expiry_source}


@router.get("/alerts")
def alerts(ctx: Ctx, facade: Facade):
    today = facade.today()
    items = facade.get_alerts(ctx)
    expiring = [s.item(i, ctx, today) for i in items if i.alert_priority() == 1]
    return {"expiring": expiring, "expired": [s.item(i, ctx, today) for i in items if i.alert_priority() == 2],
            "banner": (f"{len(expiring)} items expire" if len(expiring) != 1 else "1 item expires") + " in the next 3 days" if expiring else None}


@router.post("/undo")
def undo(ctx: Ctx, facade: Facade):
    done = facade.undo(ctx)
    return {"undone": done, "message": f"Undid: {done}" if done else
            "Nothing to undo (the undo history is cleared when the server restarts)."}


@router.patch("/{item_id}")
def update_item(item_id: UUID, body: UpdateBody, ctx: Ctx, facade: Facade):
    item = facade.update_item(ctx, item_id, **body.model_dump(exclude_none=True))
    return s.item(item, ctx, facade.today())


@router.delete("/{item_id}")
def remove_item(item_id: UUID, ctx: Ctx, facade: Facade):
    facade.remove_item(ctx, item_id)
    return {"ok": True}


@router.post("/{item_id}/offer")
def offer(item_id: UUID, body: OfferBody, ctx: Ctx, facade: Facade):
    return s.item(facade.offer_item(ctx, item_id, body.note), ctx, facade.today())


@router.post("/{item_id}/claim")
def claim(item_id: UUID, ctx: Ctx, facade: Facade):
    return s.item(facade.claim_item(ctx, item_id), ctx, facade.today())
