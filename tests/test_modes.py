"""Tests for agent modes functionality."""

from __future__ import annotations


import pytest

from good_agent import Agent, ModeContext


@pytest.mark.asyncio
async def test_mode_registration():
    """Test mode registration via decorator."""
    agent = Agent("Test agent")

    @agent.modes("test-mode")
    async def test_mode_handler(ctx: ModeContext):
        return "test response"

    assert "test-mode" in agent.modes.list_modes()
    info = agent.modes.get_info("test-mode")
    assert info["name"] == "test-mode"


@pytest.mark.asyncio
async def test_mode_context_manager():
    """Test entering/exiting mode via context manager."""
    agent = Agent("Test agent")

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        return await ctx.call()

    async with agent:
        assert agent.current_mode is None

        async with agent.modes["research"] as researcher:
            assert researcher is agent
            assert agent.current_mode == "research"
            assert agent.in_mode("research")

        assert agent.current_mode is None
        assert not agent.in_mode("research")


@pytest.mark.asyncio
async def test_mode_stacking():
    """Test nested mode contexts."""
    agent = Agent("Test agent")

    @agent.modes("outer")
    async def outer_mode(ctx: ModeContext):
        ctx.state["outer_var"] = "outer"
        return await ctx.call()

    @agent.modes("inner")
    async def inner_mode(ctx: ModeContext):
        ctx.state["inner_var"] = "inner"
        # Should see outer_var
        assert ctx.state.get("outer_var") == "outer"
        return await ctx.call()

    async with agent:
        async with agent.modes["outer"]:
            assert agent.current_mode == "outer"
            assert agent.mode_stack == ["outer"]

            async with agent.modes["inner"]:
                assert agent.current_mode == "inner"
                assert agent.mode_stack == ["outer", "inner"]
                assert agent.in_mode("outer")
                assert agent.in_mode("inner")

            assert agent.current_mode == "outer"
            assert agent.mode_stack == ["outer"]
            assert not agent.in_mode("inner")


@pytest.mark.asyncio
async def test_scoped_state():
    """Test state scoping and shadowing."""
    agent = Agent("Test agent")

    @agent.modes("outer")
    async def outer_mode(ctx: ModeContext):
        ctx.state["x"] = "outer"
        ctx.state["y"] = "only-outer"
        return await ctx.call()

    @agent.modes("inner")
    async def inner_mode(ctx: ModeContext):
        # Read inherited state
        assert ctx.state.get("x") == "outer"
        assert ctx.state.get("y") == "only-outer"

        # Shadow outer state
        ctx.state["x"] = "inner"
        ctx.state["z"] = "only-inner"

        return await ctx.call()

    async with agent:
        async with agent.modes["outer"]:
            # Manually set state for testing
            agent.modes.set_state("x", "outer")
            agent.modes.set_state("y", "only-outer")

            # Outer state: x='outer', y='only-outer'
            assert agent.modes.get_state("x") == "outer"
            assert agent.modes.get_state("y") == "only-outer"

            async with agent.modes["inner"]:
                # Shadow outer state
                agent.modes.set_state("x", "inner")
                agent.modes.set_state("z", "only-inner")

                # Inner state (with shadowing)
                # x='inner' (shadowed), y='only-outer' (inherited), z='only-inner'
                assert agent.modes.get_state("x") == "inner"
                assert agent.modes.get_state("y") == "only-outer"
                assert agent.modes.get_state("z") == "only-inner"

            # Back to outer - shadow removed
            # x='outer' (restored), y='only-outer', z removed
            assert agent.modes.get_state("x") == "outer"
            assert agent.modes.get_state("y") == "only-outer"
            assert agent.modes.get_state("z") is None


@pytest.mark.asyncio
async def test_direct_mode_entry_exit():
    """Test direct mode entry/exit without context manager."""
    agent = Agent("Test agent")

    @agent.modes("test")
    async def test_mode(ctx: ModeContext):
        return await ctx.call()

    async with agent:
        # Enter mode directly
        await agent.modes.enter_mode("test")

        # Now in test mode
        assert agent.current_mode == "test"

        # Exit mode
        await agent.modes.exit_mode()

        # Back to no mode
        assert agent.current_mode is None


