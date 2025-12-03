"""Tests for agent modes functionality."""

from __future__ import annotations

import pytest
from good_agent import Agent, ModeContext


@pytest.mark.asyncio
async def test_mode_registration():
    """Test mode registration via decorator."""
    agent = Agent("Test agent")

    @agent.modes("test-mode")
    async def test_mode_handler(agent_param: Agent):
        yield agent_param

    assert "test-mode" in agent.modes.list_modes()
    info = agent.modes.get_info("test-mode")
    assert info["name"] == "test-mode"


@pytest.mark.asyncio
async def test_mode_context_manager():
    """Test entering/exiting mode via context manager."""
    agent = Agent("Test agent")

    @agent.modes("research")
    async def research_mode(agent_param: Agent):
        yield agent_param

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
    async def outer_mode(agent_param: Agent):
        agent_param.mode.state["outer_var"] = "outer"
        yield agent_param

    @agent.modes("inner")
    async def inner_mode(agent_param: Agent):
        agent_param.mode.state["inner_var"] = "inner"
        # Should see outer_var
        assert agent_param.mode.state.get("outer_var") == "outer"
        yield agent_param

    async with agent, agent.modes["outer"]:
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
    async def outer_mode(agent_param: Agent):
        agent_param.mode.state["x"] = "outer"
        agent_param.mode.state["y"] = "only-outer"
        yield agent_param

    @agent.modes("inner")
    async def inner_mode(agent_param: Agent):
        # Read inherited state
        assert agent_param.mode.state.get("x") == "outer"
        assert agent_param.mode.state.get("y") == "only-outer"

        # Shadow outer state
        agent_param.mode.state["x"] = "inner"
        agent_param.mode.state["z"] = "only-inner"

        yield agent_param

    async with agent, agent.modes["outer"]:
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
    async def test_mode(agent_param: Agent):
        yield agent_param

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
    async def test_mode(agent_param: Agent):
        yield agent_param

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
    async def test_mode(agent_param: Agent):
        yield agent_param

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
    async def research_mode(agent_param: Agent):
        # Use agent.append() to add system message to conversation
        agent_param.append("You are in research mode. Focus on accuracy.", role="system")
        yield agent_param

    async with agent:
        with agent.mock("Mock response"):
            async with agent.modes["research"]:
                await agent.call("Trigger handler")

    system_messages = [m for m in agent.messages if m.role == "system"]
    assert system_messages
    assert any("research mode" in str(m.content).lower() for m in system_messages if m.content)


@pytest.mark.asyncio
async def test_mode_list():
    """Test listing registered modes."""
    agent = Agent("Test agent")

    @agent.modes("mode1")
    async def mode1(agent_param: Agent):
        yield agent_param

    @agent.modes("mode2")
    async def mode2(agent_param: Agent):
        yield agent_param

    modes = agent.modes.list_modes()
    assert "mode1" in modes
    assert "mode2" in modes
    assert len(modes) == 2


@pytest.mark.asyncio
async def test_mode_info():
    """Test getting mode metadata."""
    agent = Agent("Test agent")

    @agent.modes("test")
    async def test_mode(agent_param: Agent):
        """Test mode with description."""
        yield agent_param

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
    async def research_mode(agent_param: Agent):
        assert agent_param.mode.name is not None
        handler_runs.append((agent_param.mode.name, tuple(agent_param.mode.stack)))
        agent_param.mode.state["ran"] = agent_param.mode.state.get("ran", 0) + 1
        yield agent_param

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
    """Handler can request switching to another mode via schedule_mode_switch."""
    agent = Agent("Test agent")
    sequence: list[tuple[str, tuple[str, ...]]] = []

    @agent.modes("analysis")
    async def analysis_mode(agent_param: Agent):
        assert agent_param.mode.name is not None
        sequence.append((agent_param.mode.name, tuple(agent_param.mode.stack)))
        # With generators, use schedule_mode_switch instead of mode.switch()
        agent_param.modes.schedule_mode_switch("execution")
        yield agent_param

    @agent.modes("execution")
    async def execution_mode(agent_param: Agent):
        assert agent_param.mode.name is not None
        sequence.append((agent_param.mode.name, tuple(agent_param.mode.stack)))
        agent_param.mode.state["done"] = True
        yield agent_param

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
    """Handler can exit to outer mode via schedule_mode_exit."""
    agent = Agent("Test agent")
    inner_runs: list[tuple[str, ...]] = []
    outer_runs: list[tuple[str, ...]] = []

    @agent.modes("outer")
    async def outer_mode(agent_param: Agent):
        outer_runs.append(tuple(agent_param.mode.stack))
        agent_param.mode.state["outer_counter"] = agent_param.mode.state.get("outer_counter", 0) + 1
        yield agent_param

    @agent.modes("inner")
    async def inner_mode(agent_param: Agent):
        inner_runs.append(tuple(agent_param.mode.stack))
        # With generators, use schedule_mode_exit instead of mode.exit()
        agent_param.modes.schedule_mode_exit()
        yield agent_param

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
    async def research_mode(agent_param: Agent):
        assert agent_param.mode.name is not None
        entries.append(agent_param.mode.name)
        agent_param.mode.state["entered"] = True
        yield agent_param

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
    async def focus_mode(agent_param: Agent):
        agent_param.mode.state["hits"] = agent_param.mode.state.get("hits", 0) + 1
        yield agent_param

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("focus")
            agent.modes.schedule_mode_exit()
            await agent.call("work")
            assert agent.current_mode is None


