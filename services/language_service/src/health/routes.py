# services/language_service/src/health/routes.py
from __future__ import annotations

from fastapi import APIRouter
from typing import Dict, Any

from ..core.settings import settings
from ..metrics.store import metrics
from .checks import (
    check_stt_rest,
    check_stt_streaming,
    check_translator,
    check_orchestrator,
)

router = APIRouter(prefix="/v1/language", tags=["health"])


@router.get("/health")
async def health() -> Dict[str, Any]:
    """
    Full health snapshot (quick).
    """
    stt_stream = await check_stt_streaming()
    orch = await check_orchestrator(timeout_s=4.0)

    return {
        "service": settings.SERVICE_NAME,
        "ok": bool(stt_stream["ok"] and orch["ok"]),
        "stt_streaming": stt_stream,
        "orchestrator": orch,
    }


@router.get("/health/stt")
async def health_stt() -> Dict[str, Any]:
    """
    STT diagnostics: REST + Streaming.
    """
    rest = await check_stt_rest()
    stream = await check_stt_streaming()
    return {"ok": bool(rest["ok"] or stream["ok"]), "rest": rest, "streaming": stream}


@router.get("/health/translator")
async def health_translator() -> Dict[str, Any]:
    """
    Translator diagnostics: provider + roundtrip sample.
    """
    return await check_translator()


@router.get("/health/orchestrator")
async def health_orchestrator() -> Dict[str, Any]:
    """
    Orchestrator diagnostics: reachability + basic status.
    """
    return await check_orchestrator()


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Returns in-memory latency/error metrics snapshots.
    """
    return {
        "service": settings.SERVICE_NAME,
        "metrics": metrics.snapshot(),
    }
