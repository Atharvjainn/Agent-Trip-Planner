"""
Single entry point for every model call in this codebase. Two different
kinds of calls live here, matched to what OpenJev actually is:

1. TYPED DECISIONS (`decide`) - yes/no, a choice among a fixed set, or a
   score. Read straight off token probabilities, cannot go off-schema.
2. FREE-FORM GENERATION (`generate`) - reply text, or pulling an
   open-ended value (a budget number, a date, a city name) out of a
   sentence via tool-calling JSON.

MODEL TIERS - by task complexity, not one model for everything:

  FAST_MODEL       verdict-1.4    <=24 options, cheapest/fastest.
                    Router intent, nearby-category, single yes/no checks.
  STANDARD_MODEL   laya-1.0       <=255 options. Candidate lists that
                    might run past verdict's 24-option cap.
  REASONING_MODEL  openjev-latest  Used when a decision needs real
                    disambiguation, not pattern matching - specifically
                    classify_adjustment_type below: "reschedule a day"
                    vs "replace what's planned" vs "extend the trip" is
                    a genuinely harder call than routing a greeting, and
                    gets the model that can actually reason about it.
  GENERATION_MODEL gemini-2.5-flash - free text + tool-call extraction.
                    Reached via Gemini's OpenAI-compatible endpoint, so
                    `generate()` below is unchanged; only the client's
                    base_url/api_key and the model string differ from the
                    three decision tiers above, which stay on OpenJev.

TWO-LEVEL INTENT CLASSIFICATION, and why: a flat "modify_plan vs
in_trip_query" split (the first version of this file) doesn't match how
these requests actually show up - "the itinerary isn't working because
of rain" and "I want to change my hotel" can happen before or during the
trip, and look identical either way. So routing only asks the coarse
question (new trip / adjust the existing plan / greeting / continuing
something already in progress); classify_adjustment_type then asks the
harder question - *which kind* of adjustment - using the full trip
context, not conversation_stage, as the signal.
"""
from __future__ import annotations
import json
from datetime import date
from typesafe_sdk import TypeSafeClient
from openai import OpenAI

import config

FAST_MODEL = "verdict-1.4"
STANDARD_MODEL = "laya-1.0"
REASONING_MODEL = "openjev-latest"
GENERATION_MODEL = "gemini-2.5-flash"

_decision_client = TypeSafeClient(
    base_url=config.TYPESAFE_BASE_URL, api_key=config.TYPESAFE_API_KEY
)
# Gemini via its OpenAI-compatible endpoint - same `openai.OpenAI` client
# class as before, just pointed at Google instead of OpenJev, so generate()
# and everything built on it (build_reply, extract_trip_slots) needs no
# other changes.
_generation_client = OpenAI(
    base_url=config.GEMINI_BASE_URL, api_key=config.GEMINI_API_KEY
)


# ---------------------------------------------------------------- core --

def decide(state: str, questions: dict, model: str = FAST_MODEL, think: int | None = None) -> dict:
    """
    Thin wrapper over OpenJev's typed-decision endpoint. Returns
    {"values": {qid: value}, "confidences": {qid: 0-1}}.
    """
    kwargs = {"model": model}
    if think:
        kwargs["think"] = think
    result = _decision_client.system_one(state, questions, **kwargs)

    values, confidences = {}, {}
    for qid, spec in questions.items():
        if spec["type"] == "noul":
            p_yes = result.nouls[qid].noul
            values[qid] = p_yes >= 0.5
            confidences[qid] = p_yes if values[qid] else 1 - p_yes
        elif spec["type"] == "choice":
            values[qid] = result.choices[qid].choice
            confidences[qid] = result.choices[qid].confidence
        elif spec["type"] == "score":
            values[qid] = result.scores[qid].score
            confidences[qid] = result.scores[qid].confidence
        else:
            raise ValueError(f"Unknown OpenJev question type: {spec['type']}")
    return {"values": values, "confidences": confidences}


