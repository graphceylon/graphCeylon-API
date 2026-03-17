from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerifyLabel(str, Enum):
    SUPPORTED      = "SUPPORTED"
    UNSUPPORTED    = "UNSUPPORTED"
    NEED_MORE_INFO = "NEED_MORE_INFO"


@dataclass
class Observation:
    ok: bool
    coverage: float = 0.0
    risk_flags: Dict[str, Any] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


@dataclass
class VerifyIssue:
    code: str
    severity: str           # "low" | "medium" | "high"
    message: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerifyReport:
    ok: bool
    quality_score: float    # 0..1
    issues: List[VerifyIssue] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepairAction:
    name: str               # e.g. "replan_with_corrected_destination"
    reason: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopResult:
    observation: Observation
    verify_report: Optional[VerifyReport]
    repairs_applied: List[RepairAction] = field(default_factory=list)
    changed_summary: List[str] = field(default_factory=list)
    confidence: str = "medium"   # "low" | "medium" | "high"