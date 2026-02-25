from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Tuple, Type, TypeVar, Dict
import httpx

T = TypeVar("T")

@dataclass
class CallResult:
    ok: bool
    status_code: int
    data: Optional[dict] = None
    error: Optional[str] = None
    detail: Any = None

class RecommenderClient:
    def __init__(self, base_url: str, timeout_s: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(timeout_s, connect=3.0)
        self._client = httpx.Client(timeout=self.timeout)

    def post_json(self, path: str, payload: dict) -> CallResult:
        url = f"{self.base_url}{path}"
        try:
            resp = self._client.post(url, json=payload)
            status = resp.status_code

            # try parse json always
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text}

            if 200 <= status < 300:
                if isinstance(body, dict):
                    return CallResult(ok=True, status_code=status, data=body)
                return CallResult(ok=True, status_code=status, data={"value": body})

            return CallResult(
                ok=False,
                status_code=status,
                error=f"{status} {resp.reason_phrase}",
                detail=body,
            )

        except httpx.RequestError as e:
            return CallResult(
                ok=False,
                status_code=0,
                error=f"Network error: {type(e).__name__}: {e}",
                detail=None,
            )

    def close(self) -> None:
        self._client.close()