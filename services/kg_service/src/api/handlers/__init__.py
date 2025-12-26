"""API handlers package for organized route management."""

from .kg_handler import router as kg_router
from .db_handler import router as db_router

__all__ = [
    "kg_router",
    "db_router",
]
