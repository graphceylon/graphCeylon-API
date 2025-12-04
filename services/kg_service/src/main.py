"""Main entry point for the Knowledge Graph application."""

from api.main import app

if __name__ == "__main__":
    import uvicorn
    from core.config import settings
    
    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info"
    )
