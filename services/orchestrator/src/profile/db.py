import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

PROFILE_DB_URL = os.getenv(
    "PROFILE_DB_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/profile_db",
)

engine = create_engine(PROFILE_DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
