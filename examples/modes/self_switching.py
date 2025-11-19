"""Demonstrate agents self-switching modes via tools and transitions."""

from __future__ import annotations

import asyncio

from good_agent import Agent, ModeContext, tool
from good_agent.agent.config import Context
from good_agent.messages import SystemMessage


@tool
async def enter_research_mode(
    agent: Agent = Context(),
    topic: str = Context("topic", default="today's topic"),
) -> str:
    """Schedule research mode for the next call with a topic parameter."""

    agent.modes.schedule_mode_switch("research", topic=topic)
    return f"Scheduled research mode for {topic}."


@tool
async def exit_mode_after_response(agent: Agent = Context()) -> str:
    """Exit whatever mode is currently active on the next call."""

    if not agent.current_mode:
        return "Not in a mode right now."
    agent.modes.schedule_mode_exit()
    return f"Will exit {agent.current_mode} mode after this response."


async def main() -> None:
    agent = Agent(
        tools=[enter_research_mode, exit_mode_after_response],
        model="gpt-4o-mini",
    )
    agent.messages.append(
        SystemMessage(
            "You are a helpful assistant who can switch modes using tools."
        )
    )

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        topic = ctx.state.get("topic", "the user's request")
        ctx.add_system_message(f"Research mode: dig deep into {topic} with citations.")

        # After one research call, automatically transition to writing
        if ctx.state.get("handoff_to_writing"):
            return ctx.switch_mode("writing", report_topic=topic)

        ctx.state["handoff_to_writing"] = True

    @agent.modes("writing")
    async def writing_mode(ctx: ModeContext):
        report_topic = ctx.state.get("report_topic", "the prior topic")
        ctx.add_system_message(
            f"Writing mode: produce a structured report about {report_topic}."
        )
        return ctx.exit_mode()

    async with agent:
        with agent.mock(
            agent.mock.create("General response", role="assistant"),
            agent.mock.create("Research response", role="assistant"),
            agent.mock.create("Drafted report", role="assistant"),
            agent.mock.create("Back to normal", role="assistant"),
        ):
            print("=== Initial call (no mode) ===")
            reply = await agent.call("Say hello")
            print(reply.content)

            print("\n=== Scheduling research mode via tool ===")
            await enter_research_mode(agent=agent, topic="renewable energy storage")
            reply = await agent.call("Take a closer look")
            print(reply.content)
            print(f"Current mode: {agent.current_mode}")
            print(f"Mode state: {agent.modes.get_state('topic')}")

            print("\n=== Automatic transition into writing mode ===")
            reply = await agent.call("Ready to summarize?")
            print(reply.content)
            print(f"Current mode after handoff: {agent.current_mode}")

            print("\n=== Exit mode via tool ===")
            await exit_mode_after_response(agent=agent)
            reply = await agent.call("Wrap up")
            print(reply.content)
            print(f"Current mode: {agent.current_mode}")


if __name__ == "__main__":
    asyncio.run(main())
