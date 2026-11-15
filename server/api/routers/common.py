from typing import Annotated

from fastapi import Depends

from server.api.token_verifier import Session, current_context, get_facade, verify_token
from server.application.facade import FridgemateFacade
from server.application.request_context import RequestContext

Facade = Annotated[FridgemateFacade, Depends(get_facade)]
Ctx = Annotated[RequestContext, Depends(current_context)]
Auth = Annotated[Session, Depends(verify_token)]
