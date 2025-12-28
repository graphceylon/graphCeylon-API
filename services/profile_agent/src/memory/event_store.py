from sqlalchemy.orm import Session
from uuid import uuid4
from .models import ProfileEvent

class EventStore:

    def __init__(self, db: Session):
        self.db = db

    def log_event(self, user_id, session_id, event_type, payload):
        event = ProfileEvent(
            id=str(uuid4()),
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload
        )
        self.db.add(event)
        self.db.commit()
