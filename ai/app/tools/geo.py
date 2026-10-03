"""
Pure geo math, no network calls — unit-testable without mocks.

ai/AGENT.md: "Distance = haversine km from hotel to each selected spot
(no Distance Matrix calls in MVP)." and "The LLM never produces a price,
distance, or total." This module is one of the only sources of truth for
distances in the whole system.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    lat: float
    lng: float


EARTH_RADIUS_KM = 6371.0088


def haversine_km(a: Point, b: Point) -> float:
    """Great-circle distance between two lat/lng points, in kilometers."""
    lat1, lng1, lat2, lng2 = map(math.radians, (a.lat, a.lng, b.lat, b.lng))
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    h = min(1.0, max(0.0, h))  # clamp for float noise at antipodal/identical points
    c = 2 * math.asin(math.sqrt(h))
    return EARTH_RADIUS_KM * c


def centroid(points: list[Point]) -> Point:
    """
    Simple arithmetic-mean centroid of the selected spots. Good enough at
    city scale for the MVP (we are not spanning hemispheres), and keeps the
    hotel-search graph free of any heavier geospatial dependency.
    """
    if not points:
        raise ValueError("centroid() requires at least one point")
    lat = sum(p.lat for p in points) / len(points)
    lng = sum(p.lng for p in points) / len(points)
    return Point(lat=lat, lng=lng)


def normalize(value: float, lo: float, hi: float, *, invert: bool = False) -> float:
    """
    Min-max normalize `value` into [0, 1] given the observed range [lo, hi]
    across the candidate set. `invert=True` for metrics where lower is
    better (e.g. price, distance), so the output stays "higher is better"
    like the other two factors in the hotel score.
    """
    if hi <= lo:
        # No spread in the candidate set (e.g. a single hotel) — treat
        # everything as equally good rather than dividing by zero.
        return 1.0
    score = (value - lo) / (hi - lo)
    score = min(1.0, max(0.0, score))
    return 1.0 - score if invert else score
