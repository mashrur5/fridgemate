from __future__ import annotations

from dataclasses import dataclass

from server.domain.model import Household, Member


@dataclass(frozen=True)
class RequestContext:
    """Who is making the request. Every service call is limited to this member's household."""

    member: Member
    household: Household
