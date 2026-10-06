# AGENT.md — Backend + Frontend (phased build)

Covers `backend/` (Express) and `frontend/` (Next.js). Put this at the repo root next to `AGENTS.md`.
Read root `AGENTS.md` first for product rules. **Where it conflicts with this file on folder names, this file wins** (root says `apps/api`, `apps/web`, `services/ai`; the real folders are `backend/`, `frontend/`, `ai/`).

Work **one phase at a time**. Don't start phase N+1 until phase N's "Done when" checks pass.

---

## 0. What exists today

| Area | State |
|------|-------|
| `backend/` | Express + Better Auth + Prisma (auth tables only), CORS, `/health`, `/api/me`. **No** Redis, BullMQ, Trip/Job models, Zod. |
| `frontend/` | Next 16 App Router, Tailwind 4, Better Auth client (`app/lib/auth-client.ts`). `app/page.tsx` is an auth test page. No Zod, no trip routes. |
| `ai/` | **Done. Don't modify.** The real service is `ai/app/` (FastAPI, 7 job endpoints). `ai/graph.py`, `nodes/`, `services.py`, `state.py`, `llm.py`, `tools/`, `graphdb/` are an old conversational prototype — ignore them. |
| `packages/shared` | Enum JSON only (`vibes`, `trip_status`, `budget_categories`, `job_names`). No TS source, no workspace. |

Run the AI service (works with no keys, no Redis, no Neo4j — fixtures + fallbacks):
```bash
cd ai && uv sync && cp .env.example .env && uv run fastapi dev app/main.py   # :8000
```

---

## 1. Hard rules (condensed from root AGENTS.md)

1. **Browser → backend only.** Never call `ai/` or SerpApi from the frontend.
2. **Anything slow is a BullMQ job.** Route returns `202 { jobId }`; frontend polls `GET /jobs/:jobId`.
3. **Only `backend/src/clients/ai.client.ts` calls the AI service**, with header `X-Internal-Key`. Validate every response with Zod. A schema mismatch = failed job, don't patch around it.
4. **Money is `{ amountMinor: int, currency: "ISO" }`.** No floats, no bare numbers. One `formatMoney()` on the frontend.
5. **Enums come from `packages/shared/enums/*.json`**, never hard-coded. Statuses: only values in `trip_status.json`.
6. Wire format is **camelCase**. Dates are `YYYY-MM-DD`.
7. Use **fixtures** (`USE_LIVE_APIS=false`) in dev. Don't turn on live APIs without being asked.
8. **Strict layering: routes → controllers → services → repositories** (see §3). Every endpoint: session check, Zod validation, ownership check, status guard (`409` if wrong status). Details and per-layer rules in §3.
9. No stack traces to the client. Job failures get a user-safe message.
10. Every job screen has **loading / error (with retry) / empty** states.
11. No new deps without saying why. (Phase 1 needs: backend `zod`, `bullmq`, `ioredis`; frontend `zod`. These are in the mandated stack.)
12. Before saying a phase is done: `npm run build` (backend), `npm run lint && npm run build` (frontend).

### Known deviations from root AGENTS.md (decided, don't re-litigate)

- No pnpm workspace exists, so **no `@repo/shared` package yet.** Zod schemas live in `backend/src/schemas/*.schema.ts` and are mirrored by hand in `frontend/app/lib/api/schemas.ts`. Enums are copied from `packages/shared/enums/` by `scripts/sync-enums.mjs` into `backend/src/shared/` and `frontend/app/lib/shared/`. Never edit the copies.
- Frontend has no `src/` dir; new code goes under `frontend/app/lib/`, `frontend/app/hooks/`, `frontend/app/components/`.
- Route protection on the frontend is a client-side guard in `app/trips/layout.tsx` (`useSession` → redirect to `/`). Next 16 renamed `middleware.ts` to `proxy.ts`; if you want a server-side guard, check the Next docs in `node_modules/next` first.

---

## 2. AI contract used in Phase 1 (source of truth: `ai/app/schemas/`)

All endpoints: `POST /internal/...`, header `X-Internal-Key` (default `dev-internal-key`), camelCase JSON.

