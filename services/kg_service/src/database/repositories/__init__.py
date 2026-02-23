"""Repository pattern implementation for domain-specific data operations.

Repositories provide clean abstractions for database operations, following
the Repository Pattern for separation of concerns and testability.

Available Repositories:
- BaseRepository: Common database operations (queries, transactions)
- AttractionRepository: Tourist attractions and points of interest
- HolidayRepository: Public holidays and cultural celebrations
- ProjectRepository: Tourism development projects
- NewsRepository: Tourism-related news articles
- OntologyRepository: RDF/OWL ontology and domain structure
- RailwayRepository: Railway stations and train schedules

Usage:
    from database.repositories import AttractionRepository
    from core.dependencies import create_driver
    
    driver = create_driver()
    repo = AttractionRepository(driver)
    attractions = repo.query_attractions({"province": "Western"})
"""

from .base import BaseRepository
from .attraction_repository import AttractionRepository
from .holiday_repository import HolidayRepository
from .project_repository import ProjectRepository
from .news_repository import NewsRepository
from .ontology_repository import OntologyRepository
from .railway_repository import RailwayRepository
from .sub_attraction_repository import SubAttractionRepository
from .event_repository import EventRepository

__all__ = [
    "BaseRepository",
    "AttractionRepository",
    "HolidayRepository",
    "ProjectRepository",
    "NewsRepository",
    "OntologyRepository",
    "RailwayRepository",
    "SubAttractionRepository",
    "EventRepository",
]
