"""Keeps the CLI's login token in the user's home folder (never in the project folder)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


class TokenStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(os.getenv("FRIDGEMATE_HOME", Path.home() / ".fridgemate")) / "token.json"

    def load(self) -> Optional[str]:
        try:
            return json.loads(self.path.read_text())["token"]
        except (OSError, ValueError, KeyError):
            return None

    def save(self, token: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"token": token}))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass
