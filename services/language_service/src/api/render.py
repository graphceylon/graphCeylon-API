# /v1/language/render

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from .schemas import RenderRequest, RenderResponse
from ..pipeline.output_pipeline import OutputPipeline

router = APIRouter()
pipe = OutputPipeline()

@router.post("/render", response_model=RenderResponse)
async def render(req: RenderRequest):
    try:
        out = await pipe.render(
            session_id=req.session_id,
            orchestrator_output=req.orchestrator_output,
        )
        return out
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
