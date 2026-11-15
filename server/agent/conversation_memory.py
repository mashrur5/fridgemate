"""F12: remembers each member's recent conversation, so "actually, make that 12" works."""
from __future__ import annotations

from collections import deque
from uuid import UUID

from server.infrastructure.llm import Message

MAX_TURNS = 10


class ConversationMemory:
    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self._turns: dict[UUID, deque[Message]] = {}
        self.max_turns = max_turns

    def history(self, member_id: UUID) -> list[Message]:
        return list(self._turns.get(member_id, []))

    def remember(self, member_id: UUID, user_text: str, agent_text: str) -> None:
        turns = self._turns.setdefault(member_id, deque(maxlen=self.max_turns * 2))
        turns.append(Message("user", user_text))
        turns.append(Message("model", agent_text))

    def clear(self, member_id: UUID) -> None:
        self._turns.pop(member_id, None)
