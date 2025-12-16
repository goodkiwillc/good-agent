"""Performance best practices: async tools, caching, connection pooling, and timeouts."""

import asyncio
import time
from functools import lru_cache

from good_agent import Agent, tool

# Connection pool (shared across tool calls)
HTTP_CLIENT = None


async def get_http_client():
    """Get or create shared HTTP client for connection pooling."""
    global HTTP_CLIENT
    if not HTTP_CLIENT:
        import aiohttp

        HTTP_CLIENT = aiohttp.ClientSession()
    return HTTP_CLIENT


@tool
async def fetch_url(url: str, timeout: float = 10.0) -> str:
    """Fetch URL with connection pooling and timeout."""
    client = await get_http_client()

    try:
        async with asyncio.timeout(timeout):
            async with client.get(url) as response:
                return await response.text()
    except TimeoutError as err:
        raise ValueError(f"Timeout fetching {url}") from err


# Sync tool with caching
@tool
@lru_cache(maxsize=100)
def expensive_calculation(n: int) -> int:
    """Cached expensive calculation."""
    time.sleep(1)  # Simulate expensive work
    return n * n * n


async def main():
    """Demonstrate performance best practices for tools."""
    async with Agent(
        "You are a helpful assistant.", tools=[fetch_url, expensive_calculation]
    ) as agent:
        # Test cached expensive calculation
        print("First call to expensive_calculation(5)...")
        result1 = await agent.invoke(expensive_calculation, n=5)
        print(f"Result: {result1.response}")  # Takes ~1 second

        print("\nSecond call to expensive_calculation(5)...")
        result2 = await agent.invoke(expensive_calculation, n=5)
        print(f"Result: {result2.response}")  # Instant (cached)

        # Demonstrate connection pooling would work with real URLs
        print("\nConnection pooling example (would reuse HTTP client across calls)")

    # Clean up the global HTTP client
    global HTTP_CLIENT
    if HTTP_CLIENT:
        await HTTP_CLIENT.close()
        HTTP_CLIENT = None


if __name__ == "__main__":
    asyncio.run(main())
