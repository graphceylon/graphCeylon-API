# TranscriptionResult

# services/language_service/src/voice/stt/models.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    is_final: bool
    timestamp: datetime

    def meets_confidence_threshold(self, threshold: float) -> bool:
        return self.confidence >= threshold