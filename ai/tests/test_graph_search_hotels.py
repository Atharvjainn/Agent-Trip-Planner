import pytest

from app.graphs.search_hotels import HotelDeps, run
from app.schemas.common import GeoPoint, Money
from app.schemas.hotels import HotelSearchRequest, SelectedSpotInput
from app.tools.serpapi import SerpApiClient


def _request() -> HotelSearchRequest:
    return HotelSearchRequest(
        trip_id="trip-1",
        city="Paris",
        selected_spots=[
            SelectedSpotInput(
                id="place-museum-1", name="Old Town Museum", location=GeoPoint(lat=48.8534, lng=2.3488)
            ),
            SelectedSpotInput(
                id="place-market-3", name="Riverside Market", location=GeoPoint(lat=48.851, lng=2.356)
            ),
        ],
        stay_budget=Money(amount_minor=100000, currency="USD"),
        nights=5,
    )


@pytest.mark.asyncio
async def test_happy_path_scores_and_sorts_hotels():
    deps = HotelDeps(serpapi=SerpApiClient())
    response = await run(_request(), deps=deps)

    assert response.fallback_used is False
    assert 1 <= len(response.options) <= 15
    # scores should be non-increasing
    scores = [o.score for o in response.options]
    assert scores == sorted(scores, reverse=True)
    # every option carries a distance entry per selected spot
    assert all(len(o.distances) == 2 for o in response.options)


@pytest.mark.asyncio
async def test_distances_are_real_haversine_km_not_placeholder_zero():
    deps = HotelDeps(serpapi=SerpApiClient())
    response = await run(_request(), deps=deps)
    for option in response.options:
        assert any(d.distance_km > 0 for d in option.distances)


@pytest.mark.asyncio
async def test_options_capped_at_fifteen():
    deps = HotelDeps(serpapi=SerpApiClient())
    response = await run(_request(), deps=deps)
    assert len(response.options) <= 15
