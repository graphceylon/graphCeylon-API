# build FastAPI() + CORS + include routers

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..core.settings import settings
from .routes import router as language_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="GraphCeylon Language Service",
        description="Multilingual NLP service for Sri Lankan tourism",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(language_router)

    @app.get("/")
    async def root():
        return {"service": settings.SERVICE_NAME, "status": "running", "version": "0.1.0"}

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": settings.SERVICE_NAME}

    return app
