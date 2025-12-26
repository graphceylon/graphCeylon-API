from ...api.schemas import OrchestrateRequest, ParsedIntent
from ..contracts.price import PriceForecastRequest


def map_price_request(parsed_intent: ParsedIntent, req: OrchestrateRequest) -> PriceForecastRequest:
    e = parsed_intent.entities  # Entities (pydantic object)

    # heuristic defaults: use city if present, otherwise poi_name
    city = e.city
    poi_name = e.poi_name
    country = e.country
    start_date = e.start_date
    end_date = e.end_date
    time_of_day = e.time_of_day

    # optional: decide category based on domain_category
    # if your extractor sets domain_category="hotel", set category="hotel"
    category = "hotel" if parsed_intent.domain_category == "hotel" else "general"

    return PriceForecastRequest(
        intent="forecast_price",
        user_id=req.user_id,
        session_id=req.session_id,
        raw_text=req.input_text,
        city=city,
        poi_name=poi_name,
        country=country,
        start_date=start_date,
        end_date=end_date,
        time_of_day=time_of_day,
        category=category,
        currency="LKR",
    )
