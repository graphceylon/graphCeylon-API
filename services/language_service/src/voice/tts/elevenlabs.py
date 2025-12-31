# ElevenLabs TTS implementation

# services/language_service/src/voice/tts/elevenlabs.py
from __future__ import annotations
from typing import Optional


class ElevenLabsTTS:
    """
    Minimal TTS stub.
    Later: integrate actual ElevenLabs SDK/API.
    """

    def __init__(self, api_key: Optional[str] = None, voice_id: Optional[str] = None):
        self.api_key = api_key
        self.voice_id = voice_id

    async def synthesize(self, text: str) -> bytes:
        # Placeholder: return empty audio bytes so pipeline doesn’t crash
        return b""
