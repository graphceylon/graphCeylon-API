# src/db/session.py
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load .env from project root (Proactive-Tourism-Recommendation)
ROOT_DIR = Path(__file__).resolve().parents[2]
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Example: COMP3_DB_URL=postgresql+psycopg2://user:pass@localhost:5432/tourgraph
DATABASE_URL = os.getenv(
    "COMP3_DB_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/tourgraph",  # change for your env
)

engine = create_engine(
    DATABASE_URL,
    echo=False,       # set True if you want to see SQL logs
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)

Base = declarative_base()
