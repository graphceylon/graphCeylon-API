# safe fallback if translation fails

from __future__ import annotations

def fallback_translate_to_english(text: str, source_lang: str) -> str:
    # dev-safe fallback: return original if translation provider unavailable
    return text

def fallback_translate_from_english(text: str, target_lang: str) -> str:
    return text