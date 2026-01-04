from collections import defaultdict

def group_by_district(candidates):
    buckets = defaultdict(list)
    for p in candidates:
        d = p.get("district", "unknown")
        buckets[d].append(p)

    for d in buckets:
        buckets[d].sort(key=lambda x: x.get("_final_score", x.get("_score", 0)), reverse=True)

    return buckets


def district_centroid(pois):
    lats = [p["lat"] for p in pois if p.get("lat")]
    lngs = [p["lng"] for p in pois if p.get("lng")]
    return (sum(lats)/len(lats), sum(lngs)/len(lngs))


def order_districts(buckets, anchor):
    ax, ay = anchor
    centroids = []
    for d, pois in buckets.items():
        centroids.append((d, district_centroid(pois)))

    centroids.sort(key=lambda x: (x[1][0]-ax)**2 + (x[1][1]-ay)**2)
    return [d for d,_ in centroids]


def build_itinerary(ranked_candidates, days, per_day=2, anchor=None):
    buckets = group_by_district(ranked_candidates)
    ordered_districts = order_districts(buckets, anchor)

    itinerary = []
    used = set()

    for day in range(days):
        if not ordered_districts:
            break

        district = ordered_districts.pop(0)
        pois = buckets[district]

        day_plan = []
        for p in pois:
            if p["attraction_id"] not in used:
                day_plan.append(p)
                used.add(p["attraction_id"])
            if len(day_plan) == per_day:
                break

        itinerary.append({
            "day": day+1,
            "district": district,
            "attractions": day_plan
        })

    return itinerary
