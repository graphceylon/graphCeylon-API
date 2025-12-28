from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from datetime import date, datetime
from typing import Any

from datetime import date, datetime
from typing import Any

def _json_safe(obj: Any) -> Any:
    """Recursively convert objects into JSON-safe values (pydantic models, datetime, etc.)."""

    # ✅ Pydantic v2 models
    if hasattr(obj, "model_dump"):
        return _json_safe(obj.model_dump(exclude_none=True))

    # ✅ Pydantic v1 models (just in case)
    if hasattr(obj, "dict") and callable(getattr(obj, "dict")):
        try:
            return _json_safe(obj.dict(exclude_none=True))
        except TypeError:
            return _json_safe(obj.dict())

    # ✅ datetime/date
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # ✅ dict/list/tuple
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]

    return obj



PROFILE_AGENT_URL = os.getenv("PROFILE_AGENT_URL", "http://127.0.0.1:8007").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "")


class ProfileAgentClient:
    def __init__(self, base_url: str | None = None, timeout: float = 6.0) -> None:
        self.base_url = (base_url or PROFILE_AGENT_URL).rstrip("/")
        self.timeout = timeout

    def build_context(
        self,
        *,
        user_id: str,
        session_id: str,
        raw_text: str,
        parsed_intent: Optional[Dict[str, Any]] = None,
        query_overrides: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        user_id = (user_id or "").strip()
        if not user_id:
            return None

        url = f"{self.base_url}/v1/profile/context"

        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "raw_text": raw_text,
            "parsed_intent": parsed_intent or {},
            "query_overrides": query_overrides or {},
        }
        payload = _json_safe(payload)

        headers = {}
        if SERVICE_TOKEN:
            headers["x-service-token"] = SERVICE_TOKEN

        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json=payload, headers=headers)

        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def log_event(
        self,
        *,
        user_id: str,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        url = f"{self.base_url}/v1/profile/events"

        headers = {}
        if SERVICE_TOKEN:
            headers["x-service-token"] = SERVICE_TOKEN

        body = _json_safe({
            "user_id": (user_id or "").strip(),
            "session_id": (session_id or "").strip(),
            "event_type": event_type,
            "payload": payload,
        })


        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(url, json=body, headers=headers)

        r.raise_for_status()
