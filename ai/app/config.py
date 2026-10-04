"""
Central config for the AI service.

Per root AGENTS.md §5, enums shared between TS and Python live as JSON in
packages/shared/enums/*.json and BOTH sides load from those files — we never
hard-code the values separately in this service.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load .env into the process environment before anything below reads
# os.getenv(). Neither `uvicorn` nor `fastapi dev` do this automatically —
# without it, values written to .env are silently ignored and every
# os.getenv() call below sees only what the shell already had set.
load_dotenv()


def _find_shared_enums_dir() -> Path:
    """
    Locate packages/shared/enums by walking up from this file until we find
    it, so this works whether services/ai is nested under the monorepo root
    (apps/web, apps/api, services/ai, packages/shared — per root AGENTS.md §2)
    or the service is checked out standalone for local dev.
    """
    env_override = os.getenv("SHARED_ENUMS_DIR") or None
    if env_override:
        return Path(env_override)

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "packages" / "shared" / "enums"
        if candidate.is_dir():
            return candidate

    # Fallback for a checkout that only contains the ai service: a bundled
    # read-only mirror shipped alongside this package. This must stay in
    # sync with packages/shared/enums in the monorepo; it exists only so
    # `uv run pytest` works from a bare clone of services/ai.
    fallback = here.parent.parent / "fixtures" / "shared_enums_fallback"
    return fallback


class Settings:
    # --- service identity / auth ---
    internal_api_key: str = os.getenv("AI_INTERNAL_KEY", "dev-internal-key")

    # --- external services ---
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "neo4j")

    # --- LLM providers (root AGENTS.md §3: Gemini primary, OpenAI/Grok fallback) ---
    # `or None`: .env files commonly set unset secrets to an empty string
    # rather than omitting them, and "" must be treated as "not configured"
    # (ProviderUnavailable), not as a literal empty API key.
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None
    groq_api_key: str | None = os.getenv("GROQ_API_KEY") or None
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS") or "20")

    # --- SerpApi (root AGENTS.md §7) ---
    serpapi_key: str | None = os.getenv("SERPAPI_KEY") or None
    use_live_apis: bool = (os.getenv("USE_LIVE_APIS") or "false").lower() == "true"
    fixtures_dir: Path = Path(
        # app/config.py -> parents[0]=app, parents[1]=<service root> (services/ai)
        os.getenv("SERPAPI_FIXTURES_DIR")
        or str(Path(__file__).resolve().parents[1] / "fixtures" / "serpapi")
    )

    # --- quota caps (root AGENTS.md §7) ---
    cap_destination_candidates: int = 5
    cap_spots: int = 20
    cap_hotels: int = 15
    cap_flights: int = 10
    cap_events: int = 10

    # --- Graph similarity ---
    graph_similarity_threshold: float = float(os.getenv("GRAPH_SIMILARITY_THRESHOLD") or "0.8")

    # --- cache TTLs, seconds (root AGENTS.md §7) ---
    # Stable data (longer TTL)
    ttl_place_metadata: int = 24 * 60 * 60
    ttl_hotel_metadata: int = 24 * 60 * 60
    ttl_places: int = 24 * 60 * 60

    # Volatile data (shorter TTL)
    ttl_flights: int = 15 * 60
    ttl_hotel_prices: int = 60 * 60
    ttl_hotels: int = 60 * 60
    ttl_events: int = 60 * 60
    ttl_fx: int = 12 * 60 * 60  # owned by apps/api, listed here for reference only

    shared_enums_dir: Path = _find_shared_enums_dir()



@lru_cache
def get_settings() -> Settings:
    return Settings()
