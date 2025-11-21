"""MCP server configuration with various options."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate MCP server configuration options."""
    mcp_servers = [
        # Simple string format
        "filesystem-server",
        # Dictionary with command
        {
            "name": "custom-server",
            "command": "python /path/to/server.py",
            "args": ["--config", "production"],
            "env": {"API_KEY": "secret"},
        },
        # URI-based connection
        {"name": "remote-server", "uri": "tcp://remote.example.com:8080"},
    ]

    async with Agent("MCP-enabled assistant", mcp_servers=mcp_servers) as agent:
        # All MCP tools are available alongside native tools
        response = await agent.call("What MCP tools are available?")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
