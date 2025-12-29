from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, List

import math
import numpy as np
from psycopg.types.json import Jsonb

from .db import db_conn
from .settings import EMBED_DIM


@dataclass
class InterestUpdateResult:
    ok: bool
    user_id: str
    n_used: int
    updated_at: Optional[datetime]
    reason: str = ""


def _fetch_recent_embeddings(conn, user_id: str, n: int) -> List[tuple]:
    # newest first
    return conn.execute(
        """
        SELECT embedding::real[], created_at
        FROM profile_memory_embeddings
        WHERE user_id=%s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, n),
    ).fetchall()


def _compute_decay_weights(times: List[datetime], half_life_days: float) -> np.ndarray:
    # Exponential decay: weight halves every `half_life_days`
    # w = 0.5^(age/half_life)
    now = max(times)  # newest item time as reference (stable even if DB clock differs)
    hl_seconds = max(half_life_days, 0.001) * 86400.0

    ages = np.array([(now - t).total_seconds() for t in times], dtype=np.float32)
    w = np.power(0.5, ages / hl_seconds).astype(np.float32)
    w_sum = float(w.sum())
    if w_sum <= 0:
        return np.ones(len(times), dtype=np.float32) / max(len(times), 1)
    return w / w_sum


def update_interest_vector(
    user_id: str,
    *,
    n: int = 200,
    half_life_days: float = 14.0,
) -> InterestUpdateResult:
    """
    Computes a recency-weighted mean of the last N memory embeddings and upserts into profile_interest_vectors.
    """
    with db_conn() as conn:
        conn.autocommit = False

        rows = _fetch_recent_embeddings(conn, user_id, n)
        if not rows:
            return InterestUpdateResult(ok=True, user_id=user_id, n_used=0, updated_at=None, reason="no_embeddings")

        vecs = []
        times = []
        for emb, created_at in rows:
            arr = np.asarray(emb, dtype=np.float32)
            if arr.shape[0] != EMBED_DIM:
                raise RuntimeError(f"Dim mismatch in DB: got {arr.shape[0]} expected {EMBED_DIM}")
            vecs.append(arr)
            times.append(created_at)

        V = np.stack(vecs, axis=0)  # (n, dim)
        w = _compute_decay_weights(times, half_life_days)  # (n,)

        interest = (V * w[:, None]).sum(axis=0)

        # Normalize to unit vector (cosine space)
        norm = float(np.linalg.norm(interest))
        if norm > 0:
            interest = interest / norm

        meta: Dict[str, Any] = {
            "n_used": len(rows),
            "half_life_days": half_life_days,
            "source": "profile_memory_embeddings",
            "updated_at": datetime.utcnow().isoformat(),
        }

        # Upsert
        conn.execute(
            """
            INSERT INTO profile_interest_vectors (user_id, embedding, meta, updated_at)
            VALUES (%s, %s::vector, %s, now())
            ON CONFLICT (user_id) DO UPDATE
            SET embedding = EXCLUDED.embedding,
                meta = EXCLUDED.meta,
                updated_at = now()
            """,
            (user_id, _vector_literal(interest.tolist()), Jsonb(meta)),
        )
        conn.commit()

        # fetch updated_at back
        updated_at = conn.execute(
            "SELECT updated_at FROM profile_interest_vectors WHERE user_id=%s",
            (user_id,),
        ).fetchone()[0]

        return InterestUpdateResult(ok=True, user_id=user_id, n_used=len(rows), updated_at=updated_at, reason="updated")


def _vector_literal(v: List[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"
