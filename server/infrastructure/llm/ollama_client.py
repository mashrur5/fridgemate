"""Adapter: makes a local Ollama server look like LLMClient (backup model)."""
from __future__ import annotations

import base64

import httpx

from server.infrastructure.llm.llm_client import Image, LLMClient, LLMResponse, LLMUnavailableError, Message, UsageMeter


class OllamaClient(LLMClient):
    name = "ollama"

    def __init__(self, base_url: str, model: str, http: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.http = http or httpx.Client(timeout=120)
        self.usage = UsageMeter()

    def generate(self, system: str, messages: list[Message], json_mode: bool = True,
                 images: list[Image] | None = None) -> LLMResponse:
        chat = [{"role": "system", "content": system}]
        chat += [{"role": "assistant" if m.role == "model" else "user", "content": m.text} for m in messages]
        if images and len(chat) > 1:
            chat[-1]["images"] = [base64.b64encode(i.data).decode() for i in images]
        body = {"model": self.model, "messages": chat, "stream": False, **({"format": "json"} if json_mode else {})}
        try:
            r = self.http.post(f"{self.base_url}/api/chat", json=body)
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            raise LLMUnavailableError(f"Ollama is unavailable ({e.__class__.__name__})") from e
        response = LLMResponse(data["message"]["content"], data.get("prompt_eval_count", 0), data.get("eval_count", 0))
        self.usage.record(response)
        return response
