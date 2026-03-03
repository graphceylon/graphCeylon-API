from __future__ import annotations
from typing import Any, Dict, List
from .models import VerifyIssue, VerifyReport

class VerifierAgent:
    """
    Lightweight deterministic verifier (demo-friendly).
    Reads results and preferences. Produces issues + score.
    """

    def verify(self, *, results: Dict[str, Any], prefs: Dict[str, Any]) -> VerifyReport:
        issues: List[VerifyIssue] = []
        score = 1.0

        itinerary = results.get("itinerary_result") or results.get("modify_result")
        if itinerary is None:
            return VerifyReport(
                ok=False,
                quality_score=0.0,
                issues=[VerifyIssue(code="NO_ITINERARY", severity="high", message="No itinerary was produced.")]
            )

        it = itinerary.model_dump(mode="json") if hasattr(itinerary, "model_dump") else dict(itinerary)

        # 1) too many POIs/day
        per_day_limit = int(prefs.get("per_day_attractions") or 6)
        daily = (it.get("plans") or {}).get("daily_plan") or it.get("daily_plan") or []
        for d in daily:
            pois = d.get("attractions") or d.get("pois") or []
            if len(pois) > per_day_limit:
                issues.append(VerifyIssue(
                    code="TOO_MANY_POIS",
                    severity="medium",
                    message=f"Day {d.get('day')} has too many stops ({len(pois)}).",
                    meta={"day": d.get("day"), "count": len(pois), "limit": per_day_limit},
                ))
                score -= 0.15

        # 2) crowd mismatch if avoid_crowds
        avoid_crowds = bool(prefs.get("avoid_crowds"))
        crowd = results.get("crowd_result")
        if avoid_crowds and crowd is not None:
            cr = crowd.model_dump(mode="json") if hasattr(crowd, "model_dump") else dict(crowd)
            risk = (cr.get("risk") or "").lower()
            if risk in {"high", "very_high"}:
                issues.append(VerifyIssue(
                    code="CROWD_RISK",
                    severity="medium",
                    message="Crowd risk is high but user prefers to avoid crowds.",
                    meta={"risk": risk},
                ))
                score -= 0.2

        # 3) weather risk
        weather = results.get("weather_result")
        if weather is not None:
            wr = weather.model_dump(mode="json") if hasattr(weather, "model_dump") else dict(weather)
            risk = (wr.get("risk") or "").lower()
            if risk in {"high", "very_high"}:
                issues.append(VerifyIssue(
                    code="WEATHER_RISK",
                    severity="medium",
                    message="Weather risk is high for at least one day.",
                    meta={"risk": risk},
                ))
                score -= 0.2

        score = max(0.0, min(1.0, score))

        # ok=True means "valid enough to show", but issues mean "repair recommended"
        return VerifyReport(ok=True, quality_score=score, issues=issues)