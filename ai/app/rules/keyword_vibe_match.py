"""
ai/AGENT.md discover_spots fallback: "keyword-based tag match".

Deliberately simple substring matching against the place's name and
SerpApi `types`. This runs for every place first (cheap, deterministic);
graphs/discover_spots.py then asks the LLM to improve tagging only for
places this leaves with no confident tag, and keeps this result untouched
for everything else or if the LLM is unavailable.
"""
from __future__ import annotations

_KEYWORDS: dict[str, list[str]] = {
    "adventure": ["adventure", "trek", "zipline", "rafting", "climbing", "safari", "diving"],
    "relaxed": ["spa", "resort", "beach", "retreat", "garden", "lake"],
    "nightlife": ["bar", "club", "pub", "nightlife", "lounge", "casino"],
    "culture_heritage": ["museum", "temple", "heritage", "fort", "palace", "monument", "historic", "gallery"],
    "spiritual": ["temple", "ashram", "shrine", "monastery", "church", "mosque", "meditation"],
    "food": ["restaurant", "market", "food", "cafe", "street food", "brewery", "winery"],
    "nature": ["park", "waterfall", "mountain", "forest", "lake", "wildlife", "garden", "beach"],
    "shopping": ["mall", "market", "bazaar", "shopping", "store"],
    "family": ["zoo", "aquarium", "amusement", "theme park", "water park", "park"],
    "romantic": ["sunset", "viewpoint", "garden", "lake", "beach", "palace"],
}


def tag_place(name: str, types: list[str]) -> list[tuple[str, float]]:
    haystack = " ".join([name, *types]).lower()
    scores: list[tuple[str, float]] = []
    for vibe, keywords in _KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in haystack)
        if hits:
            score = min(1.0, 0.5 + 0.2 * hits)
            scores.append((vibe, round(score, 2)))
    scores.sort(key=lambda t: -t[1])
    return scores[:3]
