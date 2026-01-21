# /Users/dev/Desktop/graphCeylon-API/services/recommender_service/src/api/main.py
from __future__ import annotations

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from src.db.session import SessionLocal

from src.recommendation.service import recommend_pois_from_payload


# existing routers
from src.api.routes.weather import router as weather_router
from src.api.routes.crowd import router as crowd_router

# ✅ NEW: itinerary router (create this file below)
from src.api.routes.itinerary import router as itinerary_router

from src.api.routes.sustainability import router as sustainability_router





app = FastAPI(
    title="Component 3 – Recommendation & Sustainability Service",
    version="0.1.0",
)

# routers
app.include_router(weather_router)
app.include_router(crowd_router)
app.include_router(itinerary_router)  # ✅ add
app.include_router(sustainability_router)



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
