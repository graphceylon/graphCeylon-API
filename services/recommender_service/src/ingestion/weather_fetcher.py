# src/ingestion/weather_fetcher.py

import csv
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.config import OPENWEATHER_API_KEY, WEATHER_RAW_DIR
from src.ingestion.location_loader import load_locations_from_kg


def fetch_weather_for_location(name: str, lat: float, lon: float) -> dict:
    """
    Call OpenWeatherMap 5-day/3-hour forecast API for a given location.
    Returns the JSON response.
    """
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def save_weather_to_csv(location_id: str, data: dict) -> Path:
    """
    Save flattened forecast data as CSV in data_raw/weather/.
    Uses a stable location_id (e.g. 'anuradhapura') in the filename.
    Returns the path to the created file.
    """
    WEATHER_RAW_DIR.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = WEATHER_RAW_DIR / f"weather_{location_id}_{ts}.csv"

    fieldnames = [
        "location_id",
        "dt_utc",
        "dt_iso",
        "temp",
        "feels_like",
        "pressure",
        "humidity",
        "wind_speed",
        "wind_deg",
        "weather_main",
        "weather_description",
    ]

    with filename.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in data.get("list", []):
            dt_utc = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
            main = item.get("main", {})
            wind = item.get("wind", {})
            weather_arr = item.get("weather", [])
            weather_info = weather_arr[0] if weather_arr else {}

            writer.writerow(
                {
                    "location_id": location_id,
                    "dt_utc": item["dt"],
                    "dt_iso": dt_utc.isoformat(),
                    "temp": main.get("temp"),
                    "feels_like": main.get("feels_like"),
                    "pressure": main.get("pressure"),
                    "humidity": main.get("humidity"),
                    "wind_speed": wind.get("speed"),
                    "wind_deg": wind.get("deg"),
                    "weather_main": weather_info.get("main"),
                    "weather_description": weather_info.get("description"),
                }
            )

    return filename


def run_weather_ingestion(max_locations: int | None = None) -> None:
    """
    Fetch and save weather forecasts for all (or first N) attractions
    loaded from the Knowledge Graph JSON.
    """
    print("=== Weather ingestion started ===")
    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY == "YOUR_OPENWEATHER_API_KEY_HERE":
        raise RuntimeError("Please set OPENWEATHER_API_KEY in src/config.py")

    # Load locations from KG JSON instead of hard-coded dict
    locations = load_locations_from_kg(max_locations=max_locations)

    print(f"[weather] Loaded {len(locations)} locations from KG.")
    for loc in locations:
        loc_id = loc["id"]      # e.g. "anuradhapura"
        name = loc["name"]      # e.g. "Anuradhapura"
        lat = loc["lat"]
        lon = loc["lon"]

        print(f"[weather] Fetching for {name} ({lat}, {lon})...")
        data = fetch_weather_for_location(name, lat, lon)
        csv_path = save_weather_to_csv(loc_id, data)
        print(f"[weather] Saved CSV for {name} -> {csv_path}")

    print("=== Weather ingestion complete ===")


if __name__ == "__main__":
    # While testing, you can limit to a few locations:
    # run_weather_ingestion(max_locations=5)
    run_weather_ingestion()
