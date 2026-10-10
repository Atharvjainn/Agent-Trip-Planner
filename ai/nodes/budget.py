from __future__ import annotations

import asyncio
import concurrent.futures
from typing import Any

from app.graphs import estimate_budget
from app.schemas.budget import BudgetEstimateRequest
from app.schemas.common import Money, get_currency_exponent
import llm
from state import TripState


def _run_sync(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


def is_international_trip(departure_city: str | None, destination_city: str | None, currency: str = "INR") -> bool:
    if currency and currency.upper() != "INR":
        return True
    dest_upper = (destination_city or "").upper().strip()
    if dest_upper and any(c in dest_upper for c in ("PARIS", "LONDON", "NEW YORK", "TOKYO", "DUBAI", "SINGAPORE", "BALI", "BANGKOK")):
        return True
    return False


def budget_node(state: TripState) -> TripState:
    dest = state.get("destination_city") or "your destination"
    currency = state.get("currency", "INR") or "INR"

    if not state.get("budget_total"):
        state["conversation_stage"] = "collecting_budget"
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"destination_city": dest},
                instruction="Ask the user what their total budget is for the trip.",
            ),
            "stage": "collecting_budget",
            "ui_component": "text",
            "options": [],
            "requires_user_input": True,
            "input_type": "free_text",
        }
        return state

    if not state.get("departure_city"):
        state["conversation_stage"] = "collecting_departure"
        exp = get_currency_exponent(currency)
        major_b = state["budget_total"] / (10 ** exp)
        state["turn_response"] = {
            "reply": llm.build_reply(
                context={"destination_city": dest, "budget": f"{currency} {major_b:g}"},
                instruction=f"Acknowledge the {currency} {major_b:g} budget for the trip to {dest}, and ask where the user will be traveling/departing from.",
            ),
            "stage": "collecting_departure",
            "ui_component": "text",
            "options": [],
            "requires_user_input": True,
            "input_type": "free_text",
        }
        return state

    # budget_total is ALREADY an int representing amountMinor per Task 4
    budget_minor = state["budget_total"]
    duration = state.get("duration_days") or 4
    vibes = [state["vibe"]] if state.get("vibe") else []
    is_intl = is_international_trip(state.get("departure_city"), state.get("destination_city"), currency)

    req = BudgetEstimateRequest(
        trip_id=state.get("session_id") or "chat_session",
        budget_total=Money(amount_minor=budget_minor, currency=currency),
        is_international=is_intl,
        duration_days=duration,
        vibes=vibes,
    )

    exp = get_currency_exponent(currency)
    try:
        res = _run_sync(estimate_budget.run(req))
        alloc_dict = {}
        summary_parts = []

        for alloc in res.allocations:
            # Preserve exact canonical category key from budget_categories.json
            alloc_dict[alloc.category] = {
                "amountMinor": alloc.amount.amount_minor,
                "currency": alloc.amount.currency,
            }
            major_val = alloc.amount.amount_minor / (10 ** exp)
            summary_parts.append(f"{alloc.category.replace('_', ' ').title()}: {currency} {major_val:g}")

        state["budget_allocation"] = alloc_dict
        total_major = budget_minor / (10 ** exp)

        header = f"Here is how I would allocate your {currency} {total_major:g} budget for your {duration}-day trip to {dest}:"
        summary_text = header + "\n" + ", ".join(summary_parts) + "."
    except Exception:
        state["budget_allocation"] = None
        summary_text = f"Set your total trip budget to {currency} {budget_minor / (10 ** exp):g}."

    state["conversation_stage"] = "collecting_attractions"
    state["turn_response"] = {
        "reply": summary_text,
        "stage": "estimating_budget",
        "ui_component": "text",
        "options": [],
        "requires_user_input": False,
        "input_type": "none",
    }
    return state
