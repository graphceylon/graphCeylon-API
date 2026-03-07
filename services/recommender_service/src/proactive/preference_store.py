"""
proactive.preference_store
~~~~~~~~~~~~~~~~~~~~~~~~~~
In-memory store for user notification preferences.

In production this would sit on top of a database table; for now an
in-memory dict with sensible defaults is sufficient to demonstrate the
flow and respect user opt-outs / rate-limits.
"""

from __future__ import annotations

from typing import Dict, Optional

from .schemas import NotificationPreferences


# ── in-memory store (user_id → prefs) ──
_STORE: Dict[str, NotificationPreferences] = {}


def get_preferences(user_id: str) -> NotificationPreferences:
    """
    Return the notification preferences for *user_id*.
    Creates a default record if one does not exist yet.
    """
    if user_id not in _STORE:
        _STORE[user_id] = NotificationPreferences(user_id=user_id)
    return _STORE[user_id]


def upsert_preferences(prefs: NotificationPreferences) -> NotificationPreferences:
    """Create or fully replace preferences for a user."""
    _STORE[prefs.user_id] = prefs
    return prefs


def update_preferences(
    user_id: str,
    patch: Dict,
) -> NotificationPreferences:
    """
    Partially update preferences.

    Parameters
    ----------
    user_id : str
    patch : dict
        Keys that map to ``NotificationPreferences`` fields.

    Returns
    -------
    NotificationPreferences
        The updated preferences object.
    """
    current = get_preferences(user_id)
    data = current.model_dump()
    data.update(patch)
    data["user_id"] = user_id  # ensure immutability of id
    updated = NotificationPreferences(**data)
    _STORE[user_id] = updated
    return updated


def delete_preferences(user_id: str) -> bool:
    """Remove stored preferences.  Returns True if they existed."""
    return _STORE.pop(user_id, None) is not None
