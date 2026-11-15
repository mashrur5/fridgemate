"""F14: shared cost split."""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade

router = APIRouter(prefix="/api/costs", tags=["cost"])


class PaidBody(BaseModel):
    from_id: UUID
    to_id: UUID
    amount: Decimal = Field(gt=0)


@router.get("")
def summary(ctx: Ctx, facade: Facade, month: Optional[str] = None):
    data = s.costs(facade.get_costs(ctx, month), facade.get_members(ctx), facade.missing_prices(ctx))
    data["month"] = month or facade.today().strftime("%Y-%m")
    data["only_member"] = len(data["members"]) < 2
    return data


@router.post("/payments", status_code=201)
def mark_paid(body: PaidBody, ctx: Ctx, facade: Facade):
    facade.mark_paid(ctx, body.from_id, body.to_id, body.amount)
    return {"ok": True}


@router.delete("/payments/{payment_id}")
def remove_payment(payment_id: UUID, ctx: Ctx, facade: Facade):
    facade.remove_payment(ctx, payment_id)
    return {"ok": True}
