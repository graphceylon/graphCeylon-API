from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.recommend_pois import RecommendPOIsRequest


def _get(prefs, key: str, default=None):
    """Read pref value from either pydantic model or dict."""
    if prefs is None:
        return default
    if isinstance(prefs, dict):
        return prefs.get(key, default)
    return getattr(prefs, key, default)


def _clean_str(x):
    if x is None:
        return None
    if isinstance(x, str):
        s = x.strip()
        if s.lower() in {"", "unknown", "any", "none"}:
            return None
        return s
    return str(x)


def _normalize_tags(e_tags, pref_tags):
    tags = []
    if isinstance(e_tags, list):
        tags.extend([t for t in e_tags if isinstance(t, str) and t.strip()])
    if isinstance(pref_tags, list):
        tags.extend([t for t in pref_tags if isinstance(t, str) and t.strip()])
    # dedupe while preserving order
    seen = set()
    out = []
    for t in tags:
        tl = t.strip()
        if tl.lower() in {"unknown", "any", "none"}:
            continue
        if tl not in seen:
            seen.add(tl)
            out.append(tl)
    return out


def _normalize_eco_pref(v):
    """
    Contract expects Optional[str].
    Normalize bool/None/unknown into a meaningful string or None.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return "high" if v else "low"
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"", "unknown", "any", "none"}:
            return None
        # allow common values
        if s in {"low", "medium", "high"}:
            return s
        # if someone stores "true"/"false"
        if s in {"true", "yes"}:
            return "high"
        if s in {"false", "no"}:
            return "low"
        return v.strip()
    # anything else -> string
    return str(v)


def map_recommend_pois_request(
    parsed_intent: ParsedIntent,
    req: OrchestrateRequest,
) -> RecommendPOIsRequest:
    e = parsed_intent.entities
    prefs = parsed_intent.preference_overrides

    # prefs can be dict OR pydantic model
    travel_style = _get(prefs, "travel_style", [])
    budget_level = _clean_str(_get(prefs, "budget_level", None))
    avoid_crowds = _get(prefs, "avoid_crowds", None)
    eco_preference = _normalize_eco_pref(_get(prefs, "eco_preference", None))

    tags = _normalize_tags(getattr(e, "tags", None), travel_style)

    return RecommendPOIsRequest(
        intent="recommend_pois",
        user_id=(req.user_id or None),
        session_id=(req.session_id or None),
        raw_text=req.input_text,

        city=getattr(e, "city", None),
        country=getattr(e, "country", None),
        start_date=getattr(e, "start_date", None),
        end_date=getattr(e, "end_date", None),

        tags=tags,
        budget_level=budget_level,
        avoid_crowds=avoid_crowds,
        eco_preference=eco_preference,
        num_results=5,
    )