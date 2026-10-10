# AGENTS.md — apps/web (Next.js frontend)

Read the root `AGENTS.md` first. This file adds frontend-specific rules.

## Responsibilities

- Render the 10-step trip flow from the root file, one route per step.
- Hold **no business logic** for budgets, currency, or ranking. The frontend displays what `apps/api` returns.
- Talk **only** to `apps/api` through the typed client in `src/lib/api/`. Never call SerpApi, the AI service, or an LLM from the browser.

## Routes

```
app/
├── (auth)/sign-in, sign-up
└── trips/
    ├── new/                         # step 2: trip input form
    └── [tripId]/
        ├── destinations/            # step 3 (skipped if destination given)
        ├── budget/                  # step 4
        ├── spots/                   # steps 5–6
        ├── flights/                 # step 7
        ├── hotels/                  # steps 8–9
        └── summary/                 # step 10
```

- Each step page reads `trip.status` from the API. If the user lands on a step they haven't reached, redirect to the correct one. Status → route mapping lives in `src/lib/trip-steps.ts` and nowhere else.

## Data fetching and jobs

- Use the shared Zod schemas from `@repo/shared` to parse every API response.
- Long operations return `202 { jobId }`. Use the single `useJob(jobId)` hook to poll `GET /jobs/:jobId` (every 1.5 s, stop on `completed` or `failed`, give up after 60 s).
- Every job-backed screen must have three states designed: **loading** (with a meaningful message like "Finding hotels near your 4 spots"), **error** (with retry), and **empty**.

## Budget tracker (steps 7–10)

- One component: `<BudgetTracker tripId />`, pinned at the top of flights, hotels, and summary pages.
- Shows each category's allocated vs. spent in the trip's `baseCurrency`, as returned by `GET /trips/:id/budget`. Do not compute totals client-side.
- Over-budget categories are visibly flagged.

## Hotel page specifics

- The stay-budget slider updates the allocation through `PATCH /trips/:id/budget` (debounced 400 ms) and then re-queries hotels. Don't re-trigger a SerpApi search on every slider tick; filter the already-fetched list client-side, and only request a new search when the user releases the slider outside the fetched price range.
- Each hotel card shows price (original currency + converted ≈ base currency), rating, review snippet, and distance to **each** selected spot.

## Money display

- Use the one `formatMoney(money)` helper. Never format prices inline.
- Converted prices always show `≈`.

## Auth

- Use the Better Auth client from `src/lib/auth-client.ts`. Protect `/trips/**` in `middleware.ts`.

## Conventions

- Server components by default. Add `"use client"` only for interactive pieces.
- Keep components under ~200 lines. Split by step, not by generic abstraction.
- Environment: only `NEXT_PUBLIC_API_URL` is public. No other `NEXT_PUBLIC_*` variables without asking.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
