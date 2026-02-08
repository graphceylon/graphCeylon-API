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
    "HOLIDAY": "Holiday",
    "PROJECT": "TourismProject",
    "NEWS": "NewsArticle",
    "DOMAIN": "Domain",
    "YEAR": "Year",
    "MONTH": "Month",
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

# Error Messages
ERROR_MESSAGES = {
    "PROVINCE_NOT_FOUND": "Province not found",
    "DISTRICT_NOT_FOUND": "District not found",
    "ATTRACTION_NOT_FOUND": "Attraction not found",
    "HOLIDAY_NOT_FOUND": "Holiday not found",
    "PROJECT_NOT_FOUND": "Project not found",
    "NEWS_NOT_FOUND": "News article not found",
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
