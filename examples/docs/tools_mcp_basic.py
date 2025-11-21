"""Loading MCP servers for external tool integration."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate MCP server loading."""
    async with Agent(
        "Assistant with external tools",
        mcp_servers=[
            # Server names (must be in PATH)
            "filesystem",
            "brave-search",
            # Full server configurations
            {"name": "web", "command": "npx @modelcontextprotocol/server-web"},
            {"name": "git", "uri": "stdio://git-mcp-server"},
        ],
    ) as agent:
        # MCP tools are automatically available
        await agent.call("List files in the current directory")
        await agent.call("Search the web for Python news")


if __name__ == "__main__":
    asyncio.run(main())
