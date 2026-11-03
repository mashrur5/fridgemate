from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class Household:
    """A group of roommates who share one fridge. Members join with the invite code."""

    name: str
    invite_code: str
    id: UUID = field(default_factory=uuid4)
