"""Generator pattern: Resource Management.

Demonstrates:
- Acquiring resources in setup phase
- Guaranteed resource release in cleanup
- Safe resource handling even on exceptions
"""

import asyncio
from dataclasses import dataclass

from good_agent import Agent


@dataclass
class ConnectionPool:
    """Simulated database connection pool."""

    name: str
    connections: int = 5
    active: bool = True

    async def execute(self, query: str) -> str:
        """Simulate executing a query."""
        return f"Result for: {query}"

    async def close(self):
        """Close the pool."""
        self.active = False
        print(f"  [pool] {self.name} closed")


async def create_connection_pool() -> ConnectionPool:
    """Simulate creating a connection pool."""
    pool = ConnectionPool(name="main_pool")
    print(f"  [pool] Created {pool.name} with {pool.connections} connections")
    return pool


async def main():
    async with Agent("You are a database assistant.") as agent:
        # Track pool outside mode scope to verify cleanup
        tracked_pool: ConnectionPool | None = None

        @agent.modes("database")
        async def database_mode(agent: Agent):
            """Database mode with connection pool lifecycle."""
            nonlocal tracked_pool

            # SETUP: Acquire resources
            pool = await create_connection_pool()
            tracked_pool = pool  # Track for verification
            agent.mode.state["db_pool"] = pool
            agent.prompt.append("You have database access.")

            try:
                yield agent  # Mode active
            finally:
                # CLEANUP: Release resources (guaranteed via finally)
                await pool.close()

        print("=== Generator Pattern: Resource Management ===\n")

        # Normal usage - pool is always closed
        print("Test 1: Normal usage")
        async with agent.modes["database"]:
            pool = agent.mode.state["db_pool"]
            result = await pool.execute("SELECT * FROM users")
            print(f"  Query result: {result}")
        assert tracked_pool is not None
        print(f"  Pool active after exit: {tracked_pool.active}\n")

        # With exception - pool is still closed due to finally block
        print("Test 2: With exception (cleanup still runs)")
        tracked_pool = None
        try:
            async with agent.modes["database"]:
                pool = agent.mode.state["db_pool"]
                print("  Raising exception...")
                raise RuntimeError("Database error!")
        except RuntimeError as e:
            print(f"  Caught: {e}")
        assert tracked_pool is not None
        print(f"  Pool active after exception: {tracked_pool.active}")


if __name__ == "__main__":
    asyncio.run(main())
