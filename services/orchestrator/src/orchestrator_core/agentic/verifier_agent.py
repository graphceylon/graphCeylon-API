from __future__ import annotations
from typing import Any, Dict, List, Optional
from .models import VerifyIssue, VerifyReport
import os


class VerifierAgent:

    def __init__(self, nli) -> None:
        self.nli = nli

    def verify(
        self,
        *,
        results: Dict[str, Any],
        prefs: Dict[str, Any],
        parsed_intent: Any,
    ) -> VerifyReport:
        issues: List[VerifyIssue] = []
        verifier_meta: Dict[str, Any] = {}

        if isinstance(parsed_intent, dict):
            intent = (parsed_intent.get("intent") or "").strip()
            ents   = parsed_intent.get("entities") or {}
        else:
            intent   = (getattr(parsed_intent, "intent", None) or "").strip()
            ents_obj = getattr(parsed_intent, "entities", None)
            ents     = (
                ents_obj.model_dump(exclude_none=False)
                if hasattr(ents_obj, "model_dump")
                else (ents_obj or {})
            )

        if intent in {"plan_itinerary", "modify_itinerary"}:
            it = results.get("itinerary_result")
            if it is None and results.get("modify_result") is None:
                issues.append(VerifyIssue(
                    code="NO_ITINERARY",
                    severity="high",
                    message="No itinerary was produced.",
                    meta={},
                ))
            elif it is not None:
                it_json = (
                    it.model_dump(mode="json")
                    if hasattr(it, "model_dump")
                    else dict(it)
                )

                # # DEMO ONLY — remove before production
                # if os.getenv("SIMULATE_CONTRADICTION", "0") == "1":
                #     it_json.setdefault("meta", {})["destination"] = "Colombo"

                meta = it_json.get("meta") or {}
                dest        = (meta.get("destination") or "").strip()
                result_days = meta.get("days")

                requested_city = (
                    ents.get("city") or ents.get("destination") or ""
                ).strip()
                requested_days = ents.get("days")

                # ── CHECK 1: destination contradiction ────────────────
                if dest and requested_city:
                    dest_claim = f"The trip destination is {dest}."
                    city_evidence = [
                        f"The user requested a trip to {requested_city}.",
                        f"User wants {requested_city}.",
                    ]

                    verdict, debug = self.nli.best_evidence(
                        claim=dest_claim,
                        evidence_snippets=city_evidence,
                        min_entail=0.70,
                        min_contra=0.25,
                    )

                    nli_r = debug.get("best")
                    if nli_r:
                        verifier_meta[dest_claim] = {
                            "entailment":    round(nli_r.entailment, 4),
                            "neutral":       round(nli_r.neutral, 4),
                            "contradiction": round(nli_r.contradiction, 4),
                            "verdict":       verdict,
                        }

                    if dest.lower() != requested_city.lower() and verdict == "UNSUPPORTED":
                        issues.append(VerifyIssue(
                            code="DESTINATION_CONTRADICTION",
                            severity="high",
                            message=(
                                f"Itinerary destination '{dest}' contradicts "
                                f"requested city '{requested_city}'."
                            ),
                            meta={
                                "requested":           requested_city,
                                "got":                 dest,
                                "contradiction_score": round(
                                    debug.get("best_contradiction", 0.0), 3
                                ),
                            },
                        ))

                # ── CHECK 2: days contradiction ───────────────────────
                if result_days and requested_days:
                    try:
                        r_days = int(result_days)
                        q_days = int(requested_days)
                    except (TypeError, ValueError):
                        r_days = q_days = None

                    if r_days is not None and q_days is not None and r_days != q_days:
                        days_claim    = f"The trip duration is {r_days} day(s)."
                        days_evidence = [f"The user requested a {q_days}-day trip."]

                        verdict2, debug2 = self.nli.best_evidence(
                            claim=days_claim,
                            evidence_snippets=days_evidence,
                            min_entail=0.70,
                            min_contra=0.55,
                        )

                        nli_r2 = debug2.get("best")
                        if nli_r2:
                            verifier_meta[days_claim] = {
                                "entailment":    round(nli_r2.entailment, 4),
                                "neutral":       round(nli_r2.neutral, 4),
                                "contradiction": round(nli_r2.contradiction, 4),
                                "verdict":       verdict2,
                            }

                        if verdict2 == "UNSUPPORTED":
                            issues.append(VerifyIssue(
                                code="DAYS_CONTRADICTION",
                                severity="medium",
                                message=(
                                    f"Itinerary has {r_days} days but user requested "
                                    f"{q_days} days."
                                ),
                                meta={
                                    "requested":           q_days,
                                    "got":                 r_days,
                                    "contradiction_score": round(
                                        debug2.get("best_contradiction", 0.0), 3
                                    ),
                                },
                            ))

        # ── CHECK 3: POI tag evidence coverage ────────────────────────
        pois = results.get("pois_result")
        if pois:
            pois_json = (
                pois.model_dump(mode="json") if hasattr(pois, "model_dump") else dict(pois)
            )
            items   = pois_json.get("items") or []
            checked = []

            for item in items[:10]:
                title  = item.get("title") or ""
                desc   = (item.get("description") or "").strip()
                tags   = (item.get("matched_preferences") or {}).get("tags") or []
                status = "HAS_TEXT_EVIDENCE" if desc else "MISSING_TEXT_EVIDENCE"
                checked.append({"title": title, "tags": tags, "evidence_status": status})

                if tags and not desc:
                    issues.append(VerifyIssue(
                        code="POI_TAG_EVIDENCE_MISSING",
                        severity="low",
                        message=(
                            f"POI '{title}' has preference tags {tags} "
                            f"but no description text to justify them."
                        ),
                        meta={"poi": title, "tags": tags},
                    ))

            verifier_meta["pois_tag_evidence"] = checked

        # ── quality score ─────────────────────────────────────────────
        quality = 1.0
        if any(i.code == "POI_TAG_EVIDENCE_MISSING" for i in issues):
            quality = min(quality, 0.75)
        if any(i.code == "DAYS_CONTRADICTION" for i in issues):
            quality = min(quality, 0.60)
        if any(i.severity == "high" for i in issues):
            quality = 0.0

        ok = (quality >= 0.5) and not any(i.severity == "high" for i in issues)

        return VerifyReport(
            ok=ok,
            quality_score=quality,
            issues=issues,
            meta={"verifier_meta": verifier_meta},
        )