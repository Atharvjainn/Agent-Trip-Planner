"""
Read/write functions for the shared (global) graph and the per-user
graph. Nodes call these functions; nothing outside this file should
call driver.session().run(...) directly, so caching/freshness logic
stays in one place.

Staleness is enforced as a WHERE clause at read time (Neo4j has no
built-in TTL) - attraction identity is trusted for ATTRACTION_CACHE_MAX_AGE_DAYS,
hotel *prices* only for HOTEL_PRICE_CACHE_MAX_AGE_DAYS since rates move
daily. Hotel identity (name/coords/amenities) is returned regardless of
price age; the caller decides whether to refresh the price for the
specific hotel a user is about to see (see tools.serpapi_client.refresh_hotel_price).
"""
from __future__ import annotations
import json
import config
from graphdb.connection import get_driver

# Neo4j node/relationship properties can only be primitives or
# homogeneous arrays of primitives - NOT a nested map. `extensions` and
# `verified_by` are lists of strings, which is fine; `operating_hours`
# (a dict like {"monday": "7 AM-6 PM", ...}) is not, and writing it
# through unchanged would fail at query time, not silently - caught
# during this review rather than at the next live write. Serialized to
# a JSON string on write, parsed back on read; every other field passes
# through unchanged.
_JSON_ENCODED_FIELDS = ("operating_hours", "extensions")


def _sanitize_value(v):
    """Recursively reduce v to something Neo4j can store:
    primitive, list-of-primitives, or JSON string."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, list):
        # Allowed only if every element is a primitive
        if all(isinstance(i, (str, int, float, bool)) or i is None for i in v):
            return v
        # Mixed or nested list — JSON-encode it
        return json.dumps(v)
    # Any other type (dict, etc.) → JSON string
    return json.dumps(v)


def _encode_for_graph(props: dict) -> dict:
    encoded = dict(props)
    # First pass: JSON-encode fields we always want as strings
    for field in _JSON_ENCODED_FIELDS:
        if encoded.get(field) is not None:
            encoded[field] = json.dumps(encoded[field])
    # Second pass: sanitize anything else that isn't a Neo4j-safe primitive
    for k, v in list(encoded.items()):
        if k not in _JSON_ENCODED_FIELDS:
            encoded[k] = _sanitize_value(v)
    return encoded


def _decode_from_graph(node: dict) -> dict:
    decoded = dict(node)
    for field in _JSON_ENCODED_FIELDS:
        if isinstance(decoded.get(field), str):
            try:
                decoded[field] = json.loads(decoded[field])
            except json.JSONDecodeError:
                pass  # leave as-is rather than fail a whole read over one bad field
    return decoded


# ---------- shared / global graph ----------

def get_cached_attractions(city: str, limit: int = 20) -> list:
    query = """
    MATCH (c:City {name:$city})-[:HAS_ATTRACTION]->(a:Attraction)
    WHERE a.verified_at > datetime() - duration({days:$max_age})
    RETURN a ORDER BY a.rating DESC LIMIT $limit
    """
    with get_driver().session() as session:
        result = session.run(
            query, city=city, max_age=config.ATTRACTION_CACHE_MAX_AGE_DAYS, limit=limit
        )
        return [_decode_from_graph(dict(r["a"])) for r in result]


def write_attractions(city: str, attractions: list) -> None:
    query = """
    MERGE (c:City {name:$city})
    MERGE (a:Attraction {place_id:$place_id})
    SET a += $props, a.verified_at = datetime()
    MERGE (c)-[:HAS_ATTRACTION]->(a)
    """
    with get_driver().session() as session:
        for place in attractions:
            if not place.get("place_id"):
                continue  # can't cache what we can't uniquely identify
            props = _encode_for_graph({k: v for k, v in place.items() if k != "place_id"})
            session.run(query, city=city, place_id=place["place_id"], props=props)


def get_cached_hotels(city: str, limit: int = 20) -> list:
    query = """
    MATCH (c:City {name:$city})-[:HAS_HOTEL]->(h:Hotel)
    RETURN h, (h.priced_at > datetime() - duration({days:$max_age})) AS price_is_fresh
    ORDER BY h.star_rating DESC LIMIT $limit
    """
    with get_driver().session() as session:
        result = session.run(
            query, city=city, max_age=config.HOTEL_PRICE_CACHE_MAX_AGE_DAYS, limit=limit
        )
        out = []
        for r in result:
            hotel = dict(r["h"])
            hotel["price_is_fresh"] = r["price_is_fresh"]
            out.append(hotel)
        return out


def write_hotels(city: str, hotels: list) -> None:
    query = """
    MERGE (c:City {name:$city})
    MERGE (h:Hotel {place_id:$place_id})
    SET h += $props, h.priced_at = datetime()
    MERGE (c)-[:HAS_HOTEL]->(h)
    """
    with get_driver().session() as session:
        for hotel in hotels:
            if not hotel.get("place_id"):
                continue
            session.run(
                query,
                city=city,
                place_id=hotel["place_id"],
                props={k: v for k, v in hotel.items() if k != "place_id"},
            )


def similar_traveler_hotels(vibe: str, budget_band: str, exclude_user_id: str, limit: int = 3) -> list:
    """Cross-user collaborative signal - what did travelers with a similar
    vibe + budget stay at. A ranking booster, never the sole source of a
    recommendation (returns empty until there's enough trip history)."""
    query = """
    MATCH (other:User)-[:TOOK_TRIP]->(t:Trip {vibe:$vibe, budget_band:$budget_band})-[:STAYED_AT]->(h:Hotel)
    WHERE other.id <> $exclude_user_id
    RETURN h.name AS name, h.place_id AS place_id, count(*) AS votes
    ORDER BY votes DESC LIMIT $limit
    """
    with get_driver().session() as session:
        result = session.run(
            query, vibe=vibe, budget_band=budget_band,
            exclude_user_id=exclude_user_id, limit=limit,
        )
        return [dict(r) for r in result]


# ---------- per-user graph ----------

def get_user_history(user_id: str, limit: int = 5) -> list:
    query = """
    MATCH (u:User {id:$user_id})-[:TOOK_TRIP]->(t:Trip)
    RETURN t ORDER BY t.start_date DESC LIMIT $limit
    """
    with get_driver().session() as session:
        result = session.run(query, user_id=user_id, limit=limit)
        return [dict(r["t"]) for r in result]


def record_trip(user_id: str, trip: dict, attraction_ids: list, hotel_id) -> None:
    """Call this once a trip is confirmed (end of itinerary_node, or when
    the trip is marked complete) - this is what makes the *next* trip for
    this user smarter."""
    query = """
    MERGE (u:User {id:$user_id})
    CREATE (t:Trip {id:$trip_id})
    SET t += $trip_props
    MERGE (u)-[:TOOK_TRIP]->(t)
    WITH t
    UNWIND $attraction_ids AS aid
    MATCH (a:Attraction {place_id:aid})
    MERGE (t)-[:VISITED]->(a)
    WITH t
    OPTIONAL MATCH (h:Hotel {place_id:$hotel_id})
    FOREACH (_ IN CASE WHEN h IS NOT NULL THEN [1] ELSE [] END |
        MERGE (t)-[:STAYED_AT]->(h)
    )
    """
    with get_driver().session() as session:
        session.run(
            query,
            user_id=user_id,
            trip_id=trip["id"],
            trip_props=trip,
            attraction_ids=attraction_ids,
            hotel_id=hotel_id,
        )