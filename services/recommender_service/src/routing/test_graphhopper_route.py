# from routing.graphhopper_route import fetch_route_sampled_points
from .graphhopper_route import fetch_route_sampled_points

def main():
    # Example: Colombo Fort -> Kandy (adjust if you want)
    origin = (6.9271, 79.8612)   # (lat, lon)
    dest   = (7.2906, 80.6337)   # (lat, lon)

    res = fetch_route_sampled_points(
        origin=origin,
        dest=dest,
        profile="car",
        points_encoded=True,      # keep True since you already have decoder
        downsample_step_km=10.0,
    )

    print("\n=== ROUTE RESULT ===")
    print("distance_m:", res.distance_m)
    print("time_ms:", res.time_ms)
    print("route_points_count:", res.route_points_count)
    print("sampled_points_count:", res.sampled_points_count)

    print("\n=== SAMPLED POINTS (lat, lon) ===")
    for i, (lat, lon) in enumerate(res.sampled_points):
        print(f"{i:02d} -> lat={lat:.6f}, lng={lon:.6f}")

if __name__ == "__main__":
    main()