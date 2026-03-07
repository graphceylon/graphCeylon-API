from __future__ import annotations
from typing import Any, Dict, List
from .models import RepairAction, VerifyReport, VerifyIssue


class RepairAgent:
    """
    Reads a VerifyReport, decides what repairs are needed,
    and applies them by re-calling the orchestrator's _execute_intent.
    """

    # ------------------------------------------------------------------
    # DECIDE: which repairs are needed given the verify report
    # ------------------------------------------------------------------
    def decide(self, report: VerifyReport) -> List[Dict[str, Any]]:
        """
        Returns a list of repair descriptors — plain dicts so loop.py
        can inspect them before calling apply_repairs.

        Each descriptor:
          {
            "type":   "replan_destination" | "replan_days" | "replan_full",
            "code":   <VerifyIssue.code that triggered it>,
            "meta":   <VerifyIssue.meta>,
          }
        """
        if not report or report.ok:
            return []

        actions = []
        seen_high = False

        for issue in report.issues:
            if issue.code == "DESTINATION_CONTRADICTION":
                actions.append({
                    "type": "replan_destination",
                    "code": issue.code,
                    "meta": issue.meta,
                })
                seen_high = True

            elif issue.code == "DAYS_CONTRADICTION":
                actions.append({
                    "type": "replan_days",
                    "code": issue.code,
                    "meta": issue.meta,
                })

            elif issue.code == "NO_ITINERARY":
                # only add a full replan if we haven't already added
                # a destination repair (which will replan anyway)
                if not seen_high:
                    actions.append({
                        "type": "replan_full",
                        "code": issue.code,
                        "meta": issue.meta,
                    })

        # deduplicate: if both destination + days need repair, a single
        # replan_destination call will naturally fix days too
        types = [a["type"] for a in actions]
        if "replan_destination" in types:
            actions = [a for a in actions if a["type"] != "replan_full"]

        return actions

    # ------------------------------------------------------------------
    # APPLY: execute each repair action
    # ------------------------------------------------------------------
    def apply_repairs(
        self,
        *,
        svc,                          # OrchestratorService
        actions: List[Dict[str, Any]],
        parsed_intent,
        req,
        db_prefs: Dict[str, Any],
        session_state,
        request_trace_id: str,
        results: Dict[str, Any],
    ) -> List[RepairAction]:
        applied: List[RepairAction] = []

        for action in actions:
            atype = action["type"]
            ameta = action.get("meta") or {}

            # ── REPAIR 1: destination contradiction ──────────────────
            if atype == "replan_destination":
                requested_city = ameta.get("requested", "")
                got_city       = ameta.get("got", "")
                nli_score      = ameta.get("contradiction_score", 0.0)

                if not requested_city:
                    continue

                # Patch entities: force the correct city
                ents = (
                    parsed_intent.entities.model_dump(exclude_none=False)
                    if hasattr(parsed_intent.entities, "model_dump")
                    else dict(getattr(parsed_intent, "entities", None) or {})
                )
                ents["city"]        = requested_city
                ents["destination"] = requested_city

                # Build a patched intent so the mapper sends the right city
                try:
                    from ..api.schemas import Entities
                    patched = parsed_intent.model_copy(
                        update={"entities": Entities(**ents)}
                    )
                except Exception:
                    # fallback: mutate in place (less safe but won't crash)
                    patched = parsed_intent
                    if hasattr(patched, "entities"):
                        patched.entities.city        = requested_city
                        patched.entities.destination = requested_city

                intent_name = (
                    getattr(parsed_intent, "intent", None)
                    or (parsed_intent.get("intent") if isinstance(parsed_intent, dict) else None)
                    or "plan_itinerary"
                )

                print(
                    f"[repair] DESTINATION_CONTRADICTION → re-running '{intent_name}' "
                    f"with city='{requested_city}' (was '{got_city}', "
                    f"NLI contradiction={nli_score})"
                )

                new_result = svc._execute_intent(
                    intent_name,
                    patched,
                    req,
                    db_prefs,
                    session_state,
                    request_trace_id,
                )

                # Update results in place so verifier sees the fixed output
                if getattr(new_result, "ok", False):
                    result_key = (
                        "modify_result"
                        if intent_name == "modify_itinerary"
                        else "itinerary_result"
                    )
                    results[result_key] = new_result.data
                    print(f"[repair] ✓ repair succeeded, updated results['{result_key}']")
                else:
                    print(f"[repair] ✗ repair call failed: {getattr(new_result, 'safety_flags', '')}")

                applied.append(RepairAction(
                    name="replan_with_corrected_destination",
                    reason=(
                        f"NLI detected destination contradiction: "
                        f"got '{got_city}', user requested '{requested_city}' "
                        f"(contradiction score: {nli_score})"
                    ),
                    meta={
                        "original_city":       got_city,
                        "corrected_city":      requested_city,
                        "nli_score":           nli_score,
                        "repair_ok":           getattr(new_result, "ok", False),
                    },
                ))

            # ── REPAIR 2: days contradiction ─────────────────────────
            elif atype == "replan_days":
                requested_days = ameta.get("requested")
                got_days       = ameta.get("got")
                nli_score      = ameta.get("contradiction_score", 0.0)

                if not requested_days:
                    continue

                ents = (
                    parsed_intent.entities.model_dump(exclude_none=False)
                    if hasattr(parsed_intent.entities, "model_dump")
                    else dict(getattr(parsed_intent, "entities", None) or {})
                )
                ents["days"] = requested_days

                try:
                    from ..api.schemas import Entities
                    patched = parsed_intent.model_copy(
                        update={"entities": Entities(**ents)}
                    )
                except Exception:
                    patched = parsed_intent
                    if hasattr(patched, "entities"):
                        patched.entities.days = requested_days

                intent_name = (
                    getattr(parsed_intent, "intent", None)
                    or (parsed_intent.get("intent") if isinstance(parsed_intent, dict) else None)
                    or "plan_itinerary"
                )

                print(
                    f"[repair] DAYS_CONTRADICTION → re-running '{intent_name}' "
                    f"with days={requested_days} (was {got_days}, "
                    f"NLI contradiction={nli_score})"
                )

                new_result = svc._execute_intent(
                    intent_name,
                    patched,
                    req,
                    db_prefs,
                    session_state,
                    request_trace_id,
                )

                if getattr(new_result, "ok", False):
                    result_key = (
                        "modify_result"
                        if intent_name == "modify_itinerary"
                        else "itinerary_result"
                    )
                    results[result_key] = new_result.data
                    print(f"[repair] ✓ repair succeeded, updated results['{result_key}']")
                else:
                    print(f"[repair] ✗ repair call failed: {getattr(new_result, 'safety_flags', '')}")

                applied.append(RepairAction(
                    name="replan_with_corrected_days",
                    reason=(
                        f"NLI detected days contradiction: "
                        f"got {got_days} days, user requested {requested_days} days "
                        f"(contradiction score: {nli_score})"
                    ),
                    meta={
                        "original_days":  got_days,
                        "corrected_days": requested_days,
                        "nli_score":      nli_score,
                        "repair_ok":      getattr(new_result, "ok", False),
                    },
                ))

            # ── REPAIR 3: full replan (NO_ITINERARY) ─────────────────
            elif atype == "replan_full":
                intent_name = (
                    getattr(parsed_intent, "intent", None)
                    or (parsed_intent.get("intent") if isinstance(parsed_intent, dict) else None)
                    or "plan_itinerary"
                )

                print(f"[repair] NO_ITINERARY → re-running '{intent_name}' with original intent")

                new_result = svc._execute_intent(
                    intent_name,
                    parsed_intent,
                    req,
                    db_prefs,
                    session_state,
                    request_trace_id,
                )

                if getattr(new_result, "ok", False):
                    result_key = (
                        "modify_result"
                        if intent_name == "modify_itinerary"
                        else "itinerary_result"
                    )
                    results[result_key] = new_result.data
                    print(f"[repair] ✓ full replan succeeded")
                else:
                    print(f"[repair] ✗ full replan failed")

                applied.append(RepairAction(
                    name="full_replan",
                    reason="No itinerary was produced on first attempt — retried.",
                    meta={"repair_ok": getattr(new_result, "ok", False)},
                ))

        return applied