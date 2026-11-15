"""F13: waste-rescue meal plans."""
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from server.api import serializers as s
from server.api.routers.common import Ctx, Facade

router = APIRouter(prefix="/api/meal-plan", tags=["meal plan"])


class PlanBody(BaseModel):
    days: int = Field(default=3, ge=3, le=5)
    meals_per_day: int = Field(default=1, ge=1, le=2)
    max_minutes: Optional[int] = Field(default=None, gt=0)


@router.post("")
def plan(body: PlanBody, ctx: Ctx, facade: Facade):
    p = facade.plan_meals(ctx, body.days, body.meals_per_day, body.max_minutes)
    trace = facade.meal_planner.last_trace
    return {**s.meal_plan(p, []), "trace": trace.to_dict() if trace else None}


@router.get("")
def latest(ctx: Ctx, facade: Facade):
    p, outdated = facade.get_meal_plan(ctx)
    return s.meal_plan(p, outdated) if p else None


@router.post("/replan")
def replan(ctx: Ctx, facade: Facade, max_minutes: Optional[int] = None):
    return s.meal_plan(facade.replan_meals(ctx, max_minutes), [])