@pytest.mark.asyncio
async def test_mode_switch_before_call():
    """Pending switches apply during call; with generators, both setups run."""
    agent = Agent("Test agent")
    events: list[str] = []

    @agent.modes("first")
    async def first_mode(agent_param: Agent):
        events.append("first")
        yield agent_param

    @agent.modes("second")
    async def second_mode(agent_param: Agent):
        events.append("second")
        yield agent_param

    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("first")
            # With generators, first_mode setup has already run at entry
            assert events == ["first"]
            agent.modes.schedule_mode_switch("second")
            await agent.call("go")
            # Switch applied during call - second_mode setup runs
            assert events == ["first", "second"]
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
        yield agent_param

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
        yield agent_param

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
        yield agent_param

    async with agent:
        with agent.mock("ok"):
            async with agent.modes["modern"]:
                await agent.call("test")
                assert agent.modes.get_state("modern") is True

    assert handler_calls == ["mode=modern"]


@pytest.mark.asyncio
async def test_agent_centric_handler_transition():
    """Test agent-centric handler can schedule mode transition."""
    agent = Agent("Test agent")
    sequence: list[str] = []

    @agent.modes("start")
    async def start_mode(agent_param: Agent):
        sequence.append("start")
        # With generators, use schedule_mode_switch instead of mode.switch()
        agent_param.modes.schedule_mode_switch("end")
        yield agent_param

    @agent.modes("end")
    async def end_mode(agent_param: Agent):
        sequence.append("end")
        agent_param.mode.state["done"] = True
        yield agent_param

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
        yield ctx.agent

    async with agent:
        with agent.mock("ok"):
            # Capture warnings at mode entry, where the deprecation is emitted
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                async with agent.modes["legacy"]:
                    await agent.call("test")

                # Should have deprecation warning
                deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
                assert len(deprecation_warnings) >= 1
                assert "ModeContext" in str(deprecation_warnings[0].message)


@pytest.mark.asyncio
async def test_mixed_handler_styles():
    """Test mixing multiple agent-centric handlers in stack."""
    agent = Agent("Test agent")
    calls: list[str] = []

    @agent.modes("outer")
    async def outer_mode(agent_param: Agent):
        calls.append(f"outer:{agent_param.mode.name}")
        agent_param.mode.state["outer_ran"] = True
        yield agent_param

    @agent.modes("inner")
    async def inner_mode(agent_param: Agent):
        calls.append(f"inner:{agent_param.mode.name}")
        agent_param.mode.state["inner_ran"] = True
        yield agent_param

    async with agent:
        with agent.mock("ok", "ok"):
            async with agent.modes["outer"]:
                await agent.call("first")
                assert agent.modes.get_state("outer_ran") is True

                async with agent.modes["inner"]:
                    await agent.call("second")
                    assert agent.modes.get_state("inner_ran") is True
                    # Can still see outer state
                    assert agent.modes.get_state("outer_ran") is True

    assert "outer:outer" in calls
    assert "inner:inner" in calls


# =============================================================================
# Phase 2: SystemPromptManager Tests
# =============================================================================


