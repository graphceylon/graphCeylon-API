# orchestrator_core/task_graph_runtime.py
from __future__ import annotations

from typing import List, Dict
from .task_graph_builder import TaskNode
from .task_executor import ExecTask


def to_exec_tasks(nodes: Dict[str, TaskNode]) -> List[ExecTask]:
    # tasks order doesn’t matter for executor; executor respects depends_on
    return [
        ExecTask(
            id=n.id,
            type=n.type,
            assigned_agent=n.assigned_agent,
            depends_on=list(n.depends_on),
        )
        for n in nodes.values()
    ]
