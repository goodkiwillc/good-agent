import asyncio

import pytest

from good_agent import Agent


@pytest.mark.asyncio
async def test_research_mode():
    """Test research mode behavior using v2 API."""
    agent = Agent("Test agent")

    @agent.modes("research")
    async def research_mode(agent: Agent):
        agent.prompt.append("Research mode active")
        agent.mode.state["research_active"] = True
        yield agent

    await agent.initialize()

    # Test mode registration
    assert "research" in agent.modes.list_modes()

    # Test mode context
    async with agent.mode("research"):
        # Test mode info
        info = agent.modes.get_info("research")
        assert info["name"] == "research"


@pytest.mark.asyncio
async def test_mode_transitions():
    """Test mode transition logic using v2 API."""
    agent = Agent("Test agent")
    transition_log = []

    @agent.modes("source")
    async def source_mode(agent: Agent):
        transition_log.append("source_entered")
        yield agent
        agent.modes.schedule_mode_switch("target")

    @agent.modes("target")
    async def target_mode(agent: Agent):
        transition_log.append("target_entered")
        yield agent
        agent.modes.schedule_mode_exit()

    await agent.initialize()

    # Mock the LLM to avoid actual calls
    with agent.mock("Test response"):
        async with agent.mode("source"):
            await agent.call("Test transition")

    # Verify transition sequence
    assert "source_entered" in transition_log
    assert "target_entered" in transition_log
    assert agent.mode.name is None  # Should exit back to normal


@pytest.mark.asyncio
async def test_mode_state_scoping():
    """Test state inheritance and scoping using v2 API."""
    agent = Agent("Test agent")

    @agent.modes("outer")
    async def outer_mode(agent: Agent):
        agent.mode.state["shared"] = "outer_value"
        agent.mode.state["outer_only"] = "outer"
        yield agent

    @agent.modes("inner")
    async def inner_mode(agent: Agent):
        # Should inherit outer state
        assert agent.mode.state.get("shared") == "outer_value"
        assert agent.mode.state.get("outer_only") == "outer"

        # Shadow shared state
        agent.mode.state["shared"] = "inner_value"
        agent.mode.state["inner_only"] = "inner"
        yield agent

    await agent.initialize()

    async with agent.mode("outer"):
        async with agent.mode("inner"):
            # Inner mode sees its own values
            assert agent.modes.get_state("shared") == "inner_value"
            assert agent.modes.get_state("inner_only") == "inner"

        # Back to outer - original values restored
        assert agent.modes.get_state("shared") == "outer_value"


async def main():
    # Skipping tests that depend on handler execution since we're not making calls
    # and we're not manually invoking handlers in this simplified example
    print("Tests skipped for doc example simplicity")


if __name__ == "__main__":
    asyncio.run(main())
