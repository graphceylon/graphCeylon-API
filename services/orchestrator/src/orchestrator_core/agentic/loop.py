from __future__ import annotations
from typing import Any, Dict
from .models import Observation, LoopResult
from .verifier_agent import VerifierAgent
from .repair import RepairAgent


class AgenticLoop:
    """
    Observe → Verify → Repair → Re-verify → Decide

    Called once per orchestrate() request after the DAG has run.
    Mutates `results` in place when a repair succeeds.
    """

    def __init__(self) -> None:
        # VerifierAgent and RepairAgent are instantiated here but
        # VerifierAgent needs the NLI model — we inject it via set_nli()
        # because the NLI model is loaded in OrchestratorService.__init__
        self._nli = None
        self._verifier: VerifierAgent | None = None
        self.repair = RepairAgent()

    def set_nli(self, nli) -> None:
        """Called by OrchestratorService after NLI model is loaded."""
        self._nli = nli
        self._verifier = VerifierAgent(nli=nli)

    @property
    def verifier(self) -> VerifierAgent:
        if self._verifier is None:
            raise RuntimeError(
                "AgenticLoop: NLI model not set. "
                "Call agentic_loop.set_nli(self.nli) in OrchestratorService.__init__."
            )
        return self._verifier

    # ------------------------------------------------------------------
    # OBSERVE
    # ------------------------------------------------------------------
    def observe(self, *, results: Dict[str, Any]) -> Observation:
        ok = (
            results.get("itinerary_result") is not None
            or results.get("modify_result") is not None
        )
        risk_flags = {}

        wr = results.get("weather_result")
        if wr is not None:
            wr_json = wr.model_dump(mode="json") if hasattr(wr, "model_dump") else dict(wr)
            risk_flags["weather"] = wr_json.get("risk")

        cr = results.get("crowd_result")
        if cr is not None:
            cr_json = cr.model_dump(mode="json") if hasattr(cr, "model_dump") else dict(cr)
            risk_flags["crowd"] = cr_json.get("risk")

        coverage = 1.0 if ok else 0.0
        return Observation(ok=ok, coverage=coverage, risk_flags=risk_flags)

    # ------------------------------------------------------------------
    # RUN  (the main agentic loop)
    # ------------------------------------------------------------------
    def run(
        self,
        *,
        svc,                        # OrchestratorService
        parsed_intent,
        req,
        db_prefs: Dict[str, Any],
        session_state,
        request_trace_id: str,
        results: Dict[str, Any],
        max_repairs: int = 1,
    ) -> LoopResult:

        # ── STEP 1: observe ───────────────────────────────────────────
        obs = self.observe(results=results)

        # ── STEP 2: first verify pass ─────────────────────────────────
        report = self.verifier.verify(
            results=results,
            prefs=db_prefs,
            parsed_intent=parsed_intent,
        )

        print(
            f"[agentic] first verify: ok={report.ok} "
            f"quality={report.quality_score:.2f} "
            f"issues={[i.code for i in report.issues]}"
        )

        repairs_applied = []
        changed_summary = []

        # ── STEP 3: repair if needed ──────────────────────────────────
        if not report.ok and max_repairs > 0:
            actions = self.repair.decide(report)

            if actions:
                print(f"[agentic] repair actions decided: {[a['type'] for a in actions]}")

                repairs_applied = self.repair.apply_repairs(
                    svc=svc,
                    actions=actions,
                    parsed_intent=parsed_intent,
                    req=req,
                    db_prefs=db_prefs,
                    session_state=session_state,
                    request_trace_id=request_trace_id,
                    results=results,    # mutated in place on success
                )

                # ── STEP 4: re-verify after repairs ───────────────────
                if repairs_applied:
                    report = self.verifier.verify(
                        results=results,
                        prefs=db_prefs,
                        parsed_intent=parsed_intent,
                    )
                    print(
                        f"[agentic] post-repair verify: ok={report.ok} "
                        f"quality={report.quality_score:.2f} "
                        f"issues={[i.code for i in report.issues]}"
                    )

                    for r in repairs_applied:
                        changed_summary.append(f"{r.name}: {r.reason}")

        # ── STEP 5: decide confidence ─────────────────────────────────
        if report.quality_score >= 0.85 and obs.ok:
            conf = "high"
        elif report.quality_score >= 0.5:
            conf = "medium"
        else:
            conf = "low"

        if not obs.ok:
            conf = "low"

        print(f"[agentic] final confidence={conf} quality={report.quality_score:.2f}")

        return LoopResult(
            observation=obs,
            verify_report=report,
            repairs_applied=repairs_applied,
            changed_summary=changed_summary,
            confidence=conf,
        )