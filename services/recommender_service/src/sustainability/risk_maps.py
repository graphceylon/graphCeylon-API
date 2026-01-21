from __future__ import annotations

def rain_risk_to_0_1(risk: str | None) -> float:
    r = (risk or "").strip().lower()
    if r == "low":
        return 0.2
    if r == "medium":
        return 0.5
    if r == "high":
        return 0.8
    # unknown -> neutral-ish
    return 0.5
