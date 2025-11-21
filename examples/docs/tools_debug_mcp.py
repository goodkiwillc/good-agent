"""Debugging MCP server connections."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate debugging MCP server connections."""
    # Debug MCP server connections
    async with Agent(
        "MCP agent",
        mcp_servers=["filesystem"],
        debug=True,  # Enable debug logging
    ) as agent:
        # Check MCP server status
        if hasattr(agent.tools, "_mcp_client"):
            mcp_client = agent.tools._mcp_client
            print(f"MCP client available: {mcp_client}")
            if hasattr(mcp_client, "connected_servers"):
                print(f"MCP servers connected: {mcp_client.connected_servers}")
        else:
            print("No MCP client found")

        # List all available tools (including MCP tools)
        print(f"\nAvailable tools: {list(agent.tools.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
