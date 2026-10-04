from __future__ import annotations

from app.rules.budget import CATEGORIES, MAX_LLM_ADJUST_PP

SYSTEM = (
    "You are a budgeting assistant for a trip planner. You may nudge a "
    "default percentage split across fixed categories, by at most "
    f"{MAX_LLM_ADJUST_PP} percentage points per category, and must explain "
    "why in one short sentence. You never touch the total or invent new "
    "categories. Respond with JSON only."
)


def build_prompt(
    *,
    base_split_pct: dict[str, int],
    is_international: bool,
    duration_days: int,
    vibes: list[str],
) -> str:
    return (
        f"Default split (percent, sums to 100): {base_split_pct}\n"
        f"Trip type: {'international' if is_international else 'domestic'}\n"
        f"Duration: {duration_days} days\n"
        f"Vibes: {', '.join(vibes) or 'none specified'}\n\n"
        f"Categories you may adjust, each by at most {MAX_LLM_ADJUST_PP} "
        f"points from its default: {', '.join(CATEGORIES)}.\n"
        f"For example, a trip tagged 'food' or 'nightlife' might shift a "
        f"little from activities toward food; 'relaxed' might shift from "
        f"local_commute toward stay. Only adjust if you have a real reason.\n\n"
        f'Return JSON: {{"adjustedPct": {{"flights": int, "stay": int, '
        f'"local_commute": int, "food": int, "activities": int, "buffer": int}}, '
        f'"explanation": str}}. The six values must sum to exactly 100.'
    )
