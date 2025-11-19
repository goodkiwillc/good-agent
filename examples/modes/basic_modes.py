"""Basic example of agent modes.

Demonstrates how to:
- Register modes using decorators
- Enter/exit modes via context managers
- Stack modes for nested behavior
- Access mode state
"""

import asyncio

from good_agent import Agent, ModeContext


async def main():
    # Create an agent
    agent = Agent("You are a helpful assistant.", model="gpt-4o-mini")

    # Register a research mode
    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        """Deep research mode with specialized instructions."""
        ctx.add_system_message(
            "You are in research mode. Focus on finding accurate, "
            "authoritative sources and provide detailed citations."
        )
        return await ctx.call()

    # Register a summary mode
    @agent.modes("summary")
    async def summary_mode(ctx: ModeContext):
        """Concise summary mode."""
        ctx.add_system_message(
            "You are in summary mode. Provide concise, "
            "bullet-pointed summaries."
        )
        return await ctx.call()

    async with agent:
        print("=== Normal Mode ===")
        print(f"Current mode: {agent.current_mode}")

        # Enter research mode
        print("\n=== Research Mode ===")
        async with agent.modes["research"]:
            print(f"Current mode: {agent.current_mode}")
            print(f"Mode stack: {agent.mode_stack}")

            # You can now make calls with research-specific behavior
            # response = await agent.call("Research quantum computing")
            # print(response.content)

            # Modes can be nested
            print("\n=== Nested: Research + Summary Mode ===")
            async with agent.modes["summary"]:
                print(f"Current mode: {agent.current_mode}")
                print(f"Mode stack: {agent.mode_stack}")
                print(f"In research mode: {agent.in_mode('research')}")
                print(f"In summary mode: {agent.in_mode('summary')}")

            print("\n=== Back to Research Mode ===")
            print(f"Current mode: {agent.current_mode}")
            print(f"Mode stack: {agent.mode_stack}")

        print("\n=== Back to Normal Mode ===")
        print(f"Current mode: {agent.current_mode}")

        # List all available modes
        print(f"\nAvailable modes: {agent.modes.list_modes()}")


if __name__ == "__main__":
    asyncio.run(main())
