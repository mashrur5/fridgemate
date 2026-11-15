"""G5: every LLM answer must be JSON that matches a small schema."""
from __future__ import annotations

import json
import re
from typing import Any, Callable


class SchemaError(ValueError):
    pass


class ResponseParser:
    def parse_json(self, text: str) -> Any:
        text = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if fenced:
            text = fenced.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
            if start >= 0:
                try:
                    return json.loads(text[start:text.rfind("}" if text[start] == "{" else "]") + 1])
                except json.JSONDecodeError:
                    pass
            raise SchemaError("the answer was not valid JSON")

    def require(self, data: Any, schema: dict[str, type | tuple]) -> dict:
        """Check that data is an object with the required keys and types."""
        if not isinstance(data, dict):
            raise SchemaError("the answer must be a JSON object")
        for key, kind in schema.items():
            if key not in data:
                raise SchemaError(f"missing key '{key}'")
            if not isinstance(data[key], kind):
                raise SchemaError(f"'{key}' has the wrong type")
        return data

    def parse(self, text: str, validate: Callable[[Any], Any]) -> Any:
        return validate(self.parse_json(text))
