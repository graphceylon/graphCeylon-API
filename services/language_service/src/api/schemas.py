# # TextIngestRequest, VoiceIngestRequest, RenderRequest, responses

from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Dict, Any

class TextIngestRequest(BaseModel):
    user_id: str
    input_text: str
    channel: str
    lang: str = "auto"
    session_id: str
    mode: str = "text"

class TextIngestResponse(BaseModel):
    session_id: str
    orchestrator_response: Dict[str, Any]

class RenderRequest(BaseModel):
    session_id: str
    orchestrator_output: Dict[str, Any]

class RenderResponse(BaseModel):
    session_id: str
    lang: str
    mode: str
    text: str
    voice_audio_base64: Optional[str] = None