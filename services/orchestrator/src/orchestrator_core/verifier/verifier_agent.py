# services/orchestrator/src/orchestrator_core/verifier/verifier_agent.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .models import VerifyReport, VerifyIssue

class VerifierAgent:
    """
    Research-grade MVP verifier:
    - Missing fields gating
    - Itinerary timeline checks (start_date + days)
    - Waypoint timeline checks (include_stops / stop_durations_days)
    - Optional NLI contradiction checks (claim vs evidence snippets)
    """

    def __init__(self, nli=None):
        # nli is your wrapper instance (optional)
        self.nli = nli

    def verify(
        self,
        *,
        parsed_intent: Dict[str, Any],
        results: Dict[str, Any],
        raw_user_text: str = "",
    ) -> VerifyReport:

        intent = (parsed_intent.get("intent") or "").strip()
        ents = parsed_intent.get("entities") or {}
        issues: List[VerifyIssue] = []
        missing_fields: List[str] = []

        # -------------------------
        # 1) Missing fields (reuse your gate outputs if present)
        # -------------------------
        gate_missing = results.get("missing_fields") or []
        if isinstance(gate_missing, list) and gate_missing:
            missing_fields = [str(x) for x in gate_missing]

        # For itinerary plan: if gate didn't run, do a tiny fallback
        if intent == "plan_itinerary" and not missing_fields:
            if not ents.get("start_date") and not ents.get("travel_month"):
                missing_fields.append("start_date")
            city = (ents.get("city") or "").strip() if isinstance(ents.get("city"), str) else ents.get("city")
            dest = (ents.get("destination") or "").strip() if isinstance(ents.get("destination"), str) else ents.get("destination")
            if not city and not dest:
                missing_fields.append("destination_city")

        if missing_fields:
            issues.append(
                VerifyIssue(
                    code="MISSING_FIELDS",
                    severity="medium",
                    message="Missing required trip details",
                    meta={"missing_fields": missing_fields},
                )
            )
            return VerifyReport(
                verdict="NEED_MORE_INFO",
                quality_score=0.35,
                confidence=0.40,
                issues=issues,
                missing_fields=missing_fields,
            )

        # -------------------------
        # 2) Pull itinerary output (structured)
        # -------------------------
        it = results.get("itinerary_result")
        it_json = self._to_dict(it)

        # If no itinerary produced (maybe tool failed or skipped)
        if not it_json:
            issues.append(
                VerifyIssue(
                    code="NO_ITINERARY",
                    severity="high",
                    message="No itinerary result to verify",
                    meta={},
                )
            )
            return VerifyReport(
                verdict="UNSUPPORTED",
                quality_score=0.10,
                confidence=0.20,
                issues=issues,
            )

        meta = it_json.get("meta") or {}
        plans = it_json.get("plans") or {}

        # -------------------------
        # 3) Timeline consistency checks
        # -------------------------
        start_date = meta.get("start_date") or it_json.get("start_date") or ents.get("start_date")
        days = meta.get("days") or it_json.get("days") or ents.get("days")

        # If days is missing, it's not fatal but lowers score
        if not start_date:
            issues.append(
                VerifyIssue(
                    code="MISSING_START_DATE",
                    severity="medium",
                    message="Itinerary has no start_date in meta/entities",
                    meta={"meta": meta},
                )
            )

        if not days:
            issues.append(
                VerifyIssue(
                    code="MISSING_DAYS",
                    severity="low",
                    message="Itinerary has no days count (cannot fully validate duration)",
                    meta={"meta": meta},
                )
            )

        # -------------------------
        # 4) Waypoint / stop duration logic (your requirement)
        # -------------------------
        wp_issue = self._verify_waypoints_logic(ents, meta)
        if wp_issue:
            issues.append(wp_issue)

        # -------------------------
        # 5) Optional NLI contradiction checks (fast demo)
        # Example: check POI city mismatches if evidence includes "poi city"
        # -------------------------
        supported = 0
        unsupported = 0
        neutral = 0
        contradictions: List[Dict[str, Any]] = []

        if self.nli:
            # Build a few simple “claims” from itinerary POIs
            poi_claims, evidence_snippets = self._extract_poi_claims_and_evidence(plans, meta, ents)

            for claim in poi_claims[:8]:
                verdict, debug = self._nli_check_claim(claim, evidence_snippets)

                if verdict == "SUPPORTED":
                    supported += 1
                elif verdict == "UNSUPPORTED":
                    unsupported += 1
                    contradictions.append({"claim": claim, "debug": self._safe_debug(debug)})
                    issues.append(
                        VerifyIssue(
                            code="CONTRADICTION_NLI",
                            severity="high",
                            message="Claim contradicts evidence (NLI)",
                            meta={"claim": claim, "nli": self._safe_debug(debug)},
                        )
                    )
                else:
                    neutral += 1

        # -------------------------
        # 6) Verdict + score
        # -------------------------
        quality_score = self._score(issues, supported=supported, unsupported=unsupported, neutral=neutral)
        confidence = self._confidence_from_score(quality_score)

        if any(i.severity == "high" for i in issues):
            verdict = "UNSUPPORTED"
        else:
            verdict = "SUPPORTED"

        report = VerifyReport(
            verdict=verdict,
            quality_score=quality_score,
            confidence=confidence,
            issues=issues,
            supported_claims=supported,
            unsupported_claims=unsupported,
            neutral_claims=neutral,
            contradictions=contradictions,
        )
        return report

    # -------------------------
    # Helpers
    # -------------------------
    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        if obj is None:
            return {}
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump(mode="json")
            except Exception:
                pass
        try:
            return dict(obj)
        except Exception:
            return {}

    def _verify_waypoints_logic(self, ents: Dict[str, Any], meta: Dict[str, Any]) -> Optional[VerifyIssue]:
        """
        Requirement you stated:
        If include_stops True + waypoints + stop_durations_days,
        user travels origin -> waypoint(s), stays there stop_duration days,
        THEN destination plan starts after that.
        Here we validate basic consistency (not full calendar math yet).
        """
        include_stops = bool(ents.get("include_stops"))
        waypoints = ents.get("waypoints") or []
        stop_durations = ents.get("stop_durations_days") or {}

        if not include_stops:
            return None
        if not waypoints or not isinstance(waypoints, list):
            return VerifyIssue(
                code="STOP_LOGIC_MISSING_WAYPOINTS",
                severity="medium",
                message="include_stops=true but no waypoints provided",
                meta={"include_stops": include_stops},
            )
        if not isinstance(stop_durations, dict) or not stop_durations:
            return VerifyIssue(
                code="STOP_LOGIC_MISSING_DURATIONS",
                severity="medium",
                message="include_stops=true but stop_durations_days missing",
                meta={"waypoints": waypoints},
            )

        # Validate each waypoint has duration
        missing = []
        for wp in waypoints:
            if wp not in stop_durations:
                missing.append(wp)

        if missing:
            return VerifyIssue(
                code="STOP_LOGIC_DURATION_GAPS",
                severity="medium",
                message="Some waypoints have no stop duration",
                meta={"missing_waypoints": missing, "stop_durations_days": stop_durations},
            )

        # Basic sanity: duration must be positive int
        bad = []
        for k, v in stop_durations.items():
            try:
                iv = int(v)
                if iv < 0:
                    bad.append({k: v})
            except Exception:
                bad.append({k: v})

        if bad:
            return VerifyIssue(
                code="STOP_LOGIC_BAD_DURATION",
                severity="medium",
                message="Invalid stop duration values",
                meta={"bad": bad},
            )

        return None

    def _extract_poi_claims_and_evidence(
        self,
        plans: Dict[str, Any],
        meta: Dict[str, Any],
        ents: Dict[str, Any],
    ) -> Tuple[List[str], List[str]]:
        """
        Claims: "POI <name> is in <destination>"
        Evidence: create snippets from structured output (destination + poi list)
        """
        dest = (meta.get("destination") or ents.get("city") or ents.get("destination") or "").strip()
        dp = plans.get("destination_plan") or {}
        pois = dp.get("pois") or dp.get("points_of_interest") or []

        claims = []
        evidence = []

        if dest:
            evidence.append(f"Destination city is {dest}.")

        # Evidence from POIs
        for p in pois[:12]:
            if isinstance(p, dict):
                name = (p.get("name") or p.get("title") or "").strip()
                if name:
                    evidence.append(f"{name} is a POI in {dest}.")
                    claims.append(f"{name} is located in {dest}.")
            elif isinstance(p, str):
                evidence.append(f"{p} is a POI in {dest}.")
                claims.append(f"{p} is located in {dest}.")

        return claims, evidence

    def _nli_check_claim(self, claim: str, evidence_snippets: List[str]) -> Tuple[str, Dict[str, Any]]:
        """
        Adapts to either:
          - wrapper.best_evidence(claim, evidence_snippets) -> (verdict, debug)
          - wrapper.score(premise, hypothesis) used manually
        """
        if hasattr(self.nli, "best_evidence"):
            verdict, debug = self.nli.best_evidence(claim, evidence_snippets)
            # normalize to our labels
            if verdict == "SUPPORTED":
                return "SUPPORTED", debug
            if verdict == "UNSUPPORTED":
                return "UNSUPPORTED", debug
            return "NEED_MORE_INFO", debug

        # fallback: pick first snippet
        if evidence_snippets and hasattr(self.nli, "score"):
            r = self.nli.score(premise=evidence_snippets[0], hypothesis=claim)
            # expect r.label in {"entailment","contradiction","neutral"}
            lbl = getattr(r, "label", "neutral")
            if lbl == "contradiction":
                return "UNSUPPORTED", {"r": vars(r)}
            if lbl == "entailment":
                return "SUPPORTED", {"r": vars(r)}
            return "NEED_MORE_INFO", {"r": vars(r)}

        return "NEED_MORE_INFO", {"error": "No NLI method available"}

    def _score(self, issues: List[VerifyIssue], supported: int, unsupported: int, neutral: int) -> float:
        # Start optimistic, subtract penalties
        score = 0.95

        for i in issues:
            if i.severity == "high":
                score -= 0.35
            elif i.severity == "medium":
                score -= 0.18
            else:
                score -= 0.08

        # claim-based adjustment
        score += min(0.05, supported * 0.01)
        score -= min(0.20, unsupported * 0.05)

        # clamp
        if score < 0.0:
            score = 0.0
        if score > 1.0:
            score = 1.0
        return float(score)

    def _confidence_from_score(self, score: float) -> float:
        # simple mapping
        if score >= 0.85:
            return 0.88
        if score >= 0.70:
            return 0.78
        if score >= 0.50:
            return 0.62
        return 0.45

    def _safe_debug(self, debug: Any) -> Any:
        # prevent huge dumps
        try:
            s = str(debug)
            return s[:1200] + ("..." if len(s) > 1200 else "")
        except Exception:
            return {"debug": "unserializable"}