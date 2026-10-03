from __future__ import annotations

from app.schemas.common import vibe_tags

SYSTEM = (
    "You are a concise travel-recommendation assistant. You rank candidate "
    "destination cities for a trip and explain each pick in one short "
    "sentence. You never invent prices or distances — those are given to "
    "you. Respond with JSON only, matching the requested schema exactly."
)


def build_prompt(
    *,
    source: str,
    budget_total_minor: int,
    currency: str,
    travelers: int,
    duration_days: int,
    vibes: list[str],
    candidates: list[dict],
) -> str:
    return (
        f"Traveler profile:\n"
        f"- departing from: {source}\n"
        f"- budget: {budget_total_minor} {currency} minor units total\n"
        f"- travelers: {travelers}\n"
        f"- trip length: {duration_days} days\n"
        f"- desired vibes: {', '.join(vibes)} (allowed vibe tags: {', '.join(vibe_tags())})\n\n"
        f"Candidate cities (already matched by our knowledge graph + a live "
        f"flight price check — do not change the estimatedFlightPrice or "
        f"vibeMatchScore fields, only choose and order up to 5, and write "
        f"the `reason` for each):\n"
        f"{candidates}\n\n"
        f"Return JSON: "
        f'{{"options": [{{"city": str, "country": str, "estimatedFlightPrice": '
        f'{{"amountMinor": int, "currency": str}}, "vibeMatchScore": float, '
        f'"reason": str, "source": "llm"}}]}}, at most 5 items, ordered best first.'
    )