@pytest.mark.asyncio
async def test_system_prompt_manager_basic():
    """Test basic append/prepend/sections functionality."""
    agent = Agent("Base system prompt")

    # Test append
    agent.prompt.append("Appended content")
    assert agent.prompt.has_modifications
    assert len(agent.prompt._appends) == 1

    # Test prepend
    agent.prompt.prepend("Prepended content")
    assert len(agent.prompt._prepends) == 1

    # Test sections
    agent.prompt.sections["mode"] = "Research mode"
    assert "mode" in agent.prompt.sections
    assert agent.prompt.sections["mode"] == "Research mode"

    # Test render
    rendered = agent.prompt.render()
    assert "Prepended content" in rendered
    assert "Base system prompt" in rendered
    assert "Research mode" in rendered
    assert "Appended content" in rendered

    # Verify order: prepends, base, sections, appends
    assert rendered.index("Prepended content") < rendered.index("Base system prompt")
    assert rendered.index("Base system prompt") < rendered.index("Research mode")
    assert rendered.index("Research mode") < rendered.index("Appended content")


@pytest.mark.asyncio
async def test_system_prompt_manager_mode_restore():
    """Test that system prompt changes are restored on mode exit.

    Note: Mode handlers run during agent.call(), so we test the
    snapshot/restore mechanism directly by modifying prompt in the mode.
    """
    agent = Agent("Base prompt")

    @agent.modes("research")
    async def research_mode(agent_param: Agent):
        yield agent_param  # Handler for mode registration

    async with agent:
        # Verify no modifications before mode
        assert not agent.prompt.has_modifications

        async with agent.modes["research"]:
            # Manually add modifications while in mode
            agent.prompt.append("Research-specific instruction")
            agent.prompt.sections["context"] = "Research context"
            assert agent.prompt.has_modifications

        # After exiting mode, modifications should be restored
        assert not agent.prompt.has_modifications
        assert len(agent.prompt._appends) == 0
        assert len(agent.prompt.sections) == 0


@pytest.mark.asyncio
async def test_system_prompt_manager_persist():
    """Test persist=True survives mode exit."""
    agent = Agent("Base prompt")

    @agent.modes("research")
    async def research_mode(agent_param: Agent):
        yield agent_param  # Handler for mode registration

    async with agent:
        async with agent.modes["research"]:
            # Add modifications while in mode
            agent.prompt.append("Temporary change")
            agent.prompt.append("Permanent change", persist=True)
            agent.prompt.sections["temp"] = "Temporary section"
            agent.prompt.set_section("perm", "Permanent section", persist=True)

            assert len(agent.prompt._appends) == 2
            assert len(agent.prompt.sections) == 2

        # After mode exit: only persistent changes remain
        assert len(agent.prompt._appends) == 1
        assert agent.prompt._appends[0].content == "Permanent change"
        assert len(agent.prompt.sections) == 1
        assert "perm" in agent.prompt.sections


@pytest.mark.asyncio
async def test_system_prompt_manager_nested_modes():
    """Test system prompt snapshot/restore with nested modes."""
    agent = Agent("Base prompt")

    @agent.modes("outer")
    async def outer_mode(agent_param: Agent):
        yield agent_param

    @agent.modes("inner")
    async def inner_mode(agent_param: Agent):
        yield agent_param

    async with agent:
        async with agent.modes["outer"]:
            # Add content while in outer mode
            agent.prompt.append("Outer content")
            outer_rendered = agent.prompt.render()
            assert "Outer content" in outer_rendered
            assert "Inner content" not in outer_rendered

            async with agent.modes["inner"]:
                # Add content while in inner mode
                agent.prompt.append("Inner content")
                inner_rendered = agent.prompt.render()
                assert "Outer content" in inner_rendered
                assert "Inner content" in inner_rendered

            # After inner exit, inner content gone but outer remains
            after_inner = agent.prompt.render()
            assert "Outer content" in after_inner
            assert "Inner content" not in after_inner

        # After outer exit, all content gone
        after_outer = agent.prompt.render()
        assert "Outer content" not in after_outer
        assert "Inner content" not in after_outer


@pytest.mark.asyncio
async def test_system_prompt_manager_clear():
    """Test clearing system prompt modifications."""
    agent = Agent("Base prompt")

    agent.prompt.append("Content 1")
    agent.prompt.append("Content 2", persist=True)
    agent.prompt.sections["a"] = "Section A"

    # Clear non-persistent
    agent.prompt.clear()
    assert len(agent.prompt._appends) == 1  # Only persistent remains
    assert agent.prompt._appends[0].content == "Content 2"
    assert len(agent.prompt.sections) == 0

    # Clear all including persistent
    agent.prompt.clear(include_persistent=True)
    assert len(agent.prompt._appends) == 0


