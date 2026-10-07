from __future__ import annotations
import os
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
  GENERATION_MODEL gemini-3.1-flash-lite - free text + tool-call extraction.
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
import json
import logging
from datetime import date
from typesafe_sdk import TypeSafeClient
from openai import OpenAI

import config

logger = logging.getLogger("openjev")

FAST_MODEL = "verdict-1.4"
STANDARD_MODEL = "laya-1.0"
REASONING_MODEL = "openjev-latest"
GENERATION_MODEL = "gemini-3.8-flash"

_decision_client = TypeSafeClient(
    base_url=config.TYPESAFE_BASE_URL, api_key=config.TYPESAFE_API_KEY
)
# Gemini via its OpenAI-compatible endpoint - same `openai.OpenAI` client
# class as before, just pointed at Google instead of OpenJev, so generate()
# and everything built on it (build_reply, extract_trip_slots) needs no
# other changes.
_generation_client = OpenAI(
    base_url=config.GEMINI_BASE_URL, api_key=config.GEMINI_API_KEY, max_retries=0
)


# ---------------------------------------------------------------- core --

def _decide_fallback(state: str, questions: dict) -> dict:
    """Fallback path using the generative LLM when OpenJev is unavailable
    or returns confidence below the configured threshold.
    Never logs API keys or user secrets."""
    lines = [f"Context: {state}", "", "Answer these classification questions as JSON:"]
    for qid, spec in questions.items():
        q_type = spec["type"]
        instr = spec.get("instructions", "")
        if q_type == "choice":
            opts = ", ".join(spec["criteria"].keys())
            lines.append(f"- {qid}: Pick one of [{opts}]. {instr}")
        elif q_type == "noul":
            lines.append(f"- {qid}: true or false. {instr}")
        elif q_type == "score":
            lines.append(f"- {qid}: integer rating. {instr}")
    lines.append("")
    lines.append("Return ONLY a JSON object mapping each key to its value.")
    prompt = "\n".join(lines)

    try:
        response = generate([{"role": "user", "content": prompt}], max_tokens=150)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        parsed = json.loads(content.strip())
        if isinstance(parsed, dict):
            values = {}
            for qid, spec in questions.items():
                if qid in parsed:
                    values[qid] = parsed[qid]
                else:
                    found = False
                    for alt in (qid.lower(), "choice", "selection", "answer", "option", "picked"):
                        if alt in parsed:
                            values[qid] = parsed[alt]
                            found = True
                            break
                    if not found:
                        q_type = spec["type"]
                        if q_type == "choice":
                            values[qid] = "none"
                        elif q_type == "noul":
                            values[qid] = False
                        else:
                            values[qid] = 0
            return {"values": values, "confidences": {k: 1.0 for k in values}}
        return {"values": parsed, "confidences": {k: 1.0 for k in parsed}}
    except Exception as exc:
        logger.warning("Fallback execution failed: %s", type(exc).__name__)
        # Safe defaults so callers never receive a KeyError
        values, confidences = {}, {}
        for qid, spec in questions.items():
            q_type = spec["type"]
            fb = spec.get("fallback_default")
            if q_type == "choice":
                if fb is not None:
                    values[qid] = fb
                else:
                    keys = list(spec["criteria"].keys())
                    values[qid] = keys[0] if keys else "none"
            elif q_type == "noul":
                values[qid] = fb if fb is not None else False
            else:  # score
                values[qid] = fb if fb is not None else 0
            confidences[qid] = 0.0
        return {"values": values, "confidences": confidences}


def decide(state: str, questions: dict, model: str = FAST_MODEL, think: int | None = None) -> dict:
    """Wrapper over OpenJev's typed-decision endpoint.

    Returns {"values": {qid: value}, "confidences": {qid: 0-1}}.

    Behaviour:
    - Calls OpenJev (TypeSafeClient.system_one).
    - If *any* answer confidence < config.OPENJEV_CONFIDENCE_THRESHOLD, the
      whole batch is re-decided via the generative fallback path.
    - If OpenJev raises *any* exception (network error, auth, rate-limit…),
      falls back gracefully without surfacing an error to callers.
    - Logs decision outcomes at INFO; logs fallback triggers at WARNING.
      API keys and user trip details are never logged.
    """
    kwargs = {"model": model}
    if think:
        kwargs["think"] = think

    try:
        import time
        result = None
        for attempt in range(5):
            try:
                result = _decision_client.system_one(state, questions, **kwargs)
                break
            except Exception as exc:
                err_str = str(exc)
                if ("429" in err_str or "529" in err_str or "RateLimit" in err_str or "RESOURCE_EXHAUSTED" in err_str or "unavailable" in err_str) and attempt < 3:
                    sleep_sec = 5 * (attempt + 1)
                    logger.warning("OpenJev transient error (attempt %d/4), sleeping %ds: %s", attempt + 1, sleep_sec, err_str[:100])
                    time.sleep(sleep_sec)
                    continue
                logger.warning("OpenJev client failed with %s: %s. Falling back to generative LLM.", type(exc).__name__, err_str[:150])
                return _decide_fallback(state, questions)

        values: dict = {}
        confidences: dict = {}
        low_confidence = False
        threshold = config.OPENJEV_CONFIDENCE_THRESHOLD

        for qid, spec in questions.items():
            q_type = spec["type"]
            answer = result.answers[qid]

            if q_type == "noul":
                p_yes = answer.noul
                values[qid] = p_yes >= 0.5
                conf = p_yes if values[qid] else 1.0 - p_yes

            elif q_type == "choice":
                values[qid] = answer.choice
                conf = answer.confidence

            elif q_type == "score":
                values[qid] = answer.score
                conf = answer.confidence

            else:
                raise ValueError(f"Unknown OpenJev question type: {q_type}")

            confidences[qid] = conf
            if conf < threshold:
                low_confidence = True

        if low_confidence:
            logger.info(
                "OpenJev confidence below threshold %.2f for one or more questions "
                "(model=%s). Triggering generative fallback.",
                threshold,
                model,
            )
            return _decide_fallback(state, questions)

        logger.info(
            "OpenJev decision succeeded [model=%s, questions=%s]",
            model,
            list(questions.keys()),
        )
        return {"values": values, "confidences": confidences}

    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise


