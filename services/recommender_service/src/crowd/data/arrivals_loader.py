from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd

from configs.recommender_service.config import SLTDA_ARRIVALS_MONTHLY_CSV


@dataclass(frozen=True)
class SLTDAMonthlyArrivals:
    """
    Standardized monthly arrivals dataset.
    df columns:
      - date (Timestamp at month start)
      - year (int)
      - month (int 1..12)
      - arrivals (int)  # foreign arrivals count
    """
    df: pd.DataFrame


def _find_arrivals_column(cols: List[str]) -> Optional[str]:
    """
    Try to detect the arrivals column name in a robust way.
    Supports common variations.
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
    ]
    lower_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]
    return None


def load_sltda_arrivals_monthly(path: Path = SLTDA_ARRIVALS_MONTHLY_CSV) -> SLTDAMonthlyArrivals:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"SLTDA arrivals monthly CSV not found: {p}")

    df = pd.read_csv(p)

    # Normalize column names (strip spaces)
    df.columns = [c.strip() for c in df.columns]

    # ---- Detect year & month columns ----
    # Common: year, month
    year_col = None
    month_col = None
    for c in df.columns:
        lc = c.lower()
        if lc in ["year", "yyyy"]:
            year_col = c
        if lc in ["month", "mm", "month_no", "month_num"]:
            month_col = c

    # Sometimes there is a 'date' column already
    date_col = None
    for c in df.columns:
        if c.lower() == "date":
            date_col = c

    if date_col:
        df["date"] = pd.to_datetime(df[date_col], errors="coerce")
        df["year"] = df["date"].dt.year
        df["month"] = df["date"].dt.month
    else:
        if year_col is None or month_col is None:
            raise ValueError(
                f"Cannot find year/month columns in {p.name}. "
                f"Columns found: {list(df.columns)}. "
                f"Expected either a 'date' column or ('year' and 'month')."
            )
        df["year"] = pd.to_numeric(df[year_col], errors="coerce")
        df["month"] = pd.to_numeric(df[month_col], errors="coerce")

        # Build a proper month-start date
        df["date"] = pd.to_datetime(
            df["year"].astype("Int64").astype(str) + "-" + df["month"].astype("Int64").astype(str) + "-01",
            errors="coerce",
        )

    # ---- Detect arrivals column ----
    arrivals_col = _find_arrivals_column(list(df.columns))
    if arrivals_col is None:
        raise ValueError(
            f"Cannot detect arrivals column in {p.name}. "
            f"Columns found: {list(df.columns)}. "
            f"Rename the arrivals column to one of: arrivals / total_arrivals / foreign_arrivals."
        )

    df["arrivals"] = pd.to_numeric(df[arrivals_col], errors="coerce").fillna(0).astype(int)

    # Keep only needed cols
    df = df[["date", "year", "month", "arrivals"]].dropna(subset=["date"])
    df = df.sort_values("date")

    return SLTDAMonthlyArrivals(df=df)


data = load_sltda_arrivals_monthly().df
# nothing else


