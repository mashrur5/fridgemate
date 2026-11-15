"""FridgemateClient: the CLI's gateway to the API (the CLI never touches the database or the LLM)."""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from cli.token_store import TokenStore

DEFAULT_URL = "http://127.0.0.1:8000"


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class FridgemateClient:
    def __init__(self, base_url: Optional[str] = None, store: Optional[TokenStore] = None,
                 http: Optional[httpx.Client] = None) -> None:
        self.base_url = (base_url or os.getenv("FRIDGEMATE_URL", DEFAULT_URL)).rstrip("/")
        self.store = store or TokenStore()
        self.http = http or httpx.Client(timeout=180)

    def request(self, method: str, path: str, json: Any = None, params: Optional[dict] = None,
                files: Optional[dict] = None, auth: bool = True) -> Any:
        headers = {}
        if auth:
            token = self.store.load()
            if not token:
                raise ApiError(401, "you are not logged in; run: fridgemate login")
            headers["Authorization"] = f"Bearer {token}"
        try:
            r = self.http.request(method, self.base_url + path, json=json, params=params, files=files, headers=headers)
        except httpx.TransportError:
            raise ApiError(0, f"couldn't connect to the Fridgemate server at {self.base_url}. "
                              "Is it running? (python -m server)") from None
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail")
                if isinstance(detail, list):  # validation errors from FastAPI
                    detail = "; ".join(f"{'.'.join(str(x) for x in d.get('loc', [])[1:])}: {d.get('msg')}" for d in detail)
            except ValueError:
                detail = r.text
            if r.status_code == 401 and auth:
                detail = f"{detail}. Run: fridgemate login"
            raise ApiError(r.status_code, str(detail))
        return r.json() if r.content else None

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, json=None, **kw):
        return self.request("POST", path, json=json, **kw)

    def patch(self, path, json=None, **kw):
        return self.request("PATCH", path, json=json, **kw)

    def put(self, path, json=None, **kw):
        return self.request("PUT", path, json=json, **kw)

    def delete(self, path, **kw):
        return self.request("DELETE", path, **kw)
