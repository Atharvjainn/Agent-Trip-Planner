from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from app.config import get_settings

logger = logging.getLogger("services.ai.kg")

_driver: AsyncDriver | None = None


def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=1.0,
            max_connection_lifetime=5.0,
        )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


async def run_write(query: str, params: dict[str, Any]) -> None:
    """Fire-and-forget write used by ingestion. Per ai/AGENT.md: 'Ingestion
    failures are logged, never fail the request.' Callers in kg/ingest.py
    wrap this (or call it in a background task) — this function itself
    still raises, so tests can assert on failure handling at the ingest
    layer rather than silently swallowing everything here."""
    driver = get_driver()
    async with driver.session() as session:
        await session.run(query, params)


async def run_read(query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(query, params)
        records = [record.data() async for record in result]
        return records
