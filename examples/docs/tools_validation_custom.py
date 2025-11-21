"""Custom validation logic in tools."""

import asyncio

from good_agent import Agent, tool


@tool
async def create_user(
    name: str,
    email: str,
    age: int,
) -> dict:
    """Create a user with validation."""
    # Custom validation
    if age < 13:
        raise ValueError("Users must be at least 13 years old")

    if "@" not in email:
        raise ValueError("Invalid email format")

    return {"name": name, "email": email, "age": age, "id": "user_123"}


async def main():
    """Demonstrate custom validation."""
    async with Agent("User management assistant", tools=[create_user]) as agent:
        response = await agent.call(
            "Create a user named Alice with email alice@example.com, age 25"
        )
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