def generate(messages: list, model: str = GENERATION_MODEL, tools: list | None = None,
             max_tokens: int = 512):
    """Free-form generation / tool-calling extraction. Returns the raw
    message object (.content and/or .tool_calls)."""
    kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
    response = _generation_client.chat.completions.create(**kwargs)
    return response.choices[0].message


# ------------------------------------------------------- history context --

def _summarize_trip_context(state: dict) -> str:
    """
    Builds the "previous history" every classification below reasons
    over, instead of just the raw last message. This is what lets
    classify_intent and classify_adjustment_type tell "I'm delayed a day"
    apart from "I don't like this hotel" - both need to know what's
    already been decided (destination, itinerary, hotel), not just parse
    the sentence in isolation.
    """
    parts = [f"Conversation stage: {state.get('conversation_stage')}"]
    if state.get("destination_city"):
        parts.append(f"Destination: {state['destination_city']}")
    if state.get("vibe"):
        parts.append(f"Trip vibe: {state['vibe']}")
    if state.get("budget_total"):
        parts.append(f"Budget: {state['budget_total']} {state.get('currency', '')}")
    if state.get("duration_days"):
        parts.append(f"Planned duration: {state['duration_days']} days")
    if state.get("itinerary"):
        parts.append(f"Itinerary so far: {len(state['itinerary'])} day(s) already planned")
    if state.get("confirmed_hotel"):
        parts.append(f"Hotel booked: {state['confirmed_hotel'].get('name')}")
    parts.append(f"Latest message: {state.get('last_user_message', '')}")
    return "\n".join(parts)


# ------------------------------------------------------- routing intent --

INTENT_CRITERIA = {
    "greeting": "the user is just saying hello, with no travel request",
    "new_trip": "the user wants to start planning a brand new trip",
    "trip_adjustment": "something about a trip already being planned or already underway needs to change",
    "continue_flow": "the user is answering something the assistant just asked - a selection, a confirmation, a detail",
}


def classify_intent(state: dict) -> str:
    """Coarse routing - a small fixed set, fast tier is enough. Takes
    the whole state (not just the message) so the classifier sees the
    same trip history classify_adjustment_type does."""
    ctx = _summarize_trip_context(state)
    result = decide(
        ctx,
        {"intent": {"type": "choice", "instructions": "What is the user trying to do?",
                    "criteria": INTENT_CRITERIA}},
        model=FAST_MODEL,
    )
    return result["values"]["intent"]


# ---------------------------------------------------- adjustment intent --

ADJUSTMENT_CRITERIA = {
    "nearby_exploration": "the user has some free time right now and wants something nearby to do",
    "reschedule_day": "weather, a delay, or a schedule change means a planned day needs to move to a "
                       "different date, keeping the same places",
    "extend_trip": "the trip is now longer than planned (e.g. departure delayed) and the extra day(s) need activities",
    "replace_itinerary_items": "the user dislikes, or the weather ruins, currently planned places and wants "
                                "different ones instead",
    "change_hotel": "the user wants a different hotel - budget changed, or they're unhappy with the current choice",
    "find_flight": "the user wants to search for, check, or book an actual flight",
}


def classify_adjustment_type(state: dict) -> str:
    """Which kind of change is needed. Deliberately on REASONING_MODEL,
    not FAST_MODEL - telling "reschedule" apart from "replace" apart
    from "extend" from a casually-worded message is a harder call than
    top-level routing, and is exactly the case the README flags as
    needing real disambiguation rather than pattern matching."""
    ctx = _summarize_trip_context(state)
    result = decide(
        ctx,
        {"adjustment": {"type": "choice", "instructions": "What kind of change to the trip does the user need?",
                        "criteria": ADJUSTMENT_CRITERIA}},
        model=REASONING_MODEL,
    )
    return result["values"]["adjustment"]


