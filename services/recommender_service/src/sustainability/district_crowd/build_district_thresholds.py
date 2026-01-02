from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from pathlib import Path

ROOT_DATA_ROOT = Path("data/recommender_service")

SLTDA_ARRIVALS_MONTHLY = ROOT_DATA_ROOT / "clean/sltda_arrivals_monthly.csv"
BLENDED_SHARE_JSON = ROOT_DATA_ROOT / "clean/sustainability/district_share_blended.json"

OUT_DIR = ROOT_DATA_ROOT / "clean/sustainability"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMESTIC_MULTIPLIERS_JSON = ROOT_DATA_ROOT / "clean/crowd/domestic_multipliers.json"


# -----------------------------
# Robustness controls (defensible)
# -----------------------------
BASELINE_YEARS = (2018, 2019)

# Winsorization: cap both tails to reduce outlier influence (defensible “robust stats” choice)
WINSORIZE_LO = 0.02  # 2% lower tail
WINSORIZE_HI = 0.98  # 98% upper tail

# Minimum baseline samples per district to compute stable quantiles.
# For 2018–2019 monthly data you usually have 24 samples.
MIN_SAMPLES_PER_DISTRICT = 12

# Quantiles used for crowd levels / thresholds
QUANTILES = (0.25, 0.50, 0.75, 0.90)


def _load_domestic_multipliers() -> Dict[int, float]:
    obj = json.loads(DOMESTIC_MULTIPLIERS_JSON.read_text(encoding="utf-8"))
    # stored as {"1": 1.287, ...} -> convert to int keys
    return {int(k): float(v) for k, v in obj.items()}


def _load_blended_shares() -> Dict[str, float]:
    return json.loads(BLENDED_SHARE_JSON.read_text(encoding="utf-8"))


def _load_arrivals_monthly() -> pd.DataFrame:
    df = pd.read_csv(SLTDA_ARRIVALS_MONTHLY)
    # expected columns: date, arrivals (or similar)
    # try robust detection
    cols = {c.lower(): c for c in df.columns}
    date_col = cols.get("date") or cols.get("ds") or list(df.columns)[0]
    arr_col = cols.get("arrivals") or cols.get("total_arrivals") or cols.get("foreign_arrivals")
    if not arr_col:
        # last fallback: find something containing "arrival"
        for low, orig in cols.items():
            if "arrival" in low:
                arr_col = orig
                break
    if not arr_col:
        raise ValueError(f"Could not detect arrivals column in {SLTDA_ARRIVALS_MONTHLY}")

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).copy()

    df[arr_col] = pd.to_numeric(df[arr_col], errors="coerce")
    df = df.dropna(subset=[arr_col]).copy()

    df = df.rename(columns={date_col: "date", arr_col: "arrivals"})
    return df[["date", "arrivals"]].copy()


def _winsorize(values: List[float], lo_q: float = WINSORIZE_LO, hi_q: float = WINSORIZE_HI) -> List[float]:
    """
    Robustify thresholds by capping extreme baseline values.
    This makes p75/p90 defensible against one-off spikes.
    """
    s = pd.Series(values).dropna()
    if s.empty:
        return []
    lo = float(s.quantile(lo_q))
    hi = float(s.quantile(hi_q))
    s = s.clip(lower=lo, upper=hi)
    return [float(x) for x in s.tolist()]


def compute_thresholds(values: List[float]) -> Dict[str, float]:
    """
    Thresholds computed from robustified (winsorized) baseline distribution.
    """
    s = pd.Series(values).dropna()
    if s.empty:
        return {}
    return {
        "p25": float(s.quantile(0.25)),
        "p50": float(s.quantile(0.50)),
        "p75": float(s.quantile(0.75)),
        "p90": float(s.quantile(0.90)),
    }


def main() -> None:
    shares = _load_blended_shares()
    df = _load_arrivals_monthly()
    multipliers = _load_domestic_multipliers()

    # baseline years only
    y1, y2 = BASELINE_YEARS
    baseline = df[(df["date"].dt.year >= y1) & (df["date"].dt.year <= y2)].copy()
    if baseline.empty:
        raise ValueError("No 2018–2019 rows found in sltda_arrivals_monthly.csv")

    # collect district-level expected visitors time series (pressure-adjusted)
    district_series: Dict[str, List[float]] = {d: [] for d in shares.keys()}
    global_series: List[float] = []

    # sort ensures reproducibility (defensible)
    baseline = baseline.sort_values("date")

    for _, r in baseline.iterrows():
        total = float(r["arrivals"])
        dt = pd.to_datetime(r["date"])
        month = int(dt.month)
        m = float(multipliers.get(month, 1.0))

        for d, sh in shares.items():
            v_foreign = total * float(sh)
            v_pressure = v_foreign * m

            district_series[d].append(v_pressure)
            global_series.append(v_pressure)

    # -----------------------------
    # Robust thresholds (winsorized baseline)
    # -----------------------------
    district_thresholds: Dict[str, Dict[str, float]] = {}
    warnings: List[str] = []

    for d, vals in district_series.items():
        if len(vals) < MIN_SAMPLES_PER_DISTRICT:
            warnings.append(
                f"[warn] district '{d}' has only {len(vals)} baseline samples (<{MIN_SAMPLES_PER_DISTRICT}). thresholds may be unstable."
            )

        vals_w = _winsorize(vals)
        th = compute_thresholds(vals_w)
        if not th:
            warnings.append(f"[warn] district '{d}' thresholds empty (no valid data).")
        district_thresholds[d] = th

    global_series_w = _winsorize(global_series)
    global_thresholds = compute_thresholds(global_series_w)

    # -----------------------------
    # Save outputs
    # -----------------------------
    out_district = OUT_DIR / "district_thresholds_pressure_2018_2019.json"
    out_global = OUT_DIR / "global_thresholds_pressure_2018_2019.json"
    out_meta = OUT_DIR / "thresholds_pressure_build_meta.json"

    out_district.write_text(
        json.dumps(district_thresholds, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    out_global.write_text(
        json.dumps(global_thresholds, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Defensible metadata (so you can justify methodology in the report)
    meta = {
        "baseline_years": list(BASELINE_YEARS),
        "baseline_rows_used": int(len(baseline)),
        "district_count": int(len(shares)),
        "quantiles": [float(q) for q in QUANTILES],
        "winsorization": {
            "enabled": True,
            "lower_quantile": float(WINSORIZE_LO),
            "upper_quantile": float(WINSORIZE_HI),
            "rationale": "Reduce outlier influence in baseline distribution; improves robustness of p75/p90 thresholds.",
        },
        "domestic_multiplier": {
            "file": str(DOMESTIC_MULTIPLIERS_JSON).replace("\\", "/"),
            "applied_per_month": True,
            "rationale": "District crowd pressure includes domestic tourism seasonality; multiplier inflates foreign-only baseline into total pressure.",
        },
        "shares_file": str(BLENDED_SHARE_JSON).replace("\\", "/"),
        "arrivals_file": str(SLTDA_ARRIVALS_MONTHLY).replace("\\", "/"),
        "warnings": warnings,
    }

    out_meta.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # print warnings (still succeeds)
    for w in warnings:
        print(w)

    print("[ok] Saved thresholds to:", OUT_DIR)
    print("[ok] district:", out_district)
    print("[ok] global  :", out_global)
    print("[ok] meta    :", out_meta)


if __name__ == "__main__":
    main()
