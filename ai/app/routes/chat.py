from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict

from fastapi import APIRouter

from pathlib import Path
import sys

_ai_dir = str(Path(__file__).resolve().parent.parent.parent)
if _ai_dir not in sys.path:
    sys.path.insert(0, _ai_dir)

from graph import build_graph
from state import TripState
from nodes.router import get_routing_ms
from app.schemas.common import float_to_money_dict, trip_statuses
from app.schemas.chat import ChatMetricsModel, ChatRequest, ChatResponse, TurnResponseModel

def _format_hotel_prices(hotel: Any, default_currency: str = "INR") -> Any:
    if not isinstance(hotel, dict):
        return hotel
    res = dict(hotel)
    curr = res.get("currency") or default_currency
    for key in ("rate_per_night", "ratePerNight", "price_per_night", "pricePerNight", "total_price", "totalPrice", "price"):
        if key in res and isinstance(res[key], (int, float)):
            res[key] = float_to_money_dict(res[key], curr)
    return res

def _format_flight_prices(flight: Any, default_currency: str = "INR") -> Any:
    if not isinstance(flight, dict):
        return flight
    res = dict(flight)
    curr = res.get("currency") or default_currency
    for key in ("price", "price_total", "totalPrice", "total_price"):
        if key in res and isinstance(res[key], (int, float)):
            res[key] = float_to_money_dict(res[key], curr)
    return res

STAGE_TO_TRIP_STATUS: Dict[str, str] = {
    "start": "DRAFT",
    "collecting_departure": "DRAFT",
    "collecting_departure_airport": "DRAFT",
    "collecting_destination": "DRAFT",
    "collecting_budget": "DESTINATION_SELECTED",
    "estimating_budget": "DESTINATION_SELECTED",
    "estimating_budget": "DESTINATION_SELECTED",
    "collecting_attractions": "BUDGET_ESTIMATED",
    "collecting_hotel": "SPOTS_SELECTED",
    "confirming_hotel": "SPOTS_SELECTED",
    "itinerary_ready": "HOTEL_SELECTED",
}

def map_stage_to_trip_status(stage: str, state: Dict[str, Any]) -> str:
    valid_statuses = set(trip_statuses())
    
    if stage in STAGE_TO_TRIP_STATUS:
        mapped = STAGE_TO_TRIP_STATUS[stage]
        if mapped in valid_statuses:
            return mapped

    if stage in ("collecting_flight_departure", "collecting_flight_date", "confirming_flight", "trip_active"):
        if state.get("itinerary"):
            return "SUMMARY_READY"
        if state.get("confirmed_hotel"):
            return "HOTEL_SELECTED"
        if state.get("confirmed_flight"):
            return "FLIGHT_SELECTED"
        if state.get("confirmed_attractions"):
            return "SPOTS_SELECTED"
        if state.get("budget_total") is not None:
            return "BUDGET_ESTIMATED"
        if state.get("destination_city"):
            return "DESTINATION_SELECTED"
        return "DRAFT"

    return "DRAFT"


logger = logging.getLogger('services.ai.routes.chat')

router = APIRouter(tags=['chat'])

_chatbot_app = build_graph()

_SESSION_STORE: Dict[str, TripState] = {}
_SESSION_LOCK = threading.Lock()


def snake_to_camel(s: str) -> str:
    if '_' not in s:
        return s
    parts = s.split('_')
    return parts[0] + ''.join(x.title() for x in parts[1:])


