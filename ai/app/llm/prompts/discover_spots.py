from __future__ import annotations

from app.schemas.common import vibe_tags

SYSTEM = (
    "You tag tourist spots with vibe scores from a fixed vocabulary. You "
    "never invent new tags and never change the place name, rating, or "
    "location you're given. Respond with JSON only."
)


def build_prompt(*, places: list[dict]) -> str:
    return (
        f"Allowed vibe tags: {', '.join(vibe_tags())}.\n\n"
        f"For each place below, assign 1-3 vibe tags with a score 0-1 each "
        f"(how strongly the place matches that vibe):\n{places}\n\n"
        f'Return JSON: {{"tags": [{{"placeId": str, "vibeScores": '
        f'[{{"vibe": str, "score": float}}]}}]}}, one entry per input place, '
        f"same placeId values as given."
    )
