"""F07, F08, F09, F10: recipe suggestions, quick finder, cooking."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade
from server.domain.model import Location, Quantity, RecipeRequest
from server.domain.services.cooking_service import Leftovers, Usage

router = APIRouter(prefix="/api/recipes", tags=["recipe"])


class Options(BaseModel):
    cuisine: Optional[str] = None
    max_minutes: Optional[int] = Field(default=None, gt=0)
    weight: Optional[str] = None
    servings: int = Field(default=2, ge=1, le=10)

    def to_request(self) -> RecipeRequest:
        return RecipeRequest(self.cuisine or None, self.max_minutes, self.weight or None, self.servings)


class FindBody(Options):
    ingredients: list[str]


class UsageBody(BaseModel):
    item_id: UUID
    amount: float = Field(gt=0)
    unit: str


class CookBody(BaseModel):
    usages: list[UsageBody]
    leftover_portions: Optional[int] = Field(default=None, ge=1, le=20)
    leftover_location: str = "fridge"


def _result(r):
    return {"suggestions": [s.suggestion(x) for x in r.suggestions], "notes": r.notes, "choices": r.choices,
            "trace": r.trace.to_dict() if r.trace else None}


@router.get("/cuisines")
def cuisines(facade: Facade):
    return facade.list_cuisines()


@router.post("/suggest")
def suggest(body: Options, ctx: Ctx, facade: Facade):
    return _result(facade.suggest_recipes(ctx, body.to_request()))


@router.post("/find")
def find(body: FindBody, ctx: Ctx, facade: Facade):
    return _result(facade.find_recipes(ctx, body.ingredients, body.to_request()))


@router.get("/{recipe_id}")
def get_recipe(recipe_id: str, facade: Facade):
    return s.recipe(facade.get_recipe(recipe_id))


@router.get("/{recipe_id}/cook")
def cook_preview(recipe_id: str, ctx: Ctx, facade: Facade, servings: int = 2):
    p = facade.cook_preview(ctx, recipe_id, servings)
    names = {str(i.id): i.name for i in facade.list_items(ctx)}
    return {"recipe": s.recipe(p.recipe), "checks": [s.check(c) for c in p.check.checks],
            "usages": [{"item_id": str(u.item_id), "item_name": names.get(str(u.item_id), "?"),
                        "amount": round(u.amount.amount, 3), "unit": u.amount.unit} for u in p.usages]}


@router.post("/{recipe_id}/cook")
def cook(recipe_id: str, body: CookBody, ctx: Ctx, facade: Facade):
    usages = [Usage(u.item_id, Quantity(u.amount, u.unit)) for u in body.usages]
    leftovers = Leftovers(body.leftover_portions, Location(body.leftover_location)) if body.leftover_portions else None
    return {"message": facade.cook(ctx, recipe_id, usages, leftovers)}


@router.post("/{recipe_id}/missing-to-shopping")
def missing_to_shopping(recipe_id: str, ctx: Ctx, facade: Facade, servings: int = 2):
    added = facade.add_missing_to_shopping(ctx, recipe_id, servings)
    return {"added": [s.shopping_item(i) for i in added]}
