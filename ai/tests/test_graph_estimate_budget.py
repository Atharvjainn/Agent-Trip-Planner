import json

import pytest

from app.graphs.estimate_budget import BudgetDeps, run
from app.llm.provider import LLMProvider, ProviderUnavailable
from app.rules.budget import CATEGORIES, default_split_pct
from app.schemas.budget import BudgetEstimateRequest
from app.schemas.common import Money
from tests.conftest import FakeLLMBackend


def _request() -> BudgetEstimateRequest:
    return BudgetEstimateRequest(
        trip_id="trip-1",
        budget_total=Money(amount_minor=300000, currency="USD"),
        is_international=True,
        duration_days=7,
        vibes=["food"],
    )


@pytest.mark.asyncio
async def test_happy_path_llm_adjustment_is_applied_and_validated():
    base = default_split_pct(is_international=True, duration_days=7)
    adjusted = dict(base)
    adjusted["food"] += 5
    adjusted["buffer"] -= 5
    llm_response = json.dumps({"adjustedPct": adjusted, "explanation": "Shifted toward food, as requested."})

    deps = BudgetDeps(llm=LLMProvider(backends=[FakeLLMBackend("gemini", response_json=llm_response)]))
    response = await run(_request(), deps=deps)

    assert response.fallback_used is False
    assert response.explanation == "Shifted toward food, as requested."
    total = sum(a.amount.amount_minor for a in response.allocations)
    assert total == 300000
    assert {a.category for a in response.allocations} == set(CATEGORIES)


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_rules_split():
    backend = FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))
    deps = BudgetDeps(llm=LLMProvider(backends=[backend]))
    response = await run(_request(), deps=deps)

    assert response.fallback_used is True
    base = default_split_pct(is_international=True, duration_days=7)
    expected_flights = round(300000 * base["flights"] / 100)
    actual_flights = next(a.amount.amount_minor for a in response.allocations if a.category == "flights")
    assert actual_flights == expected_flights


@pytest.mark.asyncio
async def test_invalid_llm_adjustment_is_rejected_and_falls_back():
    # food +30 is way outside the +/-15pp allowance.
    base = default_split_pct(is_international=True, duration_days=7)
    bad_adjustment = dict(base)
    bad_adjustment["food"] += 30
    bad_adjustment["buffer"] -= 30
    llm_response = json.dumps({"adjustedPct": bad_adjustment, "explanation": "too aggressive"})

    deps = BudgetDeps(llm=LLMProvider(backends=[FakeLLMBackend("gemini", response_json=llm_response)]))
    response = await run(_request(), deps=deps)

    assert response.fallback_used is True
    total = sum(a.amount.amount_minor for a in response.allocations)
    assert total == 300000


@pytest.mark.asyncio
async def test_sum_is_always_exact_even_for_odd_totals():
    backend = FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))
    deps = BudgetDeps(llm=LLMProvider(backends=[backend]))
    req = BudgetEstimateRequest(
        trip_id="trip-2",
        budget_total=Money(amount_minor=100001, currency="USD"),
        is_international=False,
        duration_days=3,
        vibes=[],
    )
    response = await run(req, deps=deps)
    total = sum(a.amount.amount_minor for a in response.allocations)
    assert total == 100001
