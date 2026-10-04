# Travel & Local Discovery — AI service

FastAPI + LangGraph + Neo4j service implementing the 7 jobs in the root
`AGENTS.md` job table. This directory is self-contained and does not
require the `backend`/`frontend` teams' code to run or test — it only
needs `packages/shared/enums/*.json` (included here) as its source of
truth for vibe tags, trip status, and budget categories.

## What's here

```
ai/
├── app/
│   ├── main.py            FastAPI app, X-Internal-Key auth on /internal/*
│   ├── config.py          env settings, shared-enum path resolution
│   ├── routes/             one thin router per job
│   ├── graphs/             one LangGraph workflow per job (7 total)
│   ├── tools/
│   │   ├── serpapi.py      the ONLY SerpApi client: fixtures/live, Redis
│   │   │                   cache, hard caps, per-engine normalizers
│   │   └── geo.py           haversine, centroid, normalize (pure)
│   ├── llm/
│   │   ├── provider.py      Gemini -> OpenAI -> Grok fallback chain
│   │   └── prompts/         one prompt builder per LLM-using job
│   ├── kg/                  Neo4j: parameterized Cypher, idempotent
│   │                        MERGE ingestion, read helpers
│   ├── schemas/              Pydantic v2 models mirroring packages/shared,
│   │                        camelCase on the wire
│   └── rules/                deterministic logic: budget split, commute,
│                             hotel scoring, keyword vibe tagging, the
│                             (empty) saving-strategy registry
├── fixtures/serpapi/         recorded sample responses, one per engine
├── scripts/record_fixture.py
├── tests/                    54 tests, all offline (no live network needed)
├── pyproject.toml
└── .env.example
```

Also added at the repo root: `packages/shared/enums/{vibes,trip_status,budget_categories,job_names}.json`
— the canonical source every side is supposed to load from (root `AGENTS.md`
§5). If your actual repo already has different files here, diff against
these rather than overwriting; the job-name table in particular should stay
word-for-word in sync with `packages/shared/src/jobs.ts`.

## Running it

```bash
cd ai
uv sync                     # or: python -m venv .venv && pip install -e ".[dev]"
cp .env.example .env
uv run fastapi dev app/main.py
```

With no SerpApi/LLM keys set and `USE_LIVE_APIS=false` (the default), every
endpoint works end-to-end against the bundled fixtures and deterministic
fallbacks — no Redis or Neo4j needs to be running either; both degrade
gracefully (see "Demo reliability" below). I verified this with a live
`TestClient` call to `/internal/destinations/recommend` with nothing
running but this process.

```bash
curl -X POST http://localhost:8000/internal/savings/suggest \
  -H "X-Internal-Key: dev-internal-key" -H "Content-Type: application/json" \
  -d '{"tripId": "t1", "selections": {}}'
```

## Testing

```bash
uv run pytest        # 54 passed
uv run ruff check .  # clean
```

No test touches a real network, Redis, or Neo4j instance. SerpApi-dependent
tests run against the fixtures in `fixtures/serpapi/`; LLM-dependent tests
inject a `FakeLLMBackend` (see `tests/conftest.py`) through each graph's
`Deps` dataclass, so they exercise the *real* `LLMProvider.structured()`
retry/validation logic without a network call. Coverage:

- `test_budget_rules.py` — split-to-100 invariant, ±15pp LLM-adjustment
  validation, sum-equals-total-exactly rounding
- `test_hotel_scoring.py` — the 0.45/0.35/0.20 weighted score
- `test_commute.py` — haversine/centroid geo math, rate lookup, scaling
  with nights
- `test_serpapi_normalizers.py` — every engine's normalizer against its
  fixture
- `test_graph_*.py` — one happy-path + one fallback-path test per graph
  (plus extras for recommend_destinations' cold-start branch)

## The contract, for the backend/frontend teams

- **Endpoints**: exactly the 7 in root `AGENTS.md` §4, under `/internal/`,
  each requiring header `X-Internal-Key` (value from `AI_INTERNAL_KEY`).
  A missing/wrong key is a `401`. This process should never be reachable
  from the browser — only from `apps/api`'s worker.
- **Request/response shapes**: see `app/schemas/*.py`. Every model uses
  `alias_generator=to_camel`, so JSON on the wire is camelCase
  (`tripId`, `estimatedFlightPrice`, …) even though the Python attribute
  names are snake_case. This should match the Zod schemas in
  `packages/shared` field-for-field — if you change one side, change both.
- **Money**: always `{amountMinor: int, currency: "USD"}` — never a bare
  float. This service only ever returns amounts in whatever currency it
  actually observed (the provider's, or the rules engine's); it does not
  do currency conversion — that's `apps/api`'s `fx` module.
- **`fallbackUsed`**: every response carries this. `true` means an LLM
  call failed and a deterministic fallback took over — useful for a demo
  banner or for logging/QA, not required reading for normal operation.
- **Every graph is demo-reliable by construction**: no external dependency
  being down (Neo4j, Redis, SerpApi fixtures missing, or every LLM
  provider) produces a `5xx` from a healthy request — each failure mode
  has a tested fallback. The one exception is a genuinely malformed
  request, which fails Pydantic validation at the route boundary (a
  `422`), as it should.

## Known gaps / deliberate non-goals

- **`google_maps_reviews` fixture** is included for parity with the
  engine list in `ai/AGENT.md`, but no graph calls it yet — hotel review
  snippets currently come from the `reviews_breakdown` field already
  present in the `google_hotels` response. Wire it up if/when a graph
  needs independent place-level reviews.
- **`search_hotels`' check-in/check-out dates** are currently derived as
  "today + nights" rather than the trip's real dates, because this
  service never reads `Trip` rows from Postgres (root `AGENTS.md` §4.4)
  and the current `HotelSearchRequest` schema (matching what `apps/api`
  was documented to send) doesn't carry them. If real dates matter for
  hotel pricing, add `checkIn`/`checkOut` to the request schema on both
  sides.
- **`suggest_savings`** is intentionally a complete, real pipeline with an
  empty strategy list, per root `AGENTS.md` §8 — do not add strategies
  here until `docs/cost-strategies.md` exists and is agreed. The
  `SavingStrategy` protocol in `app/rules/saving_strategies.py` is the
  only place a future contributor needs to touch.
- **Neo4j ingestion runs inline, awaited**, rather than literally
  fire-and-forget on a background task queue — it already can't fail the
  request (every write is caught and logged), so the only difference
  from a "true" background task is a few extra milliseconds of request
  latency. Swap in `asyncio.create_task` + a shutdown-safe task tracker
  if that latency matters later.
- **LangGraph checkpointing** (the `langgraph` Postgres schema mentioned
  in `ai/AGENT.md`) isn't wired up — none of the 7 MVP graphs need
  resumability, per that same doc ("most MVP graphs don't; keep them
  simple"). Add it only if a graph grows a genuine need to pause/resume.

## Recording new fixtures

```bash
export SERPAPI_KEY=...
uv run python scripts/record_fixture.py --engine google_hotels --q "hotels near Baga Beach"
```

Writes `fixtures/serpapi/<engine>__<slug>.json`. The API key is stripped
from the output; double-check before committing anyway.
