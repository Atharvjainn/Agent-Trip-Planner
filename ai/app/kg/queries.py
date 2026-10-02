"""
ai/AGENT.md "Knowledge graph (Neo4j)":
  - Nodes: City, Place, Hotel, Event, Vibe, Trip (anonymized ID only, no PII).
  - Relationships: (Place)-[:IN]->(City), (Hotel)-[:IN]->(City),
    (Event)-[:IN]->(City), (Place)-[:HAS_VIBE {score}]->(Vibe),
    (Hotel)-[:NEAR {km}]->(Place), (Trip)-[:TO]->(City),
    (Trip)-[:SELECTED]->(Place|Hotel), (Trip)-[:WANTED]->(Vibe).
  - Upserts use MERGE on provider IDs (SerpApi place_id/data_id, hotel
    property_token). Ingestion must be idempotent.
  - All Cypher lives here. Parameterize every query; no string formatting.
  - No user names, emails, or free text in Neo4j.

Every query below takes a dict of parameters and never interpolates a
value into the query string.
"""
from __future__ import annotations

MERGE_CITY = """
MERGE (c:City {name: $name, country: $country})
RETURN c
"""

MERGE_VIBE = """
MERGE (v:Vibe {name: $name})
RETURN v
"""

MERGE_PLACE = """
MERGE (p:Place {providerId: $provider_id})
SET p.name = $name, p.lat = $lat, p.lng = $lng, p.rating = $rating
WITH p
MATCH (c:City {name: $city, country: $country})
MERGE (p)-[:IN]->(c)
RETURN p
"""

MERGE_PLACE_VIBE = """
MATCH (p:Place {providerId: $provider_id})
MERGE (v:Vibe {name: $vibe})
MERGE (p)-[r:HAS_VIBE]->(v)
SET r.score = $score
"""

MERGE_HOTEL = """
MERGE (h:Hotel {providerId: $provider_id})
SET h.name = $name, h.lat = $lat, h.lng = $lng, h.rating = $rating
WITH h
MATCH (c:City {name: $city, country: $country})
MERGE (h)-[:IN]->(c)
RETURN h
"""

MERGE_HOTEL_NEAR_PLACE = """
MATCH (h:Hotel {providerId: $hotel_provider_id})
MATCH (p:Place {providerId: $place_provider_id})
MERGE (h)-[r:NEAR]->(p)
SET r.km = $km
"""

MERGE_EVENT = """
MERGE (e:Event {name: $name, date: $date})
SET e.venue = $venue
WITH e
MATCH (c:City {name: $city, country: $country})
MERGE (e)-[:IN]->(c)
RETURN e
"""

MERGE_TRIP = """
MERGE (t:Trip {anonymizedId: $trip_id})
WITH t
MATCH (c:City {name: $city, country: $country})
MERGE (t)-[:TO]->(c)
"""

MERGE_TRIP_WANTED_VIBE = """
MATCH (t:Trip {anonymizedId: $trip_id})
MERGE (v:Vibe {name: $vibe})
MERGE (t)-[:WANTED]->(v)
"""

MERGE_TRIP_SELECTED_PLACE = """
MATCH (t:Trip {anonymizedId: $trip_id})
MATCH (p:Place {providerId: $provider_id})
MERGE (t)-[:SELECTED]->(p)
"""

MERGE_TRIP_SELECTED_HOTEL = """
MATCH (t:Trip {anonymizedId: $trip_id})
MATCH (h:Hotel {providerId: $provider_id})
MERGE (t)-[:SELECTED]->(h)
"""

# --- reads used by recommend_destinations (cold-start candidate lookup) ---

CANDIDATE_CITIES_BY_VIBE = """
MATCH (c:City)<-[:IN]-(p:Place)-[hv:HAS_VIBE]->(v:Vibe)
WHERE v.name IN $vibes
WITH c, avg(hv.score) AS vibeScore, count(DISTINCT p) AS placeCount
WHERE placeCount >= 3
RETURN c.name AS city, c.country AS country, vibeScore
ORDER BY vibeScore DESC
LIMIT $limit
"""

PLACE_VIBE_SCORES_FOR_CITY = """
MATCH (c:City {name: $city, country: $country})<-[:IN]-(p:Place)-[hv:HAS_VIBE]->(v:Vibe)
RETURN p.providerId AS providerId, p.name AS name, p.lat AS lat, p.lng AS lng,
       p.rating AS rating, collect({vibe: v.name, score: hv.score}) AS vibeScores
"""
