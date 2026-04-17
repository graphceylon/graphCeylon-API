from __future__ import annotations
import json
from uuid import UUID, uuid4
from typing import Any, Dict, Optional
import psycopg

def _json(v: Any):
    return psycopg.types.json.Json(v)

class BookingDraftRepo:
    def __init__(self, dsn: str):
        self.dsn = dsn

    def create_draft(self, payload: Dict[str, Any]) -> UUID:
        draft_id = uuid4()
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO booking_drafts (
                      draft_id, user_id, session_id, status,
                      city, arrival, departure, adults,
                      property_id, property_code, property_name,
                      room_category_id, room_type_id, meal_plan_id, rate_code_id,
                      currency_id, currency_code,
                      adult_rate, price_breakdown, raw_payload
                    )
                    VALUES (
                      %(draft_id)s, %(user_id)s, %(session_id)s, 'DRAFT',
                      %(city)s, %(arrival)s, %(departure)s, %(adults)s,
                      %(property_id)s, %(property_code)s, %(property_name)s,
                      %(room_category_id)s, %(room_type_id)s, %(meal_plan_id)s, %(rate_code_id)s,
                      %(currency_id)s, %(currency_code)s,
                      %(adult_rate)s, %(price_breakdown)s, %(raw_payload)s
                    )
                    """,
                    {
                        "draft_id": draft_id,
                        "user_id": str(payload["user_id"]),
                        "session_id": payload.get("session_id"),
                        "city": payload.get("city"),
                        "arrival": payload["arrival"],
                        "departure": payload["departure"],
                        "adults": int(payload.get("adults") or 2),
                        "property_id": payload.get("property_id"),
                        "property_code": payload.get("property_code"),
                        "property_name": payload.get("property_name"),
                        "room_category_id": payload["room_category_id"],
                        "room_type_id": payload["room_type_id"],
                        "meal_plan_id": payload["meal_plan_id"],
                        "rate_code_id": payload.get("rate_code_id"),
                        "currency_id": payload.get("currency_id"),
                        "currency_code": payload.get("currency_code"),
                        "adult_rate": payload.get("adult_rate"),
                        "price_breakdown": _json(payload.get("price_breakdown") or []),
                        "raw_payload": _json(payload.get("raw_payload") or {}),
                    },
                )
        return draft_id
    def update_draft(self, draft_id: UUID, payload: Dict[str, Any]) -> None:
        print("\n----- [REPO update_draft] START -----")
        print(f"[repo.update_draft] draft_id={draft_id}")
        print(f"[repo.update_draft] payload keys={list(payload.keys())}")
        print(f"[repo.update_draft] arrival={payload.get('arrival')}")
        print(f"[repo.update_draft] departure={payload.get('departure')}")
        print(f"[repo.update_draft] adults={payload.get('adults')}")
        print(f"[repo.update_draft] property_code={payload.get('property_code')}")
        print(f"[repo.update_draft] room_category_id={payload.get('room_category_id')}")
        print(f"[repo.update_draft] room_type_id={payload.get('room_type_id')}")
        print(f"[repo.update_draft] meal_plan_id={payload.get('meal_plan_id')}")

        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE booking_drafts SET
                        city            = %(city)s,
                        arrival         = %(arrival)s,
                        departure       = %(departure)s,
                        adults          = %(adults)s,
                        property_id     = %(property_id)s,
                        property_code   = %(property_code)s,
                        property_name   = %(property_name)s,
                        room_category_id = %(room_category_id)s,
                        room_type_id    = %(room_type_id)s,
                        meal_plan_id    = %(meal_plan_id)s,
                        rate_code_id    = %(rate_code_id)s,
                        currency_code   = %(currency_code)s,
                        adult_rate      = %(adult_rate)s,
                        price_breakdown = %(price_breakdown)s,
                        raw_payload     = %(raw_payload)s,
                        status          = 'DRAFT',
                        updated_at      = now()
                    WHERE draft_id = %(draft_id)s
                    """,
                    {
                        "draft_id": str(draft_id),
                        "city": payload.get("city"),
                        "arrival": payload["arrival"],
                        "departure": payload["departure"],
                        "adults": int(payload.get("adults") or 2),
                        "property_id": payload.get("property_id"),
                        "property_code": payload.get("property_code"),
                        "property_name": payload.get("property_name"),
                        "room_category_id": payload["room_category_id"],
                        "room_type_id": payload["room_type_id"],
                        "meal_plan_id": payload["meal_plan_id"],
                        "rate_code_id": payload.get("rate_code_id"),
                        "currency_code": payload.get("currency_code"),
                        "adult_rate": payload.get("adult_rate"),
                        "price_breakdown": _json(payload.get("price_breakdown") or []),
                        "raw_payload": _json(payload.get("raw_payload") or {}),
                    },
                )
                print(f"[repo.update_draft] rows_affected={cur.rowcount}")

            conn.commit()
            print("[repo.update_draft] commit done")

    print("----- [REPO update_draft] END -----\n")
    def get_status(self, draft_id: UUID) -> Optional[str]:
        print(f"[repo.get_status] checking draft_id={draft_id}")
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM booking_drafts WHERE draft_id=%s", (str(draft_id),))
                row = cur.fetchone()
                print(f"[repo.get_status] row={row}")
                return row[0] if row else None

    def set_status(self, draft_id: UUID, status: str, **fields: Any) -> None:
        # fields can include approved_by, approval_reason, rejected_reason, confirmed_ref
        sets = ["status=%(status)s", "updated_at=now()"]
        params: Dict[str, Any] = {"status": status, "draft_id": str(draft_id)}
        for k, v in fields.items():
            sets.append(f"{k}=%({k})s")
            params[k] = v
        sql = f"UPDATE booking_drafts SET {', '.join(sets)} WHERE draft_id=%(draft_id)s"
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)

    def fetch_draft_payload(self, draft_id: UUID) -> Optional[Dict[str, Any]]:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT raw_payload FROM booking_drafts WHERE draft_id=%s",
                    (str(draft_id),),
                )
                row = cur.fetchone()
                return row[0] if row else None