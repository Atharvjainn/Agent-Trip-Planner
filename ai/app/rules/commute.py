"""
ai/AGENT.md "Local commute estimate":
  per-km rate table by city tier and mode (auto, cab, metro, walk), with a
  country-level default for international cities, in local currency.
  Estimate = daily hotel -> spots -> hotel route distance x rate.
  Money returned in local currency; apps/api converts (root AGENTS.md §6).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.tools.geo import Point, haversine_km

Mode = str  # "auto" | "cab" | "metro" | "walk"

# amount_minor per km, by (city_tier, mode). Tiers are a coarse MVP proxy:
# tier_1 = major metro, tier_2 = secondary city, tier_3 = small town/rural.
# Values are illustrative placeholders in INR minor units (paise) for
# India city tiers, used when the city has a known tier; see
# DEFAULT_INTERNATIONAL_RATE for everything else.
_RATE_TABLE: dict[str, dict[Mode, int]] = {
    "tier_1": {"auto": 1800, "cab": 2200, "metro": 800, "walk": 0},
    "tier_2": {"auto": 1500, "cab": 1900, "metro": 0, "walk": 0},
    "tier_3": {"auto": 1200, "cab": 1700, "metro": 0, "walk": 0},
}

# Fallback per-km rate (minor units in the trip's local currency) for
# international / untiered cities, keyed by a generic mode choice.
DEFAULT_INTERNATIONAL_RATE_MINOR_PER_KM = 150

DEFAULT_MODE: Mode = "cab"


@dataclass(frozen=True)
class CommuteEstimate:
    daily_distance_km: float
    daily_cost_minor: int
    trip_total_cost_minor: int
    mode: Mode


def route_distance_km(hotel: Point, spots: list[Point]) -> float:
    """hotel -> spot1 -> spot2 -> ... -> hotel, naive fixed order (no TSP
    optimization needed for the MVP's small spot counts)."""
    if not spots:
        return 0.0
    route = [hotel, *spots, hotel]
    return sum(haversine_km(route[i], route[i + 1]) for i in range(len(route) - 1))


def rate_minor_per_km(*, city_tier: str | None, mode: Mode = DEFAULT_MODE) -> int:
    if city_tier and city_tier in _RATE_TABLE:
        return _RATE_TABLE[city_tier].get(mode, DEFAULT_INTERNATIONAL_RATE_MINOR_PER_KM)
    return DEFAULT_INTERNATIONAL_RATE_MINOR_PER_KM


def estimate_commute(
    *,
    hotel: Point,
    spots: list[Point],
    nights: int,
    city_tier: str | None = None,
    mode: Mode = DEFAULT_MODE,
) -> CommuteEstimate:
    if nights < 1:
        raise ValueError("nights must be >= 1")
    daily_km = route_distance_km(hotel, spots)
    rate = rate_minor_per_km(city_tier=city_tier, mode=mode)
    daily_cost = round(daily_km * rate)
    return CommuteEstimate(
        daily_distance_km=daily_km,
        daily_cost_minor=daily_cost,
        trip_total_cost_minor=daily_cost * nights,
        mode=mode,
    )
