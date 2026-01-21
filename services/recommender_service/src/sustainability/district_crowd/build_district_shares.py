from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import pandas as pd

from services.recommender_service.src.sustainability.district_crowd.district_pressure_builder import (
    DistrictPressurePaths,
    build_all_district_pressure_artifacts,
)

# -------------------------
# Paths (match your Windows repo layout)
# -------------------------
ROOT_DATA_ROOT = Path("data/recommender_service")
ATTRACTIONS_JSON = ROOT_DATA_ROOT / "clean/kg/attractions_clean.json"

# Evidence sources (FIXED mapping based on your confirmation)
TELECOM_2024 = ROOT_DATA_ROOT / "raw/data_raw/sltda_arrivals/telecom_2024_district_counts.csv"

# NOTE: despite the name, you said this contains 2018–2019 data
TOURIST_2018_2019_XLSX = ROOT_DATA_ROOT / "raw/data_raw/sltda_arrivals/tourist2017.xlsx"

# NOTE: you said this contains 2017 data
TOURIST_2017_XLSX = ROOT_DATA_ROOT / "raw/data_raw/sltda_arrivals/tourist_preferences_by_country.xlsx"

# Output
OUT_DIR = ROOT_DATA_ROOT / "clean/sustainability"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# Helpers
# -------------------------
def _normalize_district_name(s: str) -> str:
    s = str(s).strip()
    s = s.replace("  ", " ")
    return s


def _to_share_dict_from_counts(counts: Dict[str, float]) -> Dict[str, float]:
    total = float(sum(max(v, 0.0) for v in counts.values()))
    if total <= 0:
        return {}
    shares = {k: float(v) / total for k, v in counts.items() if float(v) > 0}
    # renormalize after filtering
    ssum = sum(shares.values())
    if ssum > 0:
        shares = {k: v / ssum for k, v in shares.items()}
    return shares


def _save_json(obj: dict, path: Path) -> Path:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _detect_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols:
            return cols[cand.lower()]
    # fallback: contains match
    for low, orig in cols.items():
        for cand in candidates:
            if cand.lower() in low:
                return orig
    return None


# -------------------------
# Load KG districts (for optional filtering to known districts)
# -------------------------
def _iter_attractions(obj):
    if isinstance(obj, dict) and "attractions" in obj and isinstance(obj["attractions"], list):
        for x in obj["attractions"]:
            if isinstance(x, dict):
                yield x
        return

    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, dict):
                yield x
        return

    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, dict):
                yield v


def load_known_districts_from_kg() -> List[str]:
    obj = json.loads(ATTRACTIONS_JSON.read_text(encoding="utf-8"))
    dset = set()
    for r in _iter_attractions(obj):
        d = r.get("district")
        if d:
            dset.add(_normalize_district_name(d))
    return sorted(dset)


# -------------------------
# 2024 telecom share (district-level ✅)
# -------------------------
def build_share_2024_telecom(known_districts: Optional[List[str]] = None) -> Dict[str, float]:
    df = pd.read_csv(TELECOM_2024)
    dcol = _detect_col(df, ["district"])
    ccol = _detect_col(df, ["number_of_tourists", "tourists", "count", "total", "n", "value"])

    if not dcol or not ccol:
        raise ValueError(f"Could not detect district/count columns in {TELECOM_2024}. Columns={df.columns.tolist()}")

    known_set = set(known_districts) if known_districts else None

    counts: Dict[str, float] = {}
    for _, row in df.iterrows():
        d = _normalize_district_name(row[dcol])
        v = float(row[ccol]) if pd.notna(row[ccol]) else 0.0
        if known_set and d not in known_set:
            continue
        counts[d] = counts.get(d, 0.0) + max(v, 0.0)

    return _to_share_dict_from_counts(counts)


