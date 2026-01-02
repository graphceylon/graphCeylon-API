# services/language_service/src/api/routes.py
from fastapi import APIRouter
from .ingest_text import router as ingest_text_router
from .ingest_voice import router as ingest_voice_router
from .ingest_voice_file import router as ingest_voice_file_router
from .render import router as render_router
from .ws_ingest_voice import router as ws_ingest_voice_router
from ..health.routes import router as health_router

router = APIRouter()

router.include_router(ingest_text_router, prefix="/v1/language", tags=["language"])
router.include_router(render_router, prefix="/v1/language", tags=["language"])
router.include_router(ingest_voice_router, prefix="/v1/language", tags=["language"])
router.include_router(ingest_voice_file_router, prefix="/v1/language", tags=["language"])

router.include_router(ws_ingest_voice_router)
router.include_router(ws_ingest_voice_router, prefix="/v1/language")

# health + metrics endpoints
router.include_router(health_router)
