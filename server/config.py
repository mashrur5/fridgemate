"""Reads settings from environment variables and the git-ignored .env file. Never hard-code keys."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Minimal .env reader: KEY=value lines; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Config:
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_thinking: str = "low"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    database_path: str = str(ROOT / "fridgemate.db")
    mealdb_api_key: str = "1"
    cors_origins: str = "http://localhost:5173"

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(env_file or ROOT / ".env")
        defaults = cls()
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", defaults.llm_provider).strip().lower(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            gemini_model=os.getenv("GEMINI_MODEL", defaults.gemini_model).strip(),
            gemini_thinking=os.getenv("GEMINI_THINKING", defaults.gemini_thinking).strip().lower(),
            ollama_url=os.getenv("OLLAMA_URL", defaults.ollama_url).strip(),
            ollama_model=os.getenv("OLLAMA_MODEL", defaults.ollama_model).strip(),
            database_path=os.getenv("DATABASE_PATH", defaults.database_path).strip(),
            mealdb_api_key=os.getenv("MEALDB_API_KEY", defaults.mealdb_api_key).strip(),
            cors_origins=os.getenv("CORS_ORIGINS", defaults.cors_origins).strip(),
        )
