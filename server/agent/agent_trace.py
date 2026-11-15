"""G8: every agent step is logged, so behaviour can be inspected and tested (KUMA in Stage 3)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger("fridgemate.agent")


@dataclass
class TraceStep:
    kind: str  # "tool", "final", "retry", "error", "note"
    detail: str
    tool: str | None = None
    args: dict | None = None
    at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


@dataclass
class AgentTrace:
    agent: str
    steps: list[TraceStep] = field(default_factory=list)

    def add(self, kind: str, detail: str, tool: str | None = None, args: dict | None = None) -> None:
        step = TraceStep(kind, detail[:500], tool, args)
        self.steps.append(step)
        log.info("[%s] %s %s %s", self.agent, kind, tool or "", detail[:200])

    def tool_calls(self) -> list[str]:
        return [s.tool for s in self.steps if s.kind == "tool" and s.tool]

    def to_dict(self) -> dict:
        return {"agent": self.agent, "steps": [s.__dict__ for s in self.steps]}

    def __str__(self) -> str:
        return json.dumps(self.to_dict(), indent=1)
