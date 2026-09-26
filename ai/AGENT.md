# AGENT.md

Context for any coding agent (or human) picking up this codebase. Read
this before changing anything - several design choices here look
arbitrary until you know what they're avoiding.

## What this is

A LangGraph-based backend for an agentic trip planner (hackathon
project). It plans a trip conversationally (destination -> attractions
-> hotel -> itinerary), then keeps helping once the trip has started or
plans change (weather delays, extended stays, disliked itineraries,
hotel swaps). No FastAPI layer yet, by design - see "Deferred on
purpose" below. Run it via `run_local.py`, a plain REPL.

## Current status - read this first

**Working end to end:** greeting -> destination -> attractions ->
hotel -> itinerary, plus six adjustment paths (nearby exploration,
reschedule, extend, replace items, change hotel, find a flight) via
`nodes/adjust.py`. Every reply and every routing/selection decision goes
through `llm.py` - nothing in `nodes/` pattern-matches text. Attraction
data now carries real operating hours and unfiltered highlight
extensions (previously fetched and discarded); hotel/destination prices
are requested in the user's actual currency instead of a silent USD
default; the built itinerary carries real Google Maps Directions travel
time between consecutive stops and is enriched with real nearby events;
place verification falls back to Tripadvisor when Google Maps has no
match.

**Stubbed or partial** (see "Known gaps" for the full list, this is the
short version): `reschedule_day` doesn't yet resolve *which* itinerary
day is affected, or check whether a postponement overruns the hotel's
checkout date. Two knowledge-graph functions exist but aren't called by
anything yet: `record_trip` and `similar_traveler_hotels`. The hotel
cache doesn't key on currency, so a cached hotel read under a different
currency than it was cached with will show the wrong number until
`refresh_hotel_price` corrects it at confirm time.

**Not started:** FastAPI wrapper, automated tests, a real day-planning
algorithm (current one is a greedy heuristic, flagged inline as the
first thing to replace).

## File map

```
state.py         TripState schema + TurnResponse (the eventual API contract)
config.py         env vars (loads .env here - the only place that needs to)
llm.py            every model call: OpenJev typed decisions + generation
services.py       reusable fetch/cache/rank capabilities (shared by planning + adjust)
graph.py          LangGraph wiring: entry routing + same-turn chaining
run_local.py      REPL test harness

graphdb/
  connection.py    Neo4j driver singleton
  schema.py        one-time constraint setup
  repository.py    all Cypher - the knowledge graph cache read/write layer

tools/
  serpapi_client.py  SerpApi wrapper - Maps, Hotels, Travel Explore, Flights
                       (+ autocomplete), Maps Directions, Events, Tripadvisor
  weather.py           OpenWeatherMap wrapper
  geo.py                haversine, centroid, day clustering (pure math, no
                          API calls - Directions enrichment lives in
                          services.py instead, to keep that contract intact)

nodes/
  router.py         coarse intent (calls llm.classify_intent)
  destination.py    pick or recommend a destination
  attractions.py     fetch + confirm attractions (initial planning)
  hotels.py           fetch + confirm a hotel (initial planning)
  itinerary.py         day-wise clustering into a plan
  adjust.py             every "the plan needs to change" case - pre-trip or mid-trip
  verify.py              grounds any place name against cache/live SerpApi
```

## Architectural decisions and why

Each entry: what was decided, what it avoids, what it costs.

### State design

**Decision:** `TripState` splits into collected inputs, working data, and
a `TurnResponse` sub-object every node must write before returning.
**Why:** `TurnResponse` (`reply`, `stage`, `ui_component`, `options`,
`requires_user_input`, `input_type`) is the same shape regardless of
which node ran. **Benefit:** wrapping this in an API later is "call
`graph.invoke`, return `state['turn_response']`" - not a redesign. The
frontend contract was decided before the frontend exists.
**Cost:** every node has to remember to populate it; nothing enforces
that at the type level beyond the TypedDict.

### Knowledge graph caching (Neo4j, graph-only, no hybrid store)

