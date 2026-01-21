# services/orchestrator/src/orchestrator_core/geo/region_resolver.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ✅ Canonical district names (match whatever you use in attractions_clean.json)
# Keep these in Title Case to avoid mismatches.
REGION_TO_DISTRICTS: Dict[str, List[str]] = {
    # --- Highlands / Hill Country ---
    "hill country": ["Kandy", "Matale", "Nuwara Eliya", "Badulla"],
    "upcountry": ["Kandy", "Matale", "Nuwara Eliya", "Badulla"],
    "central highlands": ["Kandy", "Matale", "Nuwara Eliya", "Badulla"],

    # --- Southern region ---
    "south": ["Galle", "Matara", "Hambantota"],
    "southern": ["Galle", "Matara", "Hambantota"],
    "southern coast": ["Galle", "Matara", "Hambantota"],

    # --- Cultural Triangle (common tourism macro-region) ---
    "cultural triangle": ["Anuradhapura", "Polonnaruwa", "Matale"],
    "ancient cities": ["Anuradhapura", "Polonnaruwa", "Matale"],

    # --- North / East / West (broad) ---
    "north": ["Jaffna", "Kilinochchi", "Mannar", "Mullaitivu", "Vavuniya"],
    "east": ["Trincomalee", "Batticaloa", "Ampara"],
    "west": ["Colombo", "Gampaha", "Kalutara"],

    # --- Other useful tourism regions ---
    "central province": ["Kandy", "Matale", "Nuwara Eliya"],
    "uva province": ["Badulla", "Moneragala"],
    "sabaragamuwa": ["Ratnapura", "Kegalle"],
}

# Optional: synonyms/normalization for user text
REGION_ALIASES: Dict[str, str] = {
    "hillcountry": "hill country",
    "hill-country": "hill country",
    "the hill country": "hill country",
    "up country": "upcountry",
    "southern province": "southern",
    "south coast": "southern coast",
}


@dataclass(frozen=True)
class RegionScope:
    """
    Output contract you can pass downstream to your recommender / KG query.
    """
    mode: str  # "city" | "region" | "country"
    region_key: Optional[str]
    districts: Optional[List[str]]
    debug: Dict[str, str]


def normalize_region_text(region: str) -> str:
    r = (region or "").strip().lower()
    r = r.replace(".", "").replace(",", "")
    # collapse whitespace
    r = " ".join(r.split())
    # apply alias mapping
    return REGION_ALIASES.get(r, r)


def resolve_region_scope(
    *,
    city: Optional[str],
    region: Optional[str],
    country: Optional[str] = None,
) -> RegionScope:
    """
    If city is present => city mode.
    Else if region is present => region mode with district list.
    Else => country mode (no filtering).
    """
    if city:
        return RegionScope(
            mode="city",
            region_key=None,
            districts=None,
            debug={"reason": "city_present", "city": city},
        )

    if region:
        key = normalize_region_text(region)
        districts = REGION_TO_DISTRICTS.get(key)

        if districts:
            return RegionScope(
                mode="region",
                region_key=key,
                districts=districts,
                debug={"reason": "region_mapped", "region_raw": region, "region_key": key},
            )

        # Unknown region string => fall back to country-level but keep debug
        return RegionScope(
            mode="country",
            region_key=key,
            districts=None,
            debug={"reason": "region_unmapped_fallback_country", "region_raw": region, "region_key": key},
        )

    return RegionScope(
        mode="country",
        region_key=None,
        districts=None,
        debug={"reason": "no_city_no_region"},
    )
