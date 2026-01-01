# # # call_orchestrator(payload) -> response_json

# services/language_service/src/orchestrator_client/client.py
from __future__ import annotations

from typing import Any, Dict, Optional, Union
import os
import httpx


class OrchestratorClient:
    """
    Minimal HTTP client to call Orchestrator.
    If orchestrator isn't running, returns a stub response instead of crashing.
    """

    def __init__(self, base_url: Optional[str] = None, timeout_s: float = 20.0):
        self.base_url = base_url or os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8002")
        self.timeout_s = timeout_s

    async def orchestrate(self, payload: Any) -> Dict[str, Any]:
        """
        Accepts either:
        - a dict
        - a Pydantic model (with model_dump/dict)
        and forwards to orchestrator route.
        """
        if isinstance(payload, dict):
            data = payload
        elif hasattr(payload, "model_dump"):   # pydantic v2
            data = payload.model_dump()
        elif hasattr(payload, "dict"):         # pydantic v1
            data = payload.dict()
        else:
            raise TypeError(f"Unsupported payload type: {type(payload)}")

        return await self.plan(data)

    async def plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calls orchestrator endpoint. Adjust path if your orchestrator route differs.
        """
        url = f"{self.base_url.rstrip('/')}/orchestrate"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                r = await client.post(url, json=payload)
                r.raise_for_status()
                return r.json()
        except Exception as e:
            return {
                "status": "fallback",
                "message": "Orchestrator unavailable or endpoint mismatch.",
                "error": str(e),
                "echo": payload,
            }