**Decision:** one shared graph (`City -[:HAS_ATTRACTION/HAS_HOTEL]->`)
plus a per-user graph (`User -[:TOOK_TRIP]-> Trip -[:VISITED/STAYED_AT]->`),
no relational or key-value layer alongside it. This was an explicit
user decision to keep the storage model singular rather than a hybrid.
**Why cache at all:** SerpApi's free tier is 250 searches/month at
50/hour - a single trip-planning session can cost 10-15+ calls, so a
team testing during a hackathon exhausts it during development, before
a judge ever sees it.
**Why Neo4j AuraDB specifically, not Kùzu (an embedded alternative with
no network dependency):** Kùzu's original maintainers archived it in
October 2025 after an acquisition; it now lives on in community forks.
AuraDB Free (50k nodes / 175k relationships, no card, no time limit) is
the more stable bet for something you need working on demo day.
**Known gotcha, not a bug:** AuraDB Free auto-pauses after 3 days of
inactivity, and has no backups. Resume it before a demo; export a JSON
snapshot periodically if the data matters.

**Decision:** staleness is a `WHERE` clause at read time
(`a.verified_at > datetime() - duration(...)`), not a TTL mechanism or
cron job. **Benefit:** Neo4j has no built-in expiry; this gets the same
effect for free, and the freshness window is visible right where the
data is read instead of hidden in a background job.

**Decision:** attraction *identity* (name/coords/category) is cached for
30 days; hotel *identity* is cached indefinitely but the *price* field
is only trusted for 1 day, and is re-fetched per-hotel (not per-city) the
moment a user is about to see a number (`serpapi_client.refresh_hotel_price`,
called from `hotels.confirm_hotel_node`). **Why:** hotel rates are
date-dependent - a cached rate for the wrong check-in dates isn't
stale-but-close, it's just wrong. This gets most of the cost savings
(skip the expensive discovery call) without showing a fabricated price.

**Decision:** `get_cached_attractions`/`get_cached_hotels` return a
*candidate set*, never a single "the" answer for a city. **Why:**
an earlier version of this idea risked always recommending the same
hotel for the same city regardless of who's asking. Personalization
(budget/vibe filtering) happens by ranking the cached set per request,
not by baking one answer into the cache.

**Decision:** `similar_traveler_hotels` and `record_trip` exist in
`repository.py` but nothing calls them yet (see Known gaps). They're
the payoff for the per-user graph - cross-user collaborative
recommendation ("travelers with a similar budget/vibe stayed here") -
and are cheap to wire in once there's enough trip history to make them
meaningful.

**Legal note, not fully resolved:** SerpApi's ToS bars reselling
*access to their Service*, but says nothing explicit about caching
results for your own app's use - separately, SerpApi scrapes Google
rather than using Google's official Places API, which has its own
caching rules (place IDs indefinitely, most fields time-limited); it's
genuinely unclear whether an equivalent restriction applies to scraped
data the same way. Low practical risk at hackathon scale. Framing
decision made as a result: this is described to judges/users as a
caching/personalization layer, not "our own database of the world's
attractions" - accurate either way, and avoids inviting a legal question
nobody here can fully answer.

### services.py - fetch logic decoupled from conversation stage

**Decision:** `fetch_attraction_candidates` / `fetch_hotel_candidates` /
`fetch_nearby` live in `services.py`, not inline in `nodes/attractions.py`
/ `nodes/hotels.py`. Every one takes an `exclude_place_ids` set.
**Why:** the original design had this logic hardwired into the initial
linear pipeline only. It broke the moment real adjustment cases showed
up ("I don't like this itinerary," "give me an extra day") because
those need the *same* search capability, just with different exclusions
and without re-running the whole conversation from scratch.
**Benefit:** `nodes/adjust.py`'s five handlers reuse these functions
instead of duplicating cache/rank logic, and "find something else"
provably can't re-suggest something already visited or already turned
down, because the exclusion is structural, not a prompt instruction.

### LangGraph flow control - conditional chaining, not a fixed pipeline

