"""BaseAgent runs the tool loop shared by RecipeAgent, MealPlanAgent and FridgeCommandAgent."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from server.agent.agent_trace import AgentTrace
from server.agent.prompt_builder import PromptBuilder
from server.agent.response_parser import ResponseParser, SchemaError
from server.agent.tools import ToolRegistry
from server.application.request_context import RequestContext
from server.infrastructure.llm import Image, LLMClient, Message

MAX_TOOL_STEPS = 6  # G6
MAX_RESULT_CHARS = 6000


class AgentError(Exception):
    """The AI did not give a usable answer."""


def ask_json(llm: LLMClient, parser: ResponseParser, system: str, messages: list[Message],
             validate: Callable[[Any], Any], trace: Optional[AgentTrace] = None,
             images: Optional[list[Image]] = None) -> Any:
    """G5: ask for JSON, check it, and retry once with the error if it is invalid."""
    convo = list(messages)
    for attempt in (1, 2):
        reply = llm.generate(system, convo, json_mode=True, images=images if attempt == 1 else images)
        try:
            return parser.parse(reply.text, validate)
        except SchemaError as e:
            if trace:
                trace.add("retry" if attempt == 1 else "error", f"invalid answer: {e}")
            if attempt == 2:
                raise AgentError("the AI gave an invalid answer twice, please try again") from e
            convo += [Message("model", reply.text[:2000]),
                      Message("user", f"Your answer was invalid ({e}). Reply again with one valid JSON object only.")]


@dataclass
class LoopResult:
    final: dict
    steps: int
    hit_limit: bool
    conversation: list[Message] = field(default_factory=list)


class BaseAgent:
    def __init__(self, llm: LLMClient, parser: ResponseParser | None = None, prompts: PromptBuilder | None = None,
                 max_steps: int = MAX_TOOL_STEPS) -> None:
        self.llm = llm
        self.parser = parser or ResponseParser()
        self.prompts = prompts or PromptBuilder()
        self.max_steps = max_steps

    @staticmethod
    def _step_shape(data: Any) -> dict:
        if not isinstance(data, dict):
            raise SchemaError("the answer must be a JSON object")
        if "final" in data:
            if not isinstance(data["final"], dict):
                raise SchemaError("'final' must be an object")
            return data
        if isinstance(data.get("tool"), str):
            if not isinstance(data.get("args", {}), dict):
                raise SchemaError("'args' must be an object")
            return data
        raise SchemaError("give either 'tool' with 'args', or 'final'")

    def run_tool_loop(self, ctx: RequestContext, system: str, messages: list[Message], registry: ToolRegistry,
                      trace: AgentTrace, max_steps: Optional[int] = None,
                      validate_final: Optional[Callable[[dict], dict]] = None) -> LoopResult:
        """Let the LLM call tools until it gives a final answer, with at most max_steps tool calls (G6)."""
        limit = self.max_steps if max_steps is None else max_steps
        convo = list(messages)
        steps = 0
        hit_limit = False

        def validate(data):
            data = self._step_shape(data)
            if "final" in data and validate_final:
                data["final"] = validate_final(data["final"])
            return data

        while True:
            if steps >= limit and not hit_limit:
                hit_limit = True
                trace.add("note", f"step limit of {limit} tool calls reached")
                convo.append(Message("user", "STEP LIMIT REACHED. Do not call any more tools. "
                                             "Reply now with the final JSON using what you know."))
            reply = ask_json(self.llm, self.parser, system, convo, validate, trace)
            if "final" in reply:
                trace.add("final", reply.get("thought", "") or "done")
                return LoopResult(reply["final"], steps, hit_limit, convo + [Message("model", json.dumps(reply))])
            if hit_limit:
                raise AgentError("the AI kept calling tools after the step limit")
            name, args = reply["tool"], reply.get("args") or {}
            result = registry.run(name, ctx, args)
            steps += 1
            text = json.dumps(result, ensure_ascii=False, default=str)
            trace.add("tool", (reply.get("thought") or "") + " -> " + text[:300], name, args)
            convo.append(Message("model", json.dumps(reply, ensure_ascii=False)))
            convo.append(Message("user", f"TOOL RESULT ({name}): {text[:MAX_RESULT_CHARS]}"))
