from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

import os
import json
import psycopg


@dataclass
class TripPlanRow:
    trip_id: str
    user_id: str
    title: Optional[str]
    destination: Optional[str]
    start_date: Optional[str]
    travel_month: Optional[str]
    days: Optional[int]
    version: int
    plan_json: Dict[str, Any]


class TripRepo:
    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.getenv("ORCH_DB_DSN", "").strip()
        if not self.dsn:
            raise RuntimeError("ORCH_DB_DSN is not set")

    def create_trip(
        self,
        *,
        user_id: str,
        title: str,
        destination: Optional[str],
        start_date: Optional[str],
        travel_month: Optional[str],
        days: Optional[int],
        plan_json: Dict[str, Any],
    ) -> str:
        sql = """
        INSERT INTO trip_plans (user_id, title, destination, start_date, travel_month, days, plan_json)
        VALUES (%s, %s, %s, %s::date, %s::date, %s, %s::jsonb)
        RETURNING trip_id::text
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        user_id,
                        title,
                        destination,
                        start_date,
                        travel_month,
                        days,
                        json.dumps(plan_json, ensure_ascii=False),
                    ),
                )
                trip_id = cur.fetchone()[0]
            conn.commit()
        return trip_id

    def update_trip_plan(
        self,
        *,
        trip_id: str,
        plan_json: Dict[str, Any],
        title: Optional[str] = None,
        destination: Optional[str] = None,
        start_date: Optional[str] = None,
        travel_month: Optional[str] = None,
        days: Optional[int] = None,
    ) -> None:
        sql = """
        UPDATE trip_plans
        SET
          title = COALESCE(%s, title),
          destination = COALESCE(%s, destination),
          start_date = COALESCE(%s::date, start_date),
          travel_month = COALESCE(%s::date, travel_month),
          days = COALESCE(%s, days),
          plan_json = %s::jsonb,
          version = version + 1,
          updated_at = now()
        WHERE trip_id = %s::uuid
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        title,
                        destination,
                        start_date,
                        travel_month,
                        days,
                        json.dumps(plan_json, ensure_ascii=False),
                        trip_id,
                    ),
                )
            conn.commit()

    def get_trip(self, *, trip_id: str, user_id: str) -> Optional[TripPlanRow]:
        sql = """
        SELECT trip_id::text, user_id, title, destination,
               start_date::text, travel_month::text, days, version, plan_json
        FROM trip_plans
        WHERE trip_id = %s::uuid AND user_id = %s
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (trip_id, user_id))
                row = cur.fetchone()
                if not row:
                    return None
                return TripPlanRow(
                    trip_id=row[0],
                    user_id=row[1],
                    title=row[2],
                    destination=row[3],
                    start_date=row[4],
                    travel_month=row[5],
                    days=row[6],
                    version=row[7],
                    plan_json=row[8] if isinstance(row[8], dict) else {},
                )

    def list_trips(self, *, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        sql = """
        SELECT trip_id::text, title, destination, start_date::text, travel_month::text,
               days, version, updated_at::text
        FROM trip_plans
        WHERE user_id = %s
        ORDER BY updated_at DESC
        LIMIT %s
        """
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, limit))
                rows = cur.fetchall()

        return [
            {
                "trip_id": r[0],
                "title": r[1],
                "destination": r[2],
                "start_date": r[3],
                "travel_month": r[4],
                "days": r[5],
                "version": r[6],
                "updated_at": r[7],
            }
            for r in rows
        ]