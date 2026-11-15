"""F15: notifications (offers and claims)."""
from fastapi import APIRouter

from server.api import serializers as s
from server.api.routers.common import Auth, Facade

router = APIRouter(prefix="/api/notifications", tags=["notification"])


@router.get("")
def get_all(auth: Auth, facade: Facade):
    notes = facade.get_notifications(auth.member)
    return {"notifications": [s.notification(n) for n in notes], "unread": sum(1 for n in notes if not n.read)}


@router.post("/read")
def mark_read(auth: Auth, facade: Facade):
    facade.mark_notifications_read(auth.member)
    return {"ok": True}
