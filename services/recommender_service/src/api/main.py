# src/api/main.py

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.recommendation.service import recommend_pois_from_payload

app = FastAPI(
    title="Component 3 – Recommendation & Sustainability Service",
    version="0.1.0",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/recommend-pois")
def recommend_pois(payload: dict, db: Session = Depends(get_db)):
    return recommend_pois_from_payload(payload, db)
