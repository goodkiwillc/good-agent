"""Manual tool registration using ToolManager."""

import asyncio

from good_agent import tool
from good_agent.tools import ToolManager


@tool
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic math operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unknown operation: {operation}")


async def main():
    """Demonstrate manual tool registration."""
    # Direct registration with ToolManager
    manager = ToolManager()
    await manager.register_tool(calculate, name="math_calc")

    # Access registered tool
    tool_instance = manager["math_calc"]
    print(f"Registered tool: {tool_instance.name}")


if __name__ == "__main__":
    asyncio.run(main())
