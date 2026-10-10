from unittest.mock import patch
import pytest
from nodes.destination import destination_node
import llm

@pytest.mark.asyncio
async def test_budget_indian_units_regex_fallback():
    cases = [
        ("1 lakh", 10000000),
        ("1lakh", 10000000),
        ("2.5 lakh", 25000000),
        ("1 crore", 1000000000),
        ("my bidget is around 1lakh ruppee(INR)", 10000000),
    ]
    with patch.object(llm, "generate", side_effect=Exception("Total LLM Outage")):
        for msg, expected_minor in cases:
            state = {
                "conversation_stage": "collecting_budget",
                "last_user_message": msg,
                "destination_city": "Goa",
                "departure_city": "Mumbai",
                "budget_total": None,
                "currency": "INR",
            }
            res_state = destination_node(state)
            assert res_state["budget_total"] == expected_minor, f"Failed for '{msg}'"


@pytest.mark.asyncio
async def test_budget_indian_units_llm_path():
    state = {
        "conversation_stage": "collecting_budget",
        "last_user_message": "my budget is 1 lakh rupees",
        "destination_city": "Goa",
        "departure_city": "Mumbai",
        "budget_total": None,
        "currency": "INR",
    }
    mock_slots = {"budget_total": 100000.0}
    with patch.object(llm, "extract_trip_slots", return_value=mock_slots):
        res_state = destination_node(state)
        assert res_state["budget_total"] == 10000000
