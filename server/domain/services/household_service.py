"""F06: households, invite codes and preferences."""
from __future__ import annotations

import secrets
import string

from server.application.request_context import RequestContext
from server.domain.errors import InvalidOperationError, NotFoundError
from server.domain.model import Household, Member
from server.infrastructure.persistence import HouseholdRepository, MemberRepository

RESTRICTIONS = ("vegetarian", "vegan", "halal", "gluten-free", "dairy-free", "nut-free")
# What each restriction blocks, so Member.allows() can filter ingredients by name.
RESTRICTION_BLOCKS: dict[str, list[str]] = {
    "vegetarian": ["chicken", "beef", "pork", "lamb", "bacon", "fish", "shrimp", "prawn", "ham", "sausage",
                   "turkey", "salmon", "tuna", "anchovy", "gelatin"],
    "vegan": ["chicken", "beef", "pork", "lamb", "bacon", "fish", "shrimp", "prawn", "ham", "sausage", "turkey",
              "salmon", "tuna", "anchovy", "gelatin", "milk", "cheese", "butter", "cream", "egg", "yogurt",
              "honey", "parmesan", "mozzarella"],
    "halal": ["pork", "bacon", "ham", "wine", "beer", "lard", "gelatin", "prosciutto", "chorizo"],
    "gluten-free": ["flour", "bread", "pasta", "spaghetti", "noodle", "wheat", "barley", "couscous", "breadcrumb"],
    "dairy-free": ["milk", "cheese", "butter", "cream", "yogurt", "parmesan", "mozzarella", "ghee"],
    "nut-free": ["peanut", "almond", "cashew", "walnut", "pecan", "hazelnut", "pistachio"],
}
_CODE_ALPHABET = string.ascii_uppercase + string.digits


def blocked_words(member: Member) -> list[str]:
    words = list(member.disliked_ingredients)
    for r in member.dietary_restrictions:
        words += RESTRICTION_BLOCKS.get(r.lower(), [r])
    return words


def member_allows(member: Member, ingredient: str) -> bool:
    name = ingredient.lower()
    return not any(w.strip().lower() and w.strip().lower() in name for w in blocked_words(member))


class HouseholdService:
    def __init__(self, households: HouseholdRepository, members: MemberRepository) -> None:
        self.households = households
        self.members = members

    def create_household(self, member: Member, name: str) -> Household:
        if member.household_id is not None:
            raise InvalidOperationError("you are already in a household")
        if not name.strip():
            raise ValueError("household name cannot be empty")
        household = Household(name=name.strip(), invite_code=self._new_code())
        self.households.save(household)
        member.household_id = household.id
        self.members.save(member)
        return household

    def join_household(self, member: Member, invite_code: str) -> Household:
        if member.household_id is not None:
            raise InvalidOperationError("you are already in a household")
        household = self.households.find_by_invite_code(invite_code)
        if household is None:
            raise NotFoundError("no household was found with that invite code")
        member.household_id = household.id
        self.members.save(member)
        return household

    def get_members(self, ctx: RequestContext) -> list[Member]:
        return sorted(self.members.find_by_household(ctx.household.id), key=lambda m: m.name.lower())

    def update_preferences(self, member: Member, restrictions: list[str], dislikes: list[str],
                           name: str | None = None) -> Member:
        unknown = [r for r in restrictions if r.lower() not in RESTRICTIONS]
        if unknown:
            raise ValueError(f"unknown restriction: {', '.join(unknown)}")
        member.dietary_restrictions = sorted({r.lower() for r in restrictions})
        member.disliked_ingredients = sorted({d.strip().lower() for d in dislikes if d.strip()})
        if name and name.strip():
            member.name = name.strip()
        self.members.save(member)
        return member

    def _new_code(self) -> str:
        while True:  # 10 random characters from 36: about 3.6e15 codes, so guessing is not realistic
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))
            if self.households.find_by_invite_code(code) is None:
                return code