**`POST /internal/destinations/recommend`** (job `recommend-destinations`)
```jsonc
// request
{ "tripId": "", "source": "DEL or city name", "startDate": "2026-12-01", "endDate": "2026-12-06",
  "travelers": 2, "budgetTotal": { "amountMinor": 8000000, "currency": "INR" }, "vibes": ["food","nature"] }
// response
{ "tripId": "", "fallbackUsed": false, "options": [   // max 5
  { "city": "", "country": "", "estimatedFlightPrice": { "amountMinor": 0, "currency": "" },
    "vibeMatchScore": 0.0-1.0, "reason": "", "source": "llm | knowledge_graph" } ] }
```

**`POST /internal/spots/discover`** (job `discover-spots`)
```jsonc
// request  (NOTE: city AND country are both required)
{ "tripId": "", "city": "", "country": "", "startDate": "", "endDate": "", "vibes": [] }
// response
{ "tripId": "", "fallbackUsed": false, "spots": [   // max 20
  { "providerRef": { "provider": "serpapi", "id": "", "deepLink": null },
    "name": "", "location": { "lat": 0, "lng": 0 }, "rating": 4.5,
    "vibeScores": [ { "vibe": "food", "score": 0.8 } ],
    "matchingEvent": { "name": "", "date": "2026-12-03", "venue": "" },   // nullable
    "tagSource": "llm | keyword_match" } ] }
```

Notes:
- `fallbackUsed: true` means an LLM step failed and deterministic logic took over. Surface it as a small, non-blocking notice, not an error.
- Unknown vibe tags → `422`. Always send tags from `vibes.json`.
- Money from the AI is in whatever currency it observed; conversion is the backend's job (`fx`, Phase 3).

---

## 3. Backend architecture (layered, keep it clean)

Request flow, always in this direction, never skipping a layer:

```
route ──► middleware (auth, validate) ──► controller ──► service ──► repository ──► Prisma
                                                           │
                                                           ├──► jobs/queue (enqueue)
                                                           └──► clients/ai.client (only from processors)
```

### Domains (each API area gets its own file in every layer)

Layers are folders; **inside each folder, one file per domain**. Don't mix domains in a file (e.g. no price logic inside `trip.service.ts`).

| Domain | Owns | Endpoints | Phase |
|--------|------|-----------|-------|
| `trip` | create trip, get trip, status transitions | `POST /trips`, `GET /trips/:id` | P1 |
| `destination` | AI destination options, pick one | `POST /trips/:id/destination` | P1 |
| `spot` | AI spot options, spot selection | `POST /trips/:id/spots` | P1 (list) / P2 (select) |
| `budget` | budget allocation, spent vs allocated, slider change | `GET/PATCH /trips/:id/budget` | P2 |
| `fx` | currency conversion + rate cache (**no routes**, used by budget/selection) | – | P3 |
| `flight` | flight options, flight selection | `POST /trips/:id/flight` | P3 |
| `hotel` | hotel options, hotel selection | `POST /trips/:id/hotel` | P4 |
| `saving` | cost-saving suggestions | `POST /trips/:id/savings` | P5 |
| `summary` | final summary | `POST/GET /trips/:id/summary` | P5 |
| `job` | job status polling | `GET /jobs/:jobId` | P1 |

"Price" = the `budget` domain (allocation + tracking) and the `fx` service (currency). Keep them separate from `flight`/`hotel`; those only call into them.

### Folder structure

Tags show the phase a file first appears in. Untagged = already exists. Files for later phases are listed so the shape is fixed up front, but **only create them when their phase starts**.