**Decision:** nodes chain automatically within one turn until a node
actually needs the user's input, then the graph ends (`after_destination`,
`after_confirm_attractions`, `after_confirm_hotel` each check
`conversation_stage` and either continue to the next node or `END`).
**Why:** a naive one-node-per-turn design would ask the user to
separately trigger "now fetch attractions" and "now fetch hotels" as
distinct messages, which is not how a conversation should feel.
**Benefit:** confirming attractions immediately triggers the hotel
search in the same turn; the user only gets stopped for things that are
actually decisions.

### Intent classification - two levels, not a stage-based split

**Decision:** routing (`llm.classify_intent`) is coarse - greeting / new
trip / `trip_adjustment` / continue_flow. A second classifier,
`llm.classify_adjustment_type`, only runs when intent is
`trip_adjustment`, and decides which of five things is meant: nearby
exploration, reschedule, extend, replace items, or change hotel.
**Why this replaced an earlier `modify_plan` vs `in_trip_query` split:**
that split routed on *when* (pre-trip vs mid-trip), but "the itinerary
isn't working because of rain" and "I want a different hotel" can
happen on either side of that line and read identically either way -
conversation_stage was the wrong signal.
**Why the adjustment classifier runs on `REASONING_MODEL` while routing
runs on `FAST_MODEL`:** telling "reschedule" apart from "replace" apart
from "extend" from a casually-worded message is a harder disambiguation
than routing a greeting. Model tier follows how hard the actual call is,
not a fixed default.
**Decision:** both classifiers see `llm._summarize_trip_context(state)`
- destination, budget, itinerary size, hotel, not just the raw message.
**Why:** "I don't like this" means something different depending on
whether a hotel is booked yet or an itinerary already exists; the
classifier needs that history to resolve it, not just the sentence in
isolation.

### Model selection inside llm.py

**Decision:** every decision that reduces to a fixed set of options
goes through OpenJev's typed-decision endpoint (`llm.decide`) - reads
probabilities straight off tokens, cannot go off-schema. Everything
open-ended (reply text, extracting a budget/city/date from free text)
goes through generation (`llm.generate`, and `llm.build_reply` /
`llm.extract_trip_slots` built on it).
**Why it matters enough to be a rule, not a preference:** an earlier
version of this codebase used keyword sets and regex for routing and
slot extraction. It looked like it worked and was actually hardcoded
guessing - it would misfire on any phrasing the author didn't happen to
anticipate. The typed-decision approach can't hallucinate an option
that wasn't offered; free text can't be avoided for open-ended values,
so it's isolated to exactly those cases via tool-calling JSON instead of
being trusted as plain text.
**Decision:** four tiers - `verdict-1.4` (fast, <=24 options),
`laya-1.0` (<=255 options, for larger candidate lists), `openjev-latest`
(full reasoning model, for genuinely hard disambiguation), and
`diffusiongemma-26b` (generation). **Benefit:** cost/latency scales with
how hard the decision actually is instead of every call hitting the
biggest model.

### Destination recommendations - real API, not a static list

**Decision:** when the user hasn't named a destination,
`services.fetch_destination_recommendations` calls SerpApi's
`google_travel_explore` engine (real names, coordinates, images, live
flight/hotel price estimates) instead of a hardcoded per-vibe list.
**Cost this introduced:** Explore requires a departure point
(`departure_id` - an airport code or Google location id), which nothing
in the flow previously collected. `destination_node` now asks for it
explicitly (`collecting_departure` stage) when missing, the same way it
already asks rather than guesses a destination - and resolves whatever
city text the user types via `google_flights_autocomplete`
(`serpapi_client.resolve_departure_id`) rather than requiring the user
to know their own airport code.
**Decision, not yet reconsidered:** this call is deliberately *not*
cached in the knowledge graph, unlike attractions/hotels - it's
departure-point- and price-dependent, so it's far less reusable across
different users than a city's attraction list is. Worth revisiting if
SerpApi usage from repeated departure/interest combos becomes a real
cost.
**`interest` selection is a reasoned OpenJev decision, not a static
lookup - but the option set itself is a hard external ceiling.** Google
Explore's `interest` parameter only recognizes six literal values
(`llm.EXPLORE_INTEREST_CRITERIA`); nothing wider is possible there, it's
the API's own constraint. What isn't capped is our own vibe taxonomy
(`llm.VIBE_CRITERIA`, 12 classes and growing, not the original 5) -
`llm.classify_explore_interest` reasons over that richer vibe plus the
raw message to pick the best-fitting one of the six, rather than a
rigid vibe->interest table. A "honeymoon" trip that mentions hiking can
land on Outdoors instead of always Beaches.

