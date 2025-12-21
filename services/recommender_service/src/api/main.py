from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.recommendation.service import recommend_pois_from_payload

from src.api.routes.weather import router as weather_router  # ✅ add
from src.api.routes.crowd import router as crowd_router

app = FastAPI(
    title="Component 3 – Recommendation & Sustainability Service",
    version="0.1.0",
)

app.include_router(weather_router)  # ✅ add
app.include_router(crowd_router)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/recommend-pois")
def recommend_pois(payload: dict, db: Session = Depends(get_db)):
    return recommend_pois_from_payload(payload, db)
