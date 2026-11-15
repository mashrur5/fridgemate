"""F06: households, invite codes and preferences."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from server.api import serializers as s
from server.api.routers.common import Auth, Ctx, Facade
from server.application.request_context import RequestContext
from server.domain.services.household_service import RESTRICTIONS

router = APIRouter(prefix="/api/household", tags=["household"])


class CreateBody(BaseModel):
    name: str


class JoinBody(BaseModel):
    invite_code: str


class PrefsBody(BaseModel):
    dietary_restrictions: list[str] = []
    disliked_ingredients: list[str] = []
    name: Optional[str] = None


@router.post("", status_code=201)
def create(body: CreateBody, auth: Auth, facade: Facade):
    home = facade.create_household(auth.member, body.name)
    return s.household(home, facade.get_members(RequestContext(auth.member, home)))


@router.post("/join")
def join(body: JoinBody, auth: Auth, facade: Facade):
    home = facade.join_household(auth.member, body.invite_code)
    return s.household(home, facade.get_members(RequestContext(auth.member, home)))


@router.get("")
def show(ctx: Ctx, facade: Facade):
    return s.household(ctx.household, facade.get_members(ctx))


@router.get("/restrictions")
def restrictions():
    return list(RESTRICTIONS)


@router.put("/preferences")
def preferences(body: PrefsBody, auth: Auth, facade: Facade):
    return s.member(facade.update_preferences(auth.member, body.dietary_restrictions, body.disliked_ingredients,
                                              body.name))
