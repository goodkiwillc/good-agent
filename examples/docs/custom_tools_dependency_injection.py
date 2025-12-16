"""Basic dependency injection in custom tools."""

import asyncio

from fast_depends import Depends

from good_agent import Agent, tool


# Define a dependency provider
def get_api_client():
    """Provide an API client instance."""
    return {"api_key": "secret", "base_url": "https://api.example.com"}


@tool
async def call_api(
    endpoint: str,
    client: dict = Depends(get_api_client),  # Inject dependency
) -> dict:
    """
    Call an API endpoint with injected client.

    Args:
        endpoint: API endpoint path
        client: API client (injected automatically)

    Returns:
        API response
    """
    url = f"{client['base_url']}/{endpoint}"
    # Make API call...
    return {"url": url, "status": "success"}


async def main():
    """Demonstrate basic dependency injection."""
    async with Agent("API assistant", tools=[call_api]) as agent:
        result = await agent.invoke(call_api, endpoint="users/123")
        print(f"API call result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
