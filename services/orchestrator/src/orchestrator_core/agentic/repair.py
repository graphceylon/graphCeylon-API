from __future__ import annotations
from typing import Any, Dict, List, Optional
from .models import RepairAction, VerifyReport

class RepairAgent:
    """
    Decides + executes repairs.
    Uses OrchestratorService._execute_intent to call modify_itinerary or re-plan.
    """

    def decide(self, report: VerifyReport) -> List[RepairAction]:
        actions: List[RepairAction] = []
        if not report or not report.issues:
            return actions

        for issue in report.issues:
            if issue.code == "WEATHER_RISK":
                actions.append(RepairAction(
                    name="repair_weather",
                    reason="Weather risk detected; swap outdoor activities to safer slots/days.",
                    meta=issue.meta,
                ))
            elif issue.code == "CROWD_RISK":
                actions.append(RepairAction(
                    name="repair_crowd",
                    reason="Avoid-crowds preference conflicts with high crowd risk; replace crowded POIs.",
                    meta=issue.meta,
                ))
            elif issue.code == "TOO_MANY_POIS":
                actions.append(RepairAction(
                    name="repair_feasibility",
                    reason="Too many POIs; reduce or redistribute to fit daily constraints.",
                    meta=issue.meta,
                ))

        # de-dupe by name preserving order
        seen = set()
        out: List[RepairAction] = []
        for a in actions:
            if a.name not in seen:
                out.append(a)
                seen.add(a.name)
        return out

    def apply_repairs(
        self,
        *,
        svc,                    # OrchestratorService instance (so we can call _execute_intent)
        actions: List[RepairAction],
        parsed_intent,
        req,
        db_prefs: Dict[str, Any],
        session_state,
        request_trace_id: str,
        results: Dict[str, Any],
    ) -> List[RepairAction]:

        applied: List[RepairAction] = []
        if not actions:
            return applied

        # We use modify_itinerary as the universal repair tool (simple + powerful)
        # We pass a "repair_mode" hint in entities so your mapper can include it.
        ents = parsed_intent.entities.model_dump(exclude_none=False)

        for a in actions:
            ents["repair_mode"] = a.name  # <-- mapper can forward this to recommender
            patched_pi = parsed_intent.model_copy(update={"entities": type(parsed_intent.entities)(**ents)})

            out = svc._execute_intent(
                "modify_itinerary",
                patched_pi,
                req,
                db_prefs,
                session_state,
                request_trace_id,
            )

            # If modify succeeded, override itinerary_result for final formatting
            if getattr(out, "ok", False):
                results["modify_result"] = out.data
                results["itinerary_result"] = out.data
                applied.append(a)

        return applied