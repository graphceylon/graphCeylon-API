from __future__ import annotations

DISTRICT_TO_CITY = {
    "Colombo": "Colombo",
    "Gampaha": "Negombo",
    "Kalutara": "Kalutara",
    "Kandy": "Kandy",
    "Galle": "Galle",
    "Matale": "Dambulla",
    "Nuwara Eliya": "Nuwara Eliya",
    "Badulla": "Ella",
    "Trincomalee": "Trincomalee",
    "Jaffna": "Jaffna",
    # add gradually (safe fallback below)
}

def district_to_city(district: str) -> str:
    d = (district or "").strip()
    return DISTRICT_TO_CITY.get(d, d)  # fallback: use district as city
