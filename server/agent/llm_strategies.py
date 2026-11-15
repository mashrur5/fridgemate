"""The AI halves of two Strategy patterns: F02 storage location and F04 expiry estimates.

Both raise on any problem, so PlacementService / ExpiryService switch to the rule-based fallback."""
from __future__ import annotations

from server.agent.base_agent import ask_json
from server.agent.prompt_builder import PromptBuilder
from server.agent.response_parser import ResponseParser, SchemaError
from server.domain.model import Location
from server.domain.services.expiry import ExpiryEstimator
from server.domain.services.placement import PlacementStrategy
from server.infrastructure.llm import LLMClient, Message

VAGUE = {"stuff", "food", "thing", "things", "item", "items", "misc", "groceries"}


class LLMPlacementStrategy(PlacementStrategy):
    def __init__(self, llm: LLMClient, parser: ResponseParser | None = None) -> None:
        self.llm, self.parser, self.prompts = llm, parser or ResponseParser(), PromptBuilder()

    def choose_location(self, item_name: str) -> tuple[Location, str]:
        if item_name.strip().lower() in VAGUE:
            raise ValueError("name too vague to place")
        system = self.prompts.plain_system_prompt(
            "You decide where a grocery item should be stored in a shared student kitchen to last longest and stay safe.",
            '{"location": "fridge" | "freezer" | "pantry", "reason": "<max 12 words>"}')

        def valid(d):
            d = self.parser.require(d, {"location": str, "reason": str})
            if d["location"].lower() not in ("fridge", "freezer", "pantry"):
                raise SchemaError("location must be fridge, freezer or pantry")
            return d

        d = ask_json(self.llm, self.parser, system, [Message("user", self.prompts.as_data("item", item_name))], valid)
        return Location(d["location"].lower()), d["reason"].strip()[:120]


class LLMExpiryEstimator(ExpiryEstimator):
    MAX_DAYS = 730

    def __init__(self, llm: LLMClient, parser: ResponseParser | None = None) -> None:
        self.llm, self.parser, self.prompts = llm, parser or ResponseParser(), PromptBuilder()

    def estimate_days(self, item_name: str, location: Location) -> int:
        system = self.prompts.plain_system_prompt(
            "You estimate how many days a freshly bought grocery item stays good when stored in the given place. "
            "Be cautious: give a typical safe number of days.", '{"days": <whole number>}')

        def valid(d):
            d = self.parser.require(d, {"days": (int, float)})
            if not 1 <= int(d["days"]) <= self.MAX_DAYS:
                raise SchemaError(f"days must be between 1 and {self.MAX_DAYS}")
            return d

        msg = self.prompts.as_data("item", {"name": item_name, "stored_in": location.value})
        return int(ask_json(self.llm, self.parser, system, [Message("user", msg)], valid)["days"])