@pytest.mark.asyncio
async def test_system_prompt_manager_sections_view():
    """Test SectionsView dict-like behavior."""
    agent = Agent("Base prompt")

    # Test setitem/getitem
    agent.prompt.sections["mode"] = "Research"
    assert agent.prompt.sections["mode"] == "Research"

    # Test delitem
    del agent.prompt.sections["mode"]
    assert "mode" not in agent.prompt.sections

    # Test KeyError on missing
    with pytest.raises(KeyError):
        _ = agent.prompt.sections["nonexistent"]

    # Test iteration
    agent.prompt.sections["a"] = "A"
    agent.prompt.sections["b"] = "B"
    assert list(agent.prompt.sections) == ["a", "b"]
    assert len(agent.prompt.sections) == 2


# =============================================================================
# Phase 3: Isolation Modes Tests
# =============================================================================


@pytest.mark.asyncio
async def test_isolation_none_default():
    """Test isolation='none' (default) shares all state."""

    agent = Agent("Test agent")

    @agent.modes("shared")
    async def shared_mode(agent: Agent):
        # Mode has isolation=none by default
        yield agent

    info = agent.modes.get_info("shared")
    assert info["isolation"] == "NONE"

    async with agent:
        # Add a message before mode
        agent.append("Before mode")
        initial_count = len(agent.messages)

        async with agent.modes["shared"]:
            # Add message in mode
            agent.append("During mode")
            assert len(agent.messages) == initial_count + 1

        # Message persists after mode exit (isolation=none)
        assert len(agent.messages) == initial_count + 1
        assert any("During mode" in str(m.content) for m in agent.messages)


@pytest.mark.asyncio
async def test_isolation_string_parameter():
    """Test isolation level can be specified as string."""
    agent = Agent("Test agent")

    @agent.modes("fork_mode", isolation="fork")
    async def fork_mode_handler(agent: Agent):
        yield agent

    @agent.modes("thread_mode", isolation="thread")
    async def thread_mode_handler(agent: Agent):
        yield agent

    @agent.modes("config_mode", isolation="config")
    async def config_mode_handler(agent: Agent):
        yield agent

    assert agent.modes.get_info("fork_mode")["isolation"] == "FORK"
    assert agent.modes.get_info("thread_mode")["isolation"] == "THREAD"
    assert agent.modes.get_info("config_mode")["isolation"] == "CONFIG"


@pytest.mark.asyncio
async def test_isolation_invalid_string():
    """Test invalid isolation string raises ValueError."""
    agent = Agent("Test agent")

    with pytest.raises(ValueError, match="Invalid isolation level"):

        @agent.modes("bad_mode", isolation="invalid")
        async def bad_mode(agent: Agent):
            yield agent


@pytest.mark.asyncio
async def test_isolation_hierarchy_validation():
    """Test child mode cannot be less isolated than parent."""
    from good_agent.agent.modes import IsolationLevel

    agent = Agent("Test agent")

    @agent.modes("outer_fork", isolation=IsolationLevel.FORK)
    async def outer_fork(agent: Agent):
        yield agent

    @agent.modes("inner_none", isolation=IsolationLevel.NONE)
    async def inner_none(agent: Agent):
        yield agent

    async with agent, agent.modes["outer_fork"]:
        # Attempting to enter a less isolated mode should fail
        with pytest.raises(ValueError, match="less restrictive"):
            async with agent.modes["inner_none"]:
                pass


@pytest.mark.asyncio
async def test_isolation_hierarchy_valid_increase():
    """Test child mode can be more isolated than parent."""
    from good_agent.agent.modes import IsolationLevel

    agent = Agent("Test agent")

    @agent.modes("outer_none", isolation=IsolationLevel.NONE)
    async def outer_none(agent: Agent):
        yield agent

    @agent.modes("inner_fork", isolation=IsolationLevel.FORK)
    async def inner_fork(agent: Agent):
        yield agent

    async with agent, agent.modes["outer_none"]:
        # More isolated mode is allowed
        async with agent.modes["inner_fork"]:
            assert agent.mode.stack == ["outer_none", "inner_fork"]


@pytest.mark.asyncio
async def test_isolation_fork_messages_restored():
    """Test fork isolation restores messages on exit."""
    from good_agent.agent.modes import IsolationLevel

    agent = Agent("Test agent")

    @agent.modes("sandbox", isolation=IsolationLevel.FORK)
    async def sandbox_mode(agent: Agent):
        yield agent

    async with agent:
        # Add message before mode
        agent.append("Original message")
        original_count = len(agent.messages)

        async with agent.modes["sandbox"]:
            # Add messages in sandbox
            agent.append("Sandbox message 1")
            agent.append("Sandbox message 2")
            assert len(agent.messages) == original_count + 2

        # Fork isolation: all changes discarded
        assert len(agent.messages) == original_count
        assert not any("Sandbox" in str(m.content) for m in agent.messages)


