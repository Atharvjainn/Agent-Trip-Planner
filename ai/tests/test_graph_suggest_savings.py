import pytest

from app.graphs.suggest_savings import run
from app.schemas.common import Money
from app.schemas.savings import SavingsSuggestRequest, SelectionSnapshot


@pytest.mark.asyncio
async def test_empty_strategy_list_produces_empty_suggestions():
    req = SavingsSuggestRequest(
        trip_id="trip-1",
        selections=SelectionSnapshot(
            flight_price=Money(amount_minor=50000, currency="USD"),
            hotel_price_per_night=Money(amount_minor=10000, currency="USD"),
            nights=5,
            stay_budget=Money(amount_minor=60000, currency="USD"),
        ),
    )
    response = await run(req)
    assert response.suggestions == []
    assert response.fallback_used is False
    assert response.trip_id == "trip-1"


@pytest.mark.asyncio
async def test_handles_fully_empty_selection_snapshot():
    req = SavingsSuggestRequest(trip_id="trip-2", selections=SelectionSnapshot())
    response = await run(req)
    assert response.suggestions == []
