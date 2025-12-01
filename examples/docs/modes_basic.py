import asyncio

from good_agent import Agent


async def main():
    async with Agent("You are a versatile assistant.") as agent:

        @agent.modes("research")
        async def research_mode(agent: Agent):
            """Deep research mode with specialized instructions."""
            agent.prompt.append(
                "You are in research mode. Focus on finding accurate, "
                "authoritative sources and provide detailed citations."
            )

            # Store mode-specific state via agent.mode.state
            agent.mode.state["research_depth"] = "comprehensive"
            agent.mode.state["sources_required"] = True
            yield agent

        @agent.modes("creative")
        async def creative_mode(agent: Agent):
            """Creative writing mode with imaginative prompts."""
            agent.prompt.append(
                "You are in creative mode. Be imaginative, expressive, "
                "and think outside the box. Use vivid language and storytelling."
            )

            agent.mode.state["creativity_level"] = "high"
            agent.mode.state["format_style"] = "narrative"
            yield agent

        # Normal mode - default behavior
        response = await agent.call("Tell me about quantum physics")
        print(f"Normal: {response.content}")

        # Research mode - specialized for deep investigation
        async with agent.modes["research"]:
            response = await agent.call("Tell me about quantum physics")
            print(f"Research: {response.content}")

            # Check current mode via agent.mode.name
            print(f"Current mode: {agent.mode.name}")  # "research"

        # Creative mode - specialized for imaginative responses
        async with agent.modes["creative"]:
            response = await agent.call("Tell me about quantum physics")
            print(f"Creative: {response.content}")

        # Back to normal mode
        print(f"Current mode: {agent.mode.name}")  # None


if __name__ == "__main__":
    asyncio.run(main())