@pytest.mark.asyncio
async def test_isolation_thread_keeps_new_messages():
    """Test thread isolation keeps new messages but restores original."""
    from good_agent.agent.modes import IsolationLevel

    agent = Agent("Test agent")

    @agent.modes("thread_mode", isolation=IsolationLevel.THREAD)
    async def thread_mode(agent: Agent):
        yield agent

    async with agent:
        # Add messages before mode
        agent.append("Original 1")
        agent.append("Original 2")
        original_count = len(agent.messages)

        async with agent.modes["thread_mode"]:
            # Add new message
            agent.append("New message in thread")
            # Thread mode should have original + new
            assert len(agent.messages) == original_count + 1

        # After exit: original messages preserved + new messages kept
        assert len(agent.messages) == original_count + 1
        assert any("New message in thread" in str(m.content) for m in agent.messages)


@pytest.mark.asyncio
async def test_isolation_level_enum_values():
    """Test IsolationLevel enum has correct ordering."""
    from good_agent.agent.modes import IsolationLevel

    # Verify ordering: NONE < CONFIG < THREAD < FORK
    assert IsolationLevel.NONE < IsolationLevel.CONFIG
    assert IsolationLevel.CONFIG < IsolationLevel.THREAD
    assert IsolationLevel.THREAD < IsolationLevel.FORK

    # Verify values
    assert IsolationLevel.NONE == 0
    assert IsolationLevel.CONFIG == 1
    assert IsolationLevel.THREAD == 2
    assert IsolationLevel.FORK == 3


@pytest.mark.asyncio
async def test_isolation_config_restores_tools():
    """Test config isolation restores tool state on exit."""
    from good_agent.agent.modes import IsolationLevel
    from good_agent.tools import ToolManager, tool

    @tool
    def original_tool() -> str:
        """Original tool."""
        return "original"

    @tool
    def mode_tool() -> str:
        """Tool added in mode."""
        return "mode"

    agent = Agent("Test agent", tools=[original_tool])

    @agent.modes("config_isolated", isolation=IsolationLevel.CONFIG)
    async def config_mode(agent: Agent):
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]
        original_tools = set(tool_manager._tools.keys())
        assert "original_tool" in original_tools

        async with agent.modes["config_isolated"]:
            # Register a new tool in mode
            await tool_manager.register_tool(mode_tool)
            assert "mode_tool" in tool_manager._tools

        # After exit, tool state should be restored
        # Note: CONFIG isolation restores tool state
        restored_tools = set(tool_manager._tools.keys())
        assert "mode_tool" not in restored_tools
        assert "original_tool" in restored_tools


# =============================================================================
# Phase 4: Agent-Invoked Modes Tests
# =============================================================================


@pytest.mark.asyncio
async def test_invokable_generates_tool():
    """Test invokable=True generates a tool for mode switching."""
    from good_agent.tools import ToolManager

    agent = Agent("Test agent")

    @agent.modes("research", invokable=True)
    async def research_mode(agent: Agent):
        """Enter research mode for deep investigation."""
        agent.mode.state["in_research"] = True
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]

        # Tool should be registered with default name
        assert "enter_research" in tool_manager._tools

        # Mode info should reflect invokable settings
        info = agent.modes.get_info("research")
        assert info["invokable"] is True
        assert info["tool_name"] == "enter_research"


@pytest.mark.asyncio
async def test_invokable_custom_tool_name():
    """Test custom tool_name parameter for invokable modes."""
    from good_agent.tools import ToolManager

    agent = Agent("Test agent")

    @agent.modes("analysis", invokable=True, tool_name="start_analysis")
    async def analysis_mode(agent: Agent):
        """Begin analysis mode."""
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]

        # Custom tool name should be used
        assert "start_analysis" in tool_manager._tools
        assert "enter_analysis_mode" not in tool_manager._tools

        # Mode info should have custom name
        info = agent.modes.get_info("analysis")
        assert info["tool_name"] == "start_analysis"


@pytest.mark.asyncio
async def test_invokable_tool_schedules_switch():
    """Test generated tool schedules mode switch for next call."""
    from good_agent.tools import ToolManager

    agent = Agent("Test agent")

    @agent.modes("planning", invokable=True)
    async def planning_mode(agent: Agent):
        """Enter planning mode."""
        agent.mode.state["planning_active"] = True
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]

        # Get the generated tool
        tool = tool_manager["enter_planning"]

        # Call the tool directly
        result = await tool()
        assert "Entering planning mode" in result.response

        # Mode switch should be scheduled, not immediate
        assert agent.current_mode is None
        assert agent.modes._pending_mode_switch == ("planning", {})

        # Apply scheduled changes (happens at next call)
        with agent.mock("ok"):
            await agent.call("test")

        # Now mode should be active
        assert agent.current_mode == "planning"
        assert agent.modes.get_state("planning_active") is True