### Capturing fields SerpApi already returns, but we were discarding

**Decision:** `_normalize_place` now keeps `hours`, `operating_hours`,
and `extensions` - all present in the `google_maps` response we were
already paying for, previously dropped on the floor.
**Benefit:** fixes two things already listed as known gaps, at zero
extra API cost - `attractions.py`'s "best time to visit" no longer has
to be inferred from rating/review count when real hours exist, and
`extensions` (e.g. "Wheelchair accessible entrance") gives real
accessibility signal, one of the documented gaps from this project's
original competitor research.
**Decision, deliberately not done:** `extensions` is stored raw,
unfiltered by keyword. Pre-filtering it for "accessibility-looking"
entries would be exactly the hardcoded semantic guessing this project
moved away from (see Conventions below) - `llm.build_reply` already
gets the full list and can surface a relevant entry when it's actually
relevant to what's being asked.
**Bug caught during this pass, not shipped:** `operating_hours` is a
nested dict (`{"monday": "7 AM-6 PM", ...}`). Neo4j node properties can
only be primitives or arrays of primitives, not maps - writing this
straight through `write_attractions`'s `SET a += $props` would have
failed at query time. `graphdb/repository.py` now JSON-encodes it on
write and decodes on read (`_encode_for_graph`/`_decode_from_graph`);
every other field is unaffected.

### Currency - a real, live bug found while scoping a "future" feature

**Decision:** `search_hotels`, `refresh_hotel_price`, and
`search_explore_destinations` now take a `currency` parameter and
`hotels.py`/`destination.py`/`adjust.py` all pass `state["currency"]`
through, instead of the implicit USD default every one of them had.
**Why this wasn't just an enhancement:** `hotels.py`'s budget filter was
already comparing a USD-denominated `rate_per_night` against
`budget_total` in whatever `TripState["currency"]` holds (default
`"INR"`) - that comparison was already silently wrong for any non-USD
user, before any of this session's changes. Currency conversion had
been scoped as a nice-to-have Tier 1 item; it turned out to be a live
correctness bug once actually traced through.
**Known limitation, not fixed here:** the shared hotel cache
(`graphdb/repository.py`) stores one rate per hotel, not one per
currency. A hotel cached by an earlier USD search and read by a later
INR search shows a USD number under an INR label until
`refresh_hotel_price` corrects it for the one hotel the user actually
picks - same "estimate now, refreshed before you commit" pattern
already used for price staleness, just not yet extended to currency. A
real fix needs the cache keyed by `(city, currency)`, not attempted
here - see Planned next.

### Real travel time in the itinerary, without an O(n^2) API bill

**Decision:** `services.attach_travel_times` calls
`serpapi_client.get_directions` once per already-decided consecutive
stop pair, AFTER `tools.geo.cluster_by_day` has grouped and ordered the
day using free haversine math - not during the clustering search
itself. **Why:** calling Directions inside the nearest-neighbor search
would multiply calls by however many candidate comparisons the greedy
algorithm makes; attaching it once to the final decided order is a
fixed, small cost (one call per stop after the first, per day).
**Confidence flag:** SerpApi's own documentation didn't show a complete
worked JSON example for `google_maps_directions` the way it did for
Explore - request parameters are confirmed, `_normalize_route`'s
response parsing is a best-effort guess from blog terminology
("distance", "duration"), not a confirmed schema. Flagged in the module
docstring; verify against a live call before trusting it fully.

