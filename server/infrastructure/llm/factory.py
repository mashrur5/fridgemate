"""Factory Method: the LLM is chosen by configuration in one place."""
from __future__ import annotations

from server.config import Config
from server.infrastructure.llm.gemini_client import GeminiClient
from server.infrastructure.llm.llm_client import LLMClient, UnavailableLLMClient
from server.infrastructure.llm.ollama_client import OllamaClient


class LLMClientFactory:
    def __init__(self, config: Config) -> None:
        self.config = config

    def create_client(self) -> LLMClient:
        provider = self.config.llm_provider
        if provider == "ollama":
            return OllamaClient(self.config.ollama_url, self.config.ollama_model)
        if provider == "gemini":
            if not self.config.gemini_api_key:
                return UnavailableLLMClient("AI is not set up: add GEMINI_API_KEY to your .env file")
            return GeminiClient(self.config.gemini_api_key, self.config.gemini_model,
                                thinking_level=self.config.gemini_thinking,
                                fallback_models=[m.strip() for m in self.config.gemini_fallback_models.split(",")])
        if provider == "none":
            return UnavailableLLMClient("AI is turned off (LLM_PROVIDER=none)")
        raise ValueError(f"unknown LLM_PROVIDER: {provider}")
