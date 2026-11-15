from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class Notification:
    member_id: UUID
    message: str
    item_id: Optional[UUID] = None
    kind: str = "info"
    read: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    id: UUID = field(default_factory=uuid4)
