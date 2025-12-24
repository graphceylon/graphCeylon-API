from __future__ import annotations
import re

def norm_district(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"\s+", " ", s)

    # Optional alias fixes (add as needed)
    aliases = {
        "nuwara eliya": "nuwara-eliya",
        "nuwara-eliya": "nuwara-eliya",
        "matale": "matale",
        "galle": "galle",
    }
    return aliases.get(s, s)
