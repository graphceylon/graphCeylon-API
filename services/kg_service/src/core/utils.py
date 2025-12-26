"""Utility functions for the Knowledge Graph Service."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)


def format_date(date_obj: date) -> str:
    """Format a date object to ISO format string (YYYY-MM-DD)."""
    if isinstance(date_obj, datetime):
        return date_obj.date().isoformat()
    return date_obj.isoformat()


def parse_date(date_str: str) -> Optional[date]:
    """Parse a date string in YYYY-MM-DD format to a date object."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        logger.warning(f"Invalid date format: {date_str}")
        return None


def extract_date_components(date_obj: date) -> Dict[str, Any]:
    """Extract year, month, day components from a date object."""
    return {
        "year": date_obj.year,
        "month": date_obj.month,
        "day": date_obj.day,
        "weekday": date_obj.strftime("%A")
    }


def calculate_duration(start_date: date, end_date: date) -> int:
    """Calculate duration in days between two dates (inclusive)."""
    return (end_date - start_date).days + 1


def generate_id(prefix: str, name: str, timestamp: Optional[float] = None) -> str:
    """Generate a unique ID with a prefix, name, and optional timestamp."""
    if timestamp is None:
        timestamp = datetime.now().timestamp()
    clean_name = name.lower().replace(' ', '_').replace('/', '_')[:50]
    return f"{prefix}_{clean_name}_{timestamp}"


def clean_filename(filename: str) -> str:
    """Clean a filename by removing/replacing invalid characters."""
    return "".join(c if c.isalnum() or c in ('-', '_', '.') else '_' for c in filename)


def ensure_directory(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length, adding a suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text by collapsing multiple spaces."""
    return " ".join(text.split())


def clean_cypher_statement(statement: str) -> str:
    """Clean a Cypher statement by removing comments and normalizing whitespace."""
    lines = statement.split('\n')
    cleaned_lines = [
        line for line in lines 
        if line.strip() and not line.strip().startswith('//')
    ]
    return '\n'.join(cleaned_lines)


def build_where_clause(conditions: List[str]) -> str:
    """Build a WHERE clause from a list of conditions."""
    if not conditions:
        return ""
    return "WHERE " + " AND ".join(conditions)


def build_cypher_params(filters: Dict[str, Any], exclude_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Build Cypher query parameters from a filters dictionary."""
    if exclude_keys is None:
        exclude_keys = []
    return {k: v for k, v in filters.items() if v is not None and k not in exclude_keys}


def format_provenance(source: str, operation: str, **kwargs) -> Dict[str, Any]:
    """Format provenance metadata for data operations."""
    return {
        "source": source,
        "operation": operation,
        "timestamp": datetime.now().isoformat(),
        **kwargs
    }


def paginate_results(results: List[Any], page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """Paginate a list of results."""
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    return {
        "results": results[start_idx:end_idx],
        "page": page,
        "page_size": page_size,
        "total": len(results),
        "total_pages": (len(results) + page_size - 1) // page_size
    }


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with dict2 values taking precedence."""
    result = dict1.copy()
    result.update(dict2)
    return result


def filter_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove keys with None values from a dictionary."""
    return {k: v for k, v in data.items() if v is not None}


def safe_get(data: Dict[str, Any], *keys, default=None) -> Any:
    """Safely get nested dictionary values with a default fallback."""
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
            if result is None:
                return default
        else:
            return default
    return result


def format_list_for_display(items: List[str], max_items: int = 5) -> str:
    """Format a list for display, truncating if too long."""
    if not items:
        return "[]"
    if len(items) <= max_items:
        return ", ".join(items)
    return ", ".join(items[:max_items]) + f", ... ({len(items) - max_items} more)"


def validate_coordinates(latitude: Optional[float], longitude: Optional[float]) -> bool:
    """Validate if coordinates are within valid ranges."""
    if latitude is None or longitude is None:
        return False
    return -90 <= latitude <= 90 and -180 <= longitude <= 180


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two coordinates using Haversine formula.
    Returns distance in kilometers.
    """
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    
    a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c
