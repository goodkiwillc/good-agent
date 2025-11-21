"""Common tool definition patterns: good practices vs anti-patterns."""

import asyncio

from good_agent import Agent, Depends, tool


# Example for demonstration purposes
class AsyncDB:
    """Mock async database."""

    async def query(self, sql: str):
        return f"Result for: {sql}"


async def get_async_db():
    """Async dependency provider."""
    return AsyncDB()


# ❌ Missing type hints - this will work but won't have proper schema generation
@tool
def bad_tool(param):  # type: ignore  # No type hints
    """Tool without type hints (not recommended)."""
    return param


# ✅ Proper type hints - recommended approach
@tool
def good_tool(param: str) -> str:
    """Tool with proper type hints."""
    return param


# ❌ Sync tool with async dependency - this won't work correctly
@tool
def sync_tool_bad(db: AsyncDB = Depends(get_async_db)):  # type: ignore
    """Sync tool trying to use async dependency (won't work)."""
    # This will fail because sync functions can't await
    pass


# ✅ Async tool with async dependency - correct approach
@tool
async def async_tool_good(db: AsyncDB = Depends(get_async_db)) -> str:
    """Async tool with async dependency (correct)."""
    result = await db.query("SELECT * FROM users")
    return result


async def main():
    """Demonstrate tool definition best practices."""
    async with Agent(
        "You are a helpful assistant.", tools=[bad_tool, good_tool, async_tool_good]
    ) as agent:
        # Good tool with type hints
        result = await agent.invoke(good_tool, param="test")
        print(f"Good tool result: {result.response}")

        # Async tool with async dependency
        result = await agent.invoke(async_tool_good)
        print(f"Async tool result: {result.response}")

        print("\nBest practices:")
        print("✅ Always use type hints for parameters and return values")
        print("✅ Use async tools for async dependencies")
        print("✅ Match tool sync/async with dependency sync/async")


if __name__ == "__main__":
    asyncio.run(main())
