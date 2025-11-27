import asyncio

from good_agent import Agent, ModeContext, tool


@tool
async def enter_research_mode(agent: Agent) -> str:
    """Schedule research mode for the next call."""
    agent.modes.schedule_mode_switch("research")
    return "Will enter research mode for the next response."


@tool
async def exit_current_mode(agent: Agent) -> str:
    """Schedule exiting current mode."""
    if not agent.current_mode:
        return "Not currently in any mode."

    agent.modes.schedule_mode_exit()
    return f"Will exit {agent.current_mode} mode after this response."


async def main():
    # Need to register research mode
    async with Agent(
        "Assistant with mode control", tools=[enter_research_mode, exit_current_mode]
    ) as agent:

        @agent.modes("research")
        async def research_mode(ctx: ModeContext):
            ctx.add_system_message("Research mode active.")

        # Normal call
        await agent.call("Hello")
        print(f"Mode: {agent.current_mode}")  # None

        # Tool schedules research mode
        await enter_research_mode(_agent=agent)  # type: ignore[call-arg,misc]

        # Next call will be in research mode
        await agent.call("Tell me about AI")
        print(f"Mode: {agent.current_mode}")  # "research"

        # Tool schedules mode exit
        await exit_current_mode(_agent=agent)  # type: ignore[call-arg,misc]

        # Next call will be in normal mode
        await agent.call("Thanks!")
        print(f"Mode: {agent.current_mode}")  # None


if __name__ == "__main__":
    asyncio.run(main())
