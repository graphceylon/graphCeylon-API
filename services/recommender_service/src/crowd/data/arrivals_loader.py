from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd

from configs.recommender_service.config import SLTDA_ARRIVALS_MONTHLY_CSV


@dataclass(frozen=True)
class SLTDAMonthlyArrivals:
    """
    Standardized monthly arrivals dataset.
    Output df columns:
      - date (Timestamp at month start)
      - year (int)
      - month (int 1..12)
      - arrivals (int)  # foreign arrivals count
    """
    df: pd.DataFrame


def _norm(s: str) -> str:
    return str(s or "").strip()


def _lower_norm(s: str) -> str:
    return _norm(s).lower().replace(" ", "").replace("_", "").replace("-", "")


def _find_first(cols: List[str], candidates: List[str]) -> Optional[str]:
    """
    Find a column matching any candidate by normalized comparison.
    """
    norm_map = {_lower_norm(c): c for c in cols}
    for cand in candidates:
        key = _lower_norm(cand)
        if key in norm_map:
            return norm_map[key]
    return None


def _find_arrivals_column(cols: List[str]) -> Optional[str]:
    """
    Detect arrivals column robustly.
    """
    candidates = [
        "arrivals",
        "total_arrivals",
        "foreign_arrivals",
        "total_foreign_arrivals",
        "tourist_arrivals",
        "international_arrivals",
        "count",
        "value",
        "total",
        "number_of_tourists",
        "num_tourists",
    ]
    return _find_first(cols, candidates)


def _parse_month_from_text(s: str) -> Optional[int]:
    """
    Accept 'January', 'Jan', 'JAN', etc.
    """
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None

    # numeric month as string
    try:
        m = int(float(t))
        if 1 <= m <= 12:
            return m
    except Exception:
        pass

    # month name
    try:
        dt = pd.to_datetime(t, errors="coerce")
        if pd.notna(dt):
            return int(dt.month)
    except Exception:
        pass

    return None


def load_sltda_arrivals_monthly(path: Path = SLTDA_ARRIVALS_MONTHLY_CSV) -> SLTDAMonthlyArrivals:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"SLTDA arrivals monthly CSV not found: {p}")

    df = pd.read_csv(p)

    # Normalize column names (strip spaces)
    df.columns = [_norm(c) for c in df.columns]
    cols = list(df.columns)

    # ---- Detect date or year/month ----
    date_col = _find_first(cols, ["date", "month_start", "monthstart", "period", "timestamp"])
    year_col = _find_first(cols, ["year", "yyyy"])
    month_col = _find_first(cols, ["month", "mm", "month_no", "month_num", "monthnumber", "monthname"])

    if date_col:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
    else:
        if year_col is None or month_col is None:
            raise ValueError(
                f"Cannot find 'date' or ('year' and 'month') in {p.name}. "
                f"Columns found: {cols}"
            )

        df["year"] = pd.to_numeric(df[year_col], errors="coerce")

        # month can be numeric or text like 'Jan'
        if df[month_col].dtype == object:
            df["month"] = df[month_col].apply(_parse_month_from_text)
        else:
            df["month"] = pd.to_numeric(df[month_col], errors="coerce")

        # Build month-start date
        df["date"] = pd.to_datetime(
            df["year"].astype("Int64").astype(str) + "-" + df["month"].astype("Int64").astype(str) + "-01",
            errors="coerce",
        )

    # ---- Detect arrivals column ----
    arrivals_col = _find_arrivals_column(cols)
    if arrivals_col is None:
        raise ValueError(
            f"Cannot detect arrivals column in {p.name}. Columns found: {cols}. "
            f"Rename the arrivals column to something like 'arrivals' or 'foreign_arrivals'."
        )

    df["arrivals"] = pd.to_numeric(df[arrivals_col], errors="coerce").fillna(0).astype(int)

    # Keep only needed cols
    df = df[["date", "year", "month", "arrivals"]].dropna(subset=["date", "year", "month"]).copy()
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    df = df.sort_values("date")

    return SLTDAMonthlyArrivals(df=df)


# ✅ IMPORTANT:
# Do NOT load data at import time.
# If you want a quick manual test, run:
#   python -c "from services.recommender_service.src.crowd.data.arrivals_loader import load_sltda_arrivals_monthly; print(load_sltda_arrivals_monthly().df.head())"
