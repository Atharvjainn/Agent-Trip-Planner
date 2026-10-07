from unittest.mock import patch
import pytest
from nodes.destination import destination_node
import llm

@pytest.mark.asyncio
async def test_slot_extraction_llm_failure_regex_fallback():
    state = {
        "conversation_stage": "start",
        "last_user_message": "Let's plan a 5 day trip to Goa",
        "destination_city": None,
        "departure_city": None,
        "duration_days": None,
        "currency": "INR",
    }

    # Mock llm.generate to raise Exception (simulating total LLM outage across Gemini and Groq)
    with patch.object(llm, "generate", side_effect=Exception("Total LLM Provider Outage")):
        res_state = destination_node(state)

        # 1. Assert destination_city ends up as "Goa" (recovered via regex fallback)
        assert res_state["destination_city"] == "Goa"
        # 2. Assert duration_days ends up as 5
        assert res_state["duration_days"] == 5
        # 3. Assert conversation_stage does NOT incorrectly become "collecting_departure"
        assert res_state["conversation_stage"] != "collecting_departure"
        # 4. Assert conversation_stage moves to "estimating_budget"
        assert res_state["conversation_stage"] == "estimating_budget"