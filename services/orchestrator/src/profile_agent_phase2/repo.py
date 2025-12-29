from __future__ import annotations
from typing import Any, Dict, List, Optional
import asyncpg

class Phase2Repo:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def fetch_prefs_merged(self, *, user_id: str, limit: int, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if session_id:
            sql = """
            SELECT id, created_at, payload
            FROM profile_events
            WHERE user_id=$1 AND session_id=$2 AND event_type='prefs_merged'
            ORDER BY created_at DESC
            LIMIT $3
            """
            args = (user_id, session_id, limit)
        else:
            sql = """
            SELECT id, created_at, payload
            FROM profile_events
            WHERE user_id=$1 AND event_type='prefs_merged'
            ORDER BY created_at DESC
            LIMIT $2
            """
            args = (user_id, limit)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)

        # oldest -> newest
        payloads = []
        for r in reversed(rows):
            p = dict(r["payload"]) if r["payload"] else {}
            p["_event_id"] = int(r["id"])
            p["_created_at"] = r["created_at"].isoformat()
            payloads.append(p)
        return payloads

    async def insert_insight(
        self,
        *,
        user_id: str,
        window_start: Optional[str],
        window_end: Optional[str],
        patterns: Dict[str, Any],
        stability: Dict[str, float],
        drift: Dict[str, Any],
        suggestions: List[Dict[str, Any]],
        insight_meta: Dict[str, Any],
    ) -> int:
        sql = """
        INSERT INTO profile_insights (
          user_id, window_start, window_end,
          patterns, stability, drift, suggestions,
          insight_meta
        )
        VALUES ($1, $2::timestamptz, $3::timestamptz, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb)
        RETURNING id
        """
        async with self.pool.acquire() as conn:
            new_id = await conn.fetchval(
                sql, user_id, window_start, window_end,
                patterns, stability, drift, suggestions, insight_meta
            )
        return int(new_id)

    async def latest_insight(self, *, user_id: str) -> Optional[Dict[str, Any]]:
        sql = """
        SELECT id, user_id, computed_at, window_start, window_end,
               patterns, stability, drift, suggestions, insight_meta
        FROM profile_insights
        WHERE user_id=$1
        ORDER BY computed_at DESC
        LIMIT 1
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, user_id)
        return dict(row) if row else None
