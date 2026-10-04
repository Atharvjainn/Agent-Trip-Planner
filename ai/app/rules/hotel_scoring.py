"""
ai/AGENT.md "Hotel scoring":
  Default score = 0.45*price_fit + 0.35*proximity + 0.20*rating, each
  normalized to 0-1. Weights live in one constant; tests cover the
  scoring function.
"""
from __future__ import annotations

from dataclasses import dataclass

PRICE_FIT_WEIGHT = 0.45
PROXIMITY_WEIGHT = 0.35
RATING_WEIGHT = 0.20

assert abs(PRICE_FIT_WEIGHT + PROXIMITY_WEIGHT + RATING_WEIGHT - 1.0) < 1e-9


@dataclass(frozen=True)
class HotelCandidate:
    price_per_night_minor: int
    avg_distance_km: float
    rating: float | None  # 0-5, None treated as the lowest observed rating


def score_hotels(candidates: list[HotelCandidate]) -> list[float]:
    """Returns one score per candidate, in the same order, each in [0, 1]."""
    if not candidates:
        return []

    from app.tools.geo import normalize  # local import to avoid a cycle at module load time

    prices = [c.price_per_night_minor for c in candidates]
    distances = [c.avg_distance_km for c in candidates]
    ratings = [c.rating if c.rating is not None else 0.0 for c in candidates]

    price_lo, price_hi = min(prices), max(prices)
    dist_lo, dist_hi = min(distances), max(distances)
    rating_lo, rating_hi = min(ratings), max(ratings)

    scores = []
    for c, rating in zip(candidates, ratings, strict=True):
        price_fit = normalize(c.price_per_night_minor, price_lo, price_hi, invert=True)
        proximity = normalize(c.avg_distance_km, dist_lo, dist_hi, invert=True)
        rating_norm = normalize(rating, rating_lo, rating_hi)
        score = PRICE_FIT_WEIGHT * price_fit + PROXIMITY_WEIGHT * proximity + RATING_WEIGHT * rating_norm
        scores.append(round(score, 4))
    return scores