NEARBY_CATEGORY_CRITERIA = {
    "nature": "outdoors, parks, natural scenery - only sensible in good weather",
    "food": "eating, cheap food, street food",
    "culture": "museums, galleries, historical sites - a good indoor option in bad weather",
    "shopping": "markets, shopping",
}


def classify_nearby_category(message: str, weather: dict) -> str:
    """Weather goes INTO the decision context here, rather than being
    applied as a manual override after the fact - the model sees
    'raining, 18C' alongside the message and picks an appropriate
    category itself, instead of a hardcoded nature->culture swap that
    only covered one case."""
    state = f"Weather right now: {weather['description']}, {weather['temp_c']}C\nUser message: {message}"
    result = decide(
        state,
        {"category": {"type": "choice",
                      "instructions": "What kind of nearby experience is the user asking for, given the weather?",
                      "criteria": NEARBY_CATEGORY_CRITERIA}},
        model=FAST_MODEL,
    )
    return result["values"]["category"]


# ------------------------------------------------- selecting from options --

def select_option(last_message: str, candidates: list, multi: bool = False) -> list:
    """Single-select asks one `choice` question over the candidate set
    (plus a "none" escape hatch); multi-select asks one `noul` per
    candidate, batched into one call. Model tier follows option count."""
    if not candidates:
        return []
    model = FAST_MODEL if len(candidates) <= 24 else STANDARD_MODEL
    labels = {str(i): (c.get("name") or str(c)) for i, c in enumerate(candidates)}
    state = f"Presented options: {labels}\nUser message: {last_message}"

    if not multi:
        criteria = {**labels, "none": "none of the above / unclear from the message"}
        result = decide(
            state,
            {"pick": {"type": "choice", "instructions": "Which option is the user selecting?",
                      "criteria": criteria}},
            model=model,
        )
        picked = result["values"]["pick"]
        return [candidates[int(picked)]] if picked != "none" else []

    questions = {
        f"pick_{i}": {"type": "noul",
                      "instructions": f"Did the user select option {i} ('{labels[str(i)]}')?"}
        for i in range(len(candidates))
    }
    result = decide(state, questions, model=model)
    return [c for i, c in enumerate(candidates) if result["values"][f"pick_{i}"]]


# ------------------------------------------------- open-ended extraction --

VIBE_CRITERIA = {
    "family": "traveling with parents, children or extended family",
    "honeymoon": "a romantic trip for a couple",
    "friends": "a group trip with friends",
    "religious": "a pilgrimage or spiritual trip",
    "solo": "traveling alone",
    "adventure_outdoor": "trekking, adventure sports, adrenaline, nature exploration",
    "luxury_relaxation": "pampering, resorts, indulgence, minimal activity",
    "budget_backpacking": "cost-conscious, hostel-style, maximizing experiences per rupee",
    "wellness_retreat": "yoga, spa, detox, a mental-health or reset-focused trip",
    "cultural_heritage": "museums, history, architecture, heritage sites",
    "culinary": "a food-focused trip - street food, cooking, dining",
    "nightlife_party": "clubs, bars, festivals, the party scene",
}
# 12 classes deliberately, not 5 - this is our own taxonomy, so it's not
# bound by anything external. Still comfortably under FAST_MODEL's
# 24-option cap. Add more here if a real conversation keeps landing on
# "unspecified" for something that clearly has a theme.


def classify_vibe(message: str) -> str | None:
    result = decide(
        message,
        {"vibe": {"type": "choice", "instructions": "What kind of trip is this, if mentioned?",
                  "criteria": {**VIBE_CRITERIA, "unspecified": "not mentioned in the message"}}},
        model=FAST_MODEL,
    )
    vibe = result["values"]["vibe"]
    return None if vibe == "unspecified" else vibe


