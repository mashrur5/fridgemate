"""Adapter: makes Google's Gemini REST API look like LLMClient."""
from __future__ import annotations

import base64

import httpx

from server.infrastructure.llm.llm_client import Image, LLMClient, LLMResponse, LLMUnavailableError, Message, UsageMeter
from server.infrastructure.llm.retry_policy import RetryPolicy

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiClient(LLMClient):
    name = "gemini"

    def __init__(self, api_key: str, model: str, http: httpx.Client | None = None,
                 retry: RetryPolicy | None = None, temperature: float = 0.3, thinking_level: str = "") -> None:
        self.api_key = api_key
        self.model = model
        self.http = http or httpx.Client(timeout=60)
        self.retry = retry or RetryPolicy()
        self.temperature = temperature
        self.thinking_level = thinking_level  # "low" keeps answers fast; "" leaves the model's default
        self.usage = UsageMeter()

    def generate(self, system: str, messages: list[Message], json_mode: bool = True,
                 images: list[Image] | None = None) -> LLMResponse:
        contents = [{"role": "model" if m.role == "model" else "user", "parts": [{"text": m.text}]} for m in messages]
        if images and contents:
            contents[-1]["parts"] += [{"inline_data": {"mime_type": i.mime_type,
                                                       "data": base64.b64encode(i.data).decode()}} for i in images]
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": self.temperature,
                                 **({"responseMimeType": "application/json"} if json_mode else {}),
                                 **({"thinkingConfig": {"thinkingLevel": self.thinking_level}}
                                    if self.thinking_level else {})},
        }

        def call() -> httpx.Response:
            r = self.http.post(API.format(model=self.model), json=body, headers={"x-goog-api-key": self.api_key})
            if r.status_code == 429 or r.status_code >= 500:
                r.raise_for_status()
            return r

        def retryable(e: Exception) -> bool:
            return isinstance(e, (httpx.TransportError, httpx.HTTPStatusError))

        try:
            r = self.retry.run(call, retryable)
        except Exception as e:  # noqa: BLE001
            raise LLMUnavailableError(f"Gemini is unavailable or rate limited, please try again shortly ({e.__class__.__name__})") from e
        if r.status_code != 200:
            raise LLMUnavailableError(f"Gemini returned HTTP {r.status_code}")
        data = r.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        except (KeyError, IndexError) as e:
            raise LLMUnavailableError("Gemini returned no answer (it may have been blocked)") from e
        usage = data.get("usageMetadata", {})
        response = LLMResponse(text, usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))
        self.usage.record(response)
        return response
