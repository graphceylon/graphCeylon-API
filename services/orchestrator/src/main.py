"""Main application entry point for Orchestrator Service."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 👇 relative import from src.api.main
from .api.main import app as orchestrator_app

app = FastAPI(
    title="GraphCeylon Orchestrator",
    description="Multi-agent orchestrator and API gateway",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/service-health")
async def service_health():
    """Health check for the wrapper app."""
    return {"service": "orchestrator-wrapper", "status": "running", "version": "0.1.0"}


# Mount the REAL orchestrator app (with /orchestrate etc.) at root
app.mount("/", orchestrator_app)
