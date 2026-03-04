# services/orchestrator/src/orchestrator_core/agentic/verify/tag_verifier.py
from typing import Dict, List, Optional, Tuple
from .nli_wrapper import DebertaNLIWrapper
from .tag_claims import tag_to_claim

def verify_tags_for_poi(
    *,
    title: str,
    description: Optional[str],
    tags: List[str],
    nli: Optional[DebertaNLIWrapper],
    min_entail: float = 0.65,
    min_contra: float = 0.60,
) -> Dict[str, Dict]:
    """
    Returns: tag_verification dict:
      { "outdoor": {"verdict": "...", "entailment": 0.8, "contradiction": 0.1, "reason": "..."} }
    """
    out: Dict[str, Dict] = {}
    desc = (description or "").strip()

    for tag in tags:
        claim = tag_to_claim(tag, title)
        if not claim:
            # unknown tag template => don't verify (but keep note)
            out[tag] = {"verdict": "NEED_MORE_INFO", "reason": "No claim template for tag"}
            continue

        if not desc:
            out[tag] = {"verdict": "WEAK_EVIDENCE", "reason": "No description evidence in KG"}
            continue

        if not nli:
            out[tag] = {"verdict": "WEAK_EVIDENCE", "reason": "NLI not available"}
            continue

        verdict, dbg = nli.best_evidence(
            claim=claim,
            evidence_snippets=[desc],
            min_entail=min_entail,
            min_contra=min_contra,
        )

        best = dbg.get("best")
        out[tag] = {
            "verdict": verdict,  # SUPPORTED | UNSUPPORTED | NEED_MORE_INFO
            "entailment": getattr(best, "entailment", None) if best else None,
            "contradiction": getattr(best, "contradiction", None) if best else None,
            "reason": "NLI over KG description",
        }

    return out