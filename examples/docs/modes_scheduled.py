import asyncio
from good_agent import Agent, tool
from good_agent.agent.config import Context

@tool
async def enter_research_mode(agent: Agent = Context()) -> str:
    """Schedule research mode for the next call."""
    agent.modes.schedule_mode_switch("research")
    return "Will enter research mode for the next response."

@tool
async def exit_current_mode(agent: Agent = Context()) -> str:
    """Schedule exiting current mode."""
    if not agent.current_mode:
        return "Not currently in any mode."

    agent.modes.schedule_mode_exit()
    return f"Will exit {agent.current_mode} mode after this response."

async def main():
    # Need to register research mode
    async with Agent("Assistant with mode control", tools=[enter_research_mode, exit_current_mode]) as agent:
        from good_agent import ModeContext
        @agent.modes("research")
        async def research_mode(ctx: ModeContext):
            ctx.add_system_message("Research mode active.")

        # Normal call
        response = await agent.call("Hello")
        print(f"Mode: {agent.current_mode}")  # None

        # Tool schedules research mode
        await enter_research_mode(agent=agent)

        # Next call will be in research mode
        response = await agent.call("Tell me about AI")
        print(f"Mode: {agent.current_mode}")  # "research"

        # Tool schedules mode exit
        await exit_current_mode(agent=agent)

        # Next call will be in normal mode
        response = await agent.call("Thanks!")
        print(f"Mode: {agent.current_mode}")  # None

if __name__ == "__main__":
    asyncio.run(main())
