# “fix sentence / reorder / cleanup” for LLM readiness

# services/language_service/src/language/normalizer.py
from __future__ import annotations

import re


def normalize_text(text: str, lang: str | None = None) -> str:
    """
    Minimal text normalization so the LLM can understand better.
    Later you can replace this with OpenAI-based rewriting (gpt-4o-mini).
    """
    if not text:
        return ""

    # Trim + collapse whitespace
    t = text.strip()
    t = re.sub(r"\s+", " ", t)

    # Fix common spacing before punctuation
    t = re.sub(r"\s+([?.!,;:])", r"\1", t)

    # Optional: if user speaks in fragments, add a trailing "?" or "." when missing
    if t and t[-1] not in ".!?":
        # If it looks like a question
        if re.search(r"\b(what|where|when|how|can|could|should|do|does|is|are|tell|recommend)\b", t.lower()):
            t += "?"
        else:
            t += "."

    return t
