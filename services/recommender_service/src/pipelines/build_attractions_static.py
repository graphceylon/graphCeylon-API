# src/pipelines/build_attractions_static.py

from pathlib import Path
import json
import pandas as pd

from src.config import KG_ATTRACTIONS_FILE, DATA_CLEAN_DIR


def build_attractions_static():
    """
    Read attractions from the KG JSON and build a static CSV with:
      - attraction_id
      - name
      - lat, lon
      - province, district
      - eco_sensitivity (placeholder)
      - capacity (placeholder)
    """

    print("=== Building static attractions table from KG JSON ===")
    path = KG_ATTRACTIONS_FILE

    if not path.exists():
        raise FileNotFoundError(f"KG attractions file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    attractions = data.get("attractions", [])
    if not attractions:
        raise ValueError("No 'attractions' key or empty list in KG JSON.")

    rows = []

    for a in attractions:
        title = a.get("title") or a.get("name") or "UNKNOWN"
        geo = a.get("geolocation", {})
        coords = geo.get("coordinates", {}) if isinstance(geo, dict) else {}
        addr = geo.get("address_info", {}) if isinstance(geo, dict) else {}
        admin = addr.get("administrative_areas", {}) if isinstance(addr, dict) else {}

        lat = coords.get("latitude")
        lon = coords.get("longitude")

        # Skip attractions without coordinates (shouldn't happen, but safe)
        if lat is None or lon is None:
            print(f"[static] Skipping attraction without coords: {title}")
            continue

        # Build a stable ID (same logic as location_loader)
        slug = (
            title.lower()
            .strip()
            .replace(" ", "_")
            .replace("/", "_")
            .replace(",", "")
        )

        province = admin.get("province")
        district = admin.get("district")

        # Placeholders for sustainability-related fields
        # You will refine these manually or via a separate research process.
        eco_sensitivity = 0.5  # default mid value in [0,1]
        capacity = 1000        # default rough carrying capacity; adjust per site later

        rows.append(
            {
                "attraction_id": slug,
                "name": title,
                "lat": lat,
                "lon": lon,
                "province": province,
                "district": district,
                "eco_sensitivity": eco_sensitivity,
                "capacity": capacity,
            }
        )

    if not rows:
        raise ValueError("No valid attractions parsed from KG JSON.")

    df = pd.DataFrame(rows)

    # Sort for consistency
    df = df.sort_values("attraction_id").reset_index(drop=True)

    DATA_CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_CLEAN_DIR / "attractions_static.csv"
    df.to_csv(out_path, index=False)

    print(f"[static] Saved static attractions table -> {out_path}")
    print(f"[static] Total attractions: {len(df)}")
    print("=== Done building static attractions table ===")


if __name__ == "__main__":
    build_attractions_static()
