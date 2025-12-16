# src/db/init_db.py

from src.db.session import Base, engine
from src.db.models.user_preferences import UserPreference  # noqa: F401 (import needed so table is registered)


def init_db():
    print("Creating tables in database...")
    Base.metadata.create_all(bind=engine)
    print("Done.")


if __name__ == "__main__":
    init_db()
