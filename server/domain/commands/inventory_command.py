from __future__ import annotations

from abc import ABC, abstractmethod


class InventoryCommand(ABC):
    """Command pattern: one inventory change wrapped as an object, so it can be undone.

    Invoker: CommandHistory. Receiver: InventoryService. Client: FridgemateFacade.
    Each command stores what it needs for undo().
    """

    description: str = ""

    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...

    def undoable(self) -> bool:
        return True