@pytest.mark.asyncio
async def test_mode_not_registered_error():
    """Test error when accessing unregistered mode."""
    agent = Agent("Test agent")

    async with agent:
        with pytest.raises(KeyError, match="not registered"):
            async with agent.modes["nonexistent"]:
                pass


@pytest.mark.asyncio
async def test_mode_idempotent_entry():
    """Test that entering same mode twice is idempotent."""
    agent = Agent("Test agent")

    @agent.modes("test")
    async def test_mode(ctx: ModeContext):
        return await ctx.call()

    async with agent:
        await agent.modes.enter_mode("test")
        assert agent.current_mode == "test"
        assert len(agent.mode_stack) == 1

        # Try to enter again - should be no-op
        await agent.modes.enter_mode("test")
        assert agent.current_mode == "test"
        assert len(agent.mode_stack) == 1


@pytest.mark.asyncio
async def test_mode_events():
    """Test that mode events can be registered (basic smoke test)."""
    agent = Agent("Test agent")

    # Just verify that event handlers can be registered
    # Full event integration testing will be done in dedicated event tests
    @agent.on("mode:entered")
    def on_entered(ctx):
        pass

    @agent.on("mode:exited")
    def on_exited(ctx):
        pass

    @agent.modes("test")
    async def test_mode(ctx: ModeContext):
        return await ctx.call()

    async with agent:
        # Just verify modes work
        async with agent.modes["test"]:
            assert agent.current_mode == "test"

        assert agent.current_mode is None


@pytest.mark.asyncio
async def test_mode_context_add_system_message():
    """Test adding system messages in mode context."""
    agent = Agent("Test agent", model="gpt-4o-mini")

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        ctx.add_system_message("You are in research mode. Focus on accuracy.")
        return None

    async with agent:
        with agent.mock("Mock response"):
            async with agent.modes["research"]:
                await agent.call("Trigger handler")

    system_messages = [m for m in agent.messages if m.role == "system"]
    assert system_messages
    assert any(
        "research mode" in str(m.content).lower() for m in system_messages if m.content
    )


@pytest.mark.asyncio
async def test_mode_list():
    """Test listing registered modes."""
    agent = Agent("Test agent")

    @agent.modes("mode1")
    async def mode1(ctx: ModeContext):
        pass

    @agent.modes("mode2")
    async def mode2(ctx: ModeContext):
        pass

    modes = agent.modes.list_modes()
    assert "mode1" in modes
    assert "mode2" in modes
    assert len(modes) == 2


@pytest.mark.asyncio
async def test_mode_info():
    """Test getting mode metadata."""
    agent = Agent("Test agent")

    @agent.modes("test")
    async def test_mode(ctx: ModeContext):
        """Test mode with description."""
        pass

    info = agent.modes.get_info("test")
    assert info["name"] == "test"
    assert "Test mode with description" in info["description"]
    assert info["handler"] is test_mode


@pytest.mark.asyncio
async def test_mode_handler_execution():
    """Mode handler should run before LLM call and update scoped state."""
    agent = Agent("Test agent")
    handler_runs: list[tuple[str, tuple[str, ...]]] = []

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        handler_runs.append((ctx.mode_name, tuple(ctx.mode_stack)))
        ctx.state["ran"] = ctx.state.get("ran", 0) + 1

    async with agent:
        with agent.mock("Mock response"):
            async with agent.modes["research"]:
                result = await agent.call("Hello")
                assert agent.modes.get_state("ran") == 1
                assert "Mock response" in str(result.content)
            assert agent.modes.get_state("ran") is None

    assert handler_runs == [("research", ("research",))]


