# AGENTS.md — services/ai (FastAPI + LangGraph + Neo4j)

Read the root `AGENTS.md` first. This file adds AI-service rules.

## Responsibilities

- Internal HTTP endpoints (one per job, see root §4) called only by the `apps/api` worker.
- LangGraph workflows that combine SerpApi data, the Neo4j knowledge graph, and LLM reasoning.
- Ingesting everything we fetch into Neo4j so recommendations improve with usage.
- This service is **stateless per request** apart from Neo4j and LangGraph checkpoints. It does not touch Prisma tables.

## Structure

```
app/
├── main.py                  # FastAPI app, X-Internal-Key dependency on all /internal routes
├── routes/                  # one router per job; thin
├── graphs/                  # one LangGraph graph per job
├── nodes/                   # reusable graph nodes (pure-ish functions)
├── tools/
│   ├── serpapi.py           # the ONLY SerpApi client (cache + fixtures + caps)
│   └── geo.py               # haversine, centroid, distance scoring
├── llm/
│   ├── provider.py          # the ONLY way to call an LLM
│   └── prompts/             # prompt templates, one file per task
├── kg/
│   ├── ingest.py            # MERGE-based upserts
│   └── queries.py           # all Cypher lives here
├── schemas/                 # Pydantic v2 models mirroring packages/shared
└── rules/                   # deterministic logic (budget split, commute rates)
scripts/record_fixture.py
tests/
```

## Graphs (one per job)

| Graph | Flow | Deterministic fallback if LLM fails |
|-------|------|-------------------------------------|
| `recommend_destinations` | parse input → KG candidates (vibe + budget + season) → SerpApi flights price check from source → LLM rank + reasons → top 5 | KG/vibe-score ranking, generic reasons |
| `estimate_budget` | rules split → LLM adjust with explanation → validate | rules split only |
| `discover_spots` | SerpApi Maps places + Events for dates → vibe-tag match → LLM tag unknown places → rank | keyword-based tag match |
| `search_flights` | SerpApi Google Flights → normalize → sort by price within flights budget | n/a (no LLM) |
| `search_hotels` | spots centroid → SerpApi Google Hotels near centroid → distance to each spot → score | n/a (no LLM) |
| `suggest_savings` | run registered `SavingStrategy` list (currently empty) | empty list |
| `build_summary` | selections → commute estimate between hotel and spots → LLM short narrative | template narrative |

Rules for graphs:

- Each node does one thing and is unit-testable without network access.
- Every graph ends with a node that validates output against the Pydantic response model.
- Use the Postgres checkpointer (schema `langgraph`) only where a graph needs resumability. Most MVP graphs don't; keep them simple.
- **The LLM never produces a price, distance, or total.** Numbers come from SerpApi, `geo.py`, or `rules/`. The LLM ranks, tags, explains, and adjusts within validated bounds.

## Budget estimate rules

- `rules/budget.py` holds default percentage splits per trip type (domestic vs. international) and duration band.
- The LLM may adjust each category by at most ±15 percentage points and must return an explanation.
- Validation after the LLM: all amounts ≥ 0, integers in minor units, sum equals the total exactly (put rounding remainder in `buffer`). If validation fails, return the rules split.

## Hotel scoring

- Distance = haversine km from hotel to each selected spot (no Distance Matrix calls in MVP).
- Default score = `0.45 * price_fit + 0.35 * proximity + 0.20 * rating`, each normalized to 0–1. Weights live in one constant; tests cover the scoring function.

## Local commute estimate

- `rules/commute.py`: per-km rate table by city tier and mode (auto, cab, metro, walk), with a country-level default for international cities, in local currency.
- Estimate = daily hotel → spots → hotel route distance × rate. Return money in local currency; `apps/api` converts.

## Knowledge graph (Neo4j)

Built from user data and API results, not pre-seeded.

Nodes: `City`, `Place`, `Hotel`, `Event`, `Vibe`, `Trip` (anonymized ID only, no PII).
Relationships: `(Place)-[:IN]->(City)`, `(Hotel)-[:IN]->(City)`, `(Event)-[:IN]->(City)`, `(Place)-[:HAS_VIBE {score}]->(Vibe)`, `(Hotel)-[:NEAR {km}]->(Place)`, `(Trip)-[:TO]->(City)`, `(Trip)-[:SELECTED]->(Place|Hotel)`, `(Trip)-[:WANTED]->(Vibe)`.

- Upserts use `MERGE` on provider IDs (SerpApi `place_id` / `data_id`, hotel `property_token`). Ingestion must be idempotent.
- Ingest after each SerpApi fetch, in the background. Ingestion failures are logged, never fail the request.
- All Cypher lives in `kg/queries.py`. Parameterize every query; no string formatting.
- **Cold start:** when the KG has too few candidates (<5 cities for a vibe), `recommend_destinations` falls back to LLM-generated candidates validated by a SerpApi flight price check.
- No user names, emails, or free text in Neo4j.

## LLM usage

- Call only through `llm/provider.py`: `await llm.structured(task, prompt, schema=PydanticModel)`.
- Order: Gemini → OpenAI → Grok. On timeout (20 s), rate limit, or schema-invalid output, try the next provider once. If all fail, the graph uses its deterministic fallback.
- Always request structured output bound to a Pydantic model. Never parse free text with regex.
- Prompts live in `llm/prompts/`, not inline in nodes. Keep them short and include the allowed vibe tags from `vibes.json`.
- Log per call: task, provider, latency, token counts. No user PII in logs.

## SerpApi

- Only through `tools/serpapi.py`. It handles Redis caching (TTLs in root §7), fixtures when `USE_LIVE_APIS` is false, and hard result caps.
- Engines used: `google_flights`, `google_hotels`, `google_maps`, `google_maps_reviews`, `google_events`.
- Normalize every response into our Pydantic models immediately. Raw SerpApi JSON never leaves `tools/`.
- Keep provider deep links from results so the frontend can link out (we don't book).

## Commands

```bash
uv sync
uv run fastapi dev app/main.py
uv run pytest
uv run ruff check . && uv run pyright
uv run python scripts/record_fixture.py --engine google_hotels --q "hotels near Baga Beach"
```

## Tests required for MVP

Budget rules and validation, hotel scoring, commute estimate, SerpApi normalizers (against fixtures), and one happy-path test per graph with LLM and SerpApi mocked.
