import asyncio
from good_agent import Agent, ModeContext, tool


# Research-specific tools
@tool
async def search_academic_papers(query: str) -> str:
    """Search academic databases for papers."""
    return f"Found 5 papers about {query}"


@tool
async def cite_source(url: str, title: str) -> str:
    """Add a citation to the research."""
    return f"Cited: {title} ({url})"


# Creative-specific tools
@tool
async def generate_character(name: str, traits: list[str]) -> str:
    """Generate a character profile."""
    return f"Character {name}: {', '.join(traits)}"


@tool
async def story_prompt(genre: str) -> str:
    """Generate a story prompt."""
    return f"Story prompt for {genre}: [generated prompt]"


async def main():
    async with Agent("Multi-tool assistant") as agent:

        @agent.modes("research")
        async def research_mode(ctx: ModeContext):
            """Research mode with academic tools."""
            ctx.add_system_message(
                "Research mode: Use search_academic_papers and cite_source tools."
            )

            # Context managers for tool registration are currently provided via
            # agent.context_manager.temporary_tools() or context manager on agent.tools
            # The example used agent.temporary_tools which might be a shortcut
            # that existed in older versions or planned.
            # Let's use the verified approach for now: registering tools on the fly

            # Register temporary tools
            await ctx.agent.tools.register_tool(search_academic_papers)
            await ctx.agent.tools.register_tool(cite_source)

            try:
                return await ctx.call()
            finally:
                # Cleanup tools (manual context management simulation)
                # In a real 'temporary_tools' context manager implementation, this would be automatic
                # For this example, we'll leave them as is or rely on mode exit cleanup if implemented
                pass

        @agent.modes("creative")
        async def creative_mode(ctx: ModeContext):
            """Creative mode with storytelling tools."""
            ctx.add_system_message(
                "Creative mode: Use generate_character and story_prompt tools."
            )

            # Register temporary tools
            await ctx.agent.tools.register_tool(generate_character)
            await ctx.agent.tools.register_tool(story_prompt)

            return await ctx.call()

        # Usage - tools are automatically available in each mode
        async with agent.modes["research"]:
            await agent.call("Research quantum computing applications")

        async with agent.modes["creative"]:
            await agent.call("Create a sci-fi story about quantum computers")


if __name__ == "__main__":
    asyncio.run(main())
