# base64 → PCM conversion

# services/language_service/src/voice/stt/audio_processor.py
from __future__ import annotations
import base64

class AudioProcessor:
    @staticmethod
    def base64_to_bytes(base64_str: str) -> bytes:
        """
        Accepts:
          - raw base64
          - data URL base64 (data:audio/wav;base64,....)
        Returns raw bytes.
        """
        cleaned = (base64_str or "").strip().replace("\n", "").replace("\r", "")
        if cleaned.startswith("data:") and "," in cleaned:
            cleaned = cleaned.split(",", 1)[1]
        return base64.b64decode(cleaned)
