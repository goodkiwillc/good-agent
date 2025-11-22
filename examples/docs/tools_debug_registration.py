"""Debugging tool registration issues."""

import asyncio

from good_agent import Agent, tool


@tool
def my_tool(value: str) -> str:
    """Example tool for debugging registration."""
    return f"Processed: {value}"


async def main():
    """Demonstrate how to debug tool registration."""
    # Check tool registration
    async with Agent("Assistant", tools=[my_tool]) as agent:
        # List available tools
        available_tools = list(agent.tools.keys())
        print("Available tools:", available_tools)

        # Check specific tool
        if "my_tool" in agent.tools:
            tool_instance = agent.tools["my_tool"]
            print("Tool name:", tool_instance.name)
            print("Tool description:", tool_instance.description)
        else:
            print("Tool 'my_tool' not found!")


if __name__ == "__main__":
    asyncio.run(main())
