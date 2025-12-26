# ✅ FILE: src/orchestrator_core/runtime/adapters/a2a.py
from __future__ import annotations

from typing import Any, Dict, Optional
import requests


class A2AHttpAdapter:
    """
    Direct agent-to-agent (service-to-service) HTTP invocation.
    Orchestrator chooses an agent from registry, then calls agent.base_url + endpoint.
    """

    def invoke(
        self,
        *,
        base_url: str,
        endpoint: str,
        payload: Dict[str, Any],
        timeout: int = 20,
    ) -> Optional[Dict[str, Any]]:
        url = f"{base_url.rstrip('/')}{endpoint}"
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json() if resp.content else None
