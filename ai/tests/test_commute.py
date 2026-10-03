import pytest

from app.rules.commute import estimate_commute, rate_minor_per_km, route_distance_km
from app.tools.geo import Point, centroid, haversine_km, normalize


def test_haversine_zero_for_identical_points():
    p = Point(lat=48.85, lng=2.35)
    assert haversine_km(p, p) == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance_paris_to_london():
    paris = Point(lat=48.8566, lng=2.3522)
    london = Point(lat=51.5074, lng=-0.1278)
    km = haversine_km(paris, london)
    # Real-world distance is ~344 km; allow a loose tolerance since this
    # is a smoke test, not a geodesy test.
    assert 330 <= km <= 360


def test_centroid_of_single_point_is_itself():
    p = Point(lat=10.0, lng=20.0)
    assert centroid([p]) == p


def test_centroid_requires_at_least_one_point():
    with pytest.raises(ValueError):
        centroid([])


def test_normalize_no_spread_returns_one():
    assert normalize(5.0, 5.0, 5.0) == 1.0


def test_normalize_invert_flips_direction():
    assert normalize(0.0, 0.0, 10.0, invert=True) == 1.0
    assert normalize(10.0, 0.0, 10.0, invert=True) == 0.0


def test_route_distance_round_trips_through_every_spot():
    hotel = Point(lat=0.0, lng=0.0)
    spots = [Point(lat=0.0, lng=1.0), Point(lat=0.0, lng=2.0)]
    km = route_distance_km(hotel, spots)
    # hotel->spot1->spot2->hotel, each leg roughly 111km per degree of lng at the equator
    leg = haversine_km(hotel, spots[0])
    assert km == pytest.approx(leg + leg + 2 * leg, rel=0.05)


def test_route_distance_with_no_spots_is_zero():
    hotel = Point(lat=0.0, lng=0.0)
    assert route_distance_km(hotel, []) == 0.0


def test_rate_lookup_known_tier_vs_default():
    tier1_cab = rate_minor_per_km(city_tier="tier_1", mode="cab")
    unknown_cab = rate_minor_per_km(city_tier=None, mode="cab")
    assert tier1_cab != unknown_cab
    assert unknown_cab > 0


def test_estimate_commute_scales_with_nights():
    hotel = Point(lat=0.0, lng=0.0)
    spots = [Point(lat=0.0, lng=0.1)]
    one_night = estimate_commute(hotel=hotel, spots=spots, nights=1)
    three_nights = estimate_commute(hotel=hotel, spots=spots, nights=3)
    assert three_nights.trip_total_cost_minor == one_night.trip_total_cost_minor * 3
    assert three_nights.daily_distance_km == pytest.approx(one_night.daily_distance_km)


def test_estimate_commute_rejects_zero_nights():
    hotel = Point(lat=0.0, lng=0.0)
    with pytest.raises(ValueError):
        estimate_commute(hotel=hotel, spots=[], nights=0)
