# in-memory store for demo/dev

from __future__ import annotations
import time
from typing import Any, Dict, Optional


class MemoryStore:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._data[key] = value
        if ttl_seconds is None:
            self._expiry.pop(key, None)
        else:
            self._expiry[key] = time.time() + ttl_seconds

    def get(self, key: str) -> Optional[Any]:
        if key in self._expiry and time.time() > self._expiry[key]:
            self.delete(key)
            return None
        return self._data.get(key)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._expiry.pop(key, None)

    def dump_all(self) -> Dict[str, Any]:
        # purge expired before dump
        now = time.time()
        for k in list(self._expiry.keys()):
            if time.time() > self._expiry[k]:
                self.delete(k)
        return dict(self._data)
