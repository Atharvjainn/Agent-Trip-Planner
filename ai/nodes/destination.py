"""
Handles two situations:
1) the user already named (or just named) a destination -> move on
2) they didn't -> recommend real destinations via
   services.fetch_destination_recommendations (Google Travel Explore),
   never a static list.

Google Travel Explore requires a departure point - that's a real
constraint of the underlying API, not a design choice - so if we don't
have one yet, this node asks for it explicitly rather than guessing a
default city, the same way it already asks rather than guessing a
destination.

Slot extraction, vibe classification, and matching a follow-up message
against previously shown options all go through llm.py - nothing here
pattern-matches the user's text itself.
"""
import logging
import re
import llm
import services
from state import TripState

logger = logging.getLogger(__name__)


def _parse_budget_number(text: str) -> float | None:
    """Parse numeric budget, supporting Indian terms (lakh, crore, k) and standard numbers.
    Never parses duration (days/nights) or traveler counts (people/persons) as budget."""
    if not text:
        return None

    # First check Indian terms like "2 lakhs", "1.5 crore", "50k"
    m_term = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr|k)\b",
        text,
        re.IGNORECASE,
    )
    if m_term:
        val = float(m_term.group(1))
        unit = m_term.group(2).lower()
        if unit in ("lakh", "lakhs", "lac", "lacs"):
            return val * 100000.0
        elif unit in ("crore", "crores", "cr"):
            return val * 10000000.0
        elif unit == "k":
            return val * 1000.0

    # Strip phrases that indicate duration, night count, traveler count, time
    clean_text = re.sub(
        r"\b\d+\s*[- ]?(?:days?|nights?|people|persons?|travelers?|travellers?|pax|weeks?|months?|hours?|hrs?|mins?|minutes?)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Check for budget with explicit currency or budget keyword
    # e.g. "budget 30000", "30000 INR", "INR 30000", "Rs 30000", "₹30000", "$500"
    m_budget_explicit = re.search(
        r"(?:budget(?:\s*(?:of|is|:))?\s*|₹|\$|rs\.?\s*|inr\s*)\s*(\d[\d,]*)|(\d[\d,]*)\s*(?:inr|rs\.?|rupees?|usd|eur|gbp|\$|₹)",
        clean_text,
        re.IGNORECASE,
    )
    if m_budget_explicit:
        raw_num = m_budget_explicit.group(1) or m_budget_explicit.group(2)
        try:
            return float(raw_num.replace(",", ""))
        except ValueError:
            pass

    # If no explicit budget keywords, check for a number in clean_text
    # but ONLY if the number is plausible for a budget (>= 500) or clean_text is just a number
    m_num = re.search(r"\b(\d[\d,]*)\b", clean_text)
    if m_num:
        try:
            val = float(m_num.group(1).replace(",", ""))
            if val >= 500 or clean_text.strip() == m_num.group(1):
                return val
        except ValueError:
            pass
    return None


def _regex_extract_slots(text: str) -> dict:
    """Lightweight regex fallback extractor when LLM provider is unavailable."""
    slots = {}
    if not text:
        return slots

    budget_val = _parse_budget_number(text)
    if budget_val is not None:
        slots["budget_total"] = budget_val

    # Detect currency if explicitly stated
    m_curr = re.search(r"\b(INR|USD|EUR|GBP|JPY|AUD|CAD|rupees?|rs\.?)\b", text, re.IGNORECASE)
    if m_curr:
        curr_raw = m_curr.group(1).upper()
        if curr_raw in ("RUPEE", "RUPEES", "RS", "RS."):
            slots["currency"] = "INR"
        else:
            slots["currency"] = curr_raw

    dur_match = re.search(r"\b(\d+)\s*[- ]?days?\b", text, re.IGNORECASE)
    if dur_match:
        try:
            slots["duration_days"] = int(dur_match.group(1))
        except ValueError:
            pass

    dep_match = re.search(
        r"\b(?:from|leaving\s+from|departing\s+from|travel\s+from|traveling\s+from)\s+([A-Za-z\s]+?)(?=\s+(?:to|for|with|on|in|during|\d+|days?)|$)",
        text,
        re.IGNORECASE,
    )
    if dep_match:
        dep = dep_match.group(1).strip()
        stop_words = {"a", "an", "the", "some", "my", "our", "me", "it", "there", "here"}
        if dep and dep.lower() not in stop_words and len(dep) >= 2:
            slots["departure_city"] = dep.title()

    dest_match = re.search(
        r"\b(?:actually,?|let'?s\s+(?:go\s+to|visit)|go\s+to|head\s+to|travel\s+to|trip\s+to|change\s+(?:destination\s+)?to|switch\s+to|visit|visiting|explore|exploring|to)\s+([A-Za-z\s]+?)(?=\s+(?:for|from|with|on|in|during|\d+|days?|instead)|$)",
        text,
        re.IGNORECASE,
    )
    if dest_match:
        dest = dest_match.group(1).strip()
        dest = re.sub(r"^(?:visit|visiting|go to|explore|head to)\s+", "", dest, flags=re.IGNORECASE).strip()
        stop_words = {"a", "an", "the", "some", "my", "our", "me", "it", "there", "here"}
        if dest and dest.lower() not in stop_words and len(dest) >= 2:
            slots["destination_city"] = dest.title()

    return slots


def destination_node(state: TripState) -> TripState:
    _fill_known_slots(state)

    if not state.get("destination_city") and state.get("destination_candidates"):
        picked = llm.select_option(state["last_user_message"], state["destination_candidates"])
        if picked:
            state["destination_city"] = picked[0]["name"]

    if state.get("destination_city"):
        state["conversation_stage"] = "estimating_budget"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"destination_city": state["destination_city"]},
                instruction="Confirm the destination and say we're about to estimate the budget.",
            ),
            "stage": "estimating_budget",
            "ui_component": "text",
            "options": [],
            "requires_user_input": False,
            "input_type": "none",
        }
        return state

    if not state.get("departure_city"):
        state["conversation_stage"] = "collecting_departure"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={},
                instruction="Ask where the user is starting their trip from - real destination "
                            "suggestions need a departure point.",
            ),
            "stage": "collecting_departure",
            "ui_component": "text",
            "options": [],
            "requires_user_input": True,
            "input_type": "free_text",
        }
        return state

    if state.get("conversation_stage") == "collecting_departure_airport" and state.get("departure_airport_options"):
        picked = llm.select_option(state["last_user_message"], state["departure_airport_options"])
        if picked:
            state["departure_airport"] = picked[0]["id"]
        else:
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"options": state["departure_airport_options"]},
                    instruction="Ask the user to pick one of the listed airport options or choose 'Any airport'.",
                ),
                "stage": "collecting_departure_airport",
                "ui_component": "airport_options",
                "options": state["departure_airport_options"],
                "requires_user_input": True,
                "input_type": "select_one",
            }
            return state

    if not state.get("departure_airport"):
        airport_options = services.fetch_departure_airport_options(state["departure_city"])
        if not airport_options:
            state["departure_city"] = None
            state["conversation_stage"] = "collecting_departure"
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"invalid_departure": state.get("last_user_message")},
                    instruction="Say that departure city/airport wasn't recognized and ask for a clearer city name or airport code.",
                ),
                "stage": "collecting_departure",
                "ui_component": "text",
                "options": [],
                "requires_user_input": True,
                "input_type": "free_text",
            }
            return state

        if len(airport_options) == 1 and airport_options[0]["id"] == state["departure_city"].upper():
            state["departure_airport"] = airport_options[0]["id"]
        else:
            any_option = {"id": "ANY", "name": "Any airport", "code": "ANY"}
            options_to_show = airport_options + [any_option]
            state["departure_airport_options"] = options_to_show
            state["conversation_stage"] = "collecting_departure_airport"
            state["turn_response"] = {
                "reply": llm.build_reply(
                    context={"departure_city": state["departure_city"], "options": options_to_show},
                    instruction="Present these real airport options for the departure city, plus an 'Any airport' option, and ask the user to select one.",
                ),
                "stage": "collecting_departure_airport",
                "ui_component": "airport_options",
                "options": options_to_show,
                "requires_user_input": True,
                "input_type": "select_one",
            }
            return state

    dep_id = state["departure_city"] if state.get("departure_airport") == "ANY" else (state.get("departure_airport") or state["departure_city"])
    interest = llm.classify_explore_interest(state["last_user_message"], state.get("vibe"))
    candidates = services.fetch_destination_recommendations(
        dep_id, interest=interest, currency=state["currency"]
    )

    if candidates is None:
        state["departure_city"] = None
        state["departure_airport"] = None
        state["conversation_stage"] = "collecting_departure"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"departure_city": state["departure_city"]},
                instruction="Say that departure city/airport wasn't recognized and ask for a "
                            "clearer one - a city name or an airport code.",
            ),
            "stage": "collecting_departure",
            "ui_component": "text",
            "options": [],
            "requires_user_input": True,
            "input_type": "free_text",
        }
        return state

    state["destination_candidates"] = candidates
    state["turn_response"] = {
        "reply": llm.build_reply(
            context={"candidates": candidates, "vibe": state.get("vibe"),
                      "departure_city": state["departure_city"]},
            instruction="Present these real destination options, including their flight/hotel "
                        "price estimates, and ask the user to pick one or name somewhere else.",
        ),
        "stage": "collecting_destination",
        "ui_component": "destination_options",
        "options": candidates,
        "requires_user_input": True,
        "input_type": "select_one",
    }
    return state


