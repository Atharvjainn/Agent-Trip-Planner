"""
Run once against a fresh AuraDB instance to set up constraints:

    python -m graphdb.schema

Safe to re-run - every statement is idempotent (`IF NOT EXISTS`).
"""
from graphdb.connection import get_driver

STATEMENTS = [
    "CREATE CONSTRAINT city_name IF NOT EXISTS FOR (c:City) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE",
    "CREATE CONSTRAINT place_id IF NOT EXISTS FOR (a:Attraction) REQUIRE a.place_id IS UNIQUE",
    "CREATE CONSTRAINT hotel_id IF NOT EXISTS FOR (h:Hotel) REQUIRE h.place_id IS UNIQUE",
    "CREATE CONSTRAINT trip_id IF NOT EXISTS FOR (t:Trip) REQUIRE t.id IS UNIQUE",
]


def setup_schema():
    driver = get_driver()
    with driver.session() as session:
        for stmt in STATEMENTS:
            session.run(stmt)
    print(f"Applied {len(STATEMENTS)} schema statements.")


if __name__ == "__main__":
    setup_schema()
