# src/orchestrator_core/mappers/weather_mapper.py

from datetime import date, timedelta

from src.api.schemas import ParsedIntent, OrchestrateRequest
from src.orchestrator_core.contracts.weather import WeatherForecastRequest


def _today_iso() -> str:
    return date.today().isoformat()


def _end_from_days(start_iso: str, days: int) -> str:
    d0 = date.fromisoformat(start_iso)
    return (d0 + timedelta(days=max(days, 1) - 1)).isoformat()


def map_weather_request(
    parsed: ParsedIntent,
    incoming: OrchestrateRequest,
) -> WeatherForecastRequest:
    e = parsed.entities

    # ---- defaults ----
    start_date = e.start_date or _today_iso()

    # If end_date missing, use days if available; else default to same day
    days = getattr(e, "days", None)
    if e.end_date:
        end_date = e.end_date
    elif isinstance(days, int) and days > 0:
        end_date = _end_from_days(start_date, days)
    else:
        end_date = start_date

    return WeatherForecastRequest(
        intent=parsed.intent,
        raw_text=parsed.raw_text or incoming.input_text,
        user_id=incoming.user_id,
        session_id=incoming.session_id,
        city=e.city,
        country=e.country,
        start_date=start_date,
        end_date=end_date,
        time_of_day=e.time_of_day,
    )