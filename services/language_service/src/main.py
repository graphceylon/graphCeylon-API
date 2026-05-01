"""Main application entry point for Language Service."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure Google credentials are loaded before any client is created
from . import config as _config  # noqa: F401
from .voice_routes import router as voice_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(name)-30s  %(levelname)-7s  %(message)s")

app = FastAPI(
    title="GraphCeylon Language Service",
    description="Multilingual voice pipeline for Sri Lankan tourism — STT (Gemini Live), TTS, Translation",
    version="0.2.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register voice endpoints
app.include_router(voice_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "language_service",
        "status": "running",
        "version": "0.2.0",
        "capabilities": ["voice_pipeline", "stt", "tts", "translation"],
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {"status": "healthy", "service": "language_service"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
