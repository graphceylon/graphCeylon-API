"""
test_verifier.py
================
Standalone test — no FastAPI, no real planner call needed.
Proves the full Observe → Verify → Repair → Re-verify loop works.

Run from your project root:
    python -m pytest services/orchestrator/src/orchestrator_core/agentic/test_verifier.py -v
OR simply:
    python services/orchestrator/src/orchestrator_core/agentic/test_verifier.py
"""
from __future__ import annotations
import sys
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

# ─────────────────────────────────────────────────────────────────────────────
# Minimal stubs so we can run without the full stack
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NLIResult:
    entailment: float
    neutral: float
    contradiction: float
    label: str


class FakeNLIWrapper:
    """
    Deterministic NLI stub.
    Returns high contradiction when destination strings differ,
    high entailment when they match.
    """
    def score(self, premise: str, hypothesis: str) -> NLIResult:
        p = premise.lower()
        h = hypothesis.lower()

        # Extract city names from sentences
        p_city = self._extract_city(p)
        h_city = self._extract_city(h)

        if p_city and h_city and p_city != h_city:
            # Cities differ → contradiction
            return NLIResult(entailment=0.04, neutral=0.05, contradiction=0.91, label="contradiction")
        elif p_city and h_city and p_city == h_city:
            # Cities match → entailment
            return NLIResult(entailment=0.92, neutral=0.05, contradiction=0.03, label="entailment")
        else:
            return NLIResult(entailment=0.40, neutral=0.40, contradiction=0.20, label="neutral")

    def _extract_city(self, text: str) -> str:
        import re
        # pulls last capitalised word sequence as city proxy
        m = re.findall(r"[a-z]+", text)
        cities = {"kandy", "colombo", "ella", "galle", "sigiriya", "nuwara"}
        for w in reversed(m):
            if w in cities:
                return w
        return ""

    def best_evidence(
        self,
        claim: str,
        evidence_snippets: List[str],
        min_entail: float = 0.70,
        min_contra: float = 0.55,
    ) -> Tuple[str, Dict]:
        best = None
        best_entail = -1.0
        best_contra = -1.0

        for ev in evidence_snippets[:6]:
            r = self.score(premise=ev, hypothesis=claim)
            best_entail = max(best_entail, r.entailment)
            best_contra = max(best_contra, r.contradiction)
            if best is None or r.entailment > best.entailment:
                best = r

        if best_contra >= min_contra:
            return "UNSUPPORTED", {"best": best, "best_contradiction": best_contra}
        if best_entail >= min_entail:
            return "SUPPORTED", {"best": best, "best_entailment": best_entail}
        return "NEED_MORE_INFO", {"best": best, "best_entailment": best_entail, "best_contradiction": best_contra}


# ─────────────────────────────────────────────────────────────────────────────
# Import real models + verifier (adjust path if needed)
# ─────────────────────────────────────────────────────────────────────────────
# If running as a standalone script, add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from services.orchestrator.src.orchestrator_core.agentic.models import (
    VerifyIssue, VerifyReport, RepairAction, LoopResult
)
from services.orchestrator.src.orchestrator_core.agentic.verifier_agent import VerifierAgent


# ─────────────────────────────────────────────────────────────────────────────
# Helpers to build fake parsed_intent + results
# ─────────────────────────────────────────────────────────────────────────────

def make_parsed_intent(city: str, days: int) -> dict:
    return {
        "intent": "plan_itinerary",
        "domain_category": "itinerary",
        "confidence": 0.95,
        "entities": {
            "city": city,
            "destination": city,
            "days": days,
        },
    }

