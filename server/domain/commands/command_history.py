from __future__ import annotations

from uuid import UUID

from server.application.request_context import RequestContext
from server.domain.commands.inventory_command import InventoryCommand

MAX_HISTORY = 20


class CommandHistory:
    """Command pattern invoker. Runs commands and keeps one undo stack per member, in memory."""

    def __init__(self) -> None:
        self.history: dict[UUID, list[InventoryCommand]] = {}

    def run(self, ctx: RequestContext, command: InventoryCommand) -> None:
        command.execute()
        if command.undoable():
            stack = self.history.setdefault(ctx.member.id, [])
            stack.append(command)
            del stack[:-MAX_HISTORY]

    def undo_last(self, ctx: RequestContext) -> bool:
        """Undo this member's most recent command. False when there is nothing to undo
        (for example after a server restart, because the history is kept in memory)."""
        stack = self.history.get(ctx.member.id)
        if not stack:
            return False
        stack.pop().undo()
        return True

    def last_description(self, ctx: RequestContext) -> str | None:
        stack = self.history.get(ctx.member.id)
        return stack[-1].description if stack else None
