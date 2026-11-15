"""Target interface of the Adapter pattern. Agents only ever talk to LLMClient."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class LLMUnavailableError(Exception):
    """The model could not be reached, is not configured, or is rate limited."""


@dataclass
class Message:
    role: str  # "user" or "model"
    text: str


@dataclass
class Image:
    mime_type: str
    data: bytes


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class UsageMeter:
    """Counts tokens so the app can show how much the AI has used."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def record(self, r: LLMResponse) -> None:
        self.calls += 1
        self.input_tokens += r.input_tokens
        self.output_tokens += r.output_tokens


class LLMClient(ABC):
    name: str = "llm"
    usage: UsageMeter

    @abstractmethod
    def generate(self, system: str, messages: list[Message], json_mode: bool = True,
                 images: list[Image] | None = None) -> LLMResponse:
        """Send a conversation and return the model's reply. Raises LLMUnavailableError."""


class UnavailableLLMClient(LLMClient):
    """Used when no model is configured, so every AI feature falls back or shows a clear error."""

    name = "none"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        self.usage = UsageMeter()

    def generate(self, system, messages, json_mode=True, images=None) -> LLMResponse:
        raise LLMUnavailableError(self.reason)
