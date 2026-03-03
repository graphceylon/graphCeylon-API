from __future__ import annotations
from typing import Any, Dict, List

def patch_agentic_text(formatted: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adds agentic signals to the final UI text (safe, non-breaking).
    Expects results["agentic_meta"] like:
      {
        "changed_summary": ["...", "..."],
        "confidence": "high|medium|low",
        "checks": ["...", "..."]   # optional
      }
    """
    if not isinstance(formatted, dict):
        return {"text": str(formatted), "followups": []}

    meta = (results or {}).get("agentic_meta") or {}
    if not isinstance(meta, dict):
        return formatted

    text = str(formatted.get("text", "") or "").strip()
    blocks: List[str] = []

    changed = meta.get("changed_summary") or []
    if isinstance(changed, list) and changed:
        bullets = "\n".join(f"- {str(x)}" for x in changed[:6])
        blocks.append(" What I changed & why:\n" + bullets)

    checks = meta.get("checks") or []
    if isinstance(checks, list) and checks:
        bullets = "\n".join(f"- {str(x)}" for x in checks[:4])
        blocks.append("Checks I ran:\n" + bullets)

    conf = meta.get("confidence")
    if conf:
        blocks.append(f" Confidence: {conf}")

    if blocks:
        text = text + "\n\n" + "\n\n".join(blocks)

    formatted["text"] = text.strip()
    return formatted