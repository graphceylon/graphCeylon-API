# orchestrator_core/agentic/verifier_agent.py
import re
from typing import Any, Dict, List, Optional
from .models import VerifyLabel, VerifyIssue, VerifyReport

class VerifierAgent:
    def __init__(self, nli_model) -> None:
        self.nli = nli_model  # your DeBERTa wrapper

    def verify(self, *, results: Dict[str, Any], prefs: Dict[str, Any], parsed_intent: Any) -> VerifyReport:
        issues: List[VerifyIssue] = []
        meta: Dict[str, Any] = {}

        # intent extraction
        if isinstance(parsed_intent, dict):
            intent = (parsed_intent.get("intent") or "").strip()
            ents = parsed_intent.get("entities") or {}
        else:
            intent = (getattr(parsed_intent, "intent", None) or "").strip()
            ents_obj = getattr(parsed_intent, "entities", None)
            ents = ents_obj.model_dump(exclude_none=False) if hasattr(ents_obj, "model_dump") else (ents_obj or {})

        # ✅ POI evidence coverage
        pois = results.get("pois_result")
        if pois:
            pois_json = pois.model_dump(mode="json") if hasattr(pois, "model_dump") else dict(pois)
            items = (pois_json.get("items") or [])

            checked = []
            for it in items[:10]:
                title = it.get("title")
                desc = (it.get("description") or "").strip()
                tags = ((it.get("matched_preferences") or {}).get("tags") or [])

                evidence_status = "HAS_TEXT_EVIDENCE" if desc else "MISSING_TEXT_EVIDENCE"
                checked.append({"title": title, "tags": tags, "evidence_status": evidence_status})

                if tags and not desc:
                    issues.append(VerifyIssue(
                        code="POI_TAG_EVIDENCE_MISSING",
                        severity="low",
                        message=f"POI '{title}' has tags {tags} but no description text to justify them.",
                        meta={"poi": title, "tags": tags}
                    ))

            meta["pois_tag_evidence"] = checked

        # ✅ itinerary-only issue
        if intent in {"plan_itinerary", "modify_itinerary"}:
            if results.get("itinerary_result") is None and results.get("modify_result") is None:
                issues.append(VerifyIssue(
                    code="NO_ITINERARY",
                    severity="high",
                    message="No itinerary was produced.",
                    meta={}
                ))

        # quality score (simple)
        quality = 1.0
        if any(i.code == "POI_TAG_EVIDENCE_MISSING" for i in issues):
            quality = 0.75
        if any(i.code == "NO_ITINERARY" for i in issues):
            quality = 0.0

        ok = (quality >= 0.5) and not any(i.severity == "high" for i in issues)

        return VerifyReport(ok=ok, quality_score=quality, issues=issues, meta=meta)

    def _collect_evidence_texts(self, results: Dict[str, Any]) -> List[str]:
        texts: List[str] = []
        # your AgentResult.evidence is typically in results[...] already
        for k, v in (results or {}).items():
            if v is None:
                continue
            # If v is a pydantic model, dump it
            try:
                if hasattr(v, "model_dump"):
                    vv = v.model_dump(mode="json")
                else:
                    vv = v
            except Exception:
                vv = v

            # pull evidence if stored separately
            if isinstance(vv, dict):
                ev = vv.get("evidence")
                if isinstance(ev, list):
                    for e in ev:
                        snip = (e.get("snippet") or e.get("text") or "")
                        if snip:
                            texts.append(str(snip)[:1200])
        return texts

    def _entailed_by_any(self, claim: str, evidence_texts: List[str]) -> bool:
        if not evidence_texts:
            return False
        for ev in evidence_texts[:12]:  # cap for speed
            label, score = self.nli.predict(premise=ev, hypothesis=claim)
            if label == "entailment" and score >= 0.70:
                return True
        return False

    def _build_claims_from_results(self, parsed_intent: Dict[str, Any], results: Dict[str, Any]) -> List[str]:
        # Minimal, measurable claims (don’t try to parse free-text yet)
        claims: List[str] = []
        it = results.get("itinerary_result")
        if it is not None:
            it_json = it.model_dump(mode="json") if hasattr(it, "model_dump") else dict(it)
            meta = it_json.get("meta") or {}
            dest = meta.get("destination")
            start = meta.get("start_date")
            days = meta.get("days")
            if dest: claims.append(f"The trip destination is {dest}.")
            if start: claims.append(f"The trip starts on {start}.")
            if days: claims.append(f"The trip duration is {days} day(s).")
        return claims

    def _find_contradictions(self, parsed_intent: Dict[str, Any], results: Dict[str, Any]) -> List[Dict[str, Any]]:
        contradictions: List[Dict[str, Any]] = []
        ents = (parsed_intent.get("entities") or {})
        it = results.get("itinerary_result")
        if it is None:
            return contradictions
        it_json = it.model_dump(mode="json") if hasattr(it, "model_dump") else dict(it)
        meta = it_json.get("meta") or {}
        dest_meta = (meta.get("destination") or "").strip().lower()
        city_ent = (ents.get("city") or "").strip().lower()

        if dest_meta and city_ent and dest_meta != city_ent:
            contradictions.append({
                "field": "destination",
                "entities_city": city_ent,
                "itinerary_destination": dest_meta,
                "message": "Destination conflict between parsed entities and itinerary meta",
            })
        return contradictions

    def _suggest_repairs(self, label, issues, parsed_intent, results) -> List[Dict[str, Any]]:
        if label == VerifyLabel.UNSUPPORTED:
            # Example repair: re-call itinerary planner with stricter args or ask followup
            return [{"type": "repair_plan", "reason": "verification_failed"}]
        return []