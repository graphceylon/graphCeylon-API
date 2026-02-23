"""Utility constants for the Knowledge Graph Service."""

# Database Configuration
DEFAULT_QUERY_LIMIT = 10
MAX_QUERY_LIMIT = 100
DEFAULT_HOLIDAY_LIMIT = 50
MAX_HOLIDAY_LIMIT = 200
DEFAULT_NEWS_LIMIT = 20
DEFAULT_PROJECT_LIMIT = 20

# Vector Search
DEFAULT_TOP_K = 5
MAX_TOP_K = 20

# Temporal
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

DAYS_OF_WEEK = [
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"
]

# Holiday Categories
HOLIDAY_CATEGORIES = {
    "RELIGIOUS": "Religious",
    "CULTURAL": "Cultural",
    "NATIONAL": "National",
    "GENERAL": "General",
}

# Holiday Types
HOLIDAY_TYPES = {
    "POYA_DAY": "Poya Day",
    "PUBLIC_HOLIDAY": "Public Holiday",
    "BANK_HOLIDAY": "Bank Holiday",
    "MERCANTILE_HOLIDAY": "Mercantile Holiday",
    "OBSERVANCE": "Observance",
}

# Project Types
PROJECT_TYPES = {
    "INFRASTRUCTURE": "Infrastructure",
    "REGIONAL": "Regional Development",
    "CULTURAL": "Cultural Heritage",
    "ENVIRONMENT": "Environmental Conservation",
    "TOURISM": "Tourism Development",
}

# Node Labels
NODE_LABELS = {
    "COUNTRY": "Country",
    "PROVINCE": "Province",
    "DISTRICT": "District",
    "ATTRACTION": "Attraction",
    "SUB_ATTRACTION": "SubAttraction",
    "POI_GROUP": "POIGroup",
    "EVENT": "Event",
    "EVENT_TYPE": "EventType",
    "VENUE": "Venue",
    "ORGANIZER": "Organizer",
    "HOLIDAY": "Holiday",
    "PROJECT": "TourismProject",
    "NEWS": "NewsArticle",
    "DOMAIN": "Domain",
    "YEAR": "Year",
    "MONTH": "Month",
    "BUS_TERMINAL": "BusTerminal",
    "BUS_SCHEDULE": "BusSchedule",
    "BUS_DEPOT": "BusDepot",
}

# Relationship Types
RELATIONSHIP_TYPES = {
    "HAS_PROVINCE": "HAS_PROVINCE",
    "HAS_DISTRICT": "HAS_DISTRICT",
    "IN_PROVINCE": "IN_PROVINCE",
    "LOCATED_IN": "LOCATED_IN",
    "HAS_ATTRACTION": "HAS_ATTRACTION",
    "HAS_DOMAIN": "HAS_DOMAIN",
    "BELONGS_TO_DOMAIN": "BELONGS_TO_DOMAIN",
    "HAS_YEAR": "HAS_YEAR",
    "HAS_MONTH": "HAS_MONTH",
    "HAS_HOLIDAY": "HAS_HOLIDAY",
    "IN_YEAR": "IN_YEAR",
    "IN_MONTH": "IN_MONTH",
    "LOCATED_IN_PROVINCE": "LOCATED_IN_PROVINCE",
    "LOCATED_IN_DISTRICT": "LOCATED_IN_DISTRICT",
    "PUBLISHED_IN_YEAR": "PUBLISHED_IN_YEAR",
    "PUBLISHED_IN_MONTH": "PUBLISHED_IN_MONTH",
    "SUB_ATTRACTION_OF": "SUB_ATTRACTION_OF",
    "BELONGS_TO_GROUP": "BELONGS_TO_GROUP",
    "NEAR_HOTEL": "NEAR_HOTEL",
    "HAS_TYPE": "HAS_TYPE",
    "HELD_AT": "HELD_AT",
    "ORGANIZED_BY": "ORGANIZED_BY",
    "DEPARTS_FROM": "DEPARTS_FROM",
    "ARRIVES_AT": "ARRIVES_AT",
    "OPERATED_BY_DEPOT": "OPERATED_BY_DEPOT",
    "CONNECTED_BY_BUS": "CONNECTED_BY_BUS",
}

# Status Values
STATUS_VALUES = {
    "ACTIVE": "active",
    "INACTIVE": "inactive",
    "CONFIRMED": "confirmed",
    "TENTATIVE": "tentative",
    "PLANNED": "planned",
    "COMPLETED": "completed",
}

# Sub-Attraction / POI Constants
DEFAULT_SUB_ATTRACTION_LIMIT = 20

POI_GROUPS = {
    "SHOPPING": "Shopping & City",
    "FOOD": "Food & Markets",
    "RELIGIOUS": "Religious / Spiritual",
    "CULTURE": "Culture & Heritage",
    "ADVENTURE": "Adventure & Hiking",
    "NATURE": "Nature & Eco",
}

# Event Constants
DEFAULT_EVENT_LIMIT = 20

# Bus Schedule Constants
DEFAULT_BUS_SCHEDULE_LIMIT = 50

EVENT_TYPES = {
    "CONFERENCE": "Conference/ Seminar",
    "DRAMA": "Drama/ Theatre",
    "EXHIBITION": "Fair/ Exhibition",
    "MUSIC": "Music/ Concert",
    "EXCURSION": "Public Lecture/ Excursion",
    "MEETING": "Public Lecture/ Meeting",
    "CULTURAL": "Social/ Cultural",
    "SPORTS": "Sports",
    "TRAINING": "Training/ Course",
    "OTHER": "Other",
}

# Error Messages
ERROR_MESSAGES = {
    "PROVINCE_NOT_FOUND": "Province not found",
    "DISTRICT_NOT_FOUND": "District not found",
    "ATTRACTION_NOT_FOUND": "Attraction not found",
    "HOLIDAY_NOT_FOUND": "Holiday not found",
    "PROJECT_NOT_FOUND": "Project not found",
    "NEWS_NOT_FOUND": "News article not found",
    "SUB_ATTRACTION_NOT_FOUND": "Sub-attraction not found",
    "EVENT_NOT_FOUND": "Event not found",
    "BUS_TERMINAL_NOT_FOUND": "Bus terminal not found",
    "BUS_SCHEDULE_NOT_FOUND": "Bus schedule not found",
    "INVALID_DATE_FORMAT": "Invalid date format. Expected YYYY-MM-DD",
    "INVALID_QUERY": "Invalid query parameters",
    "DATABASE_ERROR": "Database operation failed",
    "INITIALIZATION_ERROR": "Database initialization failed",
    "APOC_NOT_AVAILABLE": "APOC plugin is not available",
}

# Success Messages
SUCCESS_MESSAGES = {
    "CREATED": "Resource created successfully",
    "UPDATED": "Resource updated successfully",
    "DELETED": "Resource deleted successfully",
    "LOADED": "Data loaded successfully",
    "INITIALIZED": "Database initialized successfully",
}
