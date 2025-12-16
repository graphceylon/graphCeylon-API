from __future__ import annotations
from typing import List, Optional
from .models import AgentSpec


class AgentRegistry:
    def __init__(self, agents: List[AgentSpec]):
        self.agents = agents

    def find(self, capability: str, protocol: str) -> List[AgentSpec]:
        return [
            a for a in self.agents
            if a.enabled and (protocol in a.protocols) and (capability in a.capabilities)
        ]

    def choose_best(self, candidates: List[AgentSpec]) -> Optional[AgentSpec]:
        if not candidates:
            return None
        # simple scoring for now: cost then p95 latency
        return sorted(candidates, key=lambda a: (a.cost_weight, a.sla.p95_ms or 10**9))[0]

    def pick(self, capability: str, protocol: str = "a2a") -> Optional[AgentSpec]:
        cands = self.find(capability, protocol)
        return self.choose_best(cands)