@pytest.mark.asyncio
async def test_invokable_tool_description():
    """Test tool description is extracted from handler docstring."""
    from good_agent.tools import ToolManager

    agent = Agent("Test agent")

    @agent.modes("deep_dive", invokable=True)
    async def deep_dive_mode(agent: Agent):
        """Perform deep analysis on complex topics.

        This mode focuses on thorough investigation.
        """
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]
        tool = tool_manager["enter_deep_dive"]

        # First line of docstring should be the description
        assert "Perform deep analysis on complex topics" in tool.description


@pytest.mark.asyncio
async def test_invokable_no_docstring():
    """Test default description when handler has no docstring."""
    from good_agent.tools import ToolManager

    agent = Agent("Test agent")

    @agent.modes("quick", invokable=True)
    async def quick_mode(agent: Agent):
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]
        tool = tool_manager["enter_quick"]

        # Default description should be used
        assert "Enter quick mode" in tool.description


@pytest.mark.asyncio
async def test_non_invokable_no_tool():
    """Test non-invokable modes don't generate tools."""
    from good_agent.tools import ToolManager

    agent = Agent("Test agent")

    @agent.modes("private")
    async def private_mode(agent: Agent):
        """Private mode not accessible to agent."""
        yield agent

    async with agent:
        tool_manager = agent[ToolManager]

        # No tool should be generated
        assert "enter_private_mode" not in tool_manager._tools

        # Mode info should reflect non-invokable
        info = agent.modes.get_info("private")
        assert info["invokable"] is False
        assert info["tool_name"] is None


# =============================================================================
# Phase 5: Standalone Modes Tests
# =============================================================================


@pytest.mark.asyncio
async def test_standalone_mode_decorator():
    """Test @mode() decorator creates StandaloneMode."""
    from good_agent.agent.modes import StandaloneMode, mode

    @mode("research")
    async def research_mode(agent: Agent):
        """Research mode for investigation."""
        agent.mode.state["researching"] = True
        yield agent

    # Decorator returns StandaloneMode
    assert isinstance(research_mode, StandaloneMode)
    assert research_mode.name == "research"
    assert research_mode.handler is not None
    assert "Research mode" in (research_mode.handler.__doc__ or "")


@pytest.mark.asyncio
async def test_standalone_mode_with_options():
    """Test @mode() decorator with isolation and invokable options."""
    from good_agent.agent.modes import IsolationLevel, StandaloneMode, mode

    @mode("sandbox", isolation="fork", invokable=True, tool_name="start_sandbox")
    async def sandbox_mode(agent: Agent):
        """Sandbox mode with isolation."""
        yield agent

    assert isinstance(sandbox_mode, StandaloneMode)
    assert sandbox_mode.name == "sandbox"
    assert sandbox_mode.isolation == IsolationLevel.FORK
    assert sandbox_mode.invokable is True
    assert sandbox_mode.tool_name == "start_sandbox"


@pytest.mark.asyncio
async def test_modes_register_standalone():
    """Test agent.modes.register() with StandaloneMode."""
    from good_agent.agent.modes import mode

    @mode("analysis")
    async def analysis_mode(agent: Agent):
        """Analysis mode."""
        agent.mode.state["analyzing"] = True
        yield agent

    agent = Agent("Test agent")

    # Register standalone mode
    agent.modes.register(analysis_mode)

    # Mode should be registered
    assert "analysis" in agent.modes.list_modes()

    async with agent, agent.modes["analysis"]:
        with agent.mock("ok"):
            await agent.call("test")
        assert agent.modes.get_state("analyzing") is True


@pytest.mark.asyncio
async def test_modes_register_raw_handler():
    """Test agent.modes.register() with raw handler function."""
    agent = Agent("Test agent")

    async def my_handler(agent: Agent):
        """My custom handler."""
        agent.mode.state["custom"] = True
        yield agent

    # Register with explicit name
    agent.modes.register(my_handler, name="custom_mode")

    assert "custom_mode" in agent.modes.list_modes()

    async with agent, agent.modes["custom_mode"]:
        with agent.mock("ok"):
            await agent.call("test")
        assert agent.modes.get_state("custom") is True