### Flights - an on-demand adjustment, not a pipeline stage

**Decision:** `_handle_find_flight` lives in `nodes/adjust.py`, reached
via a new `find_flight` entry in `llm.ADJUSTMENT_CRITERIA` - not a sixth
stage in the destination -> attractions -> hotel -> itinerary pipeline.
**Why:** flights weren't part of the original planning flow, and
`google_travel_explore` already covers the "give me a rough idea" case
during destination selection; this is specifically for when the user
wants to check or book an actual route. Lower blast radius than adding
a new required pipeline stage every trip has to pass through.
**Real routing bug caught and fixed while building this, not shipped:**
the handler's first draft asked for a departure city by setting
`conversation_stage = "collecting_departure"` - reusing the *destination
flow's* stage name. Since `graph.py`'s routing map already sends that
stage to `destination_node`, the user's next message (their departure
city) would have silently derailed into "great, let's find places to
visit there" instead of continuing the flight search. Fixed with two
dedicated stages (`collecting_flight_departure`, `collecting_flight_date`)
that `adjust_node` checks *before* re-running `classify_adjustment_type`
- the same reasoning `graph.py` already uses for why `collecting_hotel`
routes straight to `confirm_hotel_node` rather than re-deriving intent
from a bare selection: a bare city name or date isn't reliable
classification input on its own.
**`often_delayed` is a historical statistic, not live status** - flagged
in `state.py`'s `FlightOption` and worth repeating here: SerpApi has no
live flight-tracking engine. Don't let this field get presented to a
user as "your flight is delayed" - it means "flights on this route have
historically run 30+ minutes late," nothing about a specific flight
today.

### Events - itinerary enrichment only, not destination selection yet

**Decision:** `services.fetch_events` is called from `itinerary_node`
to mention real festivals/concerts in the generated reply; it is
*not* wired into `destination.py`'s recommendation logic.
**Why this is a partial win, said plainly:** "latest events in the
news" was in the very first description of this whole project, meant to
influence *which city* gets recommended. `google_travel_explore`
replaced most of that ask (real destinations, real prices) but doesn't
factor in events at all. `google_events` closes the itinerary-side half
of the original ask, not the destination-selection half - that's still
open, see Planned next.
**Confidence flag:** SerpApi's `htichips` filter supports
`date:today`/`date:tomorrow`, not an arbitrary date range - this can't
reliably filter to "only events during my exact trip dates" yet. It
returns whatever Google Events currently lists for the city, which
skews near-term. Good enough to mention "a festival is on" in a reply;
not good enough to guarantee it falls within the trip's specific dates.

### Tripadvisor - a fallback, not a cross-check, and never cached

**Decision:** `verify.py` tries Tripadvisor only when Google Maps has no
match for a name - not on every lookup. **Why:** Maps and Tripadvisor
agreeing that something exists isn't new information; the fallback
only earns its cost on the cases where Maps alone would have wrongly
said "unverifiable," so running it every time would double the cost of
every verification call for a benefit that mostly doesn't materialize.
**Decision:** a Tripadvisor-only hit is shown to the user for that turn
and never written into the shared knowledge graph. **Why:** Tripadvisor
Search's confirmed fields (title, description, rating, reviews,
location, thumbnail) don't reliably include coordinates. Caching a
coordinate-less "attraction" would silently break every downstream
function that assumes a confirmed attraction has `lat`/`lon` - hotel
proximity clustering (`centroid`) and day clustering
(`cluster_by_day`) both would. `verified_by` (`["google_maps"]` or
`["tripadvisor"]`) records which source actually confirmed a place,
separate from `source` (which tracks where the *data* came from - cache
vs. a fresh call).

### Grounding - verify.py

**Decision:** any place name proposed for the user (from an LLM, or a
follow-up search) is checked against the knowledge graph, then a live
SerpApi call, before being shown - never trusted as generated text.
**Why:** documented industry data (cited earlier in this project's
research phase) found roughly 1 in 6 users of AI travel tools hit a
hallucinated recommendation. This is the direct countermeasure.
**Why it's not an LLM call:** a model can't confirm a place exists,
only a real lookup can - this is deliberately grounding, not another
typed decision.

