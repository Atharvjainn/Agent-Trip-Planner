"""
ai/AGENT.md graph table, discover_spots:
  SerpApi Maps places + Events for dates -> vibe-tag match -> LLM tag
  unknown places -> rank.
  Fallback: keyword-based tag match.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypedDict

import httpx
from langgraph.graph import END, StateGraph
from pydantic import Field

from app.config import get_settings
from app.kg import ingest as kg_ingest
from app.llm.prompts.discover_spots import SYSTEM, build_prompt
from app.llm.provider import LLMAllProvidersFailed, LLMProvider
from app.rules.keyword_vibe_match import tag_place
from app.schemas.common import CamelModel, GeoPoint, ProviderRef, VibeScore
from app.schemas.spots import SpotDiscoverRequest, SpotDiscoverResponse, SpotEvent, SpotOption
from app.tools.serpapi import FixtureNotFound, NormalizedEvent, NormalizedPlace, SerpApiClient

logger = logging.getLogger("services.ai.graphs.discover_spots")

LOW_CONFIDENCE_THRESHOLD = 0.6  # below this, a place is "unknown" enough to ask the LLM


class _LlmVibeTag(CamelModel):
    place_id: str
    vibe_scores: list[VibeScore]


class _LlmTagResult(CamelModel):
    tags: list[_LlmVibeTag] = Field(max_length=25)


@dataclass
class SpotDeps:
    serpapi: SerpApiClient
    llm: LLMProvider


def default_deps() -> SpotDeps:
    return SpotDeps(serpapi=SerpApiClient(), llm=LLMProvider())


class SpotState(TypedDict, total=False):
    request: SpotDiscoverRequest
    deps: SpotDeps
    places: list[NormalizedPlace]
    events: list[NormalizedEvent]
    tags_by_place: dict[str, list[tuple[str, float]]]
    tag_source_by_place: dict[str, str]
    spots: list[SpotOption]
    fallback_used: bool


async def node_fetch(state: SpotState) -> dict:
    req = state["request"]
    deps = state["deps"]

    # Two independent SerpApi calls — one failing (bad query shape, a
    # transient SerpApi error) must not take down the other, and neither
    # should ever crash the request: empty lists just mean fewer/no spots
    # and no event matches, which the rest of the graph already handles.
    try:
        places = await deps.serpapi.search_places(city=req.city, query="tourist attractions")
    except (FixtureNotFound, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("discover_spots: places lookup failed (%s), returning no spots", type(exc).__name__)
        places = []

    try:
        events = await deps.serpapi.search_events(
            city=req.city, start_date=req.start_date, end_date=req.end_date
        )
    except (FixtureNotFound, httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("discover_spots: events lookup failed (%s), returning no events", type(exc).__name__)
        events = []

    return {"places": places, "events": events}


async def node_tag(state: SpotState) -> dict:
    deps = state["deps"]
    places = state["places"]

    tags_by_place: dict[str, list[tuple[str, float]]] = {}
    tag_source_by_place: dict[str, str] = {}
    unknown: list[NormalizedPlace] = []

    for place in places:
        keyword_tags = tag_place(place.name, place.types)
        confident = [t for t in keyword_tags if t[1] >= LOW_CONFIDENCE_THRESHOLD]
        if confident:
            tags_by_place[place.provider_ref.id] = keyword_tags
            tag_source_by_place[place.provider_ref.id] = "keyword_match"
        else:
            tags_by_place[place.provider_ref.id] = keyword_tags  # keep as a baseline in case LLM also fails
            tag_source_by_place[place.provider_ref.id] = "keyword_match"
            unknown.append(place)

    fallback_used = False
    if unknown:
        try:
            prompt = build_prompt(
                places=[{"placeId": p.provider_ref.id, "name": p.name} for p in unknown]
            )
            result = await deps.llm.structured("discover_spots.tag", prompt, _LlmTagResult, system=SYSTEM)
            for tag in result.tags:
                tags_by_place[tag.place_id] = [(vs.vibe, vs.score) for vs in tag.vibe_scores]
                tag_source_by_place[tag.place_id] = "llm"
        except LLMAllProvidersFailed:
            logger.info(
                "discover_spots: LLM tagging unavailable for %d places, keeping keyword tags", len(unknown)
            )
            fallback_used = True

    return {
        "tags_by_place": tags_by_place,
        "tag_source_by_place": tag_source_by_place,
        "fallback_used": fallback_used,
    }


async def node_rank(state: SpotState) -> dict:
    req = state["request"]
    places = state["places"]
    events = state["events"]
    tags_by_place = state["tags_by_place"]
    tag_source_by_place = state["tag_source_by_place"]
    requested = set(req.vibes)

    def relevance(place: NormalizedPlace) -> float:
        scores = tags_by_place.get(place.provider_ref.id, [])
        matched = [s for v, s in scores if v in requested]
        base = max(matched) if matched else 0.0
        rating_boost = (place.rating or 0) / 5 * 0.2
        return base + rating_boost

    ranked = sorted(places, key=relevance, reverse=True)

    settings = get_settings()
    spots: list[SpotOption] = []
    for place in ranked[: settings.cap_spots]:
        scores = tags_by_place.get(place.provider_ref.id, [])
        matching_event = next(
            (e for e in events if e.venue and place.name.lower() in e.venue.lower()), None
        )
        vibe_score_models = [VibeScore(vibe=v, score=s) for v, s in scores]
        if not vibe_score_models and req.vibes:
            # Keep every spot wired to at least one requested vibe so the
            # frontend's vibe-match UI always has something to show, even
            # for a place neither keyword matching nor the LLM could tag.
            vibe_score_models = [VibeScore(vibe=req.vibes[0], score=0.3)]
        spots.append(
            SpotOption(
                provider_ref=ProviderRef(id=place.provider_ref.id, deep_link=place.provider_ref.deep_link),
                name=place.name,
                location=GeoPoint(lat=place.lat, lng=place.lng),
                rating=place.rating,
                vibe_scores=vibe_score_models,
                matching_event=(
                    SpotEvent(
                        name=matching_event.name,
                        event_date=matching_event.date,
                        venue=matching_event.venue,
                    )
                    if matching_event
                    else None
                ),
                tag_source=tag_source_by_place.get(place.provider_ref.id, "keyword_match"),
            )
        )

    # Ingest in the background (ai/AGENT.md: "Ingest after each SerpApi
    # fetch, in the background. Ingestion failures are logged, never fail
    # the request" — kg_ingest.* already swallow+log their own errors).
    for place in places:
        await kg_ingest.ingest_place(place, city=req.city, country=req.country)
        scores = tags_by_place.get(place.provider_ref.id, [])
        await kg_ingest.ingest_place_vibe_scores(place.provider_ref.id, scores)
    for event in events:
        await kg_ingest.ingest_event(event, city=req.city, country=req.country)

    return {"spots": spots}


def build_graph():
    graph = StateGraph(SpotState)
    graph.add_node("fetch", node_fetch)
    graph.add_node("tag", node_tag)
    graph.add_node("rank", node_rank)
    graph.set_entry_point("fetch")
    graph.add_edge("fetch", "tag")
    graph.add_edge("tag", "rank")
    graph.add_edge("rank", END)
    return graph.compile()


_compiled = None


async def run(request: SpotDiscoverRequest, deps: SpotDeps | None = None) -> SpotDiscoverResponse:
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    result = await _compiled.ainvoke({"request": request, "deps": deps or default_deps()})
    return SpotDiscoverResponse(
        trip_id=request.trip_id, spots=result["spots"], fallback_used=result.get("fallback_used", False)
    )
