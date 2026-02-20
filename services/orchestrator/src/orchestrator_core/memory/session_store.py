from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any, Dict

import redis

DEFAULT_TTL_SEC = 60 * 60 * 6  # 6 hours

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class SessionStore:
    def __init__(self, redis_url: str, prefix: str = "gc:sess:", ttl_sec: int = DEFAULT_TTL_SEC):
        self.r = redis.Redis.from_url(redis_url, decode_responses=True)
        self.prefix = prefix
        self.ttl_sec = ttl_sec

    def key(self, user_id: str, session_id: str) -> str:
        return f"{self.prefix}{user_id}:{session_id}"

    def load(self, user_id: str, session_id: str) -> Dict[str, Any]:
        k = self.key(user_id, session_id)
        raw = self.r.get(k)

        default_state = {
            "schema_version": "1.0",
            "conversation_stage": "discover",
            "last_intent": None,
            "slots": {},
            "last_tool_outputs_refs": {},
            "pending_actions": [],
            "updated_at": _now_iso(),
        }

        if not raw:
            return default_state

        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else default_state
        except Exception:
            return default_state

    # ✅ add this
    def get(self, *, user_id: str, session_id: str) -> Dict[str, Any]:
        return self.load(user_id=user_id, session_id=session_id)

    def save(self, user_id: str, session_id: str, state: Dict[str, Any]) -> None:
        k = self.key(user_id, session_id)
        state["updated_at"] = _now_iso()
        self.r.setex(k, self.ttl_sec, json.dumps(state, ensure_ascii=False))
