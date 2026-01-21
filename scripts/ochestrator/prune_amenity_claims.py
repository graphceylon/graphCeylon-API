import re
from collections import defaultdict
from pathlib import Path

IN_PATH  = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_clean.txt")
OUT_PATH = Path("/Users/dev/Desktop/graphCeylon-API/data/orchestrator/raw/NLI/base_claims_pruned.txt")

lines = [l.strip() for l in IN_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]

# Capture: "<hotel> offers <amenity>."
pat = re.compile(r"^(?P<hotel>.+?) offers (?P<amenity>.+?)\.$", re.IGNORECASE)

# Simple amenity normalization
def norm_amenity(a: str) -> str:
    a = a.lower().strip()
    a = re.sub(r"\s+", " ", a)
    a = a.replace("wi-fi", "wifi")
    a = a.replace("self parking", "parking")
    return a

amenities_by_hotel = defaultdict(list)
other_claims = []

for l in lines:
    m = pat.match(l)
    if not m:
        other_claims.append(l)
        continue
    hotel = m.group("hotel").strip()
    amenity = m.group("amenity").strip()
    amenities_by_hotel[hotel].append(amenity)

kept = []
for hotel, ams in amenities_by_hotel.items():
    # dedupe normalized amenities
    seen = set()
    uniq = []
    for a in ams:
        na = norm_amenity(a)
        if na in seen:
            continue
        seen.add(na)
        uniq.append(a)

    # remove "wifi" if a more specific wifi exists
    has_specific_wifi = any("wifi" in norm_amenity(a) and "public" in norm_amenity(a) for a in uniq)
    pruned = []
    for a in uniq:
        na = norm_amenity(a)
        if na == "wifi" and has_specific_wifi:
            continue
        pruned.append(a)

    # cap amenities per hotel to reduce repetition (keep first N)
    N = 8
    for a in pruned[:N]:
        kept.append(f"{hotel} offers {a}.")

final = other_claims + kept
OUT_PATH.write_text("\n".join(final) + "\n", encoding="utf-8")
print("IN :", len(lines))
print("OUT:", len(final))
print("Wrote:", OUT_PATH)
