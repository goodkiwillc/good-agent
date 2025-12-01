import asyncio

from good_agent import Agent, tool


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
        async def research_mode(agent: Agent):
            """Research mode with academic tools."""
            agent.prompt.append(
                "Research mode: Use search_academic_papers and cite_source tools."
            )

            # Register temporary tools
            await agent.tools.register_tool(search_academic_papers)
            await agent.tools.register_tool(cite_source)
            yield agent

        @agent.modes("creative")
        async def creative_mode(agent: Agent):
            """Creative mode with storytelling tools."""
            agent.prompt.append(
                "Creative mode: Use generate_character and story_prompt tools."
            )

            # Register temporary tools
            await agent.tools.register_tool(generate_character)
            await agent.tools.register_tool(story_prompt)
            yield agent

        # Usage - tools are automatically available in each mode
        async with agent.modes["research"]:
            await agent.call("Research quantum computing applications")

        async with agent.modes["creative"]:
            await agent.call("Create a sci-fi story about quantum computers")


if __name__ == "__main__":
    asyncio.run(main())
