"""Core package with configuration, logging, and dependency injection."""

from .settings import settings, Settings
from .dependencies import (
    create_driver,
    get_driver,
    get_db_manager,
    get_reasoning_orchestrator,
    set_db_manager,
    set_reasoning_orchestrator,
    close_driver,
)
from .logging_config import setup_logging, get_logger

# Backward compatibility
from .config import settings as legacy_settings

__all__ = [
    "settings",
    "Settings",
    "create_driver",
    "get_driver",
    "get_db_manager",
    "get_reasoning_orchestrator",
    "set_db_manager",
    "set_reasoning_orchestrator",
    "close_driver",
    "setup_logging",
    "get_logger",
    "legacy_settings",
]

