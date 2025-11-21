import pytest
import asyncio
from good_agent import Agent, ModeContext

@pytest.mark.asyncio
async def test_research_mode():
    """Test research mode behavior."""
    agent = Agent("Test agent")

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        ctx.add_system_message("Research mode active")
        ctx.state["research_active"] = True
        return await ctx.call()

    await agent.initialize()

    # Test mode registration
    assert "research" in agent.modes.list_modes()

    # Test mode context
    async with agent.modes["research"]:
        assert agent.current_mode == "research"
        assert agent.modes.get_state("research_active") == True

        # Test mode info
        info = agent.modes.get_info("research")
        assert info["name"] == "research"

@pytest.mark.asyncio
async def test_mode_transitions():
    """Test mode transition logic."""
    agent = Agent("Test agent")
    transition_log = []

    @agent.modes("source")
    async def source_mode(ctx: ModeContext):
        transition_log.append("source_entered")
        return ctx.switch_mode("target")

    @agent.modes("target")
    async def target_mode(ctx: ModeContext):
        transition_log.append("target_entered")
        return ctx.exit_mode()

    await agent.initialize()

    # Mock the LLM to avoid actual calls
    with agent.mock("Test response"):
        async with agent.modes["source"]:
            await agent.call("Test transition")

    # Verify transition sequence
    assert "source_entered" in transition_log
    assert "target_entered" in transition_log
    assert agent.current_mode is None  # Should exit back to normal

@pytest.mark.asyncio
async def test_mode_state_scoping():
    """Test state inheritance and scoping."""
    agent = Agent("Test agent")

    @agent.modes("outer")
    async def outer_mode(ctx: ModeContext):
        ctx.state["shared"] = "outer_value"
        ctx.state["outer_only"] = "outer"

    @agent.modes("inner")
    async def inner_mode(ctx: ModeContext):
        # Should inherit outer state
        assert ctx.state.get("shared") == "outer_value"
        assert ctx.state.get("outer_only") == "outer"

        # Shadow shared state
        ctx.state["shared"] = "inner_value"
        ctx.state["inner_only"] = "inner"

    await agent.initialize()

    async with agent.modes["outer"]:
        async with agent.modes["inner"]:
            # Inner mode sees its own values
            assert agent.modes.get_state("shared") == "inner_value"
            assert agent.modes.get_state("inner_only") == "inner"

        # Back to outer - original values restored
        assert agent.modes.get_state("shared") == "outer_value"
        assert "inner_only" not in agent.modes.get_all_state()

async def main():
    await test_research_mode()
    await test_mode_transitions()
    await test_mode_state_scoping()
    print("All tests passed")

if __name__ == "__main__":
    asyncio.run(main())
