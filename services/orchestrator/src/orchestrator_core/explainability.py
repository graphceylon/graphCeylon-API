# orchestrator_core/explainability.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class ExplainPacket:
    intent: str
    domain: str
    entities: Dict[str, Any] = field(default_factory=dict)

    effective_prefs: Dict[str, Any] = field(default_factory=dict)
    preference_sources: Dict[str, Any] = field(default_factory=dict)

    recall_used: bool = False
    recall_snippets: List[str] = field(default_factory=list)

    tool: Dict[str, Any] = field(default_factory=dict)   # provider/endpoint/latency
    summary: str = ""
    item_whys: Dict[str, List[str]] = field(default_factory=dict)  # optional per-item bullets

def merge_explain(packets: List[Dict[str, Any]]) -> Dict[str, Any]:
    merged = {
        "intent": None,
        "domain": None,
        "entities": {},
        "effective_prefs": {},
        "preference_sources": {},
        "recall_used": False,
        "recall_snippets": [],
        "tool_calls": [],
        "item_whys": {},
        "summary": [],
    }

    for p in packets:
        if not isinstance(p, dict):
            continue
        merged["intent"] = merged["intent"] or p.get("intent")
        merged["domain"] = merged["domain"] or p.get("domain")
        merged["entities"].update(p.get("entities") or {})
        merged["effective_prefs"].update(p.get("effective_prefs") or {})
        merged["preference_sources"].update(p.get("preference_sources") or {})

        merged["recall_used"] = merged["recall_used"] or bool(p.get("recall_used"))
        merged["recall_snippets"].extend(p.get("recall_snippets") or [])

        if p.get("tool"):
            merged["tool_calls"].append(p["tool"])

        iw = p.get("item_whys") or {}
        for k, v in iw.items():
            merged["item_whys"].setdefault(k, []).extend(v or [])

        if p.get("summary"):
            merged["summary"].append(p["summary"])

    merged["summary"] = " ".join([s for s in merged["summary"] if s]).strip()
    return merged