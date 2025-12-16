# src/orchestrator_core/mappers/weather_mapper.py

from src.api.schemas import ParsedIntent, OrchestrateRequest
from src.orchestrator_core.contracts.weather import WeatherForecastRequest


def map_weather_request(
    parsed: ParsedIntent,
    incoming: OrchestrateRequest,
) -> WeatherForecastRequest:
    """
    Map ParsedIntent + original OrchestrateRequest into a WeatherForecastRequest
    that can be sent to the weather / recommender service.
    """
    e = parsed.entities

    return WeatherForecastRequest(
        intent=parsed.intent,
        raw_text=parsed.raw_text or incoming.input_text,
        user_id=incoming.user_id,
        session_id=incoming.session_id,
        city=e.city,
        country=e.country,
        start_date=e.start_date,
        end_date=e.end_date,
        time_of_day=e.time_of_day,
    )