@pytest.mark.asyncio
async def test_mode_transition_switch():
    """Handler can request switching to another mode before the call."""
    agent = Agent("Test agent")
    sequence: list[tuple[str, tuple[str, ...]]] = []

    @agent.modes("analysis")
    async def analysis_mode(ctx: ModeContext):
        sequence.append((ctx.mode_name, tuple(ctx.mode_stack)))
        return ctx.switch_mode("execution")

    @agent.modes("execution")
    async def execution_mode(ctx: ModeContext):
        sequence.append((ctx.mode_name, tuple(ctx.mode_stack)))
        ctx.state["done"] = True

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("analysis")
            await agent.call("start")
            assert agent.current_mode == "execution"
            assert agent.modes.get_state("done") is True
            await agent.modes.exit_mode()

    assert sequence == [
        ("analysis", ("analysis",)),
        ("execution", ("execution",)),
    ]


@pytest.mark.asyncio
async def test_mode_transition_exit():
    """Handler can exit to outer mode before continuing the call."""
    agent = Agent("Test agent")
    inner_runs: list[tuple[str, ...]] = []
    outer_runs: list[tuple[str, ...]] = []

    @agent.modes("outer")
    async def outer_mode(ctx: ModeContext):
        outer_runs.append(tuple(ctx.mode_stack))
        ctx.state["outer_counter"] = ctx.state.get("outer_counter", 0) + 1

    @agent.modes("inner")
    async def inner_mode(ctx: ModeContext):
        inner_runs.append(tuple(ctx.mode_stack))
        return ctx.exit_mode()

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("outer")
            await agent.modes.enter_mode("inner")
            await agent.call("trigger")
            assert agent.current_mode == "outer"
            assert agent.modes.get_state("outer_counter") == 1
            await agent.modes.exit_mode()

    assert inner_runs == [("outer", "inner")]
    assert outer_runs == [("outer",)]


@pytest.mark.asyncio
async def test_scheduled_mode_switch():
    """Scheduling a mode switch applies before the next call."""
    agent = Agent("Test agent")
    entries: list[str] = []

    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        entries.append(ctx.mode_name)
        ctx.state["entered"] = True

    async with agent:
        with agent.mock("ok"):
            agent.modes.schedule_mode_switch("research")
            await agent.call("next")
            assert agent.current_mode == "research"
            assert agent.modes.get_state("entered") is True
            await agent.modes.exit_mode()

    assert entries == ["research"]


@pytest.mark.asyncio
async def test_scheduled_mode_exit():
    """Scheduling an exit leaves the mode before the next call."""
    agent = Agent("Test agent")

    @agent.modes("focus")
    async def focus_mode(ctx: ModeContext):
        ctx.state["hits"] = ctx.state.get("hits", 0) + 1

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("focus")
            agent.modes.schedule_mode_exit()
            await agent.call("work")
            assert agent.current_mode is None


@pytest.mark.asyncio
async def test_mode_switch_before_call():
    """Pending switches happen before handlers for previous modes run."""
    agent = Agent("Test agent")
    events: list[str] = []

    @agent.modes("first")
    async def first_mode(ctx: ModeContext):
        events.append("first")

    @agent.modes("second")
    async def second_mode(ctx: ModeContext):
        events.append("second")

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("first")
            agent.modes.schedule_mode_switch("second")
            await agent.call("go")
            assert events == ["second"]
            assert agent.current_mode == "second"
            await agent.modes.exit_mode()


# ============================================================================
# Phase 1: Agent-Centric Handler Tests
# ============================================================================


@pytest.mark.asyncio
async def test_mode_accessor_properties():
    """Test ModeAccessor provides correct mode information via agent.mode."""
    agent = Agent("Test agent")

    @agent.modes("research")
    async def research_mode(agent_param: Agent):
        pass

    async with agent:
        # Outside mode - accessor still exists but name is None
        assert agent.mode.name is None
        assert agent.mode.stack == []

        async with agent.modes["research"]:
            # Inside mode - accessor shows current mode
            assert agent.mode.name == "research"
            assert agent.mode.stack == ["research"]
            assert agent.mode.in_mode("research")
            assert not agent.mode.in_mode("other")

        # Back outside
        assert agent.mode.name is None
        assert agent.mode.stack == []


