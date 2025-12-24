from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd

from configs.recommender_service.config import DATA_CLEAN_DIR
from src.crowd.data.arrivals_loader import load_sltda_arrivals_monthly

# -------------------------------------------------
# PRIMARY (preferred) SARIMA forecast file/column
# -------------------------------------------------
SARIMA_FORECAST_CSV = DATA_CLEAN_DIR.parent / "forecast" / "sltda_arrivals_sarima_forecast.csv"
SARIMA_FORECAST_COL = "forecast_total_arrivals"

# -------------------------------------------------
# FAN-BACK candidates (used only if SARIMA fails)
# -------------------------------------------------
# Each candidate is: (path, list_of_possible_columns, source_label)
FANBACK_CANDIDATES: List[Tuple[Path, List[str], str]] = [
    (
        DATA_CLEAN_DIR.parent / "forecast" / "sltda_arrivals_hybrid_arima_sarima.csv",
        ["forecast_hybrid", "forecast_total_arrivals", "forecast", "arrivals"],
        "hybrid_forecast",
    ),
    (
        DATA_CLEAN_DIR.parent / "forecast" / "sltda_arrivals_arima_forecast.csv",
        ["forecast_total_arrivals", "arrivals_forecast", "forecast", "arrivals"],
        "arima_forecast",
    ),
    (
        DATA_CLEAN_DIR / "arrivals" / "sarima_arrivals_forecast.csv",
        ["arrivals_forecast", "forecast_total_arrivals", "forecast", "arrivals"],
        "sarima_forecast",
    ),
    (
        Path("models/recommender_service/sltda_arrivals_hybrid_arima_sarima.csv"),
        ["forecast_hybrid", "forecast_total_arrivals", "forecast_sarima", "forecast_arima"],
        "hybrid_forecast",
    ),
]


@dataclass(frozen=True)
class ArrivalsResolution:
    month_start: date
    arrivals: int
    source: str  # "sarima_forecast" | "hybrid_forecast" | "arima_forecast" | "historical_baseline"


def _month_start_ts(d: date) -> pd.Timestamp:
    return pd.Timestamp(d.year, d.month, 1)


def _debug(msg: str):
    print(f"[arrivals_resolver] {msg}")


def _try_read_forecast_file(path: Path, col_candidates: List[str], month_start: date, source: str) -> Optional[ArrivalsResolution]:
    p = Path(path)

    _debug(f"trying source='{source}' file={p}")
    _debug(f"exists={p.exists()}")

    if not p.exists():
        return None

    try:
        df = pd.read_csv(p)
    except Exception as e:
        _debug(f"FAILED to read CSV: {e}")
        return None

    # protect against spaces
    df.columns = [c.strip() for c in df.columns]
    _debug(f"columns={df.columns.tolist()}")

    if "date" not in df.columns:
        _debug("missing 'date' column")
        return None

    # select forecast column
    forecast_col = next((c for c in col_candidates if c in df.columns), None)
    if forecast_col is None:
        _debug(f"no matching forecast column found; candidates={col_candidates}")
        return None

    # parse dates -> month_start
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    nat = int(df["date"].isna().sum())
    _debug(f"NaT date count={nat}")
    df = df.dropna(subset=["date"]).copy()
    df["month_start"] = df["date"].dt.to_period("M").dt.to_timestamp()

    # numeric forecast
    df[forecast_col] = pd.to_numeric(df[forecast_col], errors="coerce")
    df = df.dropna(subset=[forecast_col]).copy()

    target = _month_start_ts(month_start)
    row = df[df["month_start"] == target]

    _debug(f"using_col='{forecast_col}' target={target} matched_rows={len(row)}")

    if row.empty:
        return None

    arrivals_int = int(round(float(row.iloc[0][forecast_col])))
    _debug(f"FOUND arrivals={arrivals_int} source={source}")

    return ArrivalsResolution(month_start=month_start, arrivals=arrivals_int, source=source)


def _try_read_sarima_primary(month_start: date) -> Optional[ArrivalsResolution]:
    # First priority: your real SARIMA file + exact column
    return _try_read_forecast_file(
        path=SARIMA_FORECAST_CSV,
        col_candidates=[SARIMA_FORECAST_COL],
        month_start=month_start,
        source="sarima_forecast",
    )


def resolve_total_foreign_arrivals_month(month_start: date) -> ArrivalsResolution:
    """
    Priority order:
      1) SARIMA primary file (strict)
      2) Fan-back forecast sources (hybrid/arima/etc.)
      3) Historical baseline (2018-2019 same-month mean)
    """

    _debug(f"resolve_total_foreign_arrivals_month month_start={month_start}")

    # 1) strict SARIMA
    res = _try_read_sarima_primary(month_start)
    if res is not None:
        return res

    # 2) fan-back
    _debug("SARIMA primary not found; entering fan-back candidates...")
    for path, cols, src in FANBACK_CANDIDATES:
        res = _try_read_forecast_file(path, cols, month_start, src)
        if res is not None:
            return res

    # 3) fallback baseline
    _debug("No forecast matched; falling back to historical baseline (2018-2019 same-month mean).")

    arr = load_sltda_arrivals_monthly().df.copy()
    base = arr[(arr["year"] >= 2018) & (arr["year"] <= 2019) & (arr["month"] == month_start.month)]

    if base.empty:
        fallback = int(arr["arrivals"].mean()) if not arr.empty else 0
        _debug(f"baseline empty; overall mean fallback={fallback}")
        return ArrivalsResolution(month_start, fallback, "historical_baseline")

    val = int(base["arrivals"].mean())
    _debug(f"baseline same-month mean={val}")
    return ArrivalsResolution(month_start, val, "historical_baseline")