### Deferred on purpose

- **FastAPI layer:** not built yet, but `TurnResponse` was designed so
  that wrapping it later is thin (see `state.py`'s docstring and the
  README's API contract section). Building it now would have been
  premature relative to getting the graph logic right first.
- **Day-planning algorithm (`tools/geo.cluster_by_day`):** greedy
  nearest-neighbor, explicitly not a TSP/routing solver. Flagged inline
  as the first thing to upgrade if there's time left over - not worth
  hackathon time until the agent behavior itself is solid.
- **Automated tests:** none yet. Testing so far is the REPL
  (`run_local.py`) plus the smoke-test snippets in the setup instructions
  (one-liners hitting Neo4j/SerpApi/OpenWeather/OpenJev independently).

## Known gaps (things that look done but aren't)

- `nodes/adjust.py::_handle_reschedule_day` extracts *that* a
  postponement was mentioned (`postpone_days`) but not robustly *which*
  itinerary day it refers to, and doesn't check whether the new date
  overruns the confirmed hotel's checkout - flagged in its own
  docstring rather than guessed at.
- `graphdb/repository.py::record_trip` (writes a completed trip into the
  per-user graph) exists but no node calls it. Nothing currently
  populates the per-user graph, so vibe/budget history from past trips
  isn't actually available yet for a returning user.
- `graphdb/repository.py::similar_traveler_hotels` (cross-user
  collaborative ranking) exists but `nodes/hotels.py` doesn't call it.
  It also depends on `record_trip` being wired first - there's no trip
  history to draw on otherwise.
- SerpApi field names in `tools/serpapi_client.py` (`_normalize_place`,
  `_normalize_hotel`) were checked against SerpApi's documented examples,
  not a live sandbox call - re-verify before depending on this for real
  bookings, response shapes can drift by place/property type.
- `llm.py`'s OpenJev calls (`model=`, `think=` kwargs on
  `TypeSafeClient.system_one`) were verified against OpenJev's wire-API
  docs, not the `typesafe_sdk` Python source directly - the HTTP shape
  is guaranteed by the README, the SDK's exact kwargs aren't confirmed
  beyond the one example it shows.
- The hotel cache doesn't key on currency (see "Currency" decision
  above) - reading a hotel cached in a different currency than
  requested will show a wrong number until the specific hotel a user
  picks gets its price refreshed at confirm time.
- `tools/serpapi_client.py::_normalize_route` (Google Maps Directions)
  is the least-confirmed normalizer in the file - request parameters
  are solid, response field names are a best-effort guess, not a
  worked example. Verify before relying on real travel-time numbers.
- `google_events` enriches the itinerary's reply but doesn't influence
  which destination gets recommended, and can't reliably filter to a
  trip's exact date range (see "Events" decision above) - both are
  real, current limits, not oversights.
