"""F12: natural-language fridge commands. The agent proposes changes; the user confirms (G4)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional
from uuid import UUID

from server.agent.agent_trace import AgentTrace
from server.agent.base_agent import BaseAgent
from server.agent.conversation_memory import ConversationMemory
from server.agent.response_parser import SchemaError
from server.agent.tools import ConvertUnitsTool, GetInventoryTool, ProposeInventoryChangeTool, ToolRegistry
from server.application.request_context import RequestContext
from server.domain.model import FoodItem, ProposedChanges
from server.domain.services.inventory_service import InventoryService
from server.domain.services.unit_converter import UnitConverter
from server.infrastructure.llm import LLMClient, Message

ROLE = """You are Fridgemate's fridge assistant. Roommates tell you in plain English what they bought,
used, threw away or moved, and you turn it into proposed inventory changes. You can ONLY manage the
food inventory (add, use, remove, move, set amounts). For anything else, explain what you can do."""

TASK = """How to work:
1. Call get_inventory to find the items the message mentions (you need their item_id).
2. Call propose_inventory_change once per change. If it returns an error, fix the change or tell the user.
3. If the message is unclear (e.g. "the milk" matches two items, or no amount is given for an add),
   ask ONE short follow-up question instead of guessing. Propose what you did understand.
4. Use the earlier conversation: "make that 12" refers to the previous proposal; propose the corrected change.
Never propose changes to items that belong to a roommate. Nothing changes until the user presses Confirm."""

FINAL = '{"reply": "<short message to the user>", "question": "<follow-up question or null>"}'


@dataclass
class CommandReply:
    reply: str
    question: Optional[str]
    proposal: ProposedChanges
    trace: AgentTrace


class FridgeCommandAgent(BaseAgent):
    def __init__(self, llm: LLMClient, inventory: InventoryService, memory: ConversationMemory | None = None,
                 converter: UnitConverter | None = None, today: Callable[[], date] = date.today, **kw) -> None:
        super().__init__(llm, **kw)
        self.inventory = inventory
        self.memory = memory or ConversationMemory()
        self.converter = converter or UnitConverter()
        self.today = today
        self.pending: dict[UUID, ProposedChanges] = {}

    def _items(self, ctx: RequestContext) -> list[FoodItem]:
        # G2: only the member's own and Shared items are shown (expired ones too, so they can be thrown out)
        return [i for i in self.inventory.get_items(ctx) if i.visible_to(ctx.member)]

    def _all_items(self, ctx: RequestContext) -> list[FoodItem]:
        return self.inventory.get_items(ctx)

    def handle(self, ctx: RequestContext, message: str) -> CommandReply:
        message = message.strip()[:1000]
        if not message:
            raise ValueError("type a message first")
        trace = AgentTrace("FridgeCommandAgent")
        proposal = ProposedChanges()
        previous = self.pending.get(ctx.member.id)
        if previous is not None:
            proposal.changes = list(previous.changes)  # "actually, make that 12" edits the open proposal
        registry = ToolRegistry([
            GetInventoryTool(self._items, self.today),
            ProposeInventoryChangeTool(self._all_items, proposal, self.converter),
            ConvertUnitsTool(self.converter)])
        system = self.prompts.tool_system_prompt(ROLE, TASK, registry, FINAL, self.max_steps)
        history = self.memory.history(ctx.member.id)
        open_changes = [c.describe() for c in proposal.changes]
        text = self.prompts.as_data("message", message)
        if open_changes:
            text += "\nCurrently proposed (not yet confirmed): " + json.dumps(open_changes)
        loop = self.run_tool_loop(ctx, system, history + [Message("user", text)], registry, trace,
                                  validate_final=self._valid_final)
        reply = str(loop.final.get("reply") or "").strip() or "Here is what I understood."
        question = loop.final.get("question") or None
        if proposal.rejected:
            reply += " " + " ".join(f"({r})" for r in proposal.rejected)
        self.memory.remember(ctx.member.id, message, json.dumps(
            {"reply": reply, "question": question, "proposed": [c.describe() for c in proposal.changes]}))
        if proposal.changes:
            self.pending[ctx.member.id] = proposal
        else:
            self.pending.pop(ctx.member.id, None)
        return CommandReply(reply, question, proposal, trace)

    @staticmethod
    def _valid_final(final: dict) -> dict:
        if not isinstance(final.get("reply", ""), str):
            raise SchemaError("'reply' must be text")
        return final

    def take_pending(self, ctx: RequestContext, proposal_id: UUID) -> Optional[ProposedChanges]:
        """Remove and return the open proposal if the id matches (confirm or cancel)."""
        p = self.pending.get(ctx.member.id)
        if p is None or p.id != proposal_id:
            return None
        del self.pending[ctx.member.id]
        return p
