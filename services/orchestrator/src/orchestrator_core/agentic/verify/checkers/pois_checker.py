# services/orchestrator/src/orchestrator_core/agentic/verify/checkers/pois_checker.py
from typing import Any, Dict, Optional
from ...models import VerifyReport, VerifyIssue
from ...nli_wrapper import DebertaNLIWrapper
from ..tag_verifier import verify_tags_for_poi

def verify_pois(parsed_intent: Any, results: Dict[str, Any], rep: VerifyReport, nli: Optional[DebertaNLIWrapper] = None) -> VerifyReport:
    rep.checks_run.append("pois_basic")
    rep_dict = rep.model_dump(mode="json")
    rep_dict["per_item"] = {}

    pois = results.get("pois_result")
    if not pois or pois.get("status") != "ok":
        rep.label = "UNSUPPORTED"
        rep.score_0_1 = 0.2
        rep.issues.append(VerifyIssue(code="MISSING_POIS_RESULT", severity="high", message="pois_result missing/not ok"))
        rep_dict.update(rep.model_dump(mode="json"))
        return VerifyReport(**rep_dict)

    items = pois.get("items") or []
    if not items:
        rep.label = "WEAK_EVIDENCE"
        rep.score_0_1 = 0.5
        rep.issues.append(VerifyIssue(code="NO_POIS_RETURNED", severity="med", message="POI list empty"))
        rep_dict.update(rep.model_dump(mode="json"))
        return VerifyReport(**rep_dict)

    rep.checks_run.append("pois_tag_verification")

    # demo cap
    for it in items[:6]:
        aid = it.get("attraction_id") or it.get("title")
        title = it.get("title") or "This place"
        desc = it.get("description")

        tags = ((it.get("matched_preferences") or {}).get("tags") or [])
        tags = [t for t in tags if isinstance(t, str) and t.strip()]

        tag_ver = verify_tags_for_poi(
            title=title,
            description=desc,
            tags=tags,
            nli=nli,
        )

        # scoring: penalize weak evidence
        for t, tv in tag_ver.items():
            if tv.get("verdict") == "WEAK_EVIDENCE":
                rep.score_0_1 -= 0.05
                rep.label = "WEAK_EVIDENCE"
                rep.issues.append(VerifyIssue(
                    code="TAG_WEAK_EVIDENCE",
                    severity="low",
                    message=f"Tag '{t}' has weak evidence for {title}.",
                    evidence={"attraction_id": aid, "tag": t}
                ))
            elif tv.get("verdict") == "UNSUPPORTED":
                rep.score_0_1 -= 0.08
                rep.label = "WEAK_EVIDENCE"
                rep.issues.append(VerifyIssue(
                    code="TAG_NOT_SUPPORTED",
                    severity="med",
                    message=f"Tag '{t}' not supported by KG description for {title}.",
                    evidence={"attraction_id": aid, "tag": t}
                ))

        rep_dict["per_item"][aid] = {
            "tag_verification": tag_ver
        }

    rep.score_0_1 = max(0.0, min(1.0, rep.score_0_1))
    rep_dict.update(rep.model_dump(mode="json"))
    return VerifyReport(**rep_dict)