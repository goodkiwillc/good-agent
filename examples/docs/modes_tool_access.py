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

            # Temporarily add research tools
            async with ctx.agent.temporary_tools([search_academic_papers, cite_source]):
                return await ctx.call()

        @agent.modes("creative")
        async def creative_mode(ctx: ModeContext):
            """Creative mode with storytelling tools."""
            ctx.add_system_message(
                "Creative mode: Use generate_character and story_prompt tools."
            )

            # Temporarily add creative tools
            async with ctx.agent.temporary_tools([generate_character, story_prompt]):
                return await ctx.call()

        # Usage - tools are automatically available in each mode
        async with agent.modes["research"]:
            await agent.call("Research quantum computing applications")

        async with agent.modes["creative"]:
            await agent.call("Create a sci-fi story about quantum computers")

if __name__ == "__main__":
    asyncio.run(main())
