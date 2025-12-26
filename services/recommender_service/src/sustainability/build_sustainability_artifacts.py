from __future__ import annotations

import json
import re
import calendar
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import numpy as np
import pandas as pd


# ----------------------------
# Helpers
# ----------------------------
def slug(s: str) -> str:
    s = str(s).lower().strip()
    s = s.replace("’", "'").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def pick_col(cols, candidates) -> Optional[str]:
    cols_lower = {str(c).lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None


def read_excel_clean(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing Excel file: {path}")
    df = pd.read_excel(path)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", na=False)]
    return df


def read_csv_clean(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV file: {path}")
    df = pd.read_csv(path)
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", na=False)]
    return df


# ----------------------------
# Config (YOUR repo paths)
# ----------------------------
@dataclass(frozen=True)
class BuildPaths:
    repo_root: Path

    attractions_json: Path
    arrivals_monthly_csv: Path
    telecom_district_csv: Path

    prefs_2018_2019_xlsx: Path
    prefs_2017_xlsx: Path

    out_dir: Path


def resolve_paths() -> BuildPaths:
    """
    Place this file at:
      services/recommender_service/src/sustainability/build_sustainability_artifacts.py

    Then repo root = parents[4].
    """
    repo_root = Path(__file__).resolve().parents[4]

    attractions_json = repo_root / "data/recommender_service/clean/kg/attractions_clean.json"
    arrivals_monthly_csv = repo_root / "data/recommender_service/clean/sltda_arrivals_monthly.csv"
    telecom_district_csv = repo_root / "data/recommender_service/raw/data_raw/sltda_arrivals/telecom_2024_district_counts.csv"

    prefs_2018_2019_xlsx = repo_root / "data/recommender_service/raw/data_raw/sltda_arrivals/tourist2017.xlsx"
    prefs_2017_xlsx = repo_root / "data/recommender_service/raw/data_raw/sltda_arrivals/tourist_preferences_by_country.xlsx"

    out_dir = repo_root / "data/recommender_service/clean/sustainability"

    return BuildPaths(
        repo_root=repo_root,
        attractions_json=attractions_json,
        arrivals_monthly_csv=arrivals_monthly_csv,
        telecom_district_csv=telecom_district_csv,
        prefs_2018_2019_xlsx=prefs_2018_2019_xlsx,
        prefs_2017_xlsx=prefs_2017_xlsx,
        out_dir=out_dir,
    )


# ----------------------------
# Core steps
# ----------------------------
def load_pois_from_attractions_clean(path: Path) -> pd.DataFrame:
    payload = json.loads(path.read_text(encoding="utf-8"))

    rows = payload.get("attractions") or payload.get("pois") or []
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No attractions found inside {path}. Expected key 'attractions'.")

    poi_df = pd.DataFrame(
        [
            {
                "poi_id": r.get("attraction_id") or r.get("poi_id") or r.get("id"),
                "title": r.get("title") or r.get("name"),
                "district": r.get("district"),
                "province": r.get("province"),
                "lat": r.get("lat"),
                "lng": r.get("lng"),
            }
            for r in rows
        ]
    )
    poi_df = poi_df.dropna(subset=["poi_id", "district"])
    poi_df["poi_id"] = poi_df["poi_id"].astype(str).str.strip().str.lower()
    poi_df["district_clean"] = (
        poi_df["district"].astype(str).str.strip().str.lower().str.replace(" ", "_")
    )
    return poi_df


def build_district_pressure_share(telecom_csv: Path) -> Dict[str, float]:
    """
    telecom_2024_district_counts.csv -> district_share_2024
    """
    df = read_csv_clean(telecom_csv)

    d_col = pick_col(df.columns, ["district"])
    n_col = pick_col(df.columns, ["number_of_tourists", "tourists", "count"])

    if not d_col or not n_col:
        raise ValueError(f"Telecom CSV missing columns. Found: {list(df.columns)}")

    df["district_clean"] = df[d_col].astype(str).str.strip().str.lower().str.replace(" ", "_")
    df["tourists"] = pd.to_numeric(df[n_col], errors="coerce")
    df = df.dropna(subset=["tourists"])
    df["district_share_2024"] = df["tourists"] / df["tourists"].sum()

    return df.set_index("district_clean")["district_share_2024"].to_dict()


def build_preference_means_from_excel(path: Path) -> pd.DataFrame:
    """
    Reads preference-by-country excel and returns:
      attraction_column, col_slug, mean_percent
    """
    df = read_excel_clean(path)

    # detect country column (optional)
    country_col = None
    for c in df.columns:
        if str(c).strip().lower() == "country":
            country_col = c
            break

    attraction_cols = [c for c in df.columns if c != country_col]

    mean_pref = df[attraction_cols].mean(numeric_only=True).dropna()
    out = mean_pref.reset_index()
    out.columns = ["attraction_column", "mean_percent"]
    out["col_slug"] = out["attraction_column"].map(slug)
    return out


def combine_preference_sources(prefs_2018_2019: Path, prefs_2017: Path) -> pd.DataFrame:
    """
    Combine 2017 and 2018/19 preference evidence:
      combined_mean = average( mean_2017, mean_1819 ) per attraction column slug (when both exist)
    Output:
      col_slug, attraction_column, combined_mean
    """
    a = build_preference_means_from_excel(prefs_2018_2019)
    b = build_preference_means_from_excel(prefs_2017)

    a = a.rename(columns={"mean_percent": "mean_1819"})
    b = b.rename(columns={"mean_percent": "mean_2017"})

    merged = pd.merge(
        a[["col_slug", "attraction_column", "mean_1819"]],
        b[["col_slug", "mean_2017"]],
        on="col_slug",
        how="outer",
    )

    # keep a readable column name for audit
    merged["attraction_column"] = merged["attraction_column"].fillna(merged["col_slug"])

    # average when both exist; otherwise use the available one
    merged["combined_mean"] = merged[["mean_1819", "mean_2017"]].mean(axis=1, skipna=True)
    merged = merged.dropna(subset=["combined_mean"])

    return merged[["col_slug", "attraction_column", "combined_mean", "mean_1819", "mean_2017"]]


def map_pois_to_preference(
    poi_df: pd.DataFrame,
    pref_df: pd.DataFrame,
) -> Tuple[Dict[str, float], pd.DataFrame]:
    """
    Map POIs to preference columns using slug matching.
    Returns:
      - preference_share_by_poi (sum to 1 across POIs)
      - audit_df
    """
    slug_to_mean = dict(zip(pref_df["col_slug"], pref_df["combined_mean"]))

    # For matching, we try poi_id slug and title slug.
    pref_slugs = set(slug_to_mean.keys())

    matches = []
    for _, r in poi_df.iterrows():
        pid = slug(r["poi_id"])
        title = slug(r.get("title") or "")

        matched_slug = None
        score = 0.0

        if pid in pref_slugs:
            matched_slug, score = pid, 1.0
        elif title in pref_slugs:
            matched_slug, score = title, 0.95
        else:
            # contains matching as weaker evidence
            for s in pref_slugs:
                if pid and pid in s:
                    matched_slug, score = s, 0.90
                    break
                if title and title in s:
                    matched_slug, score = s, 0.85
                    break

        mean_val = slug_to_mean.get(matched_slug) if matched_slug else np.nan
        matches.append(
            {
                "poi_id": r["poi_id"],
                "title": r.get("title"),
                "matched_preference_slug": matched_slug,
                "match_score": score,
                "combined_mean": mean_val,
            }
        )

    audit = pd.DataFrame(matches)

    # Fill missing POIs neutrally (documented assumption)
    # This avoids dropping POIs when the preference dataset has fewer columns than POIs.
    neutral = float(np.nanmean(audit["combined_mean"].values)) if np.isfinite(np.nanmean(audit["combined_mean"].values)) else 1.0
    audit["combined_mean_filled"] = audit["combined_mean"].fillna(neutral)

    # Convert to share across POIs (sum=1)
    audit["preference_share"] = audit["combined_mean_filled"] / audit["combined_mean_filled"].sum()

    pref_share = audit.set_index("poi_id")["preference_share"].to_dict()
    return pref_share, audit


def load_arrivals_monthly(arrivals_csv: Path) -> pd.DataFrame:
    df = read_csv_clean(arrivals_csv)

    date_col = pick_col(df.columns, ["date", "month", "ds"]) or df.columns[0]
    arr_col = pick_col(df.columns, ["arrivals", "total_arrivals", "foreign_arrivals", "total_foreign_arrivals"])

    if arr_col is None:
        # fallback: first non-date column
        arr_col = [c for c in df.columns if c != date_col][0]

    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df[arr_col] = pd.to_numeric(df[arr_col], errors="coerce")
    df = df.dropna(subset=[date_col, arr_col]).sort_values(date_col)

    df["month_start"] = df[date_col].dt.to_period("M").dt.to_timestamp()
    out = df.groupby("month_start")[arr_col].sum().reset_index()
    out.columns = ["month_start", "arrivals"]
    return out


def build_poi_monthly_visitors(
    poi_df: pd.DataFrame,
    arrivals_monthly: pd.DataFrame,
    district_share: Dict[str, float],
    pref_share: Dict[str, float],
) -> pd.DataFrame:
    rows = []
    for _, mrow in arrivals_monthly.iterrows():
        mstart_ts = pd.Timestamp(mrow["month_start"])
        mstart = mstart_ts.to_pydatetime().date()
        days = calendar.monthrange(mstart.year, mstart.month)[1]
        total_arrivals = float(mrow["arrivals"])

        for _, prow in poi_df.iterrows():
            pid = prow["poi_id"]
            dist = prow["district_clean"]
            d_share = float(district_share.get(dist, 0.0))
            p_share = float(pref_share.get(pid, 0.0))

            est_month = total_arrivals * d_share * p_share
            avg_daily = est_month / days if days else np.nan

            rows.append(
                {
                    "poi_id": pid,
                    "title": prow.get("title"),
                    "district": prow.get("district"),
                    "province": prow.get("province"),
                    "month_start": mstart.isoformat(),
                    "arrivals_month": total_arrivals,
                    "district_share_2024": d_share,
                    "preference_share": p_share,
                    "estimated_monthly_visitors": est_month,
                    "avg_daily_visitors": avg_daily,
                }
            )

    return pd.DataFrame(rows)


def build_capacity_baseline(
    poi_month: pd.DataFrame,
    target_pressure: float = 0.85,
) -> pd.DataFrame:
    """
    Capacity(p) = p95(avg_daily_visitors) / target_pressure
    This is a defendable operational approximation:
      - p95 = high-season daily load
      - dividing by 0.85 gives a "comfortable capacity" slightly above that load
    """
    p95 = poi_month.groupby("poi_id")["avg_daily_visitors"].quantile(0.95)
    capacity = p95 / float(target_pressure)

    cap_df = pd.DataFrame(
        {
            "poi_id": p95.index,
            "p95_daily_visitors": p95.values,
            "capacity_per_day": capacity.values,
        }
    )
    return cap_df


def add_sustainability_index(poi_month: pd.DataFrame, cap_df: pd.DataFrame) -> pd.DataFrame:
    cap_map = cap_df.set_index("poi_id")["capacity_per_day"].to_dict()
    poi_month = poi_month.copy()
    poi_month["capacity_per_day"] = poi_month["poi_id"].map(cap_map)

    # pressure ratio
    poi_month["pressure"] = poi_month["avg_daily_visitors"] / poi_month["capacity_per_day"]

    # bounded sustainability score
    poi_month["sustainability_index"] = 1.0 / (1.0 + poi_month["pressure"])

    def crowd_level(x):
        if pd.isna(x):
            return "Unknown"
        if x >= 0.90:
            return "High"
        if x >= 0.60:
            return "Medium"
        return "Low"

    poi_month["crowd_level"] = poi_month["pressure"].map(crowd_level)
    return poi_month


# ----------------------------
# Main
# ----------------------------
from services.recommender_service.src.sustainability.district_pressure_builder import (
    DistrictPressurePaths,
    build_all_district_pressure_artifacts,
)


def main() -> Dict[str, Any]:
    paths = resolve_paths()
    paths.out_dir.mkdir(parents=True, exist_ok=True)

    # Load POIs
    poi_df = load_pois_from_attractions_clean(paths.attractions_json)

    # District pressure share (telecom)
    district_share = build_district_pressure_share(paths.telecom_district_csv)

    # Preference shares (combine 2017 + 2018/19)
    pref_df = combine_preference_sources(paths.prefs_2018_2019_xlsx, paths.prefs_2017_xlsx)
    pref_share, pref_audit = map_pois_to_preference(poi_df, pref_df)

    # Monthly arrivals
    arrivals_monthly = load_arrivals_monthly(paths.arrivals_monthly_csv)

    # Build POI-month visitors
    poi_month = build_poi_monthly_visitors(poi_df, arrivals_monthly, district_share, pref_share)

    # Capacity baseline + sustainability
    cap_df = build_capacity_baseline(poi_month, target_pressure=0.85)
    poi_month = add_sustainability_index(poi_month, cap_df)

    # Write artifacts
    (paths.out_dir / "poi_master_from_attractions_clean.csv").write_text(
        poi_df.to_csv(index=False), encoding="utf-8"
    )

    (paths.out_dir / "district_pressure_share_2024.json").write_text(
        json.dumps({k: float(v) for k, v in district_share.items()}, indent=2),
        encoding="utf-8",
    )

    (paths.out_dir / "poi_preference_share.json").write_text(
        json.dumps({k: float(v) for k, v in pref_share.items()}, indent=2),
        encoding="utf-8",
    )

    (paths.out_dir / "poi_capacity_baseline.json").write_text(
        json.dumps(
            {k: float(round(v, 3)) for k, v in cap_df.set_index("poi_id")["capacity_per_day"].to_dict().items()},
            indent=2,
        ),
        encoding="utf-8",
    )

    poi_month.to_csv(paths.out_dir / "poi_monthly_visitors_and_sustainability.csv", index=False)
    pref_audit.to_csv(paths.out_dir / "poi_to_preference_column_mapping_audit.csv", index=False)

    telecom_2024_csv = (
    getattr(paths, "telecom_2024_csv", None)
    or getattr(paths, "telecom_district_counts_csv", None)
    or getattr(paths, "telecom_csv", None)
    )

    # If BuildPaths doesn't store it, fall back to your known repo location
    if telecom_2024_csv is None:
        telecom_2024_csv = Path("data/recommender_service/raw/data_raw/sltda_arrivals/telecom_2024_district_counts.csv")

    dp = DistrictPressurePaths(
        telecom_2024_csv=Path(telecom_2024_csv),
        prefs_2017_xlsx=Path(paths.prefs_2017_xlsx),
        prefs_2018_2019_xlsx=Path(paths.prefs_2018_2019_xlsx),
        out_dir=Path(paths.out_dir),
    )

    print("[sustainability] building district pressure shares (2017, 2018_2019, 2024)...")
    dp_out = build_all_district_pressure_artifacts(dp)
    print("[sustainability] district pressure done:", dp_out)

    return {
        "status": "ok",
        "poi_count": int(len(poi_df)),
        "months": int(len(arrivals_monthly)),
        "out_dir": str(paths.out_dir),
        "notes": (
            "Review 'poi_to_preference_column_mapping_audit.csv'. "
            "If many POIs are unmatched, consider adding a manual mapping layer "
            "(poi_id -> preference column) for stronger evidence."
        ),
    }


if __name__ == "__main__":
    print(main())
