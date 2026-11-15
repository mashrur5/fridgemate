"""F03: receipt import. Parse first (nothing saved), then save the reviewed items."""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade
from server.api.routers.inventory import ItemBody
from server.application.request_context import RequestContext

router = APIRouter(prefix="/api/receipts", tags=["receipt"])


class TextBody(BaseModel):
    text: str


class SaveBody(BaseModel):
    items: list[ItemBody]
    payer_id: Optional[UUID] = None


def _drafts(drafts, ctx: RequestContext, today):
    return {"items": [{**s.item(d.item, ctx, today), "note": " ".join(x for x in (d.location_note, d.expiry_note) if x),
                       "price": str(d.item.price) if d.item.price is not None else None} for d in drafts]}


@router.post("/parse")
async def parse_photo(ctx: Ctx, facade: Facade, photo: UploadFile = File(...)):
    data = await photo.read()
    return _drafts(facade.parse_receipt_image(ctx, data, photo.content_type or ""), ctx, facade.today())


@router.post("/parse-text")
def parse_text(body: TextBody, ctx: Ctx, facade: Facade):
    return _drafts(facade.parse_receipt_text(ctx, body.text), ctx, facade.today())


@router.post("/save", status_code=201)
def save(body: SaveBody, ctx: Ctx, facade: Facade):
    items = facade.save_receipt(ctx, [i.to_input() for i in body.items], body.payer_id)
    return {"saved": len(items), "message": f"{len(items)} item{'s' if len(items) != 1 else ''} added"}
