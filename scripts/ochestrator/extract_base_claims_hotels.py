import json
from pathlib import Path

INPUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/detailed_hotels_all_attractions.json")
OUTPUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims.txt")

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

claims = []

for entry in data.get("attractions", []):
    attraction = entry.get("attraction")

    # --- Attraction location ---
    admin = entry.get("geolocation", {}).get("address_info", {}).get("administrative_areas", {})
    province = admin.get("province")
    if attraction and province:
        claims.append(f"{attraction} is located in the {province} of Sri Lanka.")

    # --- Hotel count ---
    hotel_count = entry.get("hotel_count")
    if attraction and hotel_count:
        claims.append(f"{attraction} has {hotel_count} nearby hotels.")

    # --- Hotels ---
    for hotel in entry.get("hotels", []):
        hname = hotel.get("name")
        if not hname:
            continue

        hclass = hotel.get("extracted_hotel_class")
        if hclass:
            claims.append(f"{hname} is a {hclass}-star hotel.")

        rating = hotel.get("overall_rating")
        if rating:
            claims.append(f"{hname} has an overall rating of {rating}.")

        checkin = hotel.get("check_in_time")
        if checkin:
            claims.append(f"{hname} has check-in time at {checkin}.")

        address = hotel.get("address")
        if address:
            claims.append(f"{hname} is located at {address}.")

        for amenity in hotel.get("amenities", []):
            claims.append(f"{hname} offers {amenity}.")

        # --- Nearby places ---
        for place in hotel.get("nearby_places", []):
            pname = place.get("name")
            pcat = place.get("category")
            if pname and attraction:
                claims.append(f"{pname} is a {pcat} near {attraction}.")

# Save
OUTPUT_PATH.write_text("\n".join(sorted(set(claims))), encoding="utf-8")
print("Saved", len(claims), "raw claims.")
