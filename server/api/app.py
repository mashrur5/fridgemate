"""FastAPI app: 10 routers, one facade, and one place that turns domain errors into HTTP errors."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.agent.base_agent import AgentError
from server.agent.receipt_parser import ReceiptError
from server.api.routers import (
    account, command, cost, household, inventory, meal_plan, notification, receipt, recipe, shopping,
)
from server.application.facade import FridgemateFacade
from server.config import ROOT, Config
from server.domain.errors import InvalidOperationError, NotFoundError, PermissionDeniedError
from server.domain.services.account_service import AuthError
from server.infrastructure.llm import LLMUnavailableError
from server.infrastructure.recipes import RecipeSourceError

ERRORS = [(AuthError, 401), (PermissionDeniedError, 403), (NotFoundError, 404), (InvalidOperationError, 409),
          (ReceiptError, 400), (ValueError, 400), (LLMUnavailableError, 503), (RecipeSourceError, 503),
          (AgentError, 502)]
WEB_DIST = ROOT / "web" / "dist"


def create_app(facade: Optional[FridgemateFacade] = None, config: Optional[Config] = None) -> FastAPI:
    config = config or Config.from_env()
    if facade is None:
        from server.application.container import build_facade
        facade = build_facade(config)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    app = FastAPI(title="Fridgemate API", version="2.0")
    app.state.facade = facade
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in config.cors_origins.split(",") if o.strip()],
                       allow_methods=["*"], allow_headers=["*"])

    for error, status in ERRORS:
        def handler(request: Request, exc: Exception, status=status):
            return JSONResponse(status_code=status, content={"detail": str(exc)})
        app.add_exception_handler(error, handler)

    for module in (account, household, inventory, receipt, recipe, meal_plan, shopping, cost, command, notification):
        app.include_router(module.router)

    @app.get("/api/health")
    def health():
        return {"ok": True, "ai": facade.ai_status()}

    if WEB_DIST.exists():  # serve the built web app from the same server
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            file = WEB_DIST / path
            return FileResponse(file if path and file.is_file() else WEB_DIST / "index.html")
    return app


def main() -> None:
    import uvicorn
    uvicorn.run("server.api.app:create_app", factory=True, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
