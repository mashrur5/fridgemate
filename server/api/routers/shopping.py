"""F11: shopping list."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade
from server.domain.model import Quantity

router = APIRouter(prefix="/api/shopping", tags=["shopping"])


class AddBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    amount: Optional[float] = Field(default=None, gt=0)
    unit: Optional[str] = None
    shared: bool = False


class CheckBody(BaseModel):
    checked: bool


@router.get("")
def get_list(ctx: Ctx, facade: Facade):
    return s.shopping_list(facade.get_shopping_list(ctx))


@router.post("", status_code=201)
def add(body: AddBody, ctx: Ctx, facade: Facade):
    q = Quantity(body.amount, body.unit or "pcs") if body.amount else None
    return s.shopping_item(facade.add_shopping_item(ctx, body.name, q, body.shared))


@router.patch("/{item_id}")
def check(item_id: UUID, body: CheckBody, ctx: Ctx, facade: Facade):
    return s.shopping_item(facade.check_shopping_item(ctx, item_id, body.checked))


@router.delete("/checked")
def clear_checked(ctx: Ctx, facade: Facade):
    return {"removed": facade.clear_checked(ctx)}


@router.delete("/{item_id}")
def remove(item_id: UUID, ctx: Ctx, facade: Facade):
    facade.remove_shopping_item(ctx, item_id)
    return {"ok": True}
