# strict request/response models for orchestrator

from __future__ import annotations
from pydantic import BaseModel


class OrchestratorRequest(BaseModel):
    user_id: str
    input_text: str
    channel: str
    lang: str
    session_id: str


# from __future__ import annotations

# from pydantic import BaseModel, Field


# class OrchestratorRequest(BaseModel):
#     user_id: str = Field(..., min_length=1)
#     input_text: str = Field(..., min_length=1)
#     channel: str = Field(..., description="chat|voice|...")
#     lang: str = Field(..., description="language code sent to orchestrator (later always 'en')")
#     session_id: str = Field(..., min_length=1)