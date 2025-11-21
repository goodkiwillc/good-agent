import asyncio
from good_agent import Agent, ModeContext

async def main():
    async with Agent("You are a versatile assistant.") as agent:
        @agent.modes("research")
        async def research_mode(ctx: ModeContext):
            """Deep research mode with specialized instructions."""
            ctx.add_system_message(
                "You are in research mode. Focus on finding accurate, "
                "authoritative sources and provide detailed citations."
            )

            # Store mode-specific state
            ctx.state["research_depth"] = "comprehensive"
            ctx.state["sources_required"] = True

        @agent.modes("creative")
        async def creative_mode(ctx: ModeContext):
            """Creative writing mode with imaginative prompts."""
            ctx.add_system_message(
                "You are in creative mode. Be imaginative, expressive, "
                "and think outside the box. Use vivid language and storytelling."
            )

            ctx.state["creativity_level"] = "high"
            ctx.state["format_style"] = "narrative"

        # Normal mode - default behavior
        response = await agent.call("Tell me about quantum physics")
        print(f"Normal: {response.content}")

        # Research mode - specialized for deep investigation
        async with agent.modes["research"]:
            response = await agent.call("Tell me about quantum physics")
            print(f"Research: {response.content}")

            # Check current mode
            print(f"Current mode: {agent.current_mode}")  # "research"

        # Creative mode - specialized for imaginative responses
        async with agent.modes["creative"]:
            response = await agent.call("Tell me about quantum physics")
            print(f"Creative: {response.content}")

        # Back to normal mode
        print(f"Current mode: {agent.current_mode}")  # None

if __name__ == "__main__":
    asyncio.run(main())