def sanitize_for_json(obj: Any, is_budget_allocation: bool = False) -> Any:
    if obj is None or isinstance(obj, (int, float, str, bool)):
        return obj
    if isinstance(obj, dict):
        if is_budget_allocation:
            return {str(k): sanitize_for_json(v, is_budget_allocation=False) for k, v in obj.items()}
        return {snake_to_camel(str(k)): (sanitize_for_json(v, is_budget_allocation=True) if k in ("budgetAllocation", "budget_allocation") else sanitize_for_json(v, is_budget_allocation=False)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(x, is_budget_allocation=is_budget_allocation) for x in obj]
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    return str(obj)


def _parse_budget_and_currency(budget_raw: Any, default_currency: str = 'INR') -> tuple[float | None, str]:
    if budget_raw is None:
        return None, default_currency
    if isinstance(budget_raw, (int, float)):
        return float(budget_raw), default_currency
    if isinstance(budget_raw, dict):
        curr = budget_raw.get('currency') or budget_raw.get('Currency') or default_currency
        amt_minor = budget_raw.get('amountMinor')
        if amt_minor is None:
            amt_minor = budget_raw.get('amount_minor')
        if amt_minor is not None and isinstance(amt_minor, (int, float)):
            return float(amt_minor) / 100.0, curr
        amt = budget_raw.get('amount') or budget_raw.get('total')
        if amt is not None and isinstance(amt, (int, float)):
            return float(amt), curr
    return None, default_currency


def get_session_state(
    session_id: str,
    user_id: str | None = None,
    user_location: Any = None,
    existing_state: Dict[str, Any] | None = None,
) -> TripState:
    with _SESSION_LOCK:
        if session_id in _SESSION_STORE:
            base_state = _SESSION_STORE[session_id]
        else:
            base_state = {
                'session_id': session_id,
                'user_id': user_id,
                'conversation_stage': 'start',
                'last_user_message': '',
                'destination_city': None,
                'departure_city': None,
                'departure_airport': None,
                'departure_airport_options': [],
                'vibe': None,
                'budget_total': None,
                'duration_days': None,
                'currency': 'INR',
                'outbound_date': None,
                'return_date': None,
                'destination_candidates': [],
                'attraction_candidates': [],
                'confirmed_attractions': [],
                'hotel_candidates': [],
                'confirmed_hotel': None,
                'itinerary': [],
                'flight_candidates': [],
                'confirmed_flight': None,
                'user_location': user_location.model_dump() if hasattr(user_location, 'model_dump') and user_location else None,
                'free_minutes': None,
                'turn_response': {
                    'reply': '',
                    'stage': 'start',
                    'ui_component': 'text',
                    'options': [],
                    'requires_user_input': True,
                    'input_type': 'free_text',
                },
            }

        if existing_state:
            ext = existing_state

            stage = ext.get('conversationStage') or ext.get('conversation_stage') or ext.get('stage')
            if not stage and not base_state.get('conversation_stage'):
                dest = ext.get('destinationCity') or ext.get('destination_city')
                if dest:
                    stage = 'collecting_attractions'

            if stage:
                base_state['conversation_stage'] = stage
                if isinstance(base_state.get('turn_response'), dict):
                    base_state['turn_response']['stage'] = stage

            if user_id:
                base_state['user_id'] = user_id
            if user_location:
                base_state['user_location'] = user_location.model_dump() if hasattr(user_location, 'model_dump') else user_location
            elif ext.get('userLocation') or ext.get('user_location'):
                base_state['user_location'] = ext.get('userLocation') or ext.get('user_location')

            dest_city = ext.get('destinationCity') or ext.get('destination_city')
            if dest_city is not None:
                base_state['destination_city'] = dest_city

            dep_city = ext.get('departureCity') or ext.get('departure_city')
            if dep_city is not None:
                base_state['departure_city'] = dep_city

            dep_airport = ext.get('departureAirport') or ext.get('departure_airport')
            if dep_airport is not None:
                base_state['departure_airport'] = dep_airport

            dep_options = ext.get('departureAirportOptions') or ext.get('departure_airport_options')
            if dep_options is not None:
                base_state['departure_airport_options'] = dep_options

            vibe = ext.get('vibe')
            if vibe is not None:
                base_state['vibe'] = vibe

            raw_budget = ext.get('budgetTotal') if 'budgetTotal' in ext else ext.get('budget_total')
            if raw_budget is not None:
                if isinstance(raw_budget, dict):
                    amt_minor = raw_budget.get('amountMinor')
                    if amt_minor is None:
                        amt_minor = raw_budget.get('amount_minor')
                    if amt_minor is not None and isinstance(amt_minor, (int, float)):
                        base_state['budget_total'] = int(round(float(amt_minor)))
                    if raw_budget.get('currency'):
                        base_state['currency'] = str(raw_budget['currency'])
                elif isinstance(raw_budget, int):
                    base_state['budget_total'] = raw_budget
                elif isinstance(raw_budget, float):
                    base_state['budget_total'] = int(round(raw_budget))

            if ext.get('currency'):
                base_state['currency'] = ext.get('currency')

            duration = ext.get('durationDays') or ext.get('duration_days')
            if duration is not None:
                base_state['duration_days'] = duration

            outbound = ext.get('outboundDate') or ext.get('outbound_date')
            if outbound is not None:
                base_state['outbound_date'] = outbound

            ret_date = ext.get('returnDate') or ext.get('return_date')
            if ret_date is not None:
                base_state['return_date'] = ret_date

            for key_camel, key_snake in [
                ('destinationCandidates', 'destination_candidates'),
                ('attractionCandidates', 'attraction_candidates'),
                ('confirmedAttractions', 'confirmed_attractions'),
                ('hotelCandidates', 'hotel_candidates'),
                ('confirmedHotel', 'confirmed_hotel'),
                ('itinerary', 'itinerary'),
                ('flightCandidates', 'flight_candidates'),
                ('confirmedFlight', 'confirmed_flight'),
            ]:
                val = ext.get(key_camel) if key_camel in ext else ext.get(key_snake)
                if val is not None:
                    base_state[key_snake] = val

        _SESSION_STORE[session_id] = base_state
        return base_state


def save_session_state(session_id: str, state: TripState) -> None:
    with _SESSION_LOCK:
        _SESSION_STORE[session_id] = state


@router.post('/chat', response_model=ChatResponse)
@router.post('/internal/chat', response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    t0 = time.perf_counter()
    session_id = payload.session_id or payload.trip_id

    state = get_session_state(
        session_id=session_id,
        user_id=payload.user_id,
        user_location=payload.user_location,
        existing_state=payload.existing_state,
    )

    state['last_user_message'] = payload.message
    if payload.user_location and not state.get('user_location'):
        state['user_location'] = payload.user_location.model_dump()

    t_graph_start = time.perf_counter()
    updated_state = _chatbot_app.invoke(state)
    t_graph_end = time.perf_counter()

    save_session_state(session_id, updated_state)

    t1 = time.perf_counter()
    total_ms = round((t1 - t0) * 1000, 2)
    graph_exec_ms = round((t_graph_end - t_graph_start) * 1000, 2)

    routing_ms = updated_state.get('_routing_ms')
    if routing_ms is None and session_id:
        routing_ms = get_routing_ms(session_id)

    logger.info(
        'Chat request processed: trip_id=%s session_id=%s stage=%s total_ms=%.2f routing_ms=%s graph_exec_ms=%.2f',
        payload.trip_id,
        session_id,
        updated_state.get('conversation_stage'),
        total_ms,
        routing_ms,
        graph_exec_ms,
    )

    turn_res = updated_state.get('turn_response') or {}

    raw_options = turn_res.get('options') or []
    sanitized_options = sanitize_for_json(raw_options)

    budget_val = updated_state.get('budget_total')
    currency_val = updated_state.get('currency', 'INR') or 'INR'
    budget_total_money = {'amountMinor': budget_val, 'currency': currency_val} if budget_val is not None else None

    formatted_hotel = _format_hotel_prices(updated_state.get('confirmed_hotel'), currency_val)
    formatted_flight = _format_flight_prices(updated_state.get('confirmed_flight'), currency_val)

    conv_stage = updated_state.get('conversation_stage', 'start')
    trip_status_val = map_stage_to_trip_status(conv_stage, updated_state)

    raw_summary = {
        'stage': conv_stage,
        'destinationCity': updated_state.get('destination_city'),
        'departureCity': updated_state.get('departure_city'),
        'vibe': updated_state.get('vibe'),
        'budgetTotal': budget_total_money,
        'durationDays': updated_state.get('duration_days'),
        'outboundDate': updated_state.get('outbound_date'),
        'returnDate': updated_state.get('return_date'),
        'confirmedAttractions': updated_state.get('confirmed_attractions', []),
        'confirmedHotel': formatted_hotel,
        'confirmedFlight': formatted_flight,
        'budgetAllocation': updated_state.get('budget_allocation'),
        'itinerary': updated_state.get('itinerary', []),
    }
    sanitized_summary = sanitize_for_json(raw_summary)

    return ChatResponse(
        trip_id=payload.trip_id,
        session_id=session_id,
        conversation_stage=conv_stage,
        trip_status=trip_status_val,
        turn_response=TurnResponseModel(
            reply=str(turn_res.get('reply') or ''),
            stage=str(turn_res.get('stage') or 'start'),
            ui_component=str(turn_res.get('ui_component') or 'text'),
            options=sanitized_options if isinstance(sanitized_options, list) else [],
            requires_user_input=bool(turn_res.get('requires_user_input', True)),
            input_type=str(turn_res.get('input_type') or 'free_text'),
        ),
        state_summary=sanitized_summary if isinstance(sanitized_summary, dict) else {},
        metrics=ChatMetricsModel(
            total_ms=total_ms,
            routing_ms=routing_ms,
            graph_exec_ms=graph_exec_ms,
        ),
    )
