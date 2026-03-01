from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Blackboard:
    user_query: str
    user_id: str
    session_id: str

    intents: Dict[str, Any] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    slots: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)

    tool_results: Dict[str, Any] = field(default_factory=dict)

    draft_answer: Optional[Dict[str, Any]] = None
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    writeback_proposals: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_query": self.user_query,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "intents": self.intents,
            "entities": self.entities,
            "slots": self.slots,
            "preferences": self.preferences,
            "tool_results": self.tool_results,
            "draft_answer": self.draft_answer,
            "pending_actions": self.pending_actions,
            "verification": self.verification,
            "writeback_proposals": self.writeback_proposals,
        }