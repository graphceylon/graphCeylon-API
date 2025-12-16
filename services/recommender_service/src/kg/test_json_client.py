# src/kg/test_json_client.py

from pprint import pprint
from pathlib import Path

from src.kg.json_client import JsonKGClient


def main():
    # __file__ = .../Proactive-Tourism-Recommendation/component3_service/src/kg/test_json_client.py
    # parents[0] = .../kg
    # parents[1] = .../src
    # parents[2] = .../component3_service
    # parents[3] = .../Proactive-Tourism-Recommendation  ✅ we want this
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "datasets" / "kg"

    sltda_path = data_dir / "tourist_attractions.json"
    manual_path = data_dir / "attraction_features_manual.json"

    print("Project root:", project_root)
    print("SLTDA JSON :", sltda_path)
    print("Manual JSON:", manual_path)

    client = JsonKGClient(
        sltda_json_path=str(sltda_path),
        manual_features_path=str(manual_path),
    )

    print("✅ JsonKGClient initialised")

    # ✅ 2. Fetch ALL attractions
    all_attractions = client.search_attractions()
    print(f"Total attractions loaded: {len(all_attractions)}")
    print("-" * 80)

    print("First 2 attractions:")
    for a in all_attractions[:2]:
        pprint({
            "id": a.id,
            "name": a.name,
            "city": a.city,
            "district": a.district,
            "country": a.country,
            "lat": a.latitude,
            "lon": a.longitude,
            "tags": a.tags,
        })
        print("-" * 40)

    # ✅ 3. Test filter by city
    city_name = "Kandy"
    Kandy_atts = client.search_attractions(city=city_name)
    print(f"\nAttractions in city={city_name!r}: {len(Kandy_atts)}")
    for a in Kandy_atts:
        print(f"- {a.name} ({a.city}, {a.district})")

    # ✅ 4. Test get_attraction_by_id
    if all_attractions:
        sample = all_attractions[0]
        fetched = client.get_attraction_by_id(sample.id)
        print("\nTesting get_attraction_by_id:")
        print("Original:", sample.id, sample.name)
        print("Fetched :", fetched.id if fetched else None, fetched.name if fetched else None)

        assert fetched is not None, "get_attraction_by_id returned None"
        assert fetched.id == sample.id, "ID mismatch"
        print("✅ get_attraction_by_id works")

    print("\n🎉 All basic JsonKGClient tests passed.")


if __name__ == "__main__":
    main()
