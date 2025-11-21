"""Component-based tools for better organization."""

import asyncio

from good_agent import Agent, AgentComponent, tool


class MathComponent(AgentComponent):
    """Math operations component with state tracking."""

    def __init__(self):
        super().__init__()
        self.calculation_history: list[str] = []

    @tool
    def add(self, a: float, b: float) -> float:
        """Add two numbers."""
        result = a + b
        self.calculation_history.append(f"{a} + {b} = {result}")
        return result

    @tool
    def get_history(self) -> list[str]:
        """Get calculation history."""
        return self.calculation_history.copy()


async def main():
    """Demonstrate component-based tools."""
    # Usage
    math_component = MathComponent()
    async with Agent("Calculator", extensions=[math_component]) as agent:
        response = await agent.call("Add 5 and 3, then show me the history")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
