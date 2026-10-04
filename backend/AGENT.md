# AGENTS.md — apps/api (Express backend + workers)

Read the root `AGENTS.md` first. This file adds backend-specific rules.

## Responsibilities

- Public HTTP API for the frontend.
- Auth (Better Auth), trip state, and all Postgres data via Prisma.
- Enqueue BullMQ jobs and run the workers that call `services/ai`.
- Currency conversion (`fx` module) and budget tracking math.

## Structure

```
src/
├── server.ts              # Express app (HTTP only)
├── worker.ts              # BullMQ worker entrypoint (separate process)
├── auth/                  # Better Auth config + requireSession middleware
├── routes/                # thin: validate with Zod → call service → respond
├── services/              # business logic (trips, budget, fx, selections)
├── jobs/                  # queue definitions + one processor file per job
├── clients/ai.ts          # the ONLY place that calls services/ai
└── lib/                   # prisma client, redis client, logger, errors
prisma/schema.prisma
```

Routes stay thin. Logic goes in `services/`. Processors in `jobs/` call `clients/ai.ts`, validate the response with the shared Zod schema, then persist through a service.

## Core endpoints

| Method | Path | Notes |
|--------|------|-------|
| POST | `/trips` | Create trip from step-2 input. If no destination, enqueue `recommend-destinations`. |
| GET | `/trips/:id` | Full trip incl. status and current options |
| POST | `/trips/:id/destination` | Pick one of the top 5 → enqueue `estimate-budget` + `discover-spots` |
| GET / PATCH | `/trips/:id/budget` | Allocation vs. spent, in base currency. PATCH changes category amounts (e.g., hotel slider). |
| POST | `/trips/:id/spots` | Save selected spot IDs → enqueue `search-flights` |
| POST | `/trips/:id/flight` | Save selected flight → enqueue `search-hotels` |
| POST | `/trips/:id/hotel` | Save selected hotel → enqueue `build-summary` |
| POST | `/trips/:id/savings` | Enqueue `suggest-savings` |
| GET | `/jobs/:jobId` | `{ status, progress?, error? }` — only for jobs owned by the session user |

Every route: `requireSession`, verify the trip belongs to the user, validate body with Zod, and check the trip is in a valid status for the action (return `409` otherwise).

## Data model notes (Prisma)

- `Trip`: `userId`, `status` (shared enum), `source`, `destination?`, `startDate`, `endDate`, `travelers`, `vibes[]`, `budgetTotalMinor`, `baseCurrency`, plus JSONB columns for each job result (`destinationOptions`, `budgetAllocation`, `spotOptions`, `flightOptions`, `hotelOptions`, `savingSuggestions`, `summary`).
- `Selection`: one row per chosen item (`type`: spot | flight | hotel), storing provider ID, original money, converted money, `fxRate`, `fxAt`, and the provider deep link.
- `Job`: mirrors BullMQ job ID, `tripId`, `userId`, `name`, `status`, `error`. Used for ownership checks on `/jobs/:id`.
- JSONB result columns are validated with the shared Zod schema **on write and on read**.
- Never edit a merged migration. Add a new one.

## Queues and workers

- One queue: `trip-jobs`. Job name = the shared job name.
- Default job options: `attempts: 2`, exponential backoff 2 s, `removeOnComplete: 100`.
- The AI client timeout is 45 s. On final failure, mark the `Job` row `failed` with a user-safe message. Never leak stack traces to the frontend.
- Job payloads carry IDs and the minimal input needed, not whole trip objects.
- Make processors idempotent: re-running a job overwrites its result column rather than appending.

## Budget and FX

- `fx.convert(money, toCurrency)` is the only conversion function. Rates are cached in Redis (`fx:{BASE}` , 12 h TTL). If the FX API fails and there's no cached rate, fail the operation clearly rather than guessing.
- "Spent" per category = sum of `Selection` converted amounts. `local_commute` comes from the summary estimate. Compute these in `services/budget.ts` only.
- Unit tests are required for `fx` and `budget` services.

## Auth

- Better Auth mounted at `/api/auth/*`, session cookies, CORS limited to the web origin with credentials.

## Calling the AI service

- Only through `clients/ai.ts`. Send `X-Internal-Key: $AI_INTERNAL_KEY`.
- Validate every response with the shared Zod schema. A schema mismatch is a job failure, not something to patch around.