# Google Travel Explore's `interest` parameter only recognizes these six
# values - a hard ceiling from the API itself, not something we can
# widen. What CAN be reasoned about is *which* of the six fits best,
# given the full message and our own (much richer) vibe classification
# above - not a rigid vibe->interest lookup table. A "honeymoon" trip
# that mentions hiking should be able to land on Outdoors instead of
# always Beaches, for example.
EXPLORE_INTEREST_CRITERIA = {
    "0": "broadly popular destinations, no specific theme - the safe default when nothing else clearly fits",
    "/g/11bc58l13w": "outdoor activity - trekking, adventure sports, nature exploration, adrenaline",
    "/m/0b3yr": "beaches and coastal relaxation",
    "/m/09cmq": "museums and indoor cultural attractions",
    "/m/03g3w": "history and heritage sites",
    "/m/071k0": "skiing and winter sports",
}


def classify_explore_interest(message: str, vibe: str | None) -> str:
    state = f"Trip vibe (our own classification): {vibe or 'unspecified'}\nUser message: {message}"
    result = decide(
        state,
        {"interest": {"type": "choice",
                      "instructions": "Which travel interest category best fits this trip?",
                      "criteria": EXPLORE_INTEREST_CRITERIA}},
        model=FAST_MODEL,
    )
    return result["values"]["interest"]


_TRIP_SLOTS_TOOL = {
    "type": "function",
    "function": {
        "name": "extracted_slots",
        "description": "Trip planning details mentioned in the user's message. Omit any field not mentioned.",
        "parameters": {
            "type": "object",
            "properties": {
                "destination_city": {"type": "string"},
                "departure_city": {"type": "string",
                                    "description": "where the user is starting the trip from, if mentioned"},
                "budget_total": {"type": "number"},
                "duration_days": {"type": "integer"},
                "free_minutes": {"type": "integer",
                                  "description": "minutes of free time mentioned for a nearby-exploration question"},
                "postpone_days": {"type": "integer",
                                   "description": "how many days a planned day should be pushed back, if mentioned"},
                "extend_days": {"type": "integer",
                                 "description": "how many extra days the trip is being extended by, if mentioned"},
                "outbound_date": {"type": "string",
                                   "description": "ISO YYYY-MM-DD departure date, if mentioned - resolve "
                                                   "relative dates ('next Friday', 'in 10 days') against "
                                                   "today's date, given in the system message"},
                "return_date": {"type": "string",
                                 "description": "ISO YYYY-MM-DD return date, if mentioned"},
            },
        },
    },
}


def extract_trip_slots(message: str) -> dict:
    """Open-ended values (any city, any number of days, any budget, any
    date) - not a fixed option set, so this is generation with a tool
    call rather than a typed decision. Today's date is given explicitly
    so a relative phrase like 'next Friday' or 'in 10 days' (relevant
    to outbound_date/return_date) resolves against something real
    rather than the model's own notion of "now". Returns {} if nothing
    was extracted."""
    today = date.today().isoformat()
    response = generate(
        [{"role": "system", "content": f"Today's date is {today}. Extract trip planning details "
                                        "from the user's message, resolving any relative dates "
                                        "against today's date. Call extracted_slots with only the "
                                        "fields actually mentioned."},
         {"role": "user", "content": message}],
        tools=[_TRIP_SLOTS_TOOL],
        max_tokens=256,
    )
    if getattr(response, "tool_calls", None):
        return json.loads(response.tool_calls[0].function.arguments)
    return {}


def build_reply(context: dict, instruction: str, model: str = GENERATION_MODEL) -> str:
    """The conversational text shown to the user, for every node.
    Explicitly told to use only the facts given in context - the actual
    data always comes from SerpApi/the knowledge graph, never invented."""
    response = generate(
        [{"role": "system", "content": "You are a concise, friendly trip-planning assistant. "
                                        "Use only the facts given in context - never invent a place, "
                                        "price, rating, or detail that isn't there. Two or three "
                                        "sentences, no more."},
         {"role": "user", "content": f"Context: {json.dumps(context, default=str)}\n\nInstruction: {instruction}"}],
        model=model,
        max_tokens=200,
    )
    return response.content