@pytest.mark.asyncio
async def test_modes_register_raw_handler_requires_name():
    """Test agent.modes.register() raises error without name for raw handler."""
    agent = Agent("Test agent")

    async def anonymous_handler(agent: Agent):
        yield agent

    # Raw handler without @mode decorator requires explicit name
    with pytest.raises(ValueError, match="name is required"):
        agent.modes.register(anonymous_handler)


@pytest.mark.asyncio
async def test_agent_constructor_with_modes():
    """Test Agent(modes=[...]) constructor parameter."""
    from good_agent.agent.modes import mode

    @mode("research", invokable=True)
    async def research_mode(agent: Agent):
        """Research mode."""
        agent.mode.state["in_research"] = True
        yield agent

    @mode("writing")
    async def writing_mode(agent: Agent):
        """Writing mode."""
        agent.mode.state["in_writing"] = True
        yield agent

    # Pass modes to constructor
    agent = Agent("Test agent", modes=[research_mode, writing_mode])

    # Both modes should be registered
    assert "research" in agent.modes.list_modes()
    assert "writing" in agent.modes.list_modes()

    # Invokable mode should have tool
    from good_agent.tools import ToolManager

    async with agent:
        tool_manager = agent[ToolManager]
        assert "enter_research" in tool_manager._tools


@pytest.mark.asyncio
async def test_standalone_mode_with_register_invokable():
    """Test registering invokable standalone mode generates tool."""
    from good_agent.agent.modes import mode
    from good_agent.tools import ToolManager

    @mode("planning", invokable=True)
    async def planning_mode(agent: Agent):
        """Enter planning mode."""
        agent.mode.state["planning"] = True
        yield agent

    agent = Agent("Test agent")
    agent.modes.register(planning_mode)

    async with agent:
        tool_manager = agent[ToolManager]
        assert "enter_planning" in tool_manager._tools

        # Tool should work
        tool = tool_manager["enter_planning"]
        result = await tool()
        assert "Entering planning mode" in result.response


@pytest.mark.asyncio
async def test_standalone_mode_callable():
    """Test StandaloneMode is callable (delegates to handler)."""
    from good_agent.agent.modes import mode

    @mode("test_mode")
    async def test_handler(agent: Agent):
        """Test handler."""
        yield agent

    # Can call the StandaloneMode directly (for testing)
    # Since it's a generator, we need to iterate over it
    agent = Agent("Test agent")
    gen = test_handler(agent)
    result = await gen.__anext__()
    assert result is agent


# =============================================================================
# Phase 2: Parameterized Mode Entry Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mode_aware_system_prompt():
    """Test that invokable modes inject awareness into system prompt."""
    agent = Agent("Base system prompt")

    @agent.modes("research", invokable=True)
    async def research_mode(agent: Agent):
        """Deep investigation mode for thorough analysis."""
        yield agent

    @agent.modes("writing", invokable=True)
    async def writing_mode(agent: Agent):
        """Creative writing and content generation."""
        yield agent

    async with agent:
        # System prompt should contain modes section
        rendered = agent.prompt.render()
        assert "## Operational Modes" in rendered
        assert "research" in rendered
        assert "writing" in rendered
        assert "Deep investigation mode" in rendered
        assert "Creative writing" in rendered
        assert "Current mode: none" in rendered

        # Enter a mode and check prompt updates
        async with agent.modes["research"]:
            rendered = agent.prompt.render()
            assert "Current mode: research" in rendered
            assert "research (ACTIVE)" in rendered


@pytest.mark.asyncio
async def test_mode_aware_system_prompt_disabled():
    """Test that modes awareness can be disabled."""
    agent = Agent("Base system prompt")
    agent.prompt._modes_awareness = False

    @agent.modes("research", invokable=True)
    async def research_mode(agent: Agent):
        """Research mode."""
        yield agent

    async with agent:
        rendered = agent.prompt.render()
        assert "## Operational Modes" not in rendered


@pytest.mark.asyncio
async def test_mode_aware_system_prompt_non_invokable():
    """Test that non-invokable modes don't appear in system prompt."""
    agent = Agent("Base system prompt")

    @agent.modes("private")  # Not invokable
    async def private_mode(agent: Agent):
        """Private mode."""
        yield agent

    async with agent:
        rendered = agent.prompt.render()
        # No invokable modes, so no modes section
        assert "## Operational Modes" not in rendered


# =============================================================================
# Phase 7: Mode History Tests
# =============================================================================


