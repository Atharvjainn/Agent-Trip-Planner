from app.rules.hotel_scoring import HotelCandidate, score_hotels


def test_empty_input_returns_empty_output():
    assert score_hotels([]) == []


def test_single_candidate_scores_one_point_zero():
    # No spread in the candidate set -> normalize() treats it as maximal
    # on every axis, per app/tools/geo.py normalize()'s documented
    # behavior for hi <= lo.
    scores = score_hotels([HotelCandidate(price_per_night_minor=10000, avg_distance_km=2.0, rating=4.2)])
    assert scores == [1.0]


def test_cheaper_and_closer_and_better_rated_wins():
    candidates = [
        HotelCandidate(price_per_night_minor=5000, avg_distance_km=1.0, rating=4.8),  # best on all 3
        HotelCandidate(price_per_night_minor=30000, avg_distance_km=10.0, rating=3.0),  # worst on all 3
    ]
    scores = score_hotels(candidates)
    assert scores[0] > scores[1]
    assert scores[0] == 1.0  # best on every axis -> normalized to 1 on every axis
    assert scores[1] == 0.0


def test_missing_rating_treated_as_zero():
    candidates = [
        HotelCandidate(price_per_night_minor=10000, avg_distance_km=1.0, rating=None),
        HotelCandidate(price_per_night_minor=10000, avg_distance_km=1.0, rating=5.0),
    ]
    scores = score_hotels(candidates)
    assert scores[1] > scores[0]


def test_weights_sum_to_one():
    from app.rules.hotel_scoring import PRICE_FIT_WEIGHT, PROXIMITY_WEIGHT, RATING_WEIGHT

    assert abs(PRICE_FIT_WEIGHT + PROXIMITY_WEIGHT + RATING_WEIGHT - 1.0) < 1e-9
