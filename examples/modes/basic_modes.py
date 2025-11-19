"""Basic example of agent modes.

Demonstrates how to:
- Register modes using decorators
- Enter/exit modes via context managers
- Stack modes for nested behavior
- Access and mutate mode state
- Execute handlers before `agent.call()` invocations
- Transition between modes programmatically
"""

import asyncio

from good_agent import Agent, ModeContext
from good_agent.messages import SystemMessage


async def main():
    # Create an agent
    agent = Agent(model="gpt-4o-mini")
    agent.messages.append(SystemMessage("You are a helpful assistant."))

    # Register a research mode
    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        """Deep research mode with specialized instructions."""
        ctx.add_system_message(
            "You are in research mode. Focus on finding accurate, "
            "authoritative sources and provide detailed citations."
        )
        ctx.state["handler_runs"] = ctx.state.get("handler_runs", 0) + 1

    # Register a summary mode
    @agent.modes("summary")
    async def summary_mode(ctx: ModeContext):
        """Concise summary mode."""
        ctx.add_system_message(
            "You are in summary mode. Provide concise, "
            "bullet-pointed summaries."
        )
        ctx.state.setdefault("summary_notes", []).append("summaries stay short")

    # Register a mode that transitions on its own
    @agent.modes("ideation")
    async def ideation_mode(ctx: ModeContext):
        """Brainstorm ideas before drafting a response."""
        ctx.add_system_message("List three approaches before writing a draft.")
        if ctx.state.get("ideas_ready"):
            return ctx.switch_mode("drafting")
        ctx.state["ideas_ready"] = True

    @agent.modes("drafting")
    async def drafting_mode(ctx: ModeContext):
        """Draft a final answer, then exit back to normal mode."""
        topic = ctx.state.get("topic", "the user's request")
        ctx.add_system_message(f"Drafting mode: write a polished summary about {topic}.")
        return ctx.exit_mode()

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

        # Demonstrate handler execution with a mocked LLM response
        print("\n=== Handler Execution Demo ===")
        with agent.mock("[mock] research output"):
            async with agent.modes["research"]:
                response = await agent.call("How do mode handlers run?")
                print(f"Assistant (mocked): {response.content}")
                print(f"Handler runs in research: {agent.modes.get_state('handler_runs')}")

        # Demonstrate automatic transitions between modes
        print("\n=== Mode Transition Demo ===")
        with agent.mock(
            agent.mock.create("Brainstorm complete", role="assistant"),
            agent.mock.create("Draft finalized", role="assistant"),
        ):
            await agent.enter_mode("ideation", topic="mode transitions 101")
            print(f"Current mode before calls: {agent.current_mode}")
            await agent.call("Prepare outline")
            await agent.call("Write draft")
            print(f"Current mode after transitions: {agent.current_mode}")
            if agent.current_mode:
                await agent.exit_mode()


if __name__ == "__main__":
    asyncio.run(main())
