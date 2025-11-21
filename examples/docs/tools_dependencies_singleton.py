"""Dependency management with singleton pattern for shared resources."""

import asyncio

from good_agent import Agent, Depends, tool


class DatabaseConnection:
    """Singleton database connection shared across tool calls."""

    _instance = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance.connect()
        return cls._instance

    async def connect(self):
        # Initialize database connection
        self.connection = "db_connection"

    async def close(self):
        # Clean up connection
        self.connection = None


async def get_db():
    """Dependency provider for database connection."""
    return await DatabaseConnection.get_instance()


@tool
async def query_users(
    name_filter: str, db: DatabaseConnection = Depends(get_db)
) -> list[dict]:
    """Query users with shared DB connection."""
    # Use db.connection
    return [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]


async def main():
    """Demonstrate singleton dependency pattern for shared resources."""
    async with Agent("You are a helpful assistant.", tools=[query_users]) as agent:
        # First call creates the singleton instance
        result1 = await agent.invoke(query_users, name_filter="A")
        print(f"First query result: {result1.response}")

        # Second call reuses the same instance
        result2 = await agent.invoke(query_users, name_filter="B")
        print(f"Second query result: {result2.response}")

        # Verify both calls used the same connection instance
        db_instance = await DatabaseConnection.get_instance()
        print(f"\nDatabase connection: {db_instance.connection}")

    # Clean up the singleton
    if DatabaseConnection._instance:
        await DatabaseConnection._instance.close()
        DatabaseConnection._instance = None


if __name__ == "__main__":
    asyncio.run(main())
