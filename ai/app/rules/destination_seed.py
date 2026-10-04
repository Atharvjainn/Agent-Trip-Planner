"""
Last-resort deterministic candidate pool for graphs/recommend_destinations.py.

Order of preference when the KG has too few candidates for a vibe
(ai/AGENT.md "Cold start"):
  1. KG candidates (kg/reads.candidate_cities_by_vibe)
  2. LLM-generated candidates, validated by a SerpApi flight price check
  3. THIS static pool — only reached if both the KG and every LLM
     provider are unavailable. Keeps the demo alive end to end
     (root AGENTS.md §10.7: "every AI step must have a deterministic
     fallback").

Small and clearly a placeholder on purpose — real coverage should come
from the KG filling in as trips are made, not from this list growing.
"""
from __future__ import annotations

SEED_POOL: dict[str, list[tuple[str, str]]] = {
    "adventure": [("Queenstown", "New Zealand"), ("Interlaken", "Switzerland"), ("Moab", "USA")],
    "relaxed": [("Bali", "Indonesia"), ("Maldives", "Maldives"), ("Phuket", "Thailand")],
    "nightlife": [("Berlin", "Germany"), ("Bangkok", "Thailand"), ("Ibiza", "Spain")],
    "culture_heritage": [("Kyoto", "Japan"), ("Rome", "Italy"), ("Varanasi", "India")],
    "spiritual": [("Rishikesh", "India"), ("Varanasi", "India"), ("Lhasa", "China")],
    "food": [("Bangkok", "Thailand"), ("Lyon", "France"), ("Osaka", "Japan")],
    "nature": [("Banff", "Canada"), ("Munnar", "India"), ("Queenstown", "New Zealand")],
    "shopping": [("Dubai", "UAE"), ("Singapore", "Singapore"), ("Milan", "Italy")],
    "family": [("Orlando", "USA"), ("Singapore", "Singapore"), ("Goa", "India")],
    "romantic": [("Paris", "France"), ("Santorini", "Greece"), ("Udaipur", "India")],
}


def seed_candidates(vibes: list[str], limit: int) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for vibe in vibes:
        for city, country in SEED_POOL.get(vibe, []):
            key = (city, country)
            if key in seen:
                continue
            seen.add(key)
            out.append({"city": city, "country": country, "vibeScore": 0.6})
            if len(out) >= limit:
                return out
    return out
