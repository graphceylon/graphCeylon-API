# src/config.py
import os
from pathlib import Path

# 1. Base directory for this microservice
BASE_DIR = Path(__file__).resolve().parent.parent

# 2. Main Data Directory (The loader expects "DATA_DIR")
DATA_DIR = BASE_DIR / "data"

# 3. Raw Data Directories
DATA_RAW_DIR = BASE_DIR / "data_raw"
WEATHER_RAW_DIR = DATA_RAW_DIR / "weather"

# 4. Clean Data Directory
DATA_CLEAN_DIR = DATA_DIR / "clean"  # or BASE_DIR / "data_clean" if you prefer separate folders

# 5. Create directories automatically if they don't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
WEATHER_RAW_DIR.mkdir(parents=True, exist_ok=True)
DATA_CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# 6. API Keys
OPENWEATHER_API_KEY = "563f99c8a6edd46108814d78d1fd655f"

# 7. Other Paths (Optional, keep if needed for other scripts)
RESEARCH_ROOT_DIR = BASE_DIR.parent
DATASETS_DIR = RESEARCH_ROOT_DIR / "datasets"
KG_DATA_DIR = DATASETS_DIR / "kg"