# -------------------------
# 2017 share (your file is Country -> POI columns ❌ not district)
# -------------------------
def build_share_2017(known_districts: Optional[List[str]] = None) -> Dict[str, float]:
    """
    tourist_preferences_by_country.xlsx is Country -> POI preference columns,
    NOT district-level. So it cannot produce district shares reliably.
    We return {} and blend falls back to telecom-only.
    """
    print(f"[info] {TOURIST_2017_XLSX} is Country->POI preferences (not district). Skipping for district shares.")
    return {}


# -------------------------
# 2018-2019 share (your file is Country -> POI columns ❌ not district)
# -------------------------
def build_share_2018_2019(known_districts: Optional[List[str]] = None) -> Dict[str, float]:
    """
    tourist2017.xlsx (as you said: 2018-2019 data) is also Country -> POI columns,
    NOT district-level. So it cannot produce district shares reliably.
    We return {} and blend falls back to telecom-only.
    """
    print(f"[info] {TOURIST_2018_2019_XLSX} is Country->POI preferences (not district). Skipping for district shares.")
    return {}


# -------------------------
# Blend: 0.6*2024 + 0.3*2018_2019 + 0.1*2017
# with safe fallback when older sources are empty
# -------------------------
def blend_shares(
    share_2024: Dict[str, float],
    share_1819: Dict[str, float],
    share_2017: Dict[str, float],
) -> Dict[str, float]:
    if not share_2024:
        raise ValueError("[FATAL] 2024 telecom shares empty - cannot build district shares.")

    if not share_1819 and not share_2017:
        print("[info] No usable district shares from 2017/2018-2019. Using telecom-only as blended.")
        return share_2024

    districts = set(share_2024) | set(share_1819) | set(share_2017)
    blended: Dict[str, float] = {}
    for d in districts:
        blended[d] = (
            0.6 * float(share_2024.get(d, 0.0)) +
            0.3 * float(share_1819.get(d, 0.0)) +
            0.1 * float(share_2017.get(d, 0.0))
        )
    return _to_share_dict_from_counts(blended)


def build_and_save_shares() -> None:
    known = load_known_districts_from_kg()

    s2024 = build_share_2024_telecom(known_districts=known)
    s2017 = build_share_2017(known_districts=known)
    s1819 = build_share_2018_2019(known_districts=known)
    sblend = blend_shares(s2024, s1819, s2017)

    # --- sanity checks ---
    if not s2024:
        print(f"[warn] 2024 telecom shares empty -> check: {TELECOM_2024}")
    if not s2017:
        print(f"[warn] 2017 shares empty (expected) -> {TOURIST_2017_XLSX}")
    if not s1819:
        print(f"[warn] 2018-2019 shares empty (expected) -> {TOURIST_2018_2019_XLSX}")
    if not sblend:
        raise ValueError("[FATAL] blended shares are empty. Telecom parsing failed.")

    ssum = sum(sblend.values())
    print("[check] blended share sum:", ssum)
    if not (0.99 <= ssum <= 1.01):
        print("[warn] blended shares do not sum ~1.0 (unexpected).")

    # save files
    _save_json(s2017, OUT_DIR / "district_share_2017.json")
    _save_json(s1819, OUT_DIR / "district_share_2018_2019.json")
    _save_json(s2024, OUT_DIR / "district_share_2024_telecom.json")
    _save_json(sblend, OUT_DIR / "district_share_blended.json")

    print("[ok] Saved district shares to:", OUT_DIR)


def main() -> None:
    # 1) Save shares
    build_and_save_shares()

    # 2) Build pressure artifacts (thresholds etc.)
    paths = DistrictPressurePaths(
        telecom_2024_csv=Path("data/recommender_service/raw/data_raw/sltda_arrivals/telecom_2024_district_counts.csv"),
        prefs_2017_xlsx=Path("data/recommender_service/raw/data_raw/sltda_arrivals/tourist_preferences_by_country.xlsx"),
        prefs_2018_2019_xlsx=Path("data/recommender_service/raw/data_raw/sltda_arrivals/tourist2017.xlsx"),
        out_dir=Path("data/recommender_service/clean/sustainability"),
    )

    out = build_all_district_pressure_artifacts(paths)
    print(out)


if __name__ == "__main__":
    main()
