import json

import pytest

from app.graphs.build_summary import SummaryDeps, run
from app.llm.provider import LLMProvider, ProviderUnavailable
from app.schemas.common import GeoPoint, Money
from app.schemas.hotels import SelectedSpotInput
from app.schemas.summary import SummaryBuildRequest
from tests.conftest import FakeLLMBackend


def _request() -> SummaryBuildRequest:
    return SummaryBuildRequest(
        trip_id="trip-1",
        city="Paris",
        hotel_location=GeoPoint(lat=48.86, lng=2.34),
        selected_spots=[
            SelectedSpotInput(id="s1", name="Old Town Museum", location=GeoPoint(lat=48.8534, lng=2.3488)),
            SelectedSpotInput(id="s2", name="Riverside Market", location=GeoPoint(lat=48.851, lng=2.356)),
        ],
        flight_price=Money(amount_minor=61200, currency="USD"),
        hotel_total_price=Money(amount_minor=71000, currency="USD"),
        nights=5,
    )


@pytest.mark.asyncio
async def test_happy_path_uses_llm_narrative():
    llm_response = json.dumps({"narrative": "Paris awaits with museums and markets. Estimates only!"})
    deps = SummaryDeps(llm=LLMProvider(backends=[FakeLLMBackend("gemini", response_json=llm_response)]))
    response = await run(_request(), deps=deps)

    assert response.fallback_used is False
    assert response.narrative == "Paris awaits with museums and markets. Estimates only!"
    assert response.commute.trip_total_cost.amount_minor > 0
    assert response.commute.daily_distance_km > 0


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_template_narrative():
    backend = FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))
    deps = SummaryDeps(llm=LLMProvider(backends=[backend]))
    response = await run(_request(), deps=deps)

    assert response.fallback_used is True
    assert "Paris" in response.narrative
    assert "Old Town Museum" in response.narrative
    assert "estimates" in response.narrative.lower()


@pytest.mark.asyncio
async def test_commute_cost_scales_with_nights():
    backend = FakeLLMBackend("gemini", raise_exc=ProviderUnavailable("no key"))
    deps = SummaryDeps(llm=LLMProvider(backends=[backend]))
    req_5 = _request()
    req_10 = req_5.model_copy(update={"nights": 10})

    r5 = await run(req_5, deps=deps)
    r10 = await run(req_10, deps=deps)
    assert r10.commute.trip_total_cost.amount_minor == r5.commute.trip_total_cost.amount_minor * 2
