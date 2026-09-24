# AGENTS.md

Instructions for AI coding agents (Claude Code, Cursor, Codex, etc.) working in this repository.
Read this file first, then the `AGENTS.md` inside the package you are changing. The nearest file wins when they conflict.

> Tip: `ln -s AGENTS.md CLAUDE.md` in each folder that has an AGENTS.md so every tool picks it up.

---

## 1. What we are building

**Travel & Local Discovery** helps people decide where to go and how to get there, using live flights, hotels, maps, places, reviews, and events data.

This is a **hackathon MVP built by a team of 4**. Optimize for a working end-to-end demo. Prefer simple, readable code over abstractions. Do not add infrastructure, libraries, or features that are not listed here without asking.

**We do not book anything.** "Booking" a flight or hotel means saving the user's selection to their trip and showing a deep link to the provider. There are no payments, no PNRs, no booking APIs.

### User flow (the product, in order)

| # | Step | Trip status after step |
|---|------|------------------------|
| 1 | Register / sign in (Better Auth) | – |
| 2 | Enter source, destination (optional), dates/duration, budget + currency, number of travelers, vibe tags | `DRAFT` |
| 3 | If no destination: AI recommends **top 5 destinations**; user picks one | `DESTINATION_SELECTED` |
| 4 | Initial **budget distribution** (flights, stay, local commute, food, activities, buffer) | `BUDGET_ESTIMATED` |
| 5 | Popular **spots** in the destination, ranked by current events + vibe match | – |
| 6 | User selects **multiple spots** | `SPOTS_SELECTED` |
| 7 | **Flight page** with live budget tracker pinned at top; user selects a flight | `FLIGHT_SELECTED` |
| 8 | **Hotel page**: hotels near the selected spots with reviews, price, distance to each spot; slider to change the stay budget | – |
| 9 | **Smart cost-saving suggestions** for the stay (see §8, not yet designed) | `HOTEL_SELECTED` |
| 10 | **Summary** of all selections + estimated local commute cost, with provider links | `SUMMARY_READY` |

The canonical `TripStatus` enum lives in `packages/shared`. Never invent new statuses in app code.

---

## 2. Repository layout

```
.
├── apps/
│   ├── web/            # Next.js (App Router) frontend            → apps/web/AGENTS.md
│   └── api/            # Node.js + Express backend, BullMQ workers  → apps/api/AGENTS.md
├── services/
│   └── ai/             # Python FastAPI + LangGraph + Neo4j         → services/ai/AGENTS.md
├── packages/
│   └── shared/         # Zod schemas, TS types, shared enums (JSON source of truth)
├── infra/
│   └── docker-compose.yml   # postgres, redis, neo4j
├── fixtures/
│   └── serpapi/        # recorded API responses for dev and tests
├── .env.example
└── AGENTS.md
```

JS workspaces are managed with **pnpm**. Python in `services/ai` is managed with **uv**.

---

## 3. Tech stack (do not substitute)

| Area | Choice |
|------|--------|
| Frontend | Next.js (App Router), TypeScript strict |
| Backend | Node.js, Express, TypeScript strict |
| Auth | Better Auth (server in `apps/api`, client in `apps/web`) |
| Database | PostgreSQL via **Prisma** |
| Cache + queues | Redis, **BullMQ** |
| Validation | **Zod** (TS), **Pydantic v2** (Python) |
| AI service | Python 3.12, FastAPI, LangGraph |
| Knowledge graph | Neo4j |
| External data | SerpApi (Google Flights, Hotels, Maps, Maps Reviews, Events) |
| LLMs | Gemini (primary), OpenAI and Grok (fallbacks), always through the provider wrapper |
| FX rates | One free FX API, wrapped behind `fx` service (see §6) |

---

## 4. Architecture and communication rules

```
Browser ──HTTP──> apps/api (Express) ──enqueue──> Redis/BullMQ ──> apps/api worker ──HTTP (internal)──> services/ai (FastAPI)
   ▲                  │                                                   │                                  │
   └──poll /jobs/:id──┘                                         writes result to Postgres           LangGraph + Neo4j + SerpApi + LLMs
```

Hard rules:

1. **The browser only talks to `apps/api`.** `services/ai` is internal and never exposed publicly. No `fetch` to the AI service or to SerpApi from `apps/web`.
2. **Anything slow goes through a queue.** Any operation that calls SerpApi or an LLM is a BullMQ job. The API route returns `202 { jobId }`, and the frontend polls `GET /jobs/:jobId` until status is `completed` or `failed`.
3. **BullMQ lives only in Node.** The worker process in `apps/api` consumes jobs and calls FastAPI over HTTP with the `X-Internal-Key` header. Python does not consume BullMQ queues directly.
4. **Postgres is owned by Prisma in `apps/api`.** The AI service must not read or write Prisma-managed tables. The only Postgres usage in Python is the LangGraph checkpointer, and it lives in a separate schema named `langgraph`.
5. **Neo4j is owned by `services/ai`.** Node never queries Neo4j.
6. **Redis** is used for BullMQ, API response caching, and FX rate caching. It is never the source of truth for trip data.

### Job names (shared contract)

