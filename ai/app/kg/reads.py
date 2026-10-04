from __future__ import annotations

import logging

from app.kg import queries
from app.kg.driver import run_read

logger = logging.getLogger("services.ai.kg.reads")


async def candidate_cities_by_vibe(vibes: list[str], limit: int) -> list[dict]:
    """
    Used by graphs/recommend_destinations.py. Returning [] (rather than
    raising) on any Neo4j error is deliberate: an unreachable KG should
    read exactly like a cold start (too few candidates), not crash the job —
    see ai/AGENT.md "Cold start" and root AGENTS.md §10.7 (every AI step
    needs a deterministic fallback).
    """
    try:
        return await run_read(queries.CANDIDATE_CITIES_BY_VIBE, {"vibes": vibes, "limit": limit})
    except Exception:  # noqa: BLE001
        logger.warning("kg_read_failed", extra={"what": "candidate_cities_by_vibe"}, exc_info=True)
        return []


async def place_vibe_scores_for_city(city: str, country: str) -> list[dict]:
    try:
        return await run_read(queries.PLACE_VIBE_SCORES_FOR_CITY, {"city": city, "country": country})
    except Exception:  # noqa: BLE001
        logger.warning("kg_read_failed", extra={"what": "place_vibe_scores_for_city"}, exc_info=True)
        return []


async def find_similar_experiences(
    vibes: list[str], threshold: float = 0.8, limit: int = 10
) -> list[dict]:
    try:
        return await run_read(
            queries.FIND_SIMILAR_EXPERIENCES,
            {"vibes": vibes, "threshold": threshold, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        logger.warning("kg_read_failed", extra={"what": "find_similar_experiences"}, exc_info=True)
        return []


async def find_experienced_destinations(
    vibes: list[str], threshold: float = 0.8, limit: int = 5
) -> list[dict]:
    try:
        return await run_read(
            queries.FIND_EXPERIENCED_DESTINATIONS,
            {"vibes": vibes, "threshold": threshold, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        logger.warning("kg_read_failed", extra={"what": "find_experienced_destinations"}, exc_info=True)
        return []


async def find_experienced_places(
    city: str, vibes: list[str], threshold: float = 0.8, country: str | None = None, limit: int = 10
) -> list[dict]:
    try:
        return await run_read(
            queries.FIND_EXPERIENCED_PLACES,
            {"city": city, "country": country, "vibes": vibes, "threshold": threshold, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        logger.warning("kg_read_failed", extra={"what": "find_experienced_places"}, exc_info=True)
        return []


async def find_experienced_hotels(
    city: str, vibes: list[str], threshold: float = 0.8, country: str | None = None, limit: int = 10
) -> list[dict]:
    try:
        return await run_read(
            queries.FIND_EXPERIENCED_HOTELS,
            {"city": city, "country": country, "vibes": vibes, "threshold": threshold, "limit": limit},
        )
    except Exception:  # noqa: BLE001
        logger.warning("kg_read_failed", extra={"what": "find_experienced_hotels"}, exc_info=True)
        return []

