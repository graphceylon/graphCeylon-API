from __future__ import annotations
from typing import Any, Dict, Optional
from .models import Observation, LoopResult
from .verifier import VerifierAgent
from .repair import RepairAgent

class AgenticLoop:
    def __init__(self) -> None:
        self.verifier = VerifierAgent()
        self.repair = RepairAgent()

    def observe(self, *, results: Dict[str, Any]) -> Observation:
        # simple observation
        ok = results.get("itinerary_result") is not None or results.get("modify_result") is not None
        risk_flags = {}
        if results.get("weather_result") is not None:
            wr = results["weather_result"].model_dump(mode="json") if hasattr(results["weather_result"], "model_dump") else dict(results["weather_result"])
            risk_flags["weather"] = wr.get("risk")
        if results.get("crowd_result") is not None:
            cr = results["crowd_result"].model_dump(mode="json") if hasattr(results["crowd_result"], "model_dump") else dict(results["crowd_result"])
            risk_flags["crowd"] = cr.get("risk")

        # coverage heuristic
        coverage = 1.0 if ok else 0.0
        return Observation(ok=ok, coverage=coverage, risk_flags=risk_flags)

    def run(
        self,
        *,
        svc,  # OrchestratorService
        parsed_intent,
        req,
        db_prefs: Dict[str, Any],
        session_state,
        request_trace_id: str,
        results: Dict[str, Any],
        max_repairs: int = 1,
    ) -> LoopResult:

        obs = self.observe(results=results)
        # loop.py
        report = self.verifier.verify(results=results, prefs=db_prefs, parsed_intent=parsed_intent)         

        repairs_applied = []
        changed_summary = []

        # decide if repair is needed (agentic decision)
        actions = self.repair.decide(report)
        if actions and max_repairs > 0:
            repairs_applied = self.repair.apply_repairs(
                svc=svc,
                actions=actions,
                parsed_intent=parsed_intent,
                req=req,
                db_prefs=db_prefs,
                session_state=session_state,
                request_trace_id=request_trace_id,
                results=results,
            )

        if repairs_applied:
            for a in repairs_applied:
                changed_summary.append(f"{a.name}: {a.reason}")

        # confidence from quality score + whether we had to repair
        conf = "high"
        if report.quality_score < 0.7:
            conf = "medium"
        if report.quality_score < 0.45:
            conf = "low"
        if not obs.ok:
            conf = "low"

        return LoopResult(
            observation=obs,
            verify_report=report,
            repairs_applied=repairs_applied,
            changed_summary=changed_summary,
            confidence=conf,
        )