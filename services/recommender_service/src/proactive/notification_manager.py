"""
proactive.notification_manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Gate-keeper between the proactivity handler and the user.

Responsibilities
----------------
1. **Rate-limiting** – enforce per-hour / per-day caps.
2. **Quiet-hours** – suppress pushes while the user is sleeping.
3. **Moment opt-out** – skip moments the user has disabled.
4. **Confidence floor** – drop triggers below the user's threshold.
5. **Cooldown** – prevent the same moment from firing repeatedly.
6. **Delivery dispatch** – (stub) route the notification to the right
   channel (push / in-app / SMS / email).
7. **Feedback tracking** – record acceptance / dismissal for metrics.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from .micro_moments import MOMENT_REGISTRY
from .schemas import (
    AcceptanceMetrics,
    DetectedTrigger,
    MicroMomentType,
    NotificationPreferences,
    ProactiveSuggestion,
    SuggestionFeedback,
    SuggestionStatus,
)

COLOMBO = ZoneInfo("Asia/Colombo")


# ━━━━━━━━━━━━━━ in-memory tracking structures ━━━━━━━━━━━━━━━━━━

# user_id → list of (moment_type, sent_at_utc)
_send_log: Dict[str, List[Tuple[MicroMomentType, datetime]]] = defaultdict(list)

# suggestion_id → ProactiveSuggestion  (for feedback look-up)
_suggestion_store: Dict[str, ProactiveSuggestion] = {}

# user_id → list of SuggestionFeedback
_feedback_log: Dict[str, List[SuggestionFeedback]] = defaultdict(list)


# ━━━━━━━━━━━━━━ gate / filter logic ━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _is_in_quiet_hours(prefs: NotificationPreferences, now_local_hour: int) -> bool:
    start = prefs.quiet_hours_start
    end = prefs.quiet_hours_end
    if start is None or end is None:
        return False
    if start > end:
        # wraps midnight, e.g. 22 → 7
        return now_local_hour >= start or now_local_hour < end
    return start <= now_local_hour < end


def _count_recent(user_id: str, window: timedelta) -> int:
    cutoff = datetime.now(timezone.utc) - window
    return sum(1 for _, ts in _send_log[user_id] if ts >= cutoff)


def _last_sent_for_moment(user_id: str, moment: MicroMomentType) -> Optional[datetime]:
    for m, ts in reversed(_send_log[user_id]):
        if m == moment:
            return ts
    return None


def filter_triggers(
    triggers: List[DetectedTrigger],
    prefs: NotificationPreferences,
) -> Tuple[List[DetectedTrigger], int]:
    """
    Apply all suppression rules and return the triggers that survive.

    Returns
    -------
    (allowed, suppressed_count)
    """
    if not prefs.enabled:
        return [], len(triggers)

    now_local_hour = datetime.now(COLOMBO).hour

    if _is_in_quiet_hours(prefs, now_local_hour):
        return [], len(triggers)

    hour_count = _count_recent(prefs.user_id, timedelta(hours=1))
    day_count = _count_recent(prefs.user_id, timedelta(hours=24))

    allowed: List[DetectedTrigger] = []
    suppressed = 0

    for t in triggers:
        # moment disabled?
        if t.moment_type in prefs.disabled_moments:
            suppressed += 1
            continue
        # confidence below user threshold?
        if t.confidence < prefs.min_confidence:
            suppressed += 1
            continue
        # rate-limit
        if hour_count >= prefs.max_per_hour or day_count >= prefs.max_per_day:
            suppressed += 1
            continue
        # cooldown
        defn = MOMENT_REGISTRY.get(t.moment_type)
        if defn:
            last = _last_sent_for_moment(prefs.user_id, t.moment_type)
            if last and (datetime.now(timezone.utc) - last) < timedelta(minutes=defn.cooldown_minutes):
                suppressed += 1
                continue

        allowed.append(t)
        hour_count += 1
        day_count += 1

    return allowed, suppressed


# ━━━━━━━━━━━━━━ suggestion builder ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_suggestion(
    trigger: DetectedTrigger,
    recommended_pois: List[Dict],
    user_id: str,
    ttl_minutes: int = 30,
) -> ProactiveSuggestion:
    """
    Build a ``ProactiveSuggestion`` from a trigger and its resolved POIs.
    """
    defn = MOMENT_REGISTRY.get(trigger.moment_type)
    title = trigger.reason
    body = trigger.reason
    priority = defn.priority if defn else "medium"

    # template interpolation (best-effort)
    if defn:
        template_vars = {
            **trigger.metadata,
            "count": len(recommended_pois),
            "radius_km": defn.radius_km,
        }
        try:
            title = defn.notification_title_template.format(**template_vars)
        except (KeyError, IndexError):
            title = trigger.reason
        try:
            body = defn.notification_body_template.format(**template_vars)
        except (KeyError, IndexError):
            body = trigger.reason

    suggestion_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc)

    suggestion = ProactiveSuggestion(
        suggestion_id=suggestion_id,
        moment_type=trigger.moment_type,
        title=title,
        body=body,
        priority=priority,
        recommended_pois=recommended_pois,
        trigger=trigger,
        user_id=user_id,
        created_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )

    # record
    _suggestion_store[suggestion_id] = suggestion
    _send_log[user_id].append((trigger.moment_type, now))

    return suggestion


# ━━━━━━━━━━━━━━ feedback / acceptance ━━━━━━━━━━━━━━━━━━━━━━━━━━

def record_feedback(feedback: SuggestionFeedback) -> bool:
    """
    Record a user's accept / dismiss action.

    Returns True if the suggestion was found and updated.
    """
    suggestion = _suggestion_store.get(feedback.suggestion_id)
    if not suggestion:
        return False

    suggestion.status = feedback.action
    _feedback_log[feedback.user_id].append(feedback)
    return True


def get_acceptance_metrics(user_id: Optional[str] = None) -> AcceptanceMetrics:
    """
    Compute aggregate acceptance metrics, optionally filtered to a user.
    """
    if user_id:
        suggestions = [s for s in _suggestion_store.values() if s.user_id == user_id]
    else:
        suggestions = list(_suggestion_store.values())

    total = len(suggestions)
    accepted = sum(1 for s in suggestions if s.status == SuggestionStatus.ACCEPTED)
    dismissed = sum(1 for s in suggestions if s.status == SuggestionStatus.DISMISSED)

    by_moment: Dict[str, Dict[str, int]] = {}
    for s in suggestions:
        key = s.moment_type.value
        bucket = by_moment.setdefault(key, {"sent": 0, "accepted": 0, "dismissed": 0})
        bucket["sent"] += 1
        if s.status == SuggestionStatus.ACCEPTED:
            bucket["accepted"] += 1
        elif s.status == SuggestionStatus.DISMISSED:
            bucket["dismissed"] += 1

    return AcceptanceMetrics(
        total_sent=total,
        total_accepted=accepted,
        total_dismissed=dismissed,
        acceptance_rate=round(accepted / total, 4) if total else 0.0,
        by_moment=by_moment,
    )


def reset_cooldowns(user_id: Optional[str] = None) -> int:
    """
    Clear send-log entries so cooldowns no longer suppress triggers.
    If *user_id* is given only that user's log is cleared;
    otherwise **all** users' logs are cleared.
    Returns the number of log entries removed.
    """
    if user_id:
        count = len(_send_log.pop(user_id, []))
        return count
    count = sum(len(v) for v in _send_log.values())
    _send_log.clear()
    return count
