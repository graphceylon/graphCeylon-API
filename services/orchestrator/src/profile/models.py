from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def utcnow():
    return datetime.now(timezone.utc)

class UserProfileRow(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True, index=True)
    profile = Column(JSONB, nullable=False, default=dict)

    profile_version = Column(Integer, nullable=False, default=1)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
