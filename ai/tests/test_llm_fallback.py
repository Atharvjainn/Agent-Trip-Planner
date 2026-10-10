from unittest.mock import patch
import pytest
import llm

@pytest.mark.asyncio
async def test_double_llm_provider_failure_does_not_default_to_greeting():
    with patch.object(
        llm._decision_client, "system_one", side_effect=Exception("OpenJev Down")
    ):
        with patch.object(
            llm, "generate", side_effect=Exception("Gemini Down")
        ):
            # 1. Fresh session with travel keywords
            state_fresh = {
                "conversation_stage": "start",
                "last_user_message": "Let's plan a 5 day trip to Goa",
            }
            intent_fresh = llm.classify_intent(state_fresh)
            assert intent_fresh != "greeting"
            assert intent_fresh == "new_trip"

            # 2. Ambiguous short greeting on fresh session
            state_hi = {
                "conversation_stage": "start",
                "last_user_message": "Hello there",
            }
            intent_hi = llm.classify_intent(state_hi)
            assert intent_hi == "greeting"

            # 3. Active session in progress
            state_active = {
                "conversation_stage": "collecting_budget",
                "last_user_message": "50000",
            }
            intent_active = llm.classify_intent(state_active)
            assert intent_active == "continue_flow"