@pytest.mark.asyncio
async def test_mode_accessor_state():
    """Test ModeAccessor state access via agent.mode.state."""
    agent = Agent("Test agent")

    @agent.modes("stateful")
    async def stateful_mode(agent_param: Agent):
        # Can access state via agent.mode.state
        agent_param.mode.state["key"] = "value"
        agent_param.mode.state["counter"] = 42

    async with agent:
        async with agent.modes["stateful"]:
            with agent.mock("ok"):
                await agent.call("test")

            # State is accessible
            assert agent.mode.state["key"] == "value"
            assert agent.mode.state["counter"] == 42

        # State is cleared after mode exit
        assert agent.mode.state.get("key") is None


@pytest.mark.asyncio
async def test_agent_centric_handler():
    """Test new-style agent-centric mode handler (agent: Agent parameter)."""
    agent = Agent("Test agent")
    handler_calls: list[str] = []

    @agent.modes("modern")
    async def modern_mode(agent_param: Agent):
        """Modern mode using agent-centric signature."""
        handler_calls.append(f"mode={agent_param.mode.name}")
        agent_param.mode.state["modern"] = True

    async with agent:
        with agent.mock("ok"):
            async with agent.modes["modern"]:
                await agent.call("test")
                assert agent.modes.get_state("modern") is True

    assert handler_calls == ["mode=modern"]


@pytest.mark.asyncio
async def test_agent_centric_handler_transition():
    """Test agent-centric handler can return ModeTransition."""
    agent = Agent("Test agent")
    sequence: list[str] = []

    @agent.modes("start")
    async def start_mode(agent_param: Agent):
        sequence.append("start")
        return agent_param.mode.switch("end")

    @agent.modes("end")
    async def end_mode(agent_param: Agent):
        sequence.append("end")
        agent_param.mode.state["done"] = True

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("start")
            await agent.call("go")
            assert agent.current_mode == "end"
            assert agent.modes.get_state("done") is True
            await agent.modes.exit_mode()

    assert sequence == ["start", "end"]


@pytest.mark.asyncio
async def test_legacy_handler_deprecation_warning():
    """Test that legacy ModeContext handlers emit deprecation warning."""
    import warnings

    agent = Agent("Test agent")

    @agent.modes("legacy")
    async def legacy_mode(ctx: ModeContext):
        ctx.state["ran"] = True

    async with agent:
        with agent.mock("ok"):
            async with agent.modes["legacy"]:
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    await agent.call("test")

                    # Should have deprecation warning
                    deprecation_warnings = [
                        x for x in w if issubclass(x.category, DeprecationWarning)
                    ]
                    assert len(deprecation_warnings) >= 1
                    assert "ModeContext" in str(deprecation_warnings[0].message)


@pytest.mark.asyncio
async def test_mixed_handler_styles():
    """Test mixing legacy and agent-centric handlers in stack."""
    agent = Agent("Test agent")
    calls: list[str] = []

    @agent.modes("outer_legacy")
    async def outer_legacy(ctx: ModeContext):
        calls.append(f"legacy:{ctx.mode_name}")
        ctx.state["legacy_ran"] = True

    @agent.modes("inner_modern")
    async def inner_modern(agent_param: Agent):
        calls.append(f"modern:{agent_param.mode.name}")
        agent_param.mode.state["modern_ran"] = True

    async with agent:
        with agent.mock("ok", "ok"):
            async with agent.modes["outer_legacy"]:
                await agent.call("first")
                assert agent.modes.get_state("legacy_ran") is True

                async with agent.modes["inner_modern"]:
                    await agent.call("second")
                    assert agent.modes.get_state("modern_ran") is True
                    # Can still see outer state
                    assert agent.modes.get_state("legacy_ran") is True

    assert "legacy:outer_legacy" in calls
    assert "modern:inner_modern" in calls
