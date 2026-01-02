from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4
import os
import json
import psycopg

@dataclass
class ProfileEvent:
    user_id: str
    session_id: str
    event_type: str
    intent: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

class ProfileEventStore:
    def __init__(self) -> None:
        self.db_url = os.getenv("PROFILE_DB_URL")
        if not self.db_url:
            raise RuntimeError("PROFILE_DB_URL is not set")

    def append(self, e: ProfileEvent) -> None:
        payload_json = json.dumps(e.payload, ensure_ascii=False, default=str)

        try:
            with psycopg.connect(self.db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.profile_events
                        (id, user_id, session_id, created_at, event_type, intent, payload)
                        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            e.id,
                            e.user_id,
                            e.session_id,
                            e.created_at,
                            e.event_type,
                            e.intent,
                            payload_json,
                        ),
                    )
                conn.commit()
        except Exception as ex:
            # don’t crash orchestrator, but DO log
            print(f"Failed to append profile event: {ex}")
