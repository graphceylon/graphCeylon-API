# services/orchestrator/src/orchestrator_core/agentic/verify/tag_claims.py

TAG_TO_CLAIM_TEMPLATE = {
    # user-style tags
    "outdoor": "{title} is suitable for outdoor activities.",
    "family-friendly": "{title} is suitable for families and kids.",
    "history": "{title} is a historical attraction.",
    "cultural": "{title} is a cultural attraction.",
    "nature": "{title} is a nature-based attraction.",
    "wildlife": "{title} is related to wildlife or animals.",
    "beach": "{title} is a beach or beach-related attraction.",
    "religious": "{title} is a religious or spiritual site.",
    "adventure": "{title} is suitable for adventure activities.",
    "shopping": "{title} is suitable for shopping.",
    "food": "{title} is suitable for food experiences.",
}

def tag_to_claim(tag: str, title: str) -> str | None:
    t = (tag or "").strip().lower()
    tpl = TAG_TO_CLAIM_TEMPLATE.get(t)
    if not tpl:
        return None
    return tpl.format(title=title)