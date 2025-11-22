"""Best practice: Keep tools focused on single responsibilities."""

import asyncio

from good_agent import Agent, tool


# Good: Focused, single-purpose tools
@tool
async def fetch_user(user_id: int) -> dict:
    """Fetch user data by ID."""
    return {"id": user_id, "name": "User"}


@tool
async def update_user(user_id: int, name: str) -> dict:
    """Update user name."""
    return {"id": user_id, "name": name, "updated": True}


# Avoid: Tools that do too many things
@tool
async def user_operations(action: str, user_id: int, name: str | None = None) -> dict:
    """Unclear tool that does multiple operations."""
    # This is harder to use and maintain
    if action == "fetch":
        return {"id": user_id, "name": "User"}
    elif action == "update":
        return {"id": user_id, "name": name, "updated": True}
    else:
        return {"error": f"Unknown action: {action}"}


async def main():
    """Demonstrate focused tools best practice."""
    async with Agent(
        "User manager", tools=[fetch_user, update_user, user_operations]
    ) as agent:
        # Using focused tools (recommended)
        result = await agent.invoke(fetch_user, user_id=123)
        print(f"Focused fetch: {result.response}")

        result = await agent.invoke(update_user, user_id=123, name="Alice")
        print(f"Focused update: {result.response}")

        # Using multi-purpose tool (not recommended)
        result = await agent.invoke(
            user_operations, action="fetch", user_id=123, name=None
        )
        print(f"Multi-purpose fetch: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
