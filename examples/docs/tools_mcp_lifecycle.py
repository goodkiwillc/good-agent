"""MCP tool lifecycle management with automatic connection handling."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate MCP server lifecycle."""
    async with Agent("Assistant", mcp_servers=["filesystem"]) as agent:
        # Servers connect during agent initialization

        # Use MCP tools normally
        await agent.call("Create a new file called 'notes.txt'")

        # Servers disconnect automatically on context exit


if __name__ == "__main__":
    asyncio.run(main())
