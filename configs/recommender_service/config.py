# configs/recommender_service/config.py
import os
from pathlib import Path

# ---- 1. Repo root: .../graphCeylon-API ----
REPO_ROOT = Path(__file__).resolve().parents[2]

# ---- 2. Base directory for recommender service data ----
# e.g. graphCeylon-API/data/recommender_service
SERVICE_DATA_ROOT = REPO_ROOT / "data" / "recommender_service"

# ---- 3. Main Data Directory ----
DATA_DIR = SERVICE_DATA_ROOT

# ---- 4. Raw Data Directories ----
# Structure:
#   data/recommender_service/raw/data_raw/weather
#   data/recommender_service/raw/kg/attraction_features_manual.json
DATA_RAW_ROOT = SERVICE_DATA_ROOT / "raw"
DATA_RAW_DIR = DATA_RAW_ROOT / "data_raw"
WEATHER_RAW_DIR = DATA_RAW_DIR / "weather"

# ---- 5. Clean Data Directory ----
DATA_CLEAN_DIR = SERVICE_DATA_ROOT / "clean"

# ---- 6. KG Directory and file ----
KG_RAW_DIR = DATA_RAW_ROOT / "kg"
KG_ATTRACTIONS_FILE = KG_RAW_DIR / "tourist_attractions.json"

# ---- 7. Ensure directories exist ----
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_RAW_ROOT.mkdir(parents=True, exist_ok=True)
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
WEATHER_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_CLEAN_DIR.mkdir(parents=True, exist_ok=True)
KG_RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---- 8. API Key ----
OPENWEATHER_API_KEY = os.getenv(
    "OPENWEATHER_API_KEY",
    "563f99c8a6edd46108814d78d1fd655f",  # default fallback
)

# ---- 9. Deprecated paths (kept for compatibility, not used) ----
RESEARCH_ROOT_DIR = REPO_ROOT
DATASETS_DIR = RESEARCH_ROOT_DIR / "datasets"
KG_DATA_DIR = DATASETS_DIR / "kg"
