from app.rules.budget import (
    CATEGORIES,
    LlmAdjustment,
    default_split_pct,
    split_to_amounts,
    validate_amounts,
    validate_llm_adjustment,
)


def test_default_split_sums_to_100_domestic_and_international():
    for is_intl in (True, False):
        for days in (1, 3, 5, 10, 20):
            split = default_split_pct(is_international=is_intl, duration_days=days)
            assert sum(split.values()) == 100
            assert set(split.keys()) == set(CATEGORIES)


def test_international_allocates_more_to_flights_than_domestic():
    domestic = default_split_pct(is_international=False, duration_days=5)
    international = default_split_pct(is_international=True, duration_days=5)
    assert international["flights"] > domestic["flights"]


def test_split_to_amounts_sums_exactly_even_with_rounding():
    split = default_split_pct(is_international=True, duration_days=7)
    for total in (100, 999, 123457, 1, 0):
        amounts = split_to_amounts(total, split)
        assert sum(amounts.values()) == total
        assert all(isinstance(v, int) and v >= 0 for v in amounts.values())


def test_validate_llm_adjustment_accepts_small_moves():
    base = default_split_pct(is_international=False, duration_days=5)
    adjusted = dict(base)
    adjusted["food"] += 10
    adjusted["activities"] -= 10
    assert validate_llm_adjustment(base, LlmAdjustment(adjusted_pct=adjusted, explanation="shift to food"))


def test_validate_llm_adjustment_rejects_too_large_a_move():
    base = default_split_pct(is_international=False, duration_days=5)
    adjusted = dict(base)
    adjusted["food"] += 20  # exceeds MAX_LLM_ADJUST_PP
    adjusted["activities"] -= 20
    assert not validate_llm_adjustment(base, LlmAdjustment(adjusted_pct=adjusted, explanation="too much"))


def test_validate_llm_adjustment_rejects_wrong_total():
    base = default_split_pct(is_international=False, duration_days=5)
    adjusted = dict(base)
    adjusted["food"] += 5  # now sums to 105, nothing reduced
    assert not validate_llm_adjustment(base, LlmAdjustment(adjusted_pct=adjusted, explanation="bad"))


def test_validate_llm_adjustment_rejects_missing_category():
    base = default_split_pct(is_international=False, duration_days=5)
    adjusted = {k: v for k, v in base.items() if k != "buffer"}
    assert not validate_llm_adjustment(base, LlmAdjustment(adjusted_pct=adjusted, explanation="missing"))


def test_validate_amounts_rejects_mismatched_total():
    amounts = {c: 0 for c in CATEGORIES}
    amounts["flights"] = 100
    assert not validate_amounts(200, amounts)
    assert validate_amounts(100, amounts)


def test_validate_amounts_rejects_negative():
    amounts = {c: 0 for c in CATEGORIES}
    amounts["flights"] = -5
    amounts["buffer"] = 5
    assert not validate_amounts(0, amounts)
