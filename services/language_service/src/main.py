# # create the app via app_factory
# # include routers
# # run uvicorn (optional)

# # main.py = wiring
# # everything else = modules


"""Main application entry point for Language Service."""

import logging
from fastapi.middleware.cors import CORSMiddleware

from .core.logging import setup_logging
from .core.settings import settings
from .api.app_factory import create_app

def silence_httpx_request_logs() -> None:
    """
    Prevent httpx/httpcore from logging full request URLs.
    This avoids leaking query params like Google Translate API keys.
    """
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

setup_logging()
silence_httpx_request_logs()

# Create app from factory (routers should be included there)
app = create_app()

# Add CORS here (or inside create_app, but do it only once)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # configure properly later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OPTIONAL: keep root + health here if you want (safe)
@app.get("/")
async def root():
    return {
        "service": "language_service",
        "status": "running",
        "version": settings.VERSION if hasattr(settings, "VERSION") else "0.1.0",
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.SERVICE_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "services.language_service.src.main:app",
        host=settings.HOST,
        port=settings.SERVICE_PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=True,
    )



# """Main application entry point for Language Service."""

# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from .core.logging import setup_logging
# from .core.settings import settings
# from .api.app_factory import create_app

# setup_logging()
# app = create_app()

# app = FastAPI(
#     title="GraphCeylon Language Service",
#     description="Multilingual NLP service for Sri Lankan tourism",
#     version="0.1.0",
# )

# # CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Configure appropriately for production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )


# @app.get("/")
# async def root():
#     """Health check endpoint."""
#     return {
#         "service": "language_service",
#         "status": "running",
#         "version": "0.1.0",
#     }


# @app.get("/health")
# async def health():
#     """Detailed health check."""
#     return {"status": "healthy", 
#             "service": settings.SERVICE_NAME}


# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(app, host=settings.HOST, port=settings.SERVICE_PORT, log_level=settings.LOG_LEVEL.lower())
#     # uvicorn.run(app, host="0.0.0.0", port=8001)
