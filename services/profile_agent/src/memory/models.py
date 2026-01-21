from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ProfileEvent(Base):
    __tablename__ = "profile_events"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    session_id = Column(String)
    event_type = Column(String)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
