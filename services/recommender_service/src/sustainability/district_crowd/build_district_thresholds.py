from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


from pathlib import Path

ROOT_DATA_ROOT = Path("data/recommender_service")

SLTDA_ARRIVALS_MONTHLY = ROOT_DATA_ROOT / "clean/sltda_arrivals_monthly.csv"
BLENDED_SHARE_JSON = ROOT_DATA_ROOT / "clean/sustainability/district_share_blended.json"

OUT_DIR = ROOT_DATA_ROOT / "clean/sustainability"
OUT_DIR.mkdir(parents=True, exist_ok=True)




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

    df[date_col] = pd.to_datetime(df[date_col])
    df = df.rename(columns={date_col: "date", arr_col: "arrivals"})
    return df[["date", "arrivals"]].copy()


def compute_thresholds(values: List[float]) -> Dict[str, float]:
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

    # baseline years only
    baseline = df[(df["date"].dt.year >= 2018) & (df["date"].dt.year <= 2019)].copy()
    if baseline.empty:
        raise ValueError("No 2018–2019 rows found in sltda_arrivals_monthly.csv")

    # collect district-level expected visitors time series
    district_series: Dict[str, List[float]] = {d: [] for d in shares.keys()}
    global_series: List[float] = []

    for _, r in baseline.iterrows():
        total = float(r["arrivals"])
        for d, sh in shares.items():
            v = total * float(sh)
            district_series[d].append(v)
            global_series.append(v)

    district_thresholds = {d: compute_thresholds(vals) for d, vals in district_series.items()}
    global_thresholds = compute_thresholds(global_series)

    (OUT_DIR / "district_thresholds_2018_2019.json").write_text(
        json.dumps(district_thresholds, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT_DIR / "global_thresholds_2018_2019.json").write_text(
        json.dumps(global_thresholds, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("[ok] Saved thresholds to:", OUT_DIR)


if __name__ == "__main__":
    main()
