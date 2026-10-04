#!/usr/bin/env python3
"""
root AGENTS.md §7: "To record a new fixture, run the script in
services/ai/scripts/record_fixture.py once with live keys and commit the
JSON (strip any API key from URLs)."

Usage:
    uv run python scripts/record_fixture.py --engine google_hotels --q "hotels near Baga Beach"
    uv run python scripts/record_fixture.py --engine google_flights \
        --departure-id JFK --arrival-id CDG --outbound-date 2026-11-10 --return-date 2026-11-17

Writes fixtures/serpapi/<engine>__<slug>.json, matching the lookup order
tools/serpapi.py uses (query-specific fixture, falling back to
<engine>_sample.json if no specific one is recorded). Requires SERPAPI_KEY
in the environment; never writes the key into the output file.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

SERPAPI_BASE_URL = "https://serpapi.com/search"
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "serpapi"


def _slug(params: dict) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


async def record(engine: str, params: dict) -> Path:
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set — refusing to make a live call.", file=sys.stderr)
        sys.exit(1)

    query = {**params, "engine": engine, "api_key": api_key}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(SERPAPI_BASE_URL, params=query)
        resp.raise_for_status()
        data = resp.json()

    # Defensive strip: api_key should never appear in the stored response,
    # but SerpApi sometimes echoes the request URL back in search_metadata.
    def _strip_key(obj):
        if isinstance(obj, dict):
            return {k: _strip_key(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_strip_key(v) for v in obj]
        if isinstance(obj, str) and api_key in obj:
            return obj.replace(api_key, "REDACTED")
        return obj

    data = _strip_key(data)

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = FIXTURES_DIR / f"{engine}__{_slug(params)}.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", required=True, choices=[
        "google_flights", "google_hotels", "google_maps", "google_maps_reviews", "google_events",
    ])
    parser.add_argument("--q", help="free-text query, e.g. 'hotels near Baga Beach'")
    parser.add_argument("--departure-id")
    parser.add_argument("--arrival-id")
    parser.add_argument("--outbound-date")
    parser.add_argument("--return-date")
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lng", type=float)
    parser.add_argument("--check-in-date")
    parser.add_argument("--check-out-date")
    args = parser.parse_args()

    params = {k.replace("-", "_"): v for k, v in vars(args).items() if k != "engine" and v is not None}

    out_path = asyncio.run(record(args.engine, params))
    print(f"Wrote fixture: {out_path}")
    print("Commit this file. Double-check it does not contain your API key before pushing.")


if __name__ == "__main__":
    main()
