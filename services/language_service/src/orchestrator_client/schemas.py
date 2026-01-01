# strict request/response models for orchestrator

from __future__ import annotations
from pydantic import BaseModel


class OrchestratorRequest(BaseModel):
    user_id: str
    input_text: str
    channel: str
    lang: str
    session_id: str
