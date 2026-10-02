"""Small geo helpers - pure math, no external deps."""
import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def centroid(points: list) -> tuple:
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def cluster_by_day(attractions: list, days: int, max_per_day: int = 4) -> list:
    """Greedy nearest-neighbor clustering - good enough for a demo, not a
    real TSP/day-planning solver. Swap this out first if there's time
    left over after the agent behavior itself is solid."""
    remaining = list(attractions)
    clusters = []
    for _ in range(days):
        if not remaining:
            break
        day_bucket = [remaining.pop(0)]
        while len(day_bucket) < max_per_day and remaining:
            last = day_bucket[-1]
            remaining.sort(key=lambda a: haversine_km(last["lat"], last["lon"], a["lat"], a["lon"]))
            day_bucket.append(remaining.pop(0))
        clusters.append(day_bucket)
    if remaining and clusters:
        clusters[-1].extend(remaining)  # leftovers spill into the last day rather than vanishing
    return clusters
