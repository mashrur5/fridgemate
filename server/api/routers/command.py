"""F12: natural-language fridge commands with confirm / cancel."""
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade

router = APIRouter(prefix="/api/command", tags=["command"])


class MessageBody(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


@router.post("")
def chat(body: MessageBody, ctx: Ctx, facade: Facade):
    r = facade.chat(ctx, body.message)
    return {"reply": r.reply, "question": r.question, "proposal": s.proposal(r.proposal), "trace": r.trace.to_dict()}


@router.post("/{proposal_id}/confirm")
def confirm(proposal_id: UUID, ctx: Ctx, facade: Facade):
    return {"done": facade.confirm_changes(ctx, proposal_id)}


@router.post("/{proposal_id}/cancel")
def cancel(proposal_id: UUID, ctx: Ctx, facade: Facade):
    return {"cancelled": facade.cancel_changes(ctx, proposal_id)}
