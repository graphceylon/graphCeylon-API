# Sinhala (si)
# Tamil (ta)
# Hindi (hi)
# Russian (ru)
# French (fr)
# English (en)

from __future__ import annotations
from typing import Dict, Tuple
import re

# Unicode ranges
_SI_RANGE = [(0x0D80, 0x0DFF)]  # Sinhala
_TA_RANGE = [(0x0B80, 0x0BFF)]  # Tamil
_HI_RANGE = [(0x0900, 0x097F)]  # Devanagari (Hindi)
_RU_RANGE = [(0x0400, 0x04FF)]  # Cyrillic (Russian)

# French hints
_FRENCH_CHARS = set("éèêëàâäîïôöùûüçœ")
_COMMON_FR_WORDS = {
    "le","la","les","un","une","des","et","je","vous","nous","pour","avec","pas","ne",
    "sur","au","aux","dans","est","sont","être","bonjour","merci"
}

def _count_in_ranges(text: str, ranges) -> int:
    c = 0
    for ch in text:
        o = ord(ch)
        for a, b in ranges:
            if a <= o <= b:
                c += 1
                break
    return c

def _latin_ratio(text: str) -> float:
    if not text:
        return 0.0
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return latin / max(len(text), 1)

def _is_likely_french(text: str) -> bool:
    t = text.lower()
    if any(ch in _FRENCH_CHARS for ch in t):
        return True
    words = [re.sub(r"[^\w']", "", w) for w in t.split()]
    score = sum(1 for w in words if w in _COMMON_FR_WORDS)
    return score >= 2

def language_percentages(text: str) -> Dict[str, float]:
    if not text:
        return {"en": 0.0, "si": 0.0, "ta": 0.0, "hi": 0.0, "ru": 0.0, "latin": 0.0}

    total = len(text)
    si = _count_in_ranges(text, _SI_RANGE)
    ta = _count_in_ranges(text, _TA_RANGE)
    hi = _count_in_ranges(text, _HI_RANGE)
    ru = _count_in_ranges(text, _RU_RANGE)

    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    other = max(total - (si + ta + hi + ru + latin), 0)

    return {
        "si": si / total,
        "ta": ta / total,
        "hi": hi / total,
        "ru": ru / total,
        "latin": latin / total,
        "other": other / total,
    }

def detect_language(text: str, default: str = "en") -> Tuple[str, float, Dict[str, float]]:
    """
    Returns:
      lang: en|si|ta|hi|ru|fr
      confidence: 0..1
      percentages: dict
    """
    p = language_percentages(text)

    # Script-based wins
    for code in ["si", "ta", "hi", "ru"]:
        if p[code] >= 0.25:
            return code, float(p[code]), p

    # Latin → choose fr vs en
    if p["latin"] >= 0.25:
        lang = "fr" if _is_likely_french(text) else "en"
        return lang, float(p["latin"]), p

    # Mixed/short fallback
    return default, float(max(p.values())), p
