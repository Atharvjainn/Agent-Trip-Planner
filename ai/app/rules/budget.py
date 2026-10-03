"""
ai/AGENT.md "Budget estimate rules":
  - default percentage splits per trip type (domestic vs international) and
    duration band live here.
  - the LLM may adjust each category by at most +/-15 percentage points and
    must return an explanation.
  - validation after the LLM: all amounts >= 0, integers in minor units, sum
    equals the total exactly (rounding remainder goes to buffer). If
    validation fails, return the rules split.
"""
from __future__ import annotations

from dataclasses import dataclass

CATEGORIES = ("flights", "stay", "local_commute", "food", "activities", "buffer")

MAX_LLM_ADJUST_PP = 15  # percentage points, each category, either direction

# Default splits, as percentages (must sum to 100 per row). Duration bands
# are inclusive lower bound in days. International trips route more of the
# budget to flights and less to local_commute than domestic trips of the
# same length.
_DOMESTIC_SPLITS: list[tuple[int, dict[str, int]]] = [
    (1, {"flights": 20, "stay": 30, "local_commute": 15, "food": 20, "activities": 10, "buffer": 5}),
    (4, {"flights": 15, "stay": 32, "local_commute": 13, "food": 22, "activities": 13, "buffer": 5}),
    (8, {"flights": 12, "stay": 33, "local_commute": 12, "food": 23, "activities": 15, "buffer": 5}),
]

_INTERNATIONAL_SPLITS: list[tuple[int, dict[str, int]]] = [
    (1, {"flights": 38, "stay": 25, "local_commute": 8, "food": 15, "activities": 9, "buffer": 5}),
    (4, {"flights": 32, "stay": 27, "local_commute": 8, "food": 16, "activities": 12, "buffer": 5}),
    (8, {"flights": 26, "stay": 29, "local_commute": 8, "food": 17, "activities": 15, "buffer": 5}),
]


def _pick_band(duration_days: int, bands: list[tuple[int, dict[str, int]]]) -> dict[str, int]:
    chosen = bands[0][1]
    for min_days, split in bands:
        if duration_days >= min_days:
            chosen = split
    return chosen


def default_split_pct(*, is_international: bool, duration_days: int) -> dict[str, int]:
    bands = _INTERNATIONAL_SPLITS if is_international else _DOMESTIC_SPLITS
    split = dict(_pick_band(duration_days, bands))
    assert sum(split.values()) == 100, "default split must sum to 100"
    return split


def split_to_amounts(total_minor: int, split_pct: dict[str, int]) -> dict[str, int]:
    """
    Convert a percentage split into integer minor-unit amounts that sum to
    exactly `total_minor`. Largest-remainder method, remainder parked in
    `buffer` last so every other category is a clean floor() of its share.
    """
    raw = {cat: total_minor * split_pct[cat] / 100 for cat in CATEGORIES}
    floored = {cat: int(raw[cat] // 1) for cat in CATEGORIES}
    remainder = total_minor - sum(floored.values())
    floored["buffer"] += remainder
    return floored


@dataclass(frozen=True)
class LlmAdjustment:
    """What graphs/estimate_budget.py asks the LLM for, and what it must
    validate before trusting it."""

    adjusted_pct: dict[str, int]
    explanation: str


def validate_llm_adjustment(base_pct: dict[str, int], adjustment: LlmAdjustment) -> bool:
    """
    True only if every category moved by at most MAX_LLM_ADJUST_PP points,
    the result still sums to 100, covers exactly the known categories, and
    every value is non-negative. Anything else and the caller must fall
    back to the rules split untouched.
    """
    adj = adjustment.adjusted_pct
    if set(adj.keys()) != set(CATEGORIES):
        return False
    if any(v < 0 for v in adj.values()):
        return False
    if sum(adj.values()) != 100:
        return False
    for cat in CATEGORIES:
        if abs(adj[cat] - base_pct[cat]) > MAX_LLM_ADJUST_PP:
            return False
    return True


def validate_amounts(total_minor: int, amounts: dict[str, int]) -> bool:
    if set(amounts.keys()) != set(CATEGORIES):
        return False
    if any(not isinstance(v, int) or v < 0 for v in amounts.values()):
        return False
    return sum(amounts.values()) == total_minor
