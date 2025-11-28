"""Basic example of agent modes (v2 API).

Demonstrates how to:
- Register modes using decorators with agent: Agent parameter
- Enter/exit modes via context managers
- Stack modes for nested behavior
- Access and mutate mode state via agent.mode.state
- Execute handlers before `agent.call()` invocations
- Transition between modes programmatically
"""

import asyncio

from good_agent import Agent
from good_agent.messages import SystemMessage


async def main():
    # Create an agent
    agent = Agent(model="gpt-4o-mini")
    agent.messages.append(SystemMessage("You are a helpful assistant."))

    # Register a research mode - v2 API uses agent: Agent parameter
    @agent.modes("research")
    async def research_mode(agent: Agent):
        """Deep research mode with specialized instructions."""
        agent.prompt.append(
            "You are in research mode. Focus on finding accurate, "
            "authoritative sources and provide detailed citations."
        )
        agent.mode.state["handler_runs"] = agent.mode.state.get("handler_runs", 0) + 1

    # Register a summary mode
    @agent.modes("summary")
    async def summary_mode(agent: Agent):
        """Concise summary mode."""
        agent.prompt.append(
            "You are in summary mode. Provide concise, bullet-pointed summaries."
        )
        agent.mode.state.setdefault("summary_notes", []).append("summaries stay short")

    # Register a mode that transitions on its own
    @agent.modes("ideation")
    async def ideation_mode(agent: Agent):
        """Brainstorm ideas before drafting a response."""
        agent.prompt.append("List three approaches before writing a draft.")
        if agent.mode.state.get("ideas_ready"):
            return agent.mode.switch("drafting")
        agent.mode.state["ideas_ready"] = True

    @agent.modes("drafting")
    async def drafting_mode(agent: Agent):
        """Draft a final answer, then exit back to normal mode."""
        topic = agent.mode.state.get("topic", "the user's request")
        agent.prompt.append(f"Drafting mode: write a polished summary about {topic}.")
        return agent.mode.exit()

    async with agent:
        print("=== Normal Mode ===")
        print(f"Current mode: {agent.mode.name}")

        # Enter research mode
        print("\n=== Research Mode ===")
        async with agent.modes["research"]:
            print(f"Current mode: {agent.mode.name}")
            print(f"Mode stack: {agent.mode.stack}")

            # You can now make calls with research-specific behavior
            # response = await agent.call("Research quantum computing")
            # print(response.content)

            # Modes can be nested
            print("\n=== Nested: Research + Summary Mode ===")
            async with agent.modes["summary"]:
                print(f"Current mode: {agent.mode.name}")
                print(f"Mode stack: {agent.mode.stack}")
                print(f"In research mode: {agent.mode.in_mode('research')}")
                print(f"In summary mode: {agent.mode.in_mode('summary')}")

            print("\n=== Back to Research Mode ===")
            print(f"Current mode: {agent.mode.name}")
            print(f"Mode stack: {agent.mode.stack}")

        print("\n=== Back to Normal Mode ===")
        print(f"Current mode: {agent.mode.name}")

        # List all available modes
        print(f"\nAvailable modes: {agent.modes.list_modes()}")

        # Demonstrate handler execution with a mocked LLM response
        print("\n=== Handler Execution Demo ===")
        with agent.mock("[mock] research output"):
            async with agent.modes["research"]:
                response = await agent.call("How do mode handlers run?")
                print(f"Assistant (mocked): {response.content}")
                print(
                    f"Handler runs in research: {agent.modes.get_state('handler_runs')}"
                )

        # Demonstrate automatic transitions between modes
        print("\n=== Mode Transition Demo ===")
        with agent.mock(
            agent.mock.create("Brainstorm complete", role="assistant"),
            agent.mock.create("Draft finalized", role="assistant"),
        ):
            await agent.enter_mode("ideation", topic="mode transitions 101")
            print(f"Current mode before calls: {agent.mode.name}")
            await agent.call("Prepare outline")
            await agent.call("Write draft")
            print(f"Current mode after transitions: {agent.mode.name}")
            if agent.mode.name:
                await agent.exit_mode()


if __name__ == "__main__":
    asyncio.run(main())