```
backend/
├── prisma/
│   ├── schema.prisma
│   └── migrations/
├── scripts/
│   └── sync-enums.mjs                      # P0
└── src/
    ├── index.ts                            # bootstrap only: listen + shutdown
    ├── app.ts                              # P0
    ├── worker.ts                           # P0
    │
    ├── config/
    │   └── env.ts                          # P0
    │
    ├── routes/
    │   ├── index.ts                        # P0  mounts everything
    │   ├── trip.routes.ts                  # P1
    │   ├── destination.routes.ts           # P1
    │   ├── spot.routes.ts                  # P1
    │   ├── job.routes.ts                   # P1
    │   ├── budget.routes.ts                # P2
    │   ├── flight.routes.ts                # P3
    │   ├── hotel.routes.ts                 # P4
    │   ├── saving.routes.ts                # P5
    │   └── summary.routes.ts               # P5
    │
    ├── controllers/                        # same names: trip.controller.ts, destination.controller.ts, ...
    │   ├── trip.controller.ts              # P1
    │   ├── destination.controller.ts       # P1
    │   ├── spot.controller.ts              # P1
    │   ├── job.controller.ts               # P1
    │   ├── budget.controller.ts            # P2
    │   ├── flight.controller.ts            # P3
    │   ├── hotel.controller.ts             # P4
    │   ├── saving.controller.ts            # P5
    │   └── summary.controller.ts           # P5
    │
    ├── services/
    │   ├── trip.service.ts                 # P1
    │   ├── destination.service.ts          # P1
    │   ├── spot.service.ts                 # P1
    │   ├── job.service.ts                  # P1
    │   ├── budget.service.ts               # P2  all budget math lives here only
    │   ├── fx.service.ts                   # P3  convert() + Redis rate cache
    │   ├── flight.service.ts               # P3
    │   ├── hotel.service.ts                # P4
    │   ├── saving.service.ts               # P5
    │   └── summary.service.ts              # P5
    │
    ├── repositories/
    │   ├── trip.repository.ts              # P1
    │   ├── job.repository.ts               # P1
    │   └── selection.repository.ts         # P3  spot / flight / hotel selections
    │
    ├── jobs/
    │   ├── queue.ts                        # P1
    │   └── processors/
    │       ├── recommend-destinations.processor.ts   # P1
    │       ├── discover-spots.processor.ts           # P1
    │       ├── estimate-budget.processor.ts          # P2
    │       ├── search-flights.processor.ts           # P3
    │       ├── search-hotels.processor.ts            # P4
    │       ├── suggest-savings.processor.ts          # P5
    │       └── build-summary.processor.ts            # P5
    │
    ├── clients/
    │   └── ai.client.ts                    # P1  only caller of the AI service
    │
    ├── schemas/
    │   ├── common.schema.ts                # P1  Money, dates, enums
    │   ├── trip.schema.ts                  # P1
    │   ├── destination.schema.ts           # P1
    │   ├── spot.schema.ts                  # P1
    │   ├── job.schema.ts                   # P1
    │   ├── budget.schema.ts                # P2
    │   ├── flight.schema.ts                # P3
    │   ├── hotel.schema.ts                 # P4
    │   ├── saving.schema.ts                # P5
    │   └── summary.schema.ts               # P5
    │
    ├── middlewares/
    │   ├── auth.ts
    │   ├── validate.ts                     # P0
    │   └── error-handler.ts                # P0
    │
    ├── lib/
    │   ├── prisma.ts
    │   ├── auth.ts
    │   ├── redis.ts                        # P0
    │   ├── errors.ts                       # P0
    │   ├── async-handler.ts                # P0
    │   ├── logger.ts                       # P0
    │   └── money.ts                        # P1
    │
    ├── types/
    │   └── express.d.ts                    # P0
    │
    └── shared/                             # generated enum copies, never edit by hand
```

Notes:
- `destination`, `spot`, `flight`, `hotel` routers are mounted under `/trips/:id/...` with `Router({ mergeParams: true })`.
- Repositories are fewer than services on purpose: `trip.repository` owns all Trip columns (including the JSON option columns); `selection.repository` owns the `Selection` table. Add a new repository only for a new Prisma model.
- Cross-domain calls go service → service (e.g. `flight.service` → `fx.service`, `budget.service`), never controller → other domain's repository.

### Layer rules (don't break these)

