from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd

# ----------------------------
# 1) YOUR FIXED MAPPINGS (as you approved)
# ----------------------------

# POI-level preference columns (fine-grained)
PREFERENCE_COLUMN_TO_DISTRICTS: Dict[str, List[str]] = {
    "adams peak": ["Ratnapura"],
    "dambulla cave temple": ["Matale"],
    "galle fort": ["Galle"],
    "other forts and light houses": ["Galle", "Jaffna", "Trincomalee"],
    "hakgala botanical gardens": ["Nuwara Eliya"],
    "horton plains": ["Nuwara Eliya", "Badulla"],
    "kataragama temple": ["Monaragala"],
    "little adams peak ella": ["Badulla"],
    "madhu church": ["Mannar"],
    "nallur kovil": ["Jaffna"],
    "peradeniya botanical garden": ["Kandy"],
    "pidurangala rock": ["Matale"],
    "pigeon island": ["Trincomalee"],
    "pinnawala elephant orphanage": ["Kegalle"],
    "religious/spiritual places of worship": ["Kandy", "Anuradhapura", "Polonnaruwa"],
    "ridiyagama safari park": ["Hambantota"],
    "ritigala": ["Anuradhapura"],
    "sigiriya rock fortress": ["Matale"],
    "sinharaja rain forest": ["Ratnapura", "Galle"],
    "temple of tooth relic": ["Kandy"],
    "waterfalls": ["Badulla", "Ratnapura", "Kegalle"],
    "yapahuwa rock": ["Kurunegala"],
    "zoological gardens colombo": ["Colombo"],
}

# Coarse SLTDA categories
CATEGORY_TO_DISTRICTS: Dict[str, List[str]] = {
    "Kandy": ["Kandy"],
    "Colombo_Shopping": ["Colombo"],
    "South_West_Coast_Beaches": ["Galle", "Matara", "Kalutara"],
    "Sigiriya": ["Matale"],
    "Dambulla": ["Matale"],
    "Wildlife_Parks": ["Hambantota", "Monaragala", "Puttalam", "Anuradhapura"],
    "Hill_Country": ["Nuwara Eliya", "Badulla", "Kandy"],
    "Polonnaruwa": ["Polonnaruwa"],
    "Anuradhapura": ["Anuradhapura"],
    "East_Coast_Beaches": ["Trincomalee", "Batticaloa", "Ampara"],
    "Beaches_North_of_Colombo": ["Gampaha", "Puttalam"],
    "Pinnawala": ["Kegalle"],
    "Waterfalls": ["Badulla", "Ratnapura", "Kegalle"],
    "Habarana": ["Anuradhapura"],
    "Golf_Courses": ["Colombo", "Kandy", "Nuwara Eliya"],
    "Other": [],  # special fallback: all districts later
    "Jaffna": ["Jaffna"],
}

# Canonical district names list you’ll support
# (We’ll build it from telecom file OR from mappings + arrivals + preferences)
# But we still handle "Other" as all districts discovered.
# ----------------------------


def _norm_col(s: str) -> str:
    return str(s).strip()


