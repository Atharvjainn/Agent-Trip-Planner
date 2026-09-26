# Trip planner agent - backend

A LangGraph-based trip planning agent. No FastAPI layer yet by design -
this is the graph, the knowledge graph cache, and the LLM layer, meant
to be run locally (`run_local.py`) and iterated on before anything is
wrapped in an HTTP API.

## Layout

```
state.py               TripState schema + TurnResponse (the future API contract)
config.py               all environment variables, read from here everywhere else
llm.py                  every model call: OpenJev typed decisions + generation
services.py             reusable search+cache+rank capabilities, shared by
                          initial planning and later adjustments
graph.py                LangGraph wiring: entry routing + same-turn chaining
run_local.py            REPL harness, no frontend/API needed to test the graph

graphdb/
  connection.py          Neo4j driver singleton
  schema.py              one-time constraint setup (`python -m graphdb.schema`)
  repository.py          all Cypher lives here - the knowledge graph cache

tools/
  serpapi_client.py      SerpApi wrapper (Google Maps + Google Hotels)
  weather.py              OpenWeatherMap wrapper
  geo.py                  haversine distance, centroid, day clustering

nodes/
  router.py               coarse intent classification (calls llm.classify_intent)
  destination.py          pick or recommend a destination
  attractions.py           fetch + confirm attractions (initial planning)
  hotels.py                fetch + confirm a hotel (initial planning)
  itinerary.py              day-wise clustering into a plan
  adjust.py                  every "the plan needs to change" case, pre-trip
                              or mid-trip: nearby exploration, rescheduling a
                              day, extending the trip, replacing disliked
                              items, or changing hotel - see below
  verify.py                   grounds any place name against cache/live SerpApi
```

## Why `adjust.py` isn't split into "modify_plan" vs "in_trip_query"

The first version of this graph routed on *when* a request happened
(planning vs. already on the trip). That doesn't hold up: "the itinerary
isn't working because of rain" and "I want a different hotel" can both
happen before departure or mid-trip, and read identically either way -
splitting on conversation_stage would have misrouted half of them.

Instead there are two classification levels:

1. **`llm.classify_intent`** (routing, coarse) - is this a greeting, a
   brand new trip, an adjustment to something already decided, or a
   continuation of whatever the assistant just asked. Fast tier model.
2. **`llm.classify_adjustment_type`** (only when intent is
   `trip_adjustment`) - *which* adjustment: nearby exploration,
   rescheduling a day, extending the trip, replacing itinerary items, or
   changing the hotel. This one runs on the reasoning-tier model
   deliberately - telling these apart from a casually-worded message is
   a genuinely harder call than routing a greeting.

Both classifiers reason over `llm._summarize_trip_context(state)` -
destination, budget, itinerary size, hotel - not just the raw message,
so "I don't like this" resolves differently depending on what's already
been decided.

`nodes/adjust.py`'s five handlers all call the same `services.py`
functions the initial planning nodes use (`fetch_attraction_candidates`,
`fetch_hotel_candidates`), passing `exclude_place_ids` so a "find me
something else" never re-suggests something already visited or already
turned down.

**Known gap, left visible rather than guessed at:** `reschedule_day`
extracts *that* a postponement was mentioned (`postpone_days`) but not
robustly *which* itinerary day it refers to, nor whether a postponement
pushes past the current hotel's checkout date (which would need a price
refresh for the new date range). Both are flagged with a `TODO`-style
docstring in `_handle_reschedule_day` rather than implemented with a
guess that would fail silently.

## Why there's an `llm.py` instead of scattered model calls

Every decision that reduces to a fixed set of options (routing intent,
which option the user picked, trip vibe, in-trip category) goes through
**OpenJev**'s typed-decision endpoint (`llm.decide`) - it reads the
answer straight off the model's token probabilities, so it cannot go
off-schema. Nothing in `nodes/` does keyword or regex matching to guess
what the user meant.

Anything open-ended (the reply text shown to the user, or pulling a
budget/city/duration out of a free-form sentence) goes through
generation (`llm.generate`, and the `llm.build_reply` /
`llm.extract_trip_slots` helpers built on it).

Model tiers are picked by task complexity, not fixed to one model - see
the docstring at the top of `llm.py` for the full breakdown:
`verdict-1.4` (fast, <=24 options) for simple routing/classification,
`laya-1.0` (<=255 options) when a candidate list might be large,
`openjev-latest` (the full DiffusionGemma model) for anything needing
real contextual reasoning, and `diffusiongemma-26b` for free text and
tool-calling extraction.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in Neo4j / SerpApi / OpenWeather / OpenJev credentials
python -m graphdb.schema   # one-time constraint setup against AuraDB
python run_local.py
```

OpenJev: the free hosted instance at Codiv (`https://api.codiv.ai`) needs
no setup beyond an API key - see https://github.com/razorback16/openjev
for self-hosting on your own GPU/Apple silicon instead.

## The API contract (for whoever builds the FastAPI layer next)

Every node writes a `TurnResponse` into `state["turn_response"]` before
handing control back - see `state.py`. That shape is deliberately the
same regardless of which node ran:

```python
{
  "reply": str,                 # what to show as the assistant's message
  "stage": str,                 # where the conversation is now
  "ui_component": str,          # which card/component the frontend should render
  "options": list[dict],        # the structured data behind that component
  "requires_user_input": bool,  # whether the turn is waiting on the user
  "input_type": str,            # free_text | select_one | select_multi | confirm | none
}
```

Wrapping this in FastAPI later should be close to: accept
`{session_id, message}`, load or create a `TripState` for that
session_id, call `graph.invoke(state)`, persist the resulting state, and
return `state["turn_response"]` as the JSON body. Session storage (a
dict keyed by session_id, Redis, whatever) is the only piece that
doesn't already exist in this repo.
