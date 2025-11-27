"""Tools that schedule mode switches for the next agent call."""

from __future__ import annotations

import asyncio

from good_agent import Agent, ModeContext, tool
from good_agent.messages import SystemMessage


@tool
async def enter_research_mode(agent: Agent) -> str:
    """Schedule research mode for the next response."""
    agent.modes.schedule_mode_switch("research")
    return "Will enter research mode after the current response."


@tool
async def exit_current_mode(agent: Agent) -> str:
    """Schedule exiting the current mode on the next call."""

    if not agent.current_mode:
        return "Not in any mode right now."

    agent.modes.schedule_mode_exit()
    return f"Will exit {agent.current_mode} mode after this response."


async def main() -> None:
    agent = Agent(
        tools=[enter_research_mode, exit_current_mode],
        model="gpt-4o-mini",
    )
    agent.messages.append(
        SystemMessage(
            "You are a helpful assistant who can switch modes when tools ask you to."
        )
    )

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        ctx.add_system_message("Research mode: cite authoritative sources.")
        ctx.state["tool_triggered"] = True

    async with agent:
        with agent.mock(
            agent.mock.create("Normal response", role="assistant"),
            agent.mock.create("Switched into research mode", role="assistant"),
            agent.mock.create("Back to normal", role="assistant"),
        ):
            print("=== Initial call (no modes) ===")
            response = await agent.call("Say hi")
            print(response.content)

            print("\n=== Tool schedules research mode ===")
            await enter_research_mode(_agent=agent)  # type: ignore[call-arg,misc]
            response = await agent.call("Need deep research next")
            print(response.content)
            print(f"Current mode: {agent.current_mode}")

            print("\n=== Tool schedules exit ===")
            await exit_current_mode(_agent=agent)  # type: ignore[call-arg,misc]
            response = await agent.call("Back to normal please")
            print(response.content)
            print(f"Current mode: {agent.current_mode}")


if __name__ == "__main__":
    asyncio.run(main())