def _read_excel(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    # normalize col names only (keep original for readability)
    df.columns = [_norm_col(c) for c in df.columns]
    return df


def _find_country_col(cols: List[str]) -> Optional[str]:
    for c in cols:
        if str(c).strip().lower() == "country":
            return c
    return None


def _numeric_mean(series: pd.Series) -> float:
    s = pd.to_numeric(series, errors="coerce")
    return float(s.dropna().mean()) if s.notna().any() else 0.0


def extract_preference_means_from_excel(
    excel_path: Path,
    mapping_mode: str,
) -> Dict[str, float]:
    """
    Returns mean preference per COLUMN.
    mapping_mode:
      - "poi": expects columns like 'adams peak', 'galle fort', ...
      - "cat": expects columns like 'Kandy', 'Colombo_Shopping', ...
    """
    df = _read_excel(excel_path)

    country_col = _find_country_col(df.columns.tolist())
    if country_col:
        df = df.drop(columns=[country_col])

    # Clean: keep only columns that are in the intended mapping dictionary
    if mapping_mode == "poi":
        allowed = set(PREFERENCE_COLUMN_TO_DISTRICTS.keys())
    elif mapping_mode == "cat":
        allowed = set(CATEGORY_TO_DISTRICTS.keys())
    else:
        raise ValueError("mapping_mode must be 'poi' or 'cat'")

    means: Dict[str, float] = {}
    for col in df.columns:
        key = col.strip()
        # only accept exact name matches (research-safe)
        if key in allowed:
            means[key] = _numeric_mean(df[col])

    return means


def build_district_share_from_preferences(
    pref_means: Dict[str, float],
    mapping_mode: str,
    all_districts: List[str],
) -> Dict[str, float]:
    """
    Convert preference means (columns) into district shares.
    Split a column's preference equally across its mapped districts.
    Handle 'Other' (categories) as uniform across all districts.
    Finally normalize to sum=1.
    """
    if mapping_mode == "poi":
        mapping = PREFERENCE_COLUMN_TO_DISTRICTS
        other_key = None
    else:
        mapping = CATEGORY_TO_DISTRICTS
        other_key = "Other"

    dist_acc: Dict[str, float] = {d: 0.0 for d in all_districts}

    for col, val in pref_means.items():
        if val is None:
            continue
        v = float(val)

        if other_key and col == other_key:
            # spread "Other" uniformly across ALL districts
            if len(all_districts) > 0:
                add = v / len(all_districts)
                for d in all_districts:
                    dist_acc[d] += add
            continue

        dists = mapping.get(col, [])
        if not dists:
            continue

        add = v / len(dists)
        for d in dists:
            if d not in dist_acc:
                # include it if missing
                dist_acc[d] = 0.0
            dist_acc[d] += add

    total = sum(dist_acc.values())
    if total <= 0:
        # fallback: uniform
        n = len(dist_acc) if dist_acc else 1
        return {d: 1.0 / n for d in dist_acc}

    return {d: (v / total) for d, v in dist_acc.items()}


def load_telecom_2024_counts(path: Path) -> Tuple[Dict[str, float], List[str]]:
    """
    Reads telecom_2024_district_counts.csv and returns:
      - counts_by_district (float)
      - districts list
    Supports flexible column naming: district/name + count/visitors.
    """
    df = pd.read_csv(path)
    cols = [c.strip() for c in df.columns]

    # try common names
    district_col = None
    for cand in ["district", "District", "name", "Name"]:
        if cand in cols:
            district_col = cand
            break

    count_col = None
    for cand in [
        "count", "Count",
        "visitors", "Visitors",
        "value", "Value",
        "tourists", "Tourists",
        "Number_of_Tourists",   # ✅ your file
        "number_of_tourists",
        "num_tourists",
        "tourist_count",
    ]:
        if cand in cols:
            count_col = cand
            break


    if not district_col or not count_col:
        raise ValueError(f"telecom csv must have district+count cols. Found: {cols}")

    df[district_col] = df[district_col].astype(str).str.strip()
    df[count_col] = pd.to_numeric(df[count_col], errors="coerce").fillna(0.0)

    counts = dict(zip(df[district_col], df[count_col].astype(float)))
    districts = sorted(counts.keys())
    return counts, districts

def blend_shares(
    share_2024: Dict[str, float],
    share_2018_2019: Dict[str, float],
    share_2017: Dict[str, float],
    w2024: float = 0.6,
    w1819: float = 0.3,
    w2017: float = 0.1,
) -> Dict[str, float]:
    districts = set(share_2024) | set(share_2018_2019) | set(share_2017)
    out: Dict[str, float] = {}
    for d in districts:
        out[d] = (
            w2024 * float(share_2024.get(d, 0.0)) +
            w1819 * float(share_2018_2019.get(d, 0.0)) +
            w2017 * float(share_2017.get(d, 0.0))
        )
    # normalize
    total = sum(out.values())
    if total <= 0:
        n = len(out) if out else 1
        return {d: 1.0 / n for d in out}
    return {d: v / total for d, v in out.items()}


def save_json(path: Path, obj: dict) -> None:
    import json
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

def counts_to_share(counts: Dict[str, float]) -> Dict[str, float]:
    total = float(sum(counts.values()))
    if total <= 0:
        n = len(counts) if counts else 1
        return {k: 1.0 / n for k in counts}
    return {k: float(v) / total for k, v in counts.items()}


@dataclass(frozen=True)
class DistrictPressurePaths:
    telecom_2024_csv: Path
    prefs_2017_xlsx: Path
    prefs_2018_2019_xlsx: Path
    out_dir: Path


def build_all_district_pressure_artifacts(paths: DistrictPressurePaths) -> Dict[str, str]:
    """
    Outputs:
      - district_pressure_share_2024.json
      - district_pressure_share_2017_from_sltda_prefs.json
      - district_pressure_share_2018_2019_from_sltda_prefs.json
      - district_pressure_shares_all.json
      - district_pressure_shares_all.csv
      - PLUS minimal JSONs used by your new district crowd pipeline:
        district_share_2024_telecom.json
        district_share_2017.json
        district_share_2018_2019.json
        district_share_blended.json
    """
    paths.out_dir.mkdir(parents=True, exist_ok=True)

    # 2024 (telecom = ground truth)
    telecom_counts, telecom_districts = load_telecom_2024_counts(paths.telecom_2024_csv)
    share_2024 = counts_to_share(telecom_counts)

    # All districts baseline = telecom districts + anything in mappings
    extra = set()
    for v in PREFERENCE_COLUMN_TO_DISTRICTS.values():
        extra.update(v)
    for v in CATEGORY_TO_DISTRICTS.values():
        extra.update(v)
    extra.discard("")  # safety
    all_districts = sorted(set(telecom_districts).union(extra))

    # 2017 preferences (SLTDA) -> district share
    pref17_poi = extract_preference_means_from_excel(paths.prefs_2017_xlsx, mapping_mode="poi")
    pref17_cat = extract_preference_means_from_excel(paths.prefs_2017_xlsx, mapping_mode="cat")
    if len(pref17_poi) >= len(pref17_cat) and len(pref17_poi) > 0:
        share_2017 = build_district_share_from_preferences(pref17_poi, "poi", all_districts)
        mode_2017 = "poi"
    else:
        share_2017 = build_district_share_from_preferences(pref17_cat, "cat", all_districts)
        mode_2017 = "cat"

    # 2018-2019 preferences (SLTDA) -> district share
    pref18_poi = extract_preference_means_from_excel(paths.prefs_2018_2019_xlsx, mapping_mode="poi")
    pref18_cat = extract_preference_means_from_excel(paths.prefs_2018_2019_xlsx, mapping_mode="cat")
    if len(pref18_poi) >= len(pref18_cat) and len(pref18_poi) > 0:
        share_2018_2019 = build_district_share_from_preferences(pref18_poi, "poi", all_districts)
        mode_2018 = "poi"
    else:
        share_2018_2019 = build_district_share_from_preferences(pref18_cat, "cat", all_districts)
        mode_2018 = "cat"

    # ✅ Blended share (your research weighting)
    share_blended = blend_shares(share_2024, share_2018_2019, share_2017)

    # ✅ Save minimal JSONs expected by district crowd pipeline
    save_json(paths.out_dir / "district_share_2024_telecom.json", share_2024)
    save_json(paths.out_dir / "district_share_2017.json", share_2017)
    save_json(paths.out_dir / "district_share_2018_2019.json", share_2018_2019)
    save_json(paths.out_dir / "district_share_blended.json", share_blended)

    # Save “full” JSONs + CSV (your existing outputs)
    import json

    p_2024 = paths.out_dir / "district_pressure_share_2024.json"
    p_2017 = paths.out_dir / "district_pressure_share_2017_from_sltda_prefs.json"
    p_2018 = paths.out_dir / "district_pressure_share_2018_2019_from_sltda_prefs.json"
    p_all  = paths.out_dir / "district_pressure_shares_all.json"
    p_csv  = paths.out_dir / "district_pressure_shares_all.csv"

    p_2024.write_text(json.dumps({"year": 2024, "source": "telecom", "district_share": share_2024}, indent=2))
    p_2017.write_text(json.dumps({"year": 2017, "source": f"sltda_prefs_{mode_2017}", "district_share": share_2017}, indent=2))
    p_2018.write_text(json.dumps({"year": "2018_2019", "source": f"sltda_prefs_{mode_2018}", "district_share": share_2018_2019}, indent=2))

    all_obj = {
        "2024": {"source": "telecom", "district_share": share_2024},
        "2017": {"source": f"sltda_prefs_{mode_2017}", "district_share": share_2017},
        "2018_2019": {"source": f"sltda_prefs_{mode_2018}", "district_share": share_2018_2019},
        "blended": {"source": "0.6*2024 + 0.3*2018_2019 + 0.1*2017", "district_share": share_blended},
    }
    p_all.write_text(json.dumps(all_obj, indent=2))

    df = pd.DataFrame({"district": all_districts})
    df["share_2017"] = df["district"].map(share_2017).fillna(0.0)
    df["share_2018_2019"] = df["district"].map(share_2018_2019).fillna(0.0)
    df["share_2024"] = df["district"].map(share_2024).fillna(0.0)
    df["share_blended"] = df["district"].map(share_blended).fillna(0.0)
    df.to_csv(p_csv, index=False)

    return {
        "districts": str(len(all_districts)),
        "out_2024": str(p_2024),
        "out_2017": str(p_2017),
        "out_2018_2019": str(p_2018),
        "out_all_json": str(p_all),
        "out_all_csv": str(p_csv),
        "out_blended_json": str(paths.out_dir / "district_share_blended.json"),
    }
