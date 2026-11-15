from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID, uuid4

OPS = ("add", "use", "remove", "move", "set")


@dataclass
class ProposedChange:
    """F12: one change the agent wants to make. Nothing runs until the user confirms (G4)."""

    op: str
    name: str
    item_id: Optional[UUID] = None
    amount: Optional[float] = None
    unit: Optional[str] = None
    location: Optional[str] = None
    owner: str = "me"  # "me" or "shared" for new items

    def describe(self) -> str:
        qty = f" {self.amount:g} {self.unit}" if self.amount is not None and self.unit else ""
        if self.op == "add":
            return f"Add{qty} {self.name}" + (f" to the {self.location}" if self.location else "")
        if self.op == "use":
            return f"Use{qty} of {self.name}"
        if self.op == "remove":
            return f"Remove {self.name}"
        if self.op == "move":
            return f"Move {self.name} to the {self.location}"
        return f"Set {self.name} to{qty}"


@dataclass
class ProposedChanges:
    changes: list[ProposedChange] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
