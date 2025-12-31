from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..core.settings import settings
from ..core.logging import get_logger
from ..core.errors import SessionStoreError
from .memory_store import MemoryStore

logger = get_logger("language_service.session_store")

DEFAULT_TTL_SECONDS = 60 * 60 * 6  # 6 hours


class SessionStore:
    """
    Memory session store + periodic JSON backup.
    Stores: session_id -> {"lang": "...", "mode": "...", "last_updated": ...}
    """

    def __init__(self):
        self._store = MemoryStore()
        self._writes = 0
        self._backup_every = int(getattr(settings, "SESSION_STORE_BACKUP_EVERY_N_WRITES", 10) or 10)

        self._backup_path = Path(settings.SESSION_STORE_BACKUP_PATH)
        self._backup_path.parent.mkdir(parents=True, exist_ok=True)

        self._load_backup()

    def _load_backup(self) -> None:
        if not self._backup_path.exists():
            return
        try:
            data = json.loads(self._backup_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for sid, payload in data.items():
                    if isinstance(payload, dict):
                        self._store.set(sid, payload, ttl_seconds=None)
            logger.info(f"Loaded session backup: {self._backup_path}")
        except Exception as e:
            logger.warning(f"Failed to load session backup: {e}")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        if not session_id:
            return None
        v = self._store.get(session_id)
        return v if isinstance(v, dict) else None

    def set_many(self, session_id: str, *, ttl_seconds: int = DEFAULT_TTL_SECONDS, **fields) -> None:
        if not session_id:
            raise SessionStoreError("session_id is required")

        cur = self.get_session(session_id) or {}
        cur.update(fields)
        cur["last_updated"] = int(time.time())

        self._store.set(session_id, cur, ttl_seconds=ttl_seconds)
        self._maybe_backup()

    def clear(self, session_id: str) -> None:
        if session_id:
            self._store.delete(session_id)

    def set_language(self, session_id: str, lang: str) -> None:
        self.set_many(session_id, lang=lang)

    def get_language(self, session_id: str) -> Optional[str]:
        s = self.get_session(session_id) or {}
        return s.get("lang")

    def set_mode(self, session_id: str, mode: str) -> None:
        self.set_many(session_id, mode=mode)

    def get_mode(self, session_id: str) -> Optional[str]:
        s = self.get_session(session_id) or {}
        return s.get("mode")

    def _maybe_backup(self) -> None:
        self._writes += 1
        if self._backup_every <= 0:
            return
        if self._writes % self._backup_every != 0:
            return

        try:
            blob = self._store.dump_all()
            self._backup_path.write_text(
                json.dumps(blob, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"Session backup written: {self._backup_path}")
        except Exception as e:
            logger.warning(f"Failed to write session backup: {e}")


session_store = SessionStore()
