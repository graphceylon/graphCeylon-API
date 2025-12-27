from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List, Tuple

import pandas as pd
from pathlib import Path

from services.recommender_service.src.sustainability.district_crowd.district_pressure_builder import (
    DistrictPressurePaths,
    build_all_district_pressure_artifacts,
)


# -------------------------
# Paths (match your Windows repo layout)
# -------------------------
from pathlib import Path

ROOT_DATA_ROOT = Path("data/recommender_service")
SERVICE_DATA_ROOT = Path("services/recommender_service/data/recommender_service")

# KG (attractions)
ATTRACTIONS_JSON = SERVICE_DATA_ROOT / "clean/kg/attractions_clean.json"

# Evidence sources
TELECOM_2024 = ROOT_DATA_ROOT / "clean/telecom/district_counts_2024.csv"
TOURIST_2017_XLSX = ROOT_DATA_ROOT / "raw/data_raw/sltda_arrivals/tourist2017.xlsx"
TOURIST_PREF_BY_COUNTRY_XLSX = ROOT_DATA_ROOT / "raw/data_raw/sltda_arrivals/tourist_preferences_by_country.xlsx"

# Output
OUT_DIR = ROOT_DATA_ROOT / "clean/sustainability"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------
# Helpers
# -------------------------
def _normalize_district_name(s: str) -> str:
    # Keep it simple but consistent; expand if your raw files have messy naming.
    s = str(s).strip()
    # common cleanup
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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
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
    # Your KG shape is: {"attractions": [ {...}, {...} ]}
    if isinstance(obj, dict) and "attractions" in obj and isinstance(obj["attractions"], list):
        for x in obj["attractions"]:
            if isinstance(x, dict):
                yield x
        return

    # fallback support
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
# 2024 telecom share
# -------------------------
def build_share_2024_telecom(known_districts: Optional[List[str]] = None) -> Dict[str, float]:
    df = pd.read_csv(TELECOM_2024)
    dcol = _detect_col(df, ["district"])
    ccol = _detect_col(df, ["number_of_tourists", "tourists", "count", "total", "n", "value"])

    if not dcol or not ccol:
        raise ValueError(f"Could not detect district/count columns in {TELECOM_2024}")

    counts: Dict[str, float] = {}
    for _, row in df.iterrows():
        d = _normalize_district_name(row[dcol])
        v = float(row[ccol]) if pd.notna(row[ccol]) else 0.0
        if known_districts and d not in set(known_districts):
            # if your telecom includes extra regions, ignore them
            continue
        counts[d] = counts.get(d, 0.0) + max(v, 0.0)

    return _to_share_dict_from_counts(counts)


# -------------------------
# 2017 share (tourist2017.xlsx)
# -------------------------
def build_share_2017(known_districts: Optional[List[str]] = None) -> Dict[str, float]:
    xls = pd.ExcelFile(TOURIST_2017_XLSX)
    # Use first sheet by default; adjust if you know the sheet name
    df = pd.read_excel(xls, sheet_name=xls.sheet_names[0])

    dcol = _detect_col(df, ["district", "destination", "place", "location"])
    vcol = _detect_col(df, ["count", "visitors", "total", "n", "preference", "value", "percentage", "percent", "share"])
    if not dcol or not vcol:
        raise ValueError(f"Could not detect district/value columns in {TOURIST_2017_XLSX}")

    raw: Dict[str, float] = {}
    for _, row in df.iterrows():
        d = _normalize_district_name(row[dcol])
        v = row[vcol]
        if pd.isna(d) or pd.isna(v):
            continue
        if known_districts and d not in set(known_districts):
            continue

        val = float(v)
        raw[d] = raw.get(d, 0.0) + max(val, 0.0)

    # If the column was percentages already, normalization still works safely.
    return _to_share_dict_from_counts(raw)


# -------------------------
# 2018-2019 share (tourist_preferences_by_country.xlsx)
# -------------------------
def build_share_2018_2019(known_districts: Optional[List[str]] = None) -> Dict[str, float]:
    xls = pd.ExcelFile(TOURIST_PREF_BY_COUNTRY_XLSX)
    # If your file has separate sheets per year, we will try to load anything that contains 2018 or 2019
    sheets = [s for s in xls.sheet_names if ("2018" in s) or ("2019" in s)]
    if not sheets:
        # fallback: just first sheet
        sheets = [xls.sheet_names[0]]

    combined: Dict[str, float] = {}
    for sh in sheets:
        df = pd.read_excel(xls, sheet_name=sh)

        dcol = _detect_col(df, ["district", "destination", "place", "location"])
        vcol = _detect_col(df, ["count", "visitors", "total", "n", "preference", "value", "percentage", "percent", "share"])
        if not dcol or not vcol:
            continue

        for _, row in df.iterrows():
            d = _normalize_district_name(row[dcol])
            v = row[vcol]
            if pd.isna(d) or pd.isna(v):
                continue
            if known_districts and d not in set(known_districts):
                continue
            combined[d] = combined.get(d, 0.0) + max(float(v), 0.0)

    if not combined:
        raise ValueError(f"Could not parse any usable 2018/2019 sheets in {TOURIST_PREF_BY_COUNTRY_XLSX}")

    return _to_share_dict_from_counts(combined)


# -------------------------
# Blend: 0.6*2024 + 0.3*2018_2019 + 0.1*2017
# -------------------------
def blend_shares(share_2024: Dict[str, float], share_1819: Dict[str, float], share_2017: Dict[str, float]) -> Dict[str, float]:
    districts = set(share_2024) | set(share_1819) | set(share_2017)
    blended: Dict[str, float] = {}
    for d in districts:
        blended[d] = (
            0.6 * float(share_2024.get(d, 0.0)) +
            0.3 * float(share_1819.get(d, 0.0)) +
            0.1 * float(share_2017.get(d, 0.0))
        )
    return _to_share_dict_from_counts(blended)


def main() -> None:
    known = load_known_districts_from_kg()

    s2024 = build_share_2024_telecom(known_districts=known)
    s2017 = build_share_2017(known_districts=known)
    s1819 = build_share_2018_2019(known_districts=known)
    sblend = blend_shares(s2024, s1819, s2017)

    _save_json(s2017, OUT_DIR / "district_share_2017.json")
    _save_json(s1819, OUT_DIR / "district_share_2018_2019.json")
    _save_json(s2024, OUT_DIR / "district_share_2024_telecom.json")
    _save_json(sblend, OUT_DIR / "district_share_blended.json")

    print("[ok] Saved district shares to:", OUT_DIR)

def main() -> None:
    paths = DistrictPressurePaths(
        telecom_2024_csv=Path("data/recommender_service/clean/telecom/district_counts_2024.csv"),
        prefs_2017_xlsx=Path("data/recommender_service/raw/data_raw/sltda_arrivals/tourist2017.xlsx"),
        prefs_2018_2019_xlsx=Path("data/recommender_service/raw/data_raw/sltda_arrivals/tourist_preferences_by_country.xlsx"),
        out_dir=Path("data/recommender_service/clean/sustainability"),
    )
    out = build_all_district_pressure_artifacts(paths)
    print(out)

if __name__ == "__main__":
    main()
