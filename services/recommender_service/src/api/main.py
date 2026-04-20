# /Users/dev/Desktop/graphCeylon-API/services/recommender_service/src/api/main.py
from __future__ import annotations

from pathlib import Path
import sys

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# Ensure imports work in both execution modes:
# 1) direct run from src/api (uv run main.py)
# 2) module import via uvicorn (uvicorn src.api.main:app)
current_file = Path(__file__).resolve()
service_root = current_file.parents[2]  # .../services/recommender_service
path_str = str(service_root)
if path_str not in sys.path:
    sys.path.insert(0, path_str)
if len(current_file.parents) > 4:
    repo_root = current_file.parents[4]     # .../graphCeylon-API
    path_str = str(repo_root)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from src.db.session import SessionLocal

from src.recommendation.service import recommend_pois_from_payload
from src.api.routes.recommend import router as recommend_router


# existing routers
from src.api.routes.weather import router as weather_router
from src.api.routes.crowd import router as crowd_router

# ✅ NEW: itinerary router (create this file below)
from src.api.routes.itinerary import router as itinerary_router

from src.api.routes.sustainability import router as sustainability_router

# ✅ NEW: proactive micro-moment router
from src.api.routes.proactive import router as proactive_router




app = FastAPI(
    title="Component 3 – Recommendation & Sustainability Service",
    version="0.1.0",
)

# routers
app.include_router(weather_router)
app.include_router(crowd_router)
app.include_router(itinerary_router)  # ✅ add
app.include_router(sustainability_router)
app.include_router(recommend_router)
app.include_router(proactive_router)  # ✅ micro-moment proactive recommendations



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# keep your existing endpoint
@app.post("/recommend-pois")
def recommend_pois(payload: dict, db: Session = Depends(get_db)):
    return recommend_pois_from_payload(payload, db)
