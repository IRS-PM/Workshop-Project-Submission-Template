"""Client for the TypeSafe Jev System One API (POST /v1/systemone).

Used by the Jev reranker and the Jev judge. Nothing here falls back silently:
a missing key or a failed call raises, and the caller decides what that means.
"""

import os
import time
from collections.abc import Callable

import httpx

RETRYABLE_STATUS = {429, 529}
DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"


class JevConfigError(RuntimeError):
    """JEV_API_KEY is not set."""


class JevError(RuntimeError):
    """A Jev call failed and retrying did not help."""


def require_jev_key() -> str:
    key = os.getenv("JEV_API_KEY", "").strip()
    if not key:
        raise JevConfigError("JEV_API_KEY is not set")
    return key


def noul(instructions: str, when_true: str, when_false: str) -> dict:
    return {"type": "noul", "instructions": instructions,
            "criteria": {"true": when_true, "false": when_false}}


def score(instructions: str, levels: list[str]) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": levels}


class JevClient:
    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None,
                 transport: httpx.BaseTransport | None = None, max_attempts: int = 4,
                 sleep: Callable[[float], None] = time.sleep, timeout: float = 20.0):
        self.model = model or os.getenv("JEV_MODEL", DEFAULT_MODEL)
        self.url = (base_url or os.getenv("JEV_BASE_URL", DEFAULT_BASE_URL)).rstrip("/") + "/v1/systemone"
        self.max_attempts = max_attempts
        self.sleep = sleep
        self.http = httpx.Client(timeout=timeout, transport=transport,
                                 headers={"Authorization": f"Bearer {api_key}",
                                          "Content-Type": "application/json"})

    def ask(self, state, questions: dict) -> dict:
        """Return the `answers` map for the given questions about one state."""
        body = {"state": state, "model": self.model, "questions": questions}
        for attempt in range(self.max_attempts):
            try:
                response = self.http.post(self.url, json=body)
            except httpx.TransportError:
                if attempt + 1 == self.max_attempts:
                    raise JevError("Jev request failed: network error")
                self.sleep(0.5 * 2 ** attempt)
                continue
            if response.status_code == 200:
                return response.json()["answers"]
            if response.status_code in RETRYABLE_STATUS and attempt + 1 < self.max_attempts:
                self.sleep(0.5 * 2 ** attempt)
                continue
            raise JevError(f"Jev request failed with HTTP {response.status_code}")
        raise JevError("Jev request failed: retries exhausted")

    def close(self):
        self.http.close()
