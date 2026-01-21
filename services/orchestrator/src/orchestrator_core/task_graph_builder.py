# orchestrator_core/task_graph_builder.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..api.schemas import ParsedIntent, TaskSummary
from .intent_parser.intent_routing import INTENT_TO_AGENT, INTENT_TO_ACTION


# -----------------------------
# Internal DAG representation
# -----------------------------

@dataclass
class TaskNode:
    """
    A node in the orchestration DAG.
    This is the internal representation used by the executor.

    - depends_on: list of task IDs that MUST complete before this task can run
    - policy fields (timeout, retries) make it production-ready
    """
    id: str
    type: str
    assigned_agent: str
    status: str = "pending"
    depends_on: List[str] = field(default_factory=list)

    # Execution policy
    timeout_ms: int = 15000
    max_retries: int = 0
    retry_backoff_ms: int = 250
    critical: bool = True  # If True and fails => orchestration should fail


class TaskGraphError(Exception):
    pass


class TaskGraphBuilder:
    """
    Builds a DAG task graph from ParsedIntent.

    Default topology:

      T1  parse_intent (completed)
        ↓
      T2  extract_entities (pending)                [optional but recommended]
        ↓
      T3  primary task (pending)
      T4.. secondary tasks (pending, parallel fan-out)
        ↓            ↓
         └────────────┘
      T_last format_response (pending, fan-in)

    Optional:
      - Visa verification task (verify_policy_evidence)
    """

    def __init__(
        self,
        *,
        enable_entity_extraction: bool = True,
        add_verification_for_visa: bool = True,
    ) -> None:
        self.enable_entity_extraction = enable_entity_extraction
        self.add_verification_for_visa = add_verification_for_visa
        self._nodes: Dict[str, TaskNode] = {}

    def build(self, parsed: ParsedIntent) -> List[TaskSummary]:
        """
        Build the DAG, validate it, and return TaskSummary list in topological order
        for UI/debug output.

        NOTE: Your executor should use `get_nodes()` to execute the DAG properly.
        """
        self._nodes = {}
        next_id = 1

        def new_id() -> str:
            nonlocal next_id
            tid = f"T{next_id}"
            next_id += 1
            return tid

        # ---- T1: parse_intent (already executed by IntentParserAgent) ----
        t1 = TaskNode(
            id=new_id(),
            type="parse_intent",
            status="completed",
            assigned_agent="IntentParserAgent",
            depends_on=[],
            timeout_ms=5000,
            max_retries=0,
            critical=True,
        )
        self._add(t1)

        # ---- T2: extract_entities (LLM + rules) ----
        # This is the step that enriches parsed_intent.entities reliably.
        # It becomes the single dependency for downstream tasks.
        anchor_dep = t1.id
        if self.enable_entity_extraction and self._needs_entity_extraction(parsed):
            t2 = TaskNode(
                id=new_id(),
                type="extract_entities",
                assigned_agent="IntentParserAgent",  # or EntityExtractorAgent if you have one
                depends_on=[t1.id],
                timeout_ms=12000,
                max_retries=1,
                retry_backoff_ms=300,
                critical=True,
            )
            self._add(t2)
            anchor_dep = t2.id  # downstream depends on entity extraction instead of just parse_intent

        # ---- T3: primary intent task ----
        primary_intent = parsed.intent
        # primary_action = INTENT_TO_ACTION.get(primary_intent, f"handle_{primary_intent}")
        primary_agent = INTENT_TO_AGENT.get(primary_intent, "OrchestratorAgent")

        t_primary = TaskNode(
            id=new_id(),
            type=primary_intent,
            assigned_agent=primary_agent,
            depends_on=[anchor_dep],
            timeout_ms=self._default_timeout_for_intent(primary_intent),
            max_retries=self._default_retries_for_intent(primary_intent),
            retry_backoff_ms=400,
            critical=True,
        )
        self._add(t_primary)

        # ---- Secondary tasks fan-out (parallel) ----
        secondary_ids: List[str] = []
        for sec_intent in (parsed.secondary_intents or []):
            # sec_action = INTENT_TO_ACTION.get(sec_intent, f"handle_{sec_intent}")
            sec_agent = INTENT_TO_AGENT.get(sec_intent, "OrchestratorAgent")

            t_sec = TaskNode(
                id=new_id(),
                type=sec_intent,
                assigned_agent=sec_agent,
                depends_on=[anchor_dep],   # run in parallel after entities exist
                timeout_ms=self._default_timeout_for_intent(sec_intent),
                max_retries=self._default_retries_for_intent(sec_intent),
                retry_backoff_ms=400,
                critical=False,  # secondary tasks are usually "nice-to-have"
            )
            self._add(t_sec)
            secondary_ids.append(t_sec.id)

        # ---- Optional: verification task for visa (adds research-grade trust layer) ----
        verification_id: Optional[str] = None
        if self.add_verification_for_visa and self._is_visa_like(parsed):
            t_verify = TaskNode(
                id=new_id(),
                type="verify_policy_evidence",
                assigned_agent="VerificationAgent",
                depends_on=[t_primary.id],
                timeout_ms=8000,
                max_retries=0,
                critical=False,  # if verifier fails, still answer but warn
            )
            self._add(t_verify)
            verification_id = t_verify.id

        # ---- Final: format_response fan-in (wait for all tasks) ----
        deps = [t_primary.id] + secondary_ids
        if verification_id:
            deps.append(verification_id)

        t_fmt = TaskNode(
            id=new_id(),
            type="format_response",
            assigned_agent="ExplainabilityAgent",
            depends_on=deps,
            timeout_ms=15000,
            max_retries=0,
            critical=True,
        )
        self._add(t_fmt)

        # ---- Validate DAG ----
        self._validate()

        # ---- Return summaries in deterministic topological order ----
        ordered = self._toposort()
        return [self._to_summary(n) for n in ordered]

    def get_nodes(self) -> Dict[str, TaskNode]:
        """
        Executor should use this DAG.
        TaskSummary is only for display/logging.
        """
        return dict(self._nodes)

    # ----------------
    # Internal helpers
    # ----------------

    def _add(self, node: TaskNode) -> None:
        if node.id in self._nodes:
            raise TaskGraphError(f"Duplicate task id: {node.id}")
        self._nodes[node.id] = node

    def _to_summary(self, node: TaskNode) -> TaskSummary:
        # If your TaskSummary doesn't include depends_on/policy,
        # keep it minimal for UI. Executor uses TaskNode.
        return TaskSummary(
            id=node.id,
            type=node.type,
            status=node.status,
            assigned_agent=node.assigned_agent,
        )

    def _validate(self) -> None:
        # 1) Dependencies must exist
        for nid, node in self._nodes.items():
            for dep in node.depends_on:
                if dep not in self._nodes:
                    raise TaskGraphError(f"{nid} depends on missing task {dep}")

        # 2) No cycles (toposort must include all nodes)
        self._toposort(raise_on_cycle=True)

    def _toposort(self, *, raise_on_cycle: bool = True) -> List[TaskNode]:
        """
        Kahn topological sort with deterministic ordering.
        Determinism matters for benchmarking and reproducibility.
        """
        indeg: Dict[str, int] = {k: 0 for k in self._nodes}
        children: Dict[str, List[str]] = {k: [] for k in self._nodes}

        for nid, node in self._nodes.items():
            for dep in node.depends_on:
                children[dep].append(nid)
                indeg[nid] += 1

        # stable ordering: sort by numeric part of T#
        ready = sorted([nid for nid, d in indeg.items() if d == 0], key=self._task_id_num)

        out: List[TaskNode] = []
        while ready:
            nid = ready.pop(0)
            out.append(self._nodes[nid])
            for ch in children[nid]:
                indeg[ch] -= 1
                if indeg[ch] == 0:
                    ready.append(ch)
                    ready.sort(key=self._task_id_num)

        if len(out) != len(self._nodes) and raise_on_cycle:
            raise TaskGraphError("Cycle detected in task graph")

        return out

    @staticmethod
    def _task_id_num(task_id: str) -> int:
        try:
            return int(task_id[1:])  # "T12" -> 12
        except Exception:
            return 10**9

    @staticmethod
    def _default_timeout_for_intent(intent: str) -> int:
        # tune per intent: forecasting/retrieval can take longer
        if (intent or "").startswith("forecast_"):
            return 20000
        if intent in {"info_visa_policy"}:
            return 15000
        return 15000

    @staticmethod
    def _default_retries_for_intent(intent: str) -> int:
        # retrieval-like calls can benefit from one retry
        if intent in {"info_visa_policy", "info_accommodation", "info_transport", "info_attraction"}:
            return 1
        return 0

    @staticmethod
    def _is_visa_like(parsed: ParsedIntent) -> bool:
        if (parsed.domain_category or "").lower() == "visa":
            return True
        if (parsed.intent or "").startswith("info_visa"):
            return True
        return False

    @staticmethod
    def _needs_entity_extraction(parsed: ParsedIntent) -> bool:
        # Some intents do not require entity extraction (you can expand this rule)
        intent = (parsed.intent or "").lower()
        if intent in {"explanation_request"}:
            return False
        return True