Defined once in `packages/shared/src/jobs.ts` and mirrored in `services/ai/app/schemas/`:

| Job | FastAPI endpoint | Result saved to |
|-----|------------------|-----------------|
| `recommend-destinations` | `POST /internal/destinations/recommend` | `Trip.destinationOptions` |
| `estimate-budget` | `POST /internal/budget/estimate` | `Trip.budgetAllocation` |
| `discover-spots` | `POST /internal/spots/discover` | `Trip.spotOptions` |
| `search-flights` | `POST /internal/flights/search` | `Trip.flightOptions` |
| `search-hotels` | `POST /internal/hotels/search` | `Trip.hotelOptions` |
| `suggest-savings` | `POST /internal/savings/suggest` | `Trip.savingSuggestions` |
| `build-summary` | `POST /internal/summary/build` | `Trip.summary` |

When you add or change a job, update **all three**: the shared TS schema, the Pydantic schema, and this table.

---

## 5. Shared contracts

- All request/response shapes crossing a process boundary are defined in `packages/shared` as Zod schemas and mirrored as Pydantic models. Field names are `camelCase` over the wire. Pydantic models use `alias_generator=to_camel`.
- **Enums shared between TS and Python** (vibe tags, trip status, budget categories, job names) live as JSON in `packages/shared/enums/*.json`. Both sides load from these files. Never hard-code the values separately.
- **Vibe tags are a fixed list.** Current set: `adventure`, `relaxed`, `nightlife`, `culture_heritage`, `spiritual`, `food`, `nature`, `shopping`, `family`, `romantic`. Adding a tag means editing `vibes.json` only.
- **Budget categories:** `flights`, `stay`, `local_commute`, `food`, `activities`, `buffer`.

---

## 6. Money and currency (read before touching any price)

Trips can be domestic or international, so every price may arrive in a different currency.

- Represent money as `{ amountMinor: integer, currency: ISO-4217 string }`. **Never use floats for money.** No bare numbers without a currency.
- Each trip has a `baseCurrency` (the currency the user entered the budget in). Budget tracker, totals, and the summary are always shown in `baseCurrency`.
- Keep the **original provider price** and store the **converted price plus the FX rate and timestamp used** on every saved selection, so the summary is reproducible.
- All conversion goes through the single `fx` module in `apps/api` (`convert(money, toCurrency)`). Rates are cached in Redis for 12 hours. Do not call an FX API anywhere else.
- Round only at display time. Show converted prices as approximate ("≈ ₹42,300").

---

## 7. External APIs: cost and quota discipline

SerpApi and LLM calls cost money and quota. Treat them as scarce.

- **In dev and tests, use fixtures** from `fixtures/serpapi/` by default. Live calls require `USE_LIVE_APIS=true`.
- Never call a paid API inside a loop without a cap. Default caps: 5 destination candidates, 20 spots, 15 hotels, 10 flights.
- Cache SerpApi responses in Redis keyed by the normalized request. TTLs: flights 15 min, hotels 1 h, places/reviews/events 24 h.
- To record a new fixture, run the script in `services/ai/scripts/record_fixture.py` once with live keys and commit the JSON (strip any API key from URLs).
- API keys exist only in `apps/api` and `services/ai` env. **Never** put a secret in a `NEXT_PUBLIC_*` variable.

---

## 8. Open design areas: do not invent

- **Smart cost-saving strategies (step 9)** are not designed yet. Implement the `suggest-savings` job end to end with an empty strategy list and a clear interface (`SavingStrategy` → list of `SavingSuggestion`). Do not implement specific strategies until they are written in `docs/cost-strategies.md`.
- If a task requires a product decision not covered here, stop and ask rather than guessing.

---

## 9. Commands

```bash
# one-time
pnpm install
cd services/ai && uv sync && cd -
cp .env.example .env

# infra
docker compose -f infra/docker-compose.yml up -d     # postgres, redis, neo4j

# database
pnpm --filter api prisma migrate dev
pnpm --filter api prisma generate

# run everything
pnpm dev                                    # web + api + worker
cd services/ai && uv run fastapi dev app/main.py

# checks (run before you say a task is done)
pnpm lint && pnpm typecheck
cd services/ai && uv run ruff check . && uv run pyright
```

---

## 10. Working rules for agents

1. **Stay in scope.** Change only what the task needs. Do not refactor unrelated code or rename files you did not need to touch.
2. **Run the checks** in §9 for every package you changed before declaring the task done. If something fails and you can't fix it, say so explicitly.
3. **Contracts first.** If a change crosses `web ↔ api ↔ ai`, update `packages/shared` and the Pydantic mirror in the same change.
4. **Never** commit `.env` files or keys, edit an already-merged Prisma migration, or disable type checking or lint rules to make something pass.
5. **Tests we care about for the MVP:** budget math, currency conversion, hotel-to-spot distance scoring, and schema validation of every FastAPI response. Everything else is optional.
6. **No new dependencies** without stating why in your summary. Prefer what's already installed.
7. **Demo reliability beats completeness.** Every AI step must have a deterministic fallback (see `services/ai/AGENTS.md`), so a failed LLM call never blocks the flow.
8. When finished, summarize: what changed, files touched, how to test it, and anything left undone.