def _fill_known_slots(state: TripState) -> None:
    slots = {}
    try:
        slots = llm.extract_trip_slots(state["last_user_message"]) or {}
    except Exception as exc:
        logger.warning(
            "LLM extract_trip_slots failed due to provider outage: %s. Using regex fallback slot extraction.",
            exc,
        )

    # Always complement with regex extraction if LLM missed any slots
    regex_slots = _regex_extract_slots(state.get("last_user_message", ""))
    for k, v in regex_slots.items():
        if k not in slots or not slots[k]:
            slots[k] = v

    if slots.get("currency"):
        state["currency"] = slots["currency"]

    # When we're specifically waiting for a departure city, re-interpret
    # any extracted city as departure_city, and prevent overwriting
    # an already confirmed destination_city.
    if (
        state.get("conversation_stage") == "collecting_departure"
        and not state.get("departure_city")
    ):
        city = slots.get("departure_city") or slots.get("destination_city")
        if city:
            slots = dict(slots)          # don't mutate the original
            slots["departure_city"] = city
            if state.get("destination_city"):
                slots.pop("destination_city", None)  # preserve confirmed destination

    from app.schemas.common import float_to_money_dict

    current_dest = state.get("destination_city")
    extracted_dest = slots.get("destination_city")

    # Detect destination change
    if extracted_dest and current_dest and extracted_dest.strip().lower() != current_dest.strip().lower():
        state["destination_city"] = extracted_dest.strip().title()
        # Clear old destination-dependent cached options and selections
        state["destination_candidates"] = []
        state["attraction_candidates"] = []
        state["confirmed_attractions"] = []
        state["hotel_candidates"] = []
        state["confirmed_hotel"] = None
        state["itinerary"] = []
        state["budget_allocation"] = None
    elif extracted_dest and not current_dest:
        state["destination_city"] = extracted_dest.strip().title()

    # Update duration if specified
    if slots.get("duration_days"):
        state["duration_days"] = slots["duration_days"]

    # Budget handling: only set or update if valid
    if not state.get("budget_total"):
        extracted_b = slots.get("budget_total") or _parse_budget_number(state.get("last_user_message", ""))
        if extracted_b:
            curr = state.get("currency", "INR") or "INR"
            m_dict = float_to_money_dict(extracted_b, curr)
            if m_dict:
                state["budget_total"] = m_dict["amountMinor"]
    else:
        # If budget_total is already set, only update if the user explicitly provided a new budget
        user_msg = state.get("last_user_message", "")
        if re.search(r"\b(?:budget|inr|usd|eur|gbp|rupees?|rs\.?|₹|\$)\b", user_msg, re.IGNORECASE):
            extracted_b = slots.get("budget_total") or _parse_budget_number(user_msg)
            if extracted_b:
                curr = state.get("currency", "INR") or "INR"
                m_dict = float_to_money_dict(extracted_b, curr)
                if m_dict:
                    state["budget_total"] = m_dict["amountMinor"]

    for key in ("departure_city", "outbound_date", "return_date"):
        if slots.get(key) is not None and not state.get(key):
            state[key] = slots[key]

    if not state.get("vibe"):
        try:
            vibe = llm.classify_vibe(state["last_user_message"])
            if vibe:
                state["vibe"] = vibe
        except Exception as exc:
            logger.warning("LLM classify_vibe failed during provider outage: %s", exc)