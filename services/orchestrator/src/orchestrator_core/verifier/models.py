# services/orchestrator/src/orchestrator_core/verifier/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal

Verdict = Literal["SUPPORTED", "NEED_MORE_INFO", "UNSUPPORTED"]

@dataclass
class VerifyIssue:
    code: str
    severity: Literal["low", "medium", "high"]
    message: str
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class VerifyReport:
    verdict: Verdict
    quality_score: float
    confidence: float
    issues: List[VerifyIssue] = field(default_factory=list)

    supported_claims: int = 0
    unsupported_claims: int = 0
    neutral_claims: int = 0

    missing_fields: List[str] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "issues": [
                {
                    "code": i.code,
                    "severity": i.severity,
                    "message": i.message,
                    "meta": i.meta,
                } for i in self.issues
            ],
            "supported_claims": self.supported_claims,
            "unsupported_claims": self.unsupported_claims,
            "neutral_claims": self.neutral_claims,
            "missing_fields": self.missing_fields,
            "contradictions": self.contradictions,
        }