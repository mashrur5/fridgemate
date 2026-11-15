"""Adapter: makes Google's Gemini REST API look like LLMClient.

Free Gemini keys have a small daily request limit per model, so the adapter takes a list of models:
when one model's quota is used up (HTTP 429) it moves on to the next one for the rest of the day."""
from __future__ import annotations

import base64
import logging
import time
from typing import Callable

import httpx

from server.infrastructure.llm.llm_client import Image, LLMClient, LLMResponse, LLMUnavailableError, Message, UsageMeter
from server.infrastructure.llm.retry_policy import RetryPolicy

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
QUOTA_PAUSE_SECONDS = 15 * 60  # skip a model this long after it reports "quota exceeded"
log = logging.getLogger("fridgemate.llm")


class _QuotaExceeded(Exception):
    pass


class GeminiClient(LLMClient):
    name = "gemini"

    def __init__(self, api_key: str, model: str, http: httpx.Client | None = None,
                 retry: RetryPolicy | None = None, temperature: float = 0.3, thinking_level: str = "",
                 fallback_models: list[str] | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.api_key = api_key
        self.models = [model] + [m for m in (fallback_models or []) if m and m != model]
        self.http = http or httpx.Client(timeout=60)
        self.retry = retry or RetryPolicy()
        self.temperature = temperature
        self.thinking_level = thinking_level  # "low" keeps answers fast; "" leaves the model's default
        self.usage = UsageMeter()
        self._clock = clock
        self._paused_until: dict[str, float] = {}
        self.last_model: str | None = None

    @property
    def model(self) -> str:
        return self.models[0]

    def _body(self, model: str, system: str, messages: list[Message], json_mode: bool,
              images: list[Image] | None) -> dict:
        contents = [{"role": "model" if m.role == "model" else "user", "parts": [{"text": m.text}]} for m in messages]
        if images and contents:
            contents[-1]["parts"] += [{"inline_data": {"mime_type": i.mime_type,
                                                       "data": base64.b64encode(i.data).decode()}} for i in images]
        config: dict = {"temperature": self.temperature}
        if json_mode:
            config["responseMimeType"] = "application/json"
        if self.thinking_level and "lite" not in model:  # lite models don't use thinking levels
            config["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
        return {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents, "generationConfig": config}

    def generate(self, system: str, messages: list[Message], json_mode: bool = True,
                 images: list[Image] | None = None) -> LLMResponse:
        now = self._clock()
        available = [m for m in self.models if self._paused_until.get(m, 0) <= now]
        if not available:
            raise LLMUnavailableError("the free Gemini quota is used up for now; please try again later")
        last_error: Exception | None = None
        for model in available:
            try:
                r = self._call(model, self._body(model, system, messages, json_mode, images))
            except _QuotaExceeded as e:
                log.warning("Gemini model %s is over its quota, trying the next model", model)
                self._paused_until[model] = self._clock() + QUOTA_PAUSE_SECONDS
                last_error = e
                continue
            except Exception as e:  # noqa: BLE001
                raise LLMUnavailableError(
                    f"Gemini is unavailable, please try again shortly ({e.__class__.__name__})") from e
            return self._read(model, r)
        raise LLMUnavailableError("the free Gemini quota is used up for now; please try again later") from last_error

    def _call(self, model: str, body: dict) -> httpx.Response:
        def call() -> httpx.Response:
            r = self.http.post(API.format(model=model), json=body, headers={"x-goog-api-key": self.api_key})
            if r.status_code == 429:
                raise _QuotaExceeded(model)  # retrying the same model won't help
            if r.status_code >= 500:  # "high demand": usually gone after a short wait
                r.raise_for_status()
            return r

        def retryable(e: Exception) -> bool:
            return isinstance(e, (httpx.TransportError, httpx.HTTPStatusError))

        return self.retry.run(call, retryable)

    def _read(self, model: str, r: httpx.Response) -> LLMResponse:
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
        self.last_model = model
        return response