| Layer | Does | Must NOT |
|-------|------|----------|
| **routes** | Declare path + method, attach `requireAuth`, `validate(...)`, controller | Contain logic, touch `req.body` directly, import Prisma or services |
| **controllers** | Read validated input, call **one** service method, set status code, shape the response | Contain business rules, import Prisma/repositories, call the AI client or queue |
| **services** | Business logic: ownership checks, status guards (`ConflictError`), orchestration, enqueue jobs | Import Express types (`req`/`res`), write raw Prisma queries |
| **repositories** | Prisma queries only; return plain objects; scope by `userId` where relevant | Contain business rules, throw HTTP-flavored errors, call other repositories' services |
| **processors** | Load trip via repository, call `clients/ai.client.ts`, validate with Zod, save via repository, update Job row | Import controllers or Express |
| **clients** | Talk to an external service (timeout, headers, Zod-parse) | Know about Prisma or trips |
| **lib** | Tiny reusable helpers | Import from routes/controllers/services |

Conventions:
- **File naming:** `<domain>.<layer>.ts` (e.g. `trip.service.ts`). One domain per file; a file over ~200 lines gets split.
- **Imports go downward only:** routes → controllers → services → repositories → lib. Never upward, never sideways between controllers.
- **Errors:** services throw `AppError` subclasses from `lib/errors.ts`; `error-handler` turns them into `{ status: "error", message }`. Controllers have no try/catch (they're wrapped in `asyncHandler`).
- **Validation:** `validate()` middleware parses and replaces `req.body/params/query` with the Zod-parsed value. Controllers use the inferred types (`z.infer<typeof createTripSchema>`), never hand-written duplicates.
- **Response shape:** success `{ status: "success", data }`; error `{ status: "error", message }`. Keep it identical across all endpoints.
- **Config:** read env only through `config/env.ts`. Fail on boot if a required var is missing.
- **Barrel files:** none, except `routes/index.ts`. Import from the exact file.

### Frontend structure (`frontend/app/`)

```
app/
├── layout.tsx
├── page.tsx                                # existing auth page
├── globals.css
│
├── trips/
│   ├── layout.tsx                          # P1  auth guard
│   ├── new/
│   │   └── page.tsx                        # P1  trip form
│   └── [tripId]/
│       ├── destinations/page.tsx           # P1
│       └── spots/page.tsx                  # P1
│
├── components/
│   ├── ui/                                 # P1  small primitives: Button, Chip, Spinner
│   └── trips/
│       ├── TripForm.tsx                    # P1
│       ├── DestinationCard.tsx             # P1
│       ├── SpotCard.tsx                    # P1
│       └── JobState.tsx                    # P1  loading / error / empty
│
├── hooks/
│   └── useJob.ts                           # P1
│
└── lib/
    ├── auth-client.ts
    ├── api/
    │   ├── client.ts                       # P1  typed fetch wrapper
    │   ├── trips.ts                        # P1  one function per endpoint
    │   └── schemas.ts                      # P1  zod mirrors of backend schemas
    ├── shared/                             # P0  generated enum copies
    ├── formatMoney.ts                      # P1
    └── trip-steps.ts                       # P1  the one status → route map
```

Rules: pages stay thin (fetch + compose); UI lives in `components/`; every API call goes through `lib/api/`; no fetch calls inside components.

`lib/trip-steps.ts` holds the one `status → route` map. Each step page reads `trip.status` and redirects if the user isn't at that step yet.

---

## 4. Phases

### Phase 0 — Plumbing (do first, ~small)

- Add `infra/docker-compose.yml` with **Redis only** (Postgres is Neon via `DATABASE_URL`; the AI service runs without Neo4j).
- `backend/.env.example`: add `REDIS_URL=redis://localhost:6379`, `AI_BASE_URL=http://localhost:8000`, `AI_INTERNAL_KEY=dev-internal-key`.
- Backend: add `PATCH` to the CORS `methods` list (needed from Phase 2). Install `zod bullmq ioredis`. Add scripts: `"dev:worker": "tsx watch src/worker.ts"`.
- Write `scripts/sync-enums.mjs`; run it; commit the generated copies.
- **Refactor `src/index.ts` into the layered layout from §3:** move Express setup into `app.ts` (keep CORS, Better Auth mount, `/health`, `/api/me` behavior unchanged), leave `index.ts` as bootstrap only, move nothing else. Create `config/env.ts`, `lib/errors.ts`, `lib/async-handler.ts`, `lib/logger.ts`, `middlewares/validate.ts`, `middlewares/error-handler.ts`, `routes/index.ts`, `types/express.d.ts` (empty-but-wired is fine).
- `src/lib/redis.ts` (shared ioredis connection, `maxRetriesPerRequest: null` for BullMQ).

**Done when:** `docker compose -f infra/docker-compose.yml up -d` runs, `npm run dev` and `npm run dev:worker` both boot, `/health` and `/api/me` still work after the refactor, enums exist in both apps.

---

### Phase 1 — Trip form → (destinations) → spots

**Goal:** a signed-in user fills the form. If they gave a destination, we go straight to spots. If not, we show 5 AI destinations, they pick one, then we show spots. Spots are display-only in this phase (selection is Phase 2).

```
/trips/new  ──POST /trips──►  destination given?
                                 ├─ yes: status DESTINATION_SELECTED, enqueue discover-spots  ─► /trips/:id/spots
                                 └─ no:  status DRAFT, enqueue recommend-destinations         ─► /trips/:id/destinations
                                              └─ pick one ─POST /trips/:id/destination─► enqueue discover-spots ─► /trips/:id/spots
```

#### 1A. Form fields (`TripForm.tsx`)

| Field | Rules |
|-------|-------|
| `source` | Required. Free text, help text "City or airport code (e.g. DEL)". |
| `destinationCity` + `destinationCountry` | **Optional as a pair** (both or neither). The spots API needs both. |
| `startDate`, `endDate` | Required. `startDate` ≥ today, `endDate` > `startDate`. |
| `travelers` | Integer 1–20. Default 1. |
| `budgetAmount` + `currency` | Amount is a positive whole number in major units. Currency select: `INR` (default), `USD`, `EUR`, `GBP`. Convert to `amountMinor` (×100) in **one** helper; cap at 2,000,000,000 minor. |
| `vibes` | Multi-select chips from `vibes.json`, at least 1. |

Validate with the same Zod schema the backend uses (mirrored). Show inline errors. Disable submit while the request is in flight.

#### 1B. Backend

**Prisma** (new migration, never edit a merged one):
- `enum TripStatus` — values exactly as `trip_status.json`. Add a tiny check script/test that fails if the Prisma enum and the JSON drift.
- `Trip`: `id`, `userId` → User, `status` (default `DRAFT`), `source`, `destinationCity?`, `destinationCountry?`, `startDate`, `endDate`, `travelers`, `vibes String[]`, `budgetTotalMinor Int`, `baseCurrency`, `destinationOptions Json?`, `spotOptions Json?`, `createdAt`, `updatedAt`. (Other result columns arrive with their phases.)
- `Job`: `id` (= BullMQ job id), `tripId`, `userId`, `name`, `status` (`queued | active | completed | failed`), `error String?`, `createdAt`, `updatedAt`.

**Queue:** one queue `trip-jobs` (`src/jobs/queue.ts`), enqueued only from services. Defaults: `attempts: 2`, exponential backoff 2 s, `removeOnComplete: 100`. Job name = shared job name. Payload = `{ tripId, userId }` only; the processor loads the trip from Postgres.

**`clients/ai.client.ts`:** `fetch` with `AbortSignal.timeout(45_000)`, `X-Internal-Key` header, parses the response with Zod. Two functions this phase: `recommendDestinations(req)`, `discoverSpots(req)`. Non-2xx or parse failure → throw.

**Processors** (idempotent; overwrite the column, never append):
- `recommend-destinations`: build request from the Trip (`budgetTotal = { amountMinor: budgetTotalMinor, currency: baseCurrency }`, dates as `YYYY-MM-DD`) → call AI → write `Trip.destinationOptions` → mark Job `completed`.
- `discover-spots`: request from `destinationCity/Country` + dates + vibes → write `Trip.spotOptions` → mark Job `completed`.
- On final failure: Job `failed` with a safe message ("We couldn't fetch results. Try again.").

**Endpoints** (`trip.routes.ts` / `job.routes.ts` → `trip.controller.ts` / `job.controller.ts` → `trip.service.ts` / `job.service.ts` → `trip.repository.ts` / `job.repository.ts`; all behind `requireAuth` + `validate()`):

| Method | Path | Behavior |
|--------|------|----------|
| POST | `/trips` | Validate body. Create Trip. Destination given → status `DESTINATION_SELECTED` + enqueue `discover-spots`. Otherwise status `DRAFT` + enqueue `recommend-destinations`. Create Job row. Return `202 { tripId, jobId }`. |
| GET | `/trips/:id` | Owner only. Returns the trip (Zod-validated JSON columns) plus `pendingJob: { id, name, status } \| null` (latest non-completed job) so a page refresh doesn't lose the job. |
| POST | `/trips/:id/destination` | Body `{ city, country }`. Require status `DRAFT` and `destinationOptions` present, else `409`. **Check the pick is one of `destinationOptions`** (don't trust the client). Set `DESTINATION_SELECTED`, enqueue `discover-spots`, return `202 { jobId }`. |
| GET | `/jobs/:jobId` | Owner only (via Job row). Returns `{ status, error? }`. |

Routers are mounted in `routes/index.ts`, which `app.ts` mounts after `express.json()`.

#### 1C. Frontend

- **`app/lib/api/client.ts`**: typed `fetch` wrapper, `credentials: "include"`, base URL from `NEXT_PUBLIC_API_URL`, parses responses with the mirrored Zod schemas, throws a typed error on non-2xx.
- **`hooks/useJob.ts`**: `useJob(jobId)` polls every 1.5 s, stops on `completed`/`failed`, gives up after 60 s (treated as failed with a "taking longer than expected" message + retry).
- **`formatMoney.ts`**: `Intl.NumberFormat` with the currency's own fraction digits (so zero-decimal currencies don't break). Converted values are prefixed `≈` (used from Phase 3; AI flight estimates in destination cards are already approximate, show `≈` there too).
- **`trips/new`**: renders `TripForm`. On success route to `/trips/:id/spots` or `/trips/:id/destinations` per response, passing `jobId` (query param or state).
- **`trips/[tripId]/destinations`**: loads trip. If `destinationOptions` is present, render immediately; else if a job is pending, `useJob` + loading message ("Finding destinations that match your vibe"). Cards show city, country, `≈ flight price`, vibe match %, one-line reason. Click → `POST /trips/:id/destination` → go to spots. Notice if `fallbackUsed`-style fallback applies (store/return it from the job result if needed; otherwise skip this notice for destinations).
- **`trips/[tripId]/spots`**: same load pattern. Loading message: "Finding spots in {city}". Grid of `SpotCard`: name, rating, top 2–3 vibe chips (by score), event badge when `matchingEvent` exists, link to `providerRef.deepLink` if present. **No selection yet.**
- Wrong-step access (e.g. opening `/spots` on a `DRAFT` trip with no destination) redirects via `trip-steps.ts`.
- States for both job pages: loading, error + Retry (re-POSTs the last action), empty ("No spots found — try different vibes" with a link back to `/trips/new`).

#### Done when (test with fixtures, all three services running)

1. **With destination:** submit form with city+country → lands on spots → spots render. Trip status is `DESTINATION_SELECTED`.
2. **Without destination:** submit → destinations page shows ≤5 cards → pick one → spots render. Status ends `DESTINATION_SELECTED`.
3. **Refresh** on the spots/destinations page mid-job and after completion: page recovers (no lost job, no re-enqueue).
4. **AI down** (stop `uvicorn`): job fails after retry, UI shows error + Retry, no stack trace.
5. Another user's `tripId`/`jobId` returns `404`/`403`.
6. Wrong-status calls (e.g. `POST /destination` on a trip that already has one) return `409`.
7. Backend `npm run build`, frontend `npm run lint && npm run build` pass.

Smoke test:
```bash
# after signing in via the UI, copy the session cookie
curl -X POST localhost:5000/trips -H 'Content-Type: application/json' -H 'Cookie: <session cookie>' \
  -d '{"source":"DEL","startDate":"2026-12-01","endDate":"2026-12-06","travelers":2,
       "budget":{"amountMinor":8000000,"currency":"INR"},"vibes":["food","nature"]}'
curl localhost:5000/jobs/<jobId> -H 'Cookie: <session cookie>'
```

---

### Phase 2 — Budget estimate + spot selection

> Before starting: read `ai/app/schemas/budget.py` and `ai/app/graphs/estimate_budget.py` and add the contract to §2.

- Add job `estimate-budget` → `Trip.budgetAllocation` (JSON column + Zod). `POST /trips/:id/destination` and the "destination given" branch of `POST /trips` now enqueue **both** `estimate-budget` and `discover-spots`; status goes `DESTINATION_SELECTED → BUDGET_ESTIMATED` when the budget job completes.
- `GET /trips/:id/budget`: allocation per category (`flights, stay, local_commute, food, activities, buffer`) in `baseCurrency`. Math lives only in `services/budget.ts`. Unit tests required.
- Frontend `/trips/:id/budget` (or a panel on the spots page): allocation breakdown, no client-side math.
- Spot selection: `POST /trips/:id/spots` `{ spotIds: string[] }` (1+ spots, all must exist in `spotOptions`) → status `SPOTS_SELECTED`; require `BUDGET_ESTIMATED` else `409`. Frontend: multi-select on `SpotCard`, sticky "Continue (n selected)" bar.

**Done when:** destination → budget card + spots appear → select spots → status `SPOTS_SELECTED`; budget math tests pass.

### Phase 3 — Flights + FX + BudgetTracker

> Read `ai/app/schemas/flights.py` first.

- `fx` service (`convert(money, toCurrency)`, Redis cache `fx:{BASE}` 12 h, fail clearly if no rate and no cache). Tests required.
- Prisma `Selection` (`type: spot | flight | hotel`, provider id, original money, converted money, `fxRate`, `fxAt`, deep link). Persist the selected spots from Phase 2 here too.
- Job `search-flights` (triggered by `POST /trips/:id/spots`) → `Trip.flightOptions`. `POST /trips/:id/flight` saves selection → status `FLIGHT_SELECTED`.
- `<BudgetTracker tripId />`: pinned top of flights/hotels/summary; allocated vs spent per category from `GET /trips/:id/budget`; over-budget flagged.
- Flights page with job states.

### Phase 4 — Hotels

> Read `ai/app/schemas/hotels.py` first. Note: the AI service derives hotel dates as "today + nights" (see `ai/README.md` known gaps); decide whether to add `checkIn`/`checkOut` to both sides.

- Job `search-hotels` (triggered by `POST /trips/:id/flight`) → `Trip.hotelOptions`. `POST /trips/:id/hotel` → `HOTEL_SELECTED`.
- `PATCH /trips/:id/budget` for the stay slider (debounced 400 ms). Filter the fetched list client-side while sliding; only re-search when released outside the fetched price range.
- Hotel card: price (original + `≈` converted), rating, review snippet, distance to **each** selected spot.

### Phase 5 — Savings + Summary

> Read `ai/app/schemas/savings.py` and `summary.py` first.

- `suggest-savings`: full pipeline, **empty strategy list** (root AGENTS.md §8 — don't invent strategies). UI handles the empty result gracefully.
- `build-summary` → `Trip.summary`, status `SUMMARY_READY`. Summary page: all selections, estimated local commute, provider deep links, budget tracker.

### Phase 6 — Hardening for demo

- Every AI step verified against fallbacks (kill each dependency once).
- Loading/error/empty audit on every job screen.
- Seed/fixtures walkthrough script for the demo path; README with run steps.
- Tests we care about: budget math, fx, hotel-to-spot scoring (AI side exists), schema validation of every AI response.

---

## 5. Working rules for the agent

1. Stay in scope: only the current phase.
2. Contracts first: change the Zod schema (backend + frontend mirror) before the code that uses it. If a field is missing from the AI response, stop and say so — don't change `ai/`.
3. Never commit `.env`, keys, or edit an already-merged Prisma migration.
4. Don't disable type checks or lint rules to pass.
5. If a product decision isn't covered here or in root `AGENTS.md`, ask instead of guessing.
6. When done with a phase, report: what changed, files touched, how to test, what's left.