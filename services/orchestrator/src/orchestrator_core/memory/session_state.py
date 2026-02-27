from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List

@dataclass
class SessionState:
    schema_version: str = "1.0"
    conversation_stage: str = "discover"
    last_intent: Optional[str] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    last_tool_outputs_refs: Dict[str, Any] = field(default_factory=dict)
    pending_actions: List[Any] = field(default_factory=list)
    updated_at: Optional[str] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SessionState":
        d = d or {}
        return SessionState(
            schema_version=d.get("schema_version", "1.0"),
            conversation_stage=d.get("conversation_stage", "discover"),
            last_intent=d.get("last_intent"),
            slots=d.get("slots") or {},
            last_tool_outputs_refs=d.get("last_tool_outputs_refs") or {},
            pending_actions=d.get("pending_actions") or [],
            updated_at=d.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "conversation_stage": self.conversation_stage,
            "last_intent": self.last_intent,
            "slots": self.slots or {},
            "last_tool_outputs_refs": self.last_tool_outputs_refs or {},
            "pending_actions": self.pending_actions or [],
            "updated_at": self.updated_at,
        }
