from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from uuid import UUID, uuid4

from server.domain.model.recipe import RecipeSuggestion


@dataclass
class PlannedMeal:
    day: date
    slot: int  # 1 or 2 (meals per day)
    suggestion: Optional[RecipeSuggestion]
    note: str = ""


@dataclass
class MealPlan:
    """F13: a saved plan for the next few days."""

    member_id: UUID
    household_id: UUID
    start: date
    days: int
    meals: list[PlannedMeal] = field(default_factory=list)
    missing_days: list[date] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    id: UUID = field(default_factory=uuid4)