@pytest.mark.asyncio
async def test_mode_history_tracking():
    """Test that mode history tracks all modes entered."""
    agent = Agent("Test agent")

    @agent.modes("mode_a")
    async def mode_a(agent: Agent):
        yield agent

    @agent.modes("mode_b")
    async def mode_b(agent: Agent):
        yield agent

    @agent.modes("mode_c")
    async def mode_c(agent: Agent):
        yield agent

    async with agent:
        assert agent.mode.history == []

        async with agent.modes["mode_a"]:
            assert agent.mode.history == ["mode_a"]

        async with agent.modes["mode_b"]:
            assert agent.mode.history == ["mode_a", "mode_b"]

        async with agent.modes["mode_c"]:
            assert agent.mode.history == ["mode_a", "mode_b", "mode_c"]

        # History persists after mode exit
        assert agent.mode.history == ["mode_a", "mode_b", "mode_c"]


@pytest.mark.asyncio
async def test_mode_previous():
    """Test that previous returns the previously entered mode."""
    agent = Agent("Test agent")

    @agent.modes("first")
    async def first_mode(agent: Agent):
        yield agent

    @agent.modes("second")
    async def second_mode(agent: Agent):
        yield agent

    async with agent:
        assert agent.mode.previous is None

        async with agent.modes["first"]:
            assert agent.mode.previous is None  # Only one mode in history

        async with agent.modes["second"]:
            assert agent.mode.previous == "first"


@pytest.mark.asyncio
async def test_mode_return_to_previous():
    """Test return_to_previous creates correct transition."""
    agent = Agent("Test agent")

    @agent.modes("mode_a")
    async def mode_a(agent: Agent):
        yield agent

    @agent.modes("mode_b")
    async def mode_b(agent: Agent):
        yield agent

    async with agent:
        async with agent.modes["mode_a"]:
            # No previous - should return exit transition
            transition = agent.mode.return_to_previous()
            assert transition.transition_type == "exit"
            assert transition.target_mode is None

        async with agent.modes["mode_b"]:
            # Previous is mode_a - should return switch transition
            transition = agent.mode.return_to_previous()
            assert transition.transition_type == "switch"
            assert transition.target_mode == "mode_a"


@pytest.mark.asyncio
async def test_parameterized_mode_entry():
    """Test parameterized mode entry via callable context manager."""
    agent = Agent("Test agent")

    @agent.modes("research")
    async def research_mode(agent: Agent):
        yield agent

    async with agent:
        async with agent.modes["research"](topic="quantum", depth=3):
            # Parameters should be in mode state
            assert agent.mode.state["topic"] == "quantum"
            assert agent.mode.state["depth"] == 3

        # Parameters should be cleared after mode exit
        assert agent.mode.state.get("topic") is None


@pytest.mark.asyncio
async def test_parameterized_mode_entry_handler_access():
    """Test handler can access parameters passed at mode entry."""
    agent = Agent("Test agent")
    seen_params = {}

    @agent.modes("analysis")
    async def analysis_mode(agent: Agent):
        # Capture the parameters from state
        seen_params["subject"] = agent.mode.state.get("subject")
        seen_params["max_depth"] = agent.mode.state.get("max_depth")
        yield agent

    async with agent, agent.modes["analysis"](subject="physics", max_depth=5):
        pass

    # Handler should have seen the parameters
    assert seen_params["subject"] == "physics"
    assert seen_params["max_depth"] == 5


@pytest.mark.asyncio
async def test_parameterized_mode_without_params():
    """Test mode entry without parameters still works."""
    agent = Agent("Test agent")

    @agent.modes("simple")
    async def simple_mode(agent: Agent):
        yield agent

    async with agent:
        # Both styles should work
        async with agent.modes["simple"]:
            assert agent.mode.name == "simple"

        async with agent.modes["simple"]():
            assert agent.mode.name == "simple"


@pytest.mark.asyncio
async def test_parameterized_mode_nested():
    """Test parameterized modes work when nested."""
    agent = Agent("Test agent")

    @agent.modes("outer")
    async def outer_mode(agent: Agent):
        yield agent

    @agent.modes("inner")
    async def inner_mode(agent: Agent):
        yield agent

    async with agent, agent.modes["outer"](level="outer"):
        assert agent.mode.state["level"] == "outer"

        async with agent.modes["inner"](level="inner", extra="data"):
            # Inner state shadows outer
            assert agent.mode.state["level"] == "inner"
            assert agent.mode.state["extra"] == "data"

        # Back to outer state
        assert agent.mode.state["level"] == "outer"
        assert agent.mode.state.get("extra") is None
