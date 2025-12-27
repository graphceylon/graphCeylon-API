# src/pipelines/build_crowd_index_static.py

from pathlib import Path
import pandas as pd

from src.config import DATA_CLEAN_DIR, CROWD_STATIC_FILE


def build_crowd_index_static():
    """
    Create an initial crowd index table from attractions_static.csv.

    This does NOT use real SLTDA / Popular Times yet.
    It simply creates a structured CSV where:
      - each attraction gets a base_crowd_index placeholder (0.5)
      - you can later overwrite/refine these values using SLTDA, Google Popular Times, etc.

    Output:
      data_clean/crowd_index_static.csv
    """

    print("=== Building crowd index static table ===")

    attractions_path = DATA_CLEAN_DIR / "attractions_static.csv"
    if not attractions_path.exists():
        raise FileNotFoundError(f"attractions_static.csv not found: {attractions_path}")

    # Load the static attractions info
    df_attr = pd.read_csv(attractions_path)

    required_cols = {"attraction_id", "name", "province", "district"}
    missing = required_cols - set(df_attr.columns)
    if missing:
        raise ValueError(
            f"attractions_static.csv is missing required columns: {missing}"
        )

    # For now, assign a neutral base_crowd_index = 0.5 (to be refined later)
    df_crowd = df_attr[["attraction_id", "name", "province", "district"]].copy()
    df_crowd["base_crowd_index"] = 0.5  # [0,1], 0.5 = medium popularity by default
    df_crowd["notes"] = (
        "placeholder value; update using SLTDA footfall / Google Popular Times / expert judgment"
    )

    # Sort for consistency
    df_crowd = df_crowd.sort_values("attraction_id").reset_index(drop=True)

    # Ensure directory exists and save
    CROWD_STATIC_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_crowd.to_csv(CROWD_STATIC_FILE, index=False)

    print(f"[crowd] Saved static crowd index -> {CROWD_STATIC_FILE}")
    print(f"[crowd] Total attractions with crowd index: {len(df_crowd)}")
    print("=== Done building crowd index static table ===")


if __name__ == "__main__":
    build_crowd_index_static()