def make_itinerary_result(destination: str, days: int) -> dict:
    """Simulates what the downstream planner returns."""
    return {
        "status": "ok",
        "ok": True,
        "meta": {
            "destination": destination,
            "days": days,
            "start_date": "2026-04-01",
        },
        "plans": {
            "destination_plan": {"city": destination},
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

def test_no_contradiction():
    """Planner returns exactly what user asked for → quality 1.0, no issues."""
    print("\n" + "="*60)
    print("TEST 1: No contradiction (Kandy → Kandy, 3 days → 3 days)")
    print("="*60)

    nli      = FakeNLIWrapper()
    verifier = VerifierAgent(nli=nli)

    parsed = make_parsed_intent(city="Kandy", days=3)
    results = {
        "itinerary_result": make_itinerary_result(destination="Kandy", days=3)
    }

    report = verifier.verify(results=results, prefs={}, parsed_intent=parsed)

    print(f"  ok            : {report.ok}")
    print(f"  quality_score : {report.quality_score}")
    print(f"  issues        : {[i.code for i in report.issues]}")
    print(f"  verifier_meta : {report.meta.get('verifier_meta', {})}")

    assert report.ok is True,                   "Expected ok=True"
    assert report.quality_score == 1.0,         "Expected quality=1.0"
    assert len(report.issues) == 0,             "Expected no issues"
    print("  ✓ PASSED")


def test_destination_contradiction():
    """
    User asks for Kandy, planner returns Colombo.
    Verifier should raise DESTINATION_CONTRADICTION with severity=high.
    """
    print("\n" + "="*60)
    print("TEST 2: Destination contradiction (Kandy requested → Colombo returned)")
    print("="*60)

    nli      = FakeNLIWrapper()
    verifier = VerifierAgent(nli=nli)

    parsed = make_parsed_intent(city="Kandy", days=3)
    results = {
        "itinerary_result": make_itinerary_result(destination="Colombo", days=3)
    }

    report = verifier.verify(results=results, prefs={}, parsed_intent=parsed)

    print(f"  ok            : {report.ok}")
    print(f"  quality_score : {report.quality_score}")
    print(f"  issues        : {[(i.code, i.severity, i.meta) for i in report.issues]}")
    print(f"  verifier_meta : {report.meta.get('verifier_meta', {})}")

    assert report.ok is False,                              "Expected ok=False"
    assert report.quality_score == 0.0,                    "Expected quality=0.0"
    assert any(i.code == "DESTINATION_CONTRADICTION" for i in report.issues), \
        "Expected DESTINATION_CONTRADICTION issue"
    issue = next(i for i in report.issues if i.code == "DESTINATION_CONTRADICTION")
    assert issue.severity == "high",                       "Expected severity=high"
    assert issue.meta["requested"] == "Kandy"
    assert issue.meta["got"]       == "Colombo"
    print("  ✓ PASSED")


def test_days_contradiction():
    """
    User asks for 3 days, planner returns 5 days.
    Verifier should raise DAYS_CONTRADICTION with severity=medium.
    """
    print("\n" + "="*60)
    print("TEST 3: Days contradiction (3 days requested → 5 days returned)")
    print("="*60)

    nli      = FakeNLIWrapper()
    verifier = VerifierAgent(nli=nli)

    parsed = make_parsed_intent(city="Kandy", days=3)
    results = {
        "itinerary_result": make_itinerary_result(destination="Kandy", days=5)
    }

    report = verifier.verify(results=results, prefs={}, parsed_intent=parsed)

    print(f"  ok            : {report.ok}")
    print(f"  quality_score : {report.quality_score}")
    print(f"  issues        : {[(i.code, i.severity, i.meta) for i in report.issues]}")

    assert any(i.code == "DAYS_CONTRADICTION" for i in report.issues), \
        "Expected DAYS_CONTRADICTION issue"
    issue = next(i for i in report.issues if i.code == "DAYS_CONTRADICTION")
    assert issue.severity == "medium"
    assert issue.meta["requested"] == 3
    assert issue.meta["got"]       == 5
    print("  ✓ PASSED")


def test_no_itinerary():
    """
    Planner returns nothing for an itinerary intent.
    Verifier should raise NO_ITINERARY.
    """
    print("\n" + "="*60)
    print("TEST 4: No itinerary returned")
    print("="*60)

    nli      = FakeNLIWrapper()
    verifier = VerifierAgent(nli=nli)

    parsed = make_parsed_intent(city="Kandy", days=3)
    results = {
        "itinerary_result": None,
        "modify_result":    None,
    }

    report = verifier.verify(results=results, prefs={}, parsed_intent=parsed)

    print(f"  ok            : {report.ok}")
    print(f"  quality_score : {report.quality_score}")
    print(f"  issues        : {[i.code for i in report.issues]}")

    assert report.ok is False
    assert any(i.code == "NO_ITINERARY" for i in report.issues)
    print("  ✓ PASSED")


def test_repair_decide():
    """
    RepairAgent.decide() returns correct repair actions
    for each issue type.
    """
    print("\n" + "="*60)
    print("TEST 5: RepairAgent.decide() logic")
    print("="*60)

    from services.orchestrator.src.orchestrator_core.agentic.repair import RepairAgent
    repair = RepairAgent()

    # high severity → replan_destination
    report_high = VerifyReport(
        ok=False,
        quality_score=0.0,
        issues=[
            VerifyIssue(
                code="DESTINATION_CONTRADICTION",
                severity="high",
                message="...",
                meta={"requested": "Kandy", "got": "Colombo", "contradiction_score": 0.91},
            )
        ],
    )
    actions = repair.decide(report_high)
    print(f"  actions for DESTINATION_CONTRADICTION: {[a['type'] for a in actions]}")
    assert any(a["type"] == "replan_destination" for a in actions)

    # no issues → no repairs
    report_ok = VerifyReport(ok=True, quality_score=1.0, issues=[])
    actions_none = repair.decide(report_ok)
    print(f"  actions for clean report: {actions_none}")
    assert actions_none == []

    print("  ✓ PASSED")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    passed = 0
    failed = 0

    tests = [
        test_no_contradiction,
        test_destination_contradiction,
        test_days_contradiction,
        test_no_itinerary,
        test_repair_decide,
    ]

    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            import traceback
            print(f"  ✗ ERROR: {e}")
            traceback.print_exc()
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*60)

    if failed:
        sys.exit(1)