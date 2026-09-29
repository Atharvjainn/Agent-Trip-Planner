"""Central place for environment configuration and shared constants.
Every other module reads settings from here rather than calling
os.environ directly, so there's one place to check when something
isn't picking up a key correctly.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # loaded here, not just in run_local.py, so `python -m graphdb.schema`
                # and any other entry point also picks up .env correctly

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY", "")

# OpenJev (typed decisions + generation). Point TYPESAFE_BASE_URL at the
# free Codiv hosted endpoint, or your own vLLM/MLX server.
TYPESAFE_BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.codiv.ai")
TYPESAFE_API_KEY = os.environ.get("TYPESAFE_API_KEY", "")

# how long cached data is trusted before we treat it as a cache miss
ATTRACTION_CACHE_MAX_AGE_DAYS = 30
HOTEL_PRICE_CACHE_MAX_AGE_DAYS = 1

DEFAULT_TRIP_DURATION_DAYS = 3
HOTEL_BUDGET_FRACTION = 0.4  # rough share of total budget allotted to lodging
MAX_ATTRACTIONS_SHOWN = 8
MAX_HOTELS_SHOWN = 5
MAX_EVENTS_SHOWN = 5
MAX_FLIGHTS_SHOWN = 5