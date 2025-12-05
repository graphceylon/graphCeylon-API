# orchestrator_core/task_graph_builder.py

from typing import List
from api.schemas import ParsedIntent, TaskSummary
from orchestrator_core.intent_parser.intent_routing import INTENT_TO_AGENT, INTENT_TO_ACTION


class TaskGraphBuilder:
    """
    Builds a simple linear task graph from parsed intents.

    For each request:
      - T1: parse_intent (already executed by IntentParserAgent)
      - T2: primary intent task (e.g., call_plan_itinerary)
      - T3..Tk: secondary intent tasks (e.g., call_info_accommodation)
      - Tlast: format_response (ExplainabilityAgent)
    """

    def build(self, parsed: ParsedIntent) -> List[TaskSummary]:
        tasks: List[TaskSummary] = []
        task_id = 1

        # --- T1: parse_intent (already done when we reach here) ---
        tasks.append(
            TaskSummary(
                id=f"T{task_id}",
                type="parse_intent",
                status="completed",
                assigned_agent="IntentParserAgent",
            )
        )
        task_id += 1

        # --- T2: primary intent task ---
        primary = parsed.intent
        primary_action = INTENT_TO_ACTION.get(primary, f"handle_{primary}")
        primary_agent = INTENT_TO_AGENT.get(primary, "OrchestratorAgent")

        tasks.append(
            TaskSummary(
                id=f"T{task_id}",
                type=primary_action,
                status="pending",
                assigned_agent=primary_agent,
            )
        )
        task_id += 1

        # --- Secondary intents → extra tasks ---
        for sec_intent in parsed.secondary_intents:
            sec_action = INTENT_TO_ACTION.get(sec_intent, f"handle_{sec_intent}")
            sec_agent = INTENT_TO_AGENT.get(sec_intent, "OrchestratorAgent")

            tasks.append(
                TaskSummary(
                    id=f"T{task_id}",
                    type=sec_action,
                    status="pending",
                    assigned_agent=sec_agent,
                )
            )
            task_id += 1

        # --- Final: formatting / explanation step ---
        tasks.append(
            TaskSummary(
                id=f"T{task_id}",
                type="format_response",
                status="pending",
                assigned_agent="ExplainabilityAgent",
            )
        )

        return tasks
