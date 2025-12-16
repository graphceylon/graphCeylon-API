# src/forecast/forecast_service.py

import pandas as pd
from datetime import datetime, timedelta
from src.config import DATA_DIR

# 1. UPDATE PATHS: Point to the AI Forecast file
AI_FORECAST_FILE = DATA_DIR / "clean" / "ai_weather_forecast_optimized.csv"
LIVE_WEATHER_FILE = DATA_DIR / "clean" / "daily_weather_context.csv"

class HybridForecaster:
    def __init__(self):
        self.ai_forecast_df = None
        self.live_df = None
        self._load_data()
        
    def _load_data(self):
        """Load AI Forecasts and Live Data"""
        # A. Load AI Forecast (Long-Term AI Model)
        if AI_FORECAST_FILE.exists():
            print(f"[Forecaster] Loading AI Model predictions from {AI_FORECAST_FILE.name}...")
            self.ai_forecast_df = pd.read_csv(AI_FORECAST_FILE)
            # Convert date column to date objects for easy comparison
            self.ai_forecast_df['ds'] = pd.to_datetime(self.ai_forecast_df['ds']).dt.date
        else:
            print(f"[Forecaster] ⚠️ Warning: AI Forecast file missing at {AI_FORECAST_FILE}")
            print("Did you run the 'train_weather_prophet_optimized.ipynb' notebook?")
        
        # B. Load Live Forecast (Short-Term API Data)
        if LIVE_WEATHER_FILE.exists():
            self.live_df = pd.read_csv(LIVE_WEATHER_FILE)
            self.live_df['date'] = pd.to_datetime(self.live_df['date']).dt.date

    def get_forecast(self, location_id: str, date_str: str):
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            print("Error: Date must be YYYY-MM-DD")
            return None

        today = datetime.now().date()
        days_diff = (target_date - today).days
        
        # --- SCENARIO 1: SHORT TERM (0-5 Days) ---
        # Use Live OpenWeather API data if available
        if 0 <= days_diff <= 5 and self.live_df is not None:
            match = self.live_df[
                (self.live_df['location_id'] == location_id) & 
                (self.live_df['date'] == target_date)
            ]
            if not match.empty:
                rec = match.iloc[0].to_dict()
                return {
                    "source": "live_api_openweather",
                    "date": date_str,
                    "location_id": location_id,
                    "predicted_temp": rec.get('max_temp'),
                    "weather_main": rec.get('weather_main'),
                    "risk_level": rec.get('risk_level')
                }
        
        # --- SCENARIO 2: LONG TERM (Future) ---
        # Use Prophet AI Model Lookup
        if self.ai_forecast_df is not None:
            # Find the row that matches both Location and Date
            match = self.ai_forecast_df[
                (self.ai_forecast_df['location_id'] == location_id) & 
                (self.ai_forecast_df['ds'] == target_date)
            ]
            
            if not match.empty:
                rec = match.iloc[0].to_dict()
                return {
                    "source": "prophet_time_series_ai",  # <-- Shows it's using AI
                    "date": date_str,
                    "location_id": location_id,
                    "predicted_temp": rec['pred_temp'],
                    "predicted_rainfall_mm": rec['pred_rainfall'],
                    "weather_main": rec['weather_main'],
                    "risk_level": rec['risk_level']
                }
            
        # If no AI data found (e.g., date is too far in future > 2 years)
        return {
            "source": "unknown",
            "message": "No forecast available for this date."
        }

# --- Test It ---
if __name__ == "__main__":
    f = HybridForecaster()
    
    # Check a date next year (e.g., Jan 5th, 2026)
    test_date = "2026-01-05"
    
    print(f"\n🔮 Checking AI Forecast for Ella on {test_date}...")
    result = f.get_forecast("ella", test_date)
    print(result)