# logging config + get_logger()

# services/language_service/src/core/logging.py
from __future__ import annotations

import logging
from .settings import settings


def setup_logging() -> None:
    root = logging.getLogger()
    logging.getLogger("httpx").setLevel(logging.WARNING)
    level = getattr(logging, str(settings.LOG_LEVEL).upper(), logging.INFO)
    root.setLevel(level)

    # Prevent duplicate handlers on reload
    if root.handlers:
        return

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
