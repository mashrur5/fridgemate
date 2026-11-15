"""Checks the bearer token on every request and builds the RequestContext."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request

from server.application.facade import FridgemateFacade
from server.application.request_context import RequestContext
from server.domain.model import Household, Member


def get_facade(request: Request) -> FridgemateFacade:
    return request.app.state.facade


@dataclass
class Session:
    token: str
    member: Member
    household: Optional[Household]


class TokenVerifier:
    """FastAPI dependency: 'Authorization: Bearer <token>' -> Session. Unknown or expired tokens give 401."""

    def __call__(self, authorization: str = Header(default=""),
                 facade: FridgemateFacade = Depends(get_facade)) -> Session:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(401, "please log in")
        member, household = facade.load_context(token.strip())
        return Session(token.strip(), member, household)


verify_token = TokenVerifier()


def current_context(session: Session = Depends(verify_token)) -> RequestContext:
    if session.household is None:
        raise HTTPException(409, "create or join a household first")
    return RequestContext(session.member, session.household)
