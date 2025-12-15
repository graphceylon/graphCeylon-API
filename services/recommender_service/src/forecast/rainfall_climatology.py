# rainfall_climatology.py

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd


# ---------------------------
# 1) Make repo importable
# ---------------------------
repo_root = Path.cwd().resolve()
while repo_root.name != "graphCeylon-API" and repo_root != repo_root.parent:
    repo_root = repo_root.parent
sys.path.insert(0, str(repo_root))

from configs.recommender_service.config import WEATHER_RAW_DIR, DATA_CLEAN_DIR  # noqa: E402


# ---------------------------
# 2) Paths
# ---------------------------
HISTORY_FILE = WEATHER_RAW_DIR / "cleaned_history.csv"
OUT_CLIMATOLOGY = DATA_CLEAN_DIR / "rainfall_climatology.csv"


# ---------------------------
# 3) Helpers
# ---------------------------
def normalize_location_id(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.lower()
        .str.strip()
        .str.replace("’", "'", regex=False)
        .str.replace("'", "", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace(" ", "_", regex=False)
    )


def ensure_monthly_rainfall(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure monthly series:
    - Convert date to month-start timestamps
    - Sum rainfall within each month
    - Fill missing rainfall with 0 (optional, but consistent for climatology)
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "location_id", "rainfall"])

    df["location_id"] = normalize_location_id(df["location_id"])

    df["rainfall"] = pd.to_numeric(df["rainfall"], errors="coerce").fillna(0.0)
    df["rainfall"] = df["rainfall"].clip(lower=0)

    # month start
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp(how="start")

    # monthly aggregate
    df = (
        df.groupby(["location_id", "date"], as_index=False)
        .agg(rainfall=("rainfall", "sum"))
        .sort_values(["location_id", "date"])
    )

    # optional: reindex missing months for each location → rainfall=0
    out = []
    for loc, g in df.groupby("location_id"):
        start = g["date"].min()
        end = g["date"].max()
        idx = pd.date_range(start, end, freq="MS")
        g2 = g.set_index("date").reindex(idx)
        g2.index.name = "date"
        g2["location_id"] = loc
        g2["rainfall"] = g2["rainfall"].fillna(0.0).clip(lower=0)
        out.append(g2.reset_index())

    return pd.concat(out, ignore_index=True)


def safe_quantile(x: pd.Series, q: float) -> float:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) == 0:
        return float("nan")
    return float(x.quantile(q))


def build_rainfall_climatology(
    monthly_df: pd.DataFrame,
    percentiles=(0.25, 0.75, 0.90),
) -> pd.DataFrame:
    """
    Output columns:
    location_id, month, mean_rainfall, p25, p75, p90, n_years
    """
    df = monthly_df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.month

    # group by location + month across years
    rows = []
    for (loc, m), g in df.groupby(["location_id", "month"]):
        r = pd.to_numeric(g["rainfall"], errors="coerce").fillna(0.0).clip(lower=0)

        # Estimate how many years contribute for this month
        # (not perfect, but good signal)
        n_years = int(pd.to_datetime(g["date"]).dt.year.nunique())

        row = {
            "location_id": loc,
            "month": int(m),
            "mean_rainfall": float(r.mean()),
            "p25": safe_quantile(r, percentiles[0]),
            "p75": safe_quantile(r, percentiles[1]),
            "p90": safe_quantile(r, percentiles[2]),
            "n_years": n_years,
        }
        rows.append(row)

    clim = pd.DataFrame(rows).sort_values(["location_id", "month"]).reset_index(drop=True)

    # round for readability
    for c in ["mean_rainfall", "p25", "p75", "p90"]:
        clim[c] = clim[c].round(2)

    return clim


# ---------------------------
# 4) Risk classifier
# ---------------------------
RiskLabel = Literal["Dry", "Moderate", "Wet", "Extreme", "Unknown"]


@dataclass
class RainfallRiskResult:
    location_id: str
    month: int
    risk: RiskLabel
    mean_rainfall: float
    p25: float
    p75: float
    p90: float


