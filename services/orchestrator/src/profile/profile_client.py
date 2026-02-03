from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://127.0.0.1:8005").rstrip("/")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN")


class ProfileClient:
    def __init__(self, base_url: str | None = None, timeout: float = 6.0) -> None:
        self.base_url = (base_url or USER_SERVICE_URL).rstrip("/")
        self.timeout = timeout

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        user_id = (user_id or "").strip()
        if not user_id:
            return None

        # ✅ CORRECT endpoint path
        url = f"{self.base_url}/api/users/profile/{user_id}"

        headers = {}
        if SERVICE_TOKEN:
            headers["x-service-token"] = SERVICE_TOKEN  # ✅ internal auth bypass

        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, headers=headers)

        if r.status_code == 404:
            return None

        r.raise_for_status()

        data = r.json()

        # unwrap { success: true, data: {...} }
        if isinstance(data, dict) and "data" in data:
            return data["data"]

        return data