def generate(messages: list, model: str = GENERATION_MODEL, tools: list | None = None,
             max_tokens: int = 512):
    """Free-form generation / tool-calling extraction. Returns the raw
    message object (.content and/or .tool_calls)."""
    import time
    kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
    for attempt in range(2):
        try:
            response = _generation_client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as exc:
            err_str = str(exc)
            if ("429" in err_str or "RateLimit" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < 1:
                sleep_sec = 2 * (attempt + 1)
                logger.warning("Rate limit hit in generate() (attempt %d/2), sleeping %ds: %s", attempt + 1, sleep_sec, err_str[:100])
                time.sleep(sleep_sec)
                continue
            groq_key = os.getenv("GROQ_API_KEY")
            if groq_key:
                try:
                    from openai import OpenAI
                    groq_client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_key)
                    groq_kwargs = dict(kwargs)
                    groq_kwargs["model"] = "qwen/qwen3.8-27b"
                    res = groq_client.chat.completions.create(**groq_kwargs)
                    logger.info("Groq fallback successful for generate()")
                    return res.choices[0].message
                except Exception as groq_exc:
                    logger.warning("Groq fallback failed: %s", groq_exc)
            raise


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
    stage = state.get("conversation_stage", "start")

    fallback_intent = "continue_flow"
    if stage == "start":
        msg_lower = (state.get("last_user_message") or "").lower()
        keywords = ("trip", "plan", "visit", "travel", "vacation", "holiday", "book", "flight", "hotel", "days", "day", "destination", "itinerary", "stay", "resort", "explore")
        if any(kw in msg_lower for kw in keywords):
            fallback_intent = "new_trip"
        else:
            fallback_intent = "greeting"

    result = decide(
        ctx,
        {
            "intent": {
                "type": "choice",
                "instructions": "What is the user trying to do?",
                "criteria": INTENT_CRITERIA,
                "fallback_default": fallback_intent,
            }
        },
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
        {
            "adjustment": {
                "type": "choice",
                "instructions": "What kind of change to the trip does the user need?",
                "criteria": ADJUSTMENT_CRITERIA,
                "fallback_default": "replace_itinerary_items",
            }
        },
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
        {
            "category": {
                "type": "choice",
                "instructions": "What kind of nearby experience is the user asking for, given the weather?",
                "criteria": NEARBY_CATEGORY_CRITERIA,
                "fallback_default": "food",
            }
        },
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
            {
                "pick": {
                    "type": "choice",
                    "instructions": "Which option is the user selecting?",
                    "criteria": criteria,
                    "fallback_default": "none",
                }
            },
            model=model,
        )
        logger.info("select_option raw decision result: %s", result)
        values = result.get("values", {}) if isinstance(result, dict) else {}
        picked = values.get("pick")
        if picked is None:
            for alt in ("choice", "selection", "answer", "option", "picked"):
                if alt in values:
                    picked = values[alt]
                    break

        if picked is not None:
            picked_str = str(picked).strip()
            if picked_str != "none" and picked_str in labels:
                try:
                    idx = int(picked_str)
                    if 0 <= idx < len(candidates):
                        return [candidates[idx]]
                except (ValueError, TypeError):
                    pass
        return []

    questions = {
        f"pick_{i}": {"type": "noul",
                      "instructions": f"Did the user select option {i} ('{labels[str(i)]}')?"}
        for i in range(len(candidates))
    }
    result = decide(state, questions, model=model)
    values = result.get("values", {}) if isinstance(result, dict) else {}
    return [c for i, c in enumerate(candidates) if values.get(f"pick_{i}", False)]


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
        {
            "vibe": {
                "type": "choice",
                "instructions": "What kind of trip is this, if mentioned?",
                "criteria": {**VIBE_CRITERIA, "unspecified": "not mentioned in the message"},
                "fallback_default": "unspecified",
            }
        },
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
        {
            "interest": {
                "type": "choice",
                "instructions": "Which travel interest category best fits this trip?",
                "criteria": EXPLORE_INTEREST_CRITERIA,
                "fallback_default": "0",
            }
        },
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
    try:
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
    except Exception as exc:
        logger.warning("build_reply LLM call failed: %s. Using fallback reply.", exc)
        dest = context.get("destination_city")
        if dest:
            return f"Got it! Planning your trip to {dest}. Let's work out the budget next."
        return "I am processing your trip request. Let's continue planning!"