class RainfallRiskClassifier:
    """
    Percentile-based risk:
      Dry      : rainfall < p25
      Moderate : p25 <= rainfall < p75
      Wet      : p75 <= rainfall < p90
      Extreme  : rainfall >= p90
    """

    def __init__(self, climatology_csv: Path):
        if not climatology_csv.exists():
            raise FileNotFoundError(f"Climatology not found: {climatology_csv}")

        self.clim = pd.read_csv(climatology_csv)
        self.clim["location_id"] = normalize_location_id(self.clim["location_id"])
        self.clim["month"] = self.clim["month"].astype(int)

        # fast lookup
        self._idx = self.clim.set_index(["location_id", "month"])

    def classify_from_value(self, location_id: str, month: int, rainfall_mm: float) -> RainfallRiskResult:
        location_id = normalize_location_id(pd.Series([location_id])).iloc[0]
        month = int(month)

        if (location_id, month) not in self._idx.index:
            return RainfallRiskResult(
                location_id=location_id,
                month=month,
                risk="Unknown",
                mean_rainfall=float("nan"),
                p25=float("nan"),
                p75=float("nan"),
                p90=float("nan"),
            )

        row = self._idx.loc[(location_id, month)]
        p25, p75, p90 = float(row["p25"]), float(row["p75"]), float(row["p90"])
        mean_r = float(row["mean_rainfall"])

        x = float(max(0.0, rainfall_mm))

        if np.isnan(p25) or np.isnan(p75) or np.isnan(p90):
            risk: RiskLabel = "Unknown"
        elif x < p25:
            risk = "Dry"
        elif x < p75:
            risk = "Moderate"
        elif x < p90:
            risk = "Wet"
        else:
            risk = "Extreme"

        return RainfallRiskResult(
            location_id=location_id,
            month=month,
            risk=risk,
            mean_rainfall=mean_r,
            p25=p25,
            p75=p75,
            p90=p90,
        )

    def classify_month(self, location_id: str, month: int) -> RainfallRiskResult:
        """
        If you don't want to predict mm at all:
        Use mean_rainfall as a reference point, and classify that month as "typical risk".
        (Most useful for tourism explanations.)
        """
        location_id = normalize_location_id(pd.Series([location_id])).iloc[0]
        month = int(month)

        if (location_id, month) not in self._idx.index:
            return RainfallRiskResult(
                location_id=location_id,
                month=month,
                risk="Unknown",
                mean_rainfall=float("nan"),
                p25=float("nan"),
                p75=float("nan"),
                p90=float("nan"),
            )

        row = self._idx.loc[(location_id, month)]
        mean_r = float(row["mean_rainfall"])
        return self.classify_from_value(location_id, month, mean_r)


# ---------------------------
# 5) Main runner
# ---------------------------
def main():
    print("History file:", HISTORY_FILE)
    print("Exists:", HISTORY_FILE.exists())
    if not HISTORY_FILE.exists():
        raise FileNotFoundError(f"Missing: {HISTORY_FILE} (run historical_loader first)")

    raw = pd.read_csv(HISTORY_FILE)

    monthly = ensure_monthly_rainfall(raw)
    print("Monthly rows:", len(monthly), "| Locations:", monthly["location_id"].nunique())

    clim = build_rainfall_climatology(monthly)
    DATA_CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    clim.to_csv(OUT_CLIMATOLOGY, index=False)
    print("✅ Saved climatology ->", OUT_CLIMATOLOGY)

    # quick sanity demo
    clf = RainfallRiskClassifier(OUT_CLIMATOLOGY)

    demo_loc = "bentota"
    demo_month = 7
    res = clf.classify_month(demo_loc, demo_month)

    print("\n--- Demo ---")
    print(f"Location: {demo_loc} | Month: {demo_month}")
    print("Mean rainfall:", res.mean_rainfall, "mm")
    print("p25/p75/p90:", res.p25, res.p75, res.p90)
    print("Risk:", res.risk)

    print("\nTop 10 wettest typical months (by mean):")
    print(clim.sort_values("mean_rainfall", ascending=False).head(10))


if __name__ == "__main__":
    main()
