"""Basic generator mode handler with setup/cleanup lifecycle.

Demonstrates:
- Async generator mode handlers using yield
- Setup phase (before yield) runs on mode entry
- Cleanup phase (after yield) runs on mode exit
- Cleanup is guaranteed even if exceptions occur
"""

import asyncio

from good_agent import Agent


async def get_db_connection():
    """Simulate acquiring a database connection."""
    print("  [db] Connecting to database...")
    return {"connected": True, "queries": 0}


async def close_db_connection(connection):
    """Simulate closing a database connection."""
    print(f"  [db] Closing connection (executed {connection['queries']} queries)")


async def main():
    async with Agent("You are a database assistant.") as agent:

        @agent.modes("database_mode")
        async def database_mode(agent: Agent):
            """Mode with database connection lifecycle."""
            # SETUP: Acquire resources
            connection = await get_db_connection()
            agent.mode.state["db"] = connection
            agent.prompt.append("You have database access. Use it wisely.")

            yield agent  # Mode is now active

            # CLEANUP: Release resources (always runs)
            await close_db_connection(connection)

        print("=== Generator Mode: Basic Setup/Cleanup ===\n")

        # Enter mode - setup runs
        print("Entering database_mode...")
        async with agent.mode("database_mode"):
            print(f"  Mode active: {agent.mode.name}")
            print(f"  DB connected: {agent.mode.state['db']['connected']}")

            # Simulate some database operations
            agent.mode.state["db"]["queries"] += 1
            print("  Executed a query")

            agent.mode.state["db"]["queries"] += 1
            print("  Executed another query")

        # Cleanup runs automatically when exiting
        print("\nMode exited - cleanup completed")
        print(f"Current mode: {agent.mode.name}")


if __name__ == "__main__":
    asyncio.run(main())
