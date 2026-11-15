from __future__ import annotations

import time
from typing import Callable, TypeVar

T = TypeVar("T")


class RetryPolicy:
    """Retries short network problems and rate limits (HTTP 429/5xx) with a growing wait."""

    def __init__(self, attempts: int = 3, base_delay: float = 1.0, sleep: Callable[[float], None] = time.sleep):
        self.attempts = attempts
        self.base_delay = base_delay
        self._sleep = sleep

    def run(self, call: Callable[[], T], is_retryable: Callable[[Exception], bool]) -> T:
        for attempt in range(1, self.attempts + 1):
            try:
                return call()
            except Exception as error:  # noqa: BLE001 - decided by is_retryable
                if attempt == self.attempts or not is_retryable(error):
                    raise
                self._sleep(self.base_delay * 2 ** (attempt - 1))
        raise RuntimeError("unreachable")
