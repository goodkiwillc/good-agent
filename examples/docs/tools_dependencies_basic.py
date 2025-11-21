"""Basic dependency injection in tools using FastDepends."""

import asyncio

from fast_depends import Depends

from good_agent import Agent, tool


# Dependency providers
def get_database():
    """Provide a database connection."""
    return {"connection": "postgresql://localhost/db"}


def get_api_client():
    """Provide an API client."""
    return {"api_key": "secret", "base_url": "https://api.example.com"}


@tool
async def query_database(
    query: str,
    limit: int = 10,
    db: dict = Depends(get_database),  # Injected dependency
    api: dict = Depends(get_api_client),  # Multiple dependencies
) -> list[dict]:
    """Query the database with API enrichment."""
    # Use db and api connections
    results = [
        {"id": i, "query": query, "api_url": api["base_url"]} for i in range(limit)
    ]
    return results


async def main():
    """Demonstrate basic dependency injection."""
    async with Agent("Database assistant", tools=[query_database]) as agent:
        response = await agent.call("Query users with limit 5")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
