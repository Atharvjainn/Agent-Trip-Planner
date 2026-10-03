from datetime import date

import pytest

from app.graphs.search_flights import FlightDeps, run
from app.schemas.common import Money
from app.schemas.flights import FlightSearchRequest
from app.tools.serpapi import SerpApiClient


def _request(budget_minor: int) -> FlightSearchRequest:
    return FlightSearchRequest(
        trip_id="trip-1",
        source="JFK",
        destination="CDG",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 17),
        travelers=2,
        flights_budget=Money(amount_minor=budget_minor, currency="USD"),
    )


@pytest.mark.asyncio
async def test_options_are_sorted_with_within_budget_first():
    deps = FlightDeps(serpapi=SerpApiClient())
    # Budget of $500 -> only the $410 Budget Wings flight fits; the other
    # two ($612, $548) are over budget and should still appear, but after
    # the in-budget one, each group still price-sorted.
    response = await run(_request(budget_minor=50000), deps=deps)

    assert response.fallback_used is False
    assert len(response.options) == 3
    assert response.options[0].price.amount_minor == 41000  # within budget, cheapest
    assert response.options[1].price.amount_minor == 54800  # over budget, cheapest of the rest
    assert response.options[2].price.amount_minor == 61200


@pytest.mark.asyncio
async def test_everything_in_budget_sorts_purely_by_price():
    deps = FlightDeps(serpapi=SerpApiClient())
    response = await run(_request(budget_minor=100000), deps=deps)
    prices = [o.price.amount_minor for o in response.options]
    assert prices == sorted(prices)


@pytest.mark.asyncio
async def test_options_capped_at_ten():
    deps = FlightDeps(serpapi=SerpApiClient())
    response = await run(_request(budget_minor=100000), deps=deps)
    assert len(response.options) <= 10


@pytest.mark.asyncio
async def test_each_option_keeps_its_provider_deep_link():
    deps = FlightDeps(serpapi=SerpApiClient())
    response = await run(_request(budget_minor=100000), deps=deps)
    assert all(o.provider_ref.deep_link for o in response.options)
