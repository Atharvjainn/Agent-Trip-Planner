import asyncio
from neo4j import AsyncGraphDatabase
from app.config import get_settings


async def main():
    settings = get_settings()

    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )

    try:
        async with driver.session() as session:
            result = await session.run("RETURN 1 AS n")
            record = await result.single()
            print("Query result:", record["n"])
    finally:
        await driver.close()


asyncio.run(main())