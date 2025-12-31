# APIRouter(prefix="/v1/language")

from fastapi import APIRouter
from .ingest_text import router as ingest_text_router
from .render import router as render_router

router = APIRouter()
router.include_router(ingest_text_router, prefix="/v1/language", tags=["language"])
router.include_router(render_router, prefix="/v1/language", tags=["language"])
