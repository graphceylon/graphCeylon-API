# # /v1/language/ingest

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from .schemas import TextIngestRequest, TextIngestResponse
from ..pipeline.input_pipeline import InputPipeline
from ..core.logging import get_logger

router = APIRouter()
pipe = InputPipeline()
logger = get_logger("language_service.ingest_text")

@router.post("/ingest", response_model=TextIngestResponse)
async def ingest_text(req: TextIngestRequest):
    try:
        orch_json = await pipe.process_text(
            user_id=req.user_id,
            input_text=req.input_text,
            channel=req.channel,
            lang=req.lang,
            session_id=req.session_id,
            mode=req.mode,
        )
        return TextIngestResponse(
            session_id=req.session_id,
            orchestrator_response=orch_json,
        )
    except Exception as e:
        logger.exception(f"ingest failed for session_id={req.session_id}")
        raise HTTPException(status_code=502, detail=str(e))