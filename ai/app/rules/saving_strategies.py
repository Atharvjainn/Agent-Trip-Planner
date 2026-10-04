"""
root AGENTS.md §8: "Smart cost-saving strategies (step 9) are not designed
yet. Implement the suggest-savings job end to end with an empty strategy
list and a clear interface (SavingStrategy -> list of SavingSuggestion).
Do not implement specific strategies until they are written in
docs/cost-strategies.md."

This module is intentionally the ONLY place a future contributor needs to
touch to add a real strategy: write a function matching `SavingStrategy`,
append it to `REGISTERED_STRATEGIES`. graphs/suggest_savings.py and the
route never need to change.
"""
from __future__ import annotations

from typing import Protocol

from app.schemas.savings import SavingSuggestion, SelectionSnapshot


class SavingStrategy(Protocol):
    """A strategy inspects the current selections and may return zero or
    more suggestions. Must be pure / side-effect free so it can run in any
    order and be unit-tested in isolation."""

    id: str

    def __call__(self, selections: SelectionSnapshot) -> list[SavingSuggestion]:
        ...


# Deliberately empty — see module docstring. Do not add strategies here
# until they're specified in docs/cost-strategies.md; that doc doesn't
# exist yet in this MVP.
REGISTERED_STRATEGIES: list[SavingStrategy] = []


def run_all(selections: SelectionSnapshot) -> list[SavingSuggestion]:
    suggestions: list[SavingSuggestion] = []
    for strategy in REGISTERED_STRATEGIES:
        suggestions.extend(strategy(selections))
    return suggestions
