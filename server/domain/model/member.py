from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class Member:
    """A person in a household. Each member has their own login (Auth0) and preferences."""

    auth0_id: str
    name: str
    email: str
    id: UUID = field(default_factory=uuid4)
    dietary_restrictions: list[str] = field(default_factory=list)
    disliked_ingredients: list[str] = field(default_factory=list)

    def allows(self, ingredient: str) -> bool:
        """False if the ingredient matches a restriction or something the member dislikes."""
        name = ingredient.strip().lower()
        blocked = [x.strip().lower() for x in self.dietary_restrictions + self.disliked_ingredients]
        return not any(b and b in name for b in blocked)