- `_handle_find_flight`'s "couldn't recognize that city" retry path
  doesn't set a dedicated stage the way the departure/date prompts
  do - if `destination_city` itself somehow fails airport resolution
  (rare, since it's normally an already-confirmed trip destination),
  the retry relies on `classify_adjustment_type` re-deriving
  `find_flight` from context rather than a deterministic stage
  shortcut. Lower risk than the bug that WAS fixed (a bare city name
  with no other signal), but not airtight.

## Planned next (roughly in priority order)

1. Wire `record_trip` in at the point a trip is considered done (end of
   `itinerary_node`, or a future "trip complete" signal) so the
   per-user graph actually starts accumulating history.
2. Wire `similar_traveler_hotels` into `hotels.hotels_node`'s ranking as
   a boost once #1 has produced enough data to make it meaningful.
3. Finish `_handle_reschedule_day`: resolve which day from the message
   (likely another `llm.decide` choice question over the itinerary's
   days), and check/refresh the hotel booking if the new date range
   extends past checkout.
4. **Partially done, worth finishing:** the day-clustering heuristic
   still groups/orders stops by haversine distance alone;
   `services.attach_travel_times` now attaches a real Directions-based
   travel time to the *result* of that decision, but doesn't feed into
   the decision itself. A stop pair that looks close on a straight line
   but has a slow real route (a river crossing, a highway with no
   direct link) still gets clustered together and only shown to be slow
   after the fact. Next step is having `cluster_by_day` weigh candidates
   by something closer to real travel time, not just re-displaying it.
5. Key the hotel cache by `(city, currency)`, not just `city` - see the
   "Currency" decision above for why the current single-currency-per-hotel
   cache silently shows the wrong number to a different-currency reader.
6. Wire `google_events` into `destination.py`'s recommendation logic,
   not just `itinerary_node`'s reply - the destination-selection half of
   "latest events in the news" (from this project's very first
   description) is still open; only the itinerary-enrichment half got
   built.
7. Give `_handle_find_flight`'s destination-resolution-failure retry the
   same deterministic-stage treatment the departure/date prompts got,
   for full consistency (see Known gaps).
8. Wire `record_trip` in at the point a trip is considered done (end of
   `itinerary_node`, or a future "trip complete" signal) so the
   per-user graph actually starts accumulating history.
9. Wire `similar_traveler_hotels` into `hotels.hotels_node`'s ranking as
   a boost once #8 has produced enough data to make it meaningful.
10. Finish `_handle_reschedule_day`: resolve which day from the message
    (likely another `llm.decide` choice question over the itinerary's
    days), and check/refresh the hotel booking if the new date range
    extends past checkout.
11. FastAPI wrapper: `{session_id, message}` in, `state['turn_response']`
    out, with session state persisted (a dict is enough to start;
    consider Redis if this needs to survive a process restart).
12. An automated test suite - mock the SerpApi/Neo4j/OpenJev boundaries so
    graph logic can be tested without burning API quota per run.
13. Tier 3 from the SerpApi feature review, deferred again this round:
    real photo galleries (`google_maps_photos`/hotel photos) fetched
    only for what the user actually confirms, not every candidate shown.
14. Feature ideas discussed but not built: visa/entry-requirement
    checking, accessibility/dietary-aware filtering beyond the raw
    `extensions` list now captured, a carbon/sustainability score per
    itinerary option - all validated as gaps in comparable products,
    none started.

## Conventions - read before adding anything

- **A decision with a fixed, enumerable set of options is a typed
  decision (`llm.decide`), never a keyword/regex/if-chain match.** If
  you catch yourself writing `if "x" in message.lower()` for anything
  semantic, stop - that's the exact pattern this codebase moved away
  from and it degrades silently on phrasing nobody anticipated.
- **An open-ended value (a number, a name, a date) is extracted via
  generation + tool calling (`llm.generate`/`llm.extract_trip_slots`),
  never regex.** Typed decisions can't represent unbounded values;
  don't force one to.
- **Every reply shown to the user goes through `llm.build_reply` with
  real fetched data as `context`**, not an f-string template. The
  instruction told to the model explicitly forbids inventing facts
  beyond what's in `context` - keep that guardrail if you change the
  prompt.
- **A capability that might be needed outside its original node belongs
  in `services.py`, not inline in that node.** `nodes/adjust.py` exists
  because the alternative was duplicating `attractions.py`'s fetch logic
  a second time with different exclusions.
- **Anything that confirms a place is real is a grounded lookup
  (cache or live SerpApi), never trusted from model output** - see
  `nodes/verify.py`'s docstring for why this is a deliberate exception
  to "ask the model."

## Setup / run / test

Full instructions are in `README.md` and were walked through
step-by-step earlier in this project's history: virtualenv + `pip
install -r requirements.txt`, five API keys into `.env` (Neo4j AuraDB,
SerpApi, OpenWeatherMap, OpenJev/Codiv), `python -m graphdb.schema`
once, smoke-test each external service independently, then
`python run_local.py` for a full conversation.