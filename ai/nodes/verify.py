"""
Shared verification step: a generated place name can refer to something
that doesn't exist. Before anything reaches the user, it's checked
against a real lookup - the knowledge graph first, a live SerpApi call
if that misses - never trusted as text alone. This is deliberately not
an LLM call: an LLM can't confirm a place is real, only a grounded
lookup can.

Tripadvisor is tried as a FALLBACK, only when Google Maps has no match
- not a cross-check run on every lookup, which would double the cost of
every verification call for a benefit that mostly doesn't materialize
(Maps and Tripadvisor agreeing on something that exists is not new
information; the fallback earns its cost specifically on the cases
where Maps alone would have wrongly said "unverifiable").
"""
from graphdb import repository as repo
from tools import serpapi_client


def verify_and_enrich(city: str, candidate_names: list, lat: float, lon: float) -> tuple:
    """
    Returns (verified_places, unverifiable_names). Cache is checked
    first; a live Maps call next; Tripadvisor only for names Maps still
    can't confirm. Only Maps-sourced results (which carry real
    coordinates) are written back into the shared graph - a
    Tripadvisor-only hit lacks reliable coordinates (see
    serpapi_client._normalize_tripadvisor_place) and caching a
    coordinate-less "attraction" would silently break every downstream
    function that assumes confirmed attractions have lat/lon (hotel
    proximity clustering, day clustering). Such a hit is shown to the
    user for this turn only, never persisted.
    """
    cached = {p["name"].lower(): p for p in repo.get_cached_attractions(city) if p.get("name")}
    verified = []
    unverifiable = []
    to_fetch_live = []

    for name in candidate_names:
        match = cached.get(name.lower())
        if match:
            match = dict(match, source="cache", verified=True, verified_by=["google_maps"])
            verified.append(match)
        else:
            to_fetch_live.append(name)

    newly_fetched = []
    still_unmatched = []
    for name in to_fetch_live:
        results = serpapi_client.search_attractions(name, lat, lon)
        if results:
            place = dict(results[0], source="live", verified=True, verified_by=["google_maps"])
            verified.append(place)
            newly_fetched.append(place)
        else:
            still_unmatched.append(name)

    for name in still_unmatched:
        fallback = serpapi_client.search_tripadvisor(name)
        if fallback:
            place = dict(fallback[0], source="live", verified=True, verified_by=["tripadvisor"])
            verified.append(place)  # not added to newly_fetched - never cached, see docstring
        else:
            unverifiable.append(name)

    if newly_fetched:
        repo.write_attractions(city, newly_fetched)

    return verified, unverifiable