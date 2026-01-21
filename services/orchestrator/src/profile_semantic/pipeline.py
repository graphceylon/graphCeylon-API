from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from .db import db_conn
from .settings import EMBED_BATCH_SIZE, EMBED_EVENT_TYPES
from .doc_builder import build_doc
from .embedder import embed_texts, vector_literal
from psycopg.types.json import Jsonb
from .interest_updater import update_interest_vector


def get_cursor(conn, user_id: str) -> Optional[datetime]:
    row = conn.execute(
        "SELECT last_embedded_at FROM profile_embedding_cursor WHERE user_id=%s",
        (user_id,),
    ).fetchone()
    return row[0] if row else None

def set_cursor(conn, user_id: str, ts: datetime) -> None:
    conn.execute(
        """
        INSERT INTO profile_embedding_cursor(user_id, last_embedded_at)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO UPDATE SET last_embedded_at=EXCLUDED.last_embedded_at
        """,
        (user_id, ts),
    )

def fetch_events(conn, user_id: str, since: Optional[datetime], limit: int) -> List[Tuple]:
    if since is None:
        return conn.execute(
            """
            SELECT id, session_id, created_at, event_type, intent, payload
            FROM profile_events
            WHERE user_id=%s AND event_type = ANY(%s)
            ORDER BY created_at ASC
            LIMIT %s
            """,
            (user_id, EMBED_EVENT_TYPES, limit),
        ).fetchall()

    return conn.execute(
        """
        SELECT id, session_id, created_at, event_type, intent, payload
        FROM profile_events
        WHERE user_id=%s AND created_at > %s AND event_type = ANY(%s)
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (user_id, since, EMBED_EVENT_TYPES, limit),
    ).fetchall()

def run_embed_pipeline(user_id: str, limit: int = 500) -> Dict[str, Any]:
    with db_conn() as conn:
        conn.autocommit = False
        since = get_cursor(conn, user_id)
        events = fetch_events(conn, user_id, since, limit)

        if not events:
            return {"ok": True, "embedded": 0, "cursor": since}

        docs, built = [], []
        for (eid, session_id, created_at, event_type, intent, payload) in events:
            doc_text, meta = build_doc(event_type, intent, payload)
            built.append((eid, session_id, created_at, event_type, doc_text, meta))
            docs.append(doc_text)

        embedded = 0
        for i in range(0, len(docs), EMBED_BATCH_SIZE):
            batch_docs = docs[i:i+EMBED_BATCH_SIZE]
            vecs = embed_texts(batch_docs)
            for j, v in enumerate(vecs):
                (eid, session_id, created_at, event_type, doc_text, meta) = built[i+j]
                conn.execute(
                    """
                    INSERT INTO profile_memory_embeddings
                    (user_id, session_id, event_id, event_type, created_at, doc_text, meta, embedding)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, session_id, eid, event_type, created_at, doc_text, Jsonb(meta), vector_literal(v)),
                )
                embedded += 1

        new_cursor = events[-1][2]
        set_cursor(conn, user_id, new_cursor)
        conn.commit()
        update_interest_vector(user_id=user_id, n=200, half_life_days=14.0)
        return {"ok": True, "embedded": embedded, "cursor": new_cursor}
