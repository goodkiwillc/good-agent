"""Tests for async generator mode handlers."""

import pytest

from good_agent import Agent
from good_agent.agent.modes import (
    HandlerType,
    _detect_handler_type,
)


class TestHandlerDetection:
    """Test detection of handler types."""

    def test_simple_async_function_detected(self):
        async def simple(agent: Agent):
            pass

        assert _detect_handler_type(simple) == HandlerType.SIMPLE

    def test_async_generator_detected(self):
        async def generator(agent: Agent):
            yield agent

        assert _detect_handler_type(generator) == HandlerType.GENERATOR

    def test_sync_function_raises(self):
        def sync(agent: Agent):
            pass

        with pytest.raises(TypeError, match="async"):
            _detect_handler_type(sync)

    def test_sync_generator_raises(self):
        def sync_gen(agent: Agent):
            yield agent

        with pytest.raises(TypeError, match="async"):
            _detect_handler_type(sync_gen)


class TestGeneratorHandlerLifecycle:
    """Test async generator mode handlers."""

    @pytest.mark.asyncio
    async def test_setup_runs_before_yield(self):
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            events.append("setup:start")
            agent.prompt.append("test prompt")
            events.append("setup:end")
            yield agent
            events.append("cleanup")

        async with agent:
            events.append("before enter")
            async with agent.modes["gen"]:
                events.append("active")
            events.append("after exit")

        assert events == [
            "before enter",
            "setup:start",
            "setup:end",
            "active",
            "cleanup",
            "after exit",
        ]

    @pytest.mark.asyncio
    async def test_cleanup_always_runs(self):
        agent = Agent("Test")
        cleanup_ran = False

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            nonlocal cleanup_ran
            cleanup_ran = True

        async with agent:
            async with agent.modes["gen"]:
                pass

        assert cleanup_ran is True

    @pytest.mark.asyncio
    async def test_cleanup_runs_on_exception(self):
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            events.append("setup")
            yield agent
            events.append("cleanup")

        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["gen"]:
                    events.append("active")
                    raise ValueError("oops")

        assert events == ["setup", "active", "cleanup"]

    @pytest.mark.asyncio
    async def test_multiple_yields_raises_error(self):
        agent = Agent("Test")

        @agent.modes("bad")
        async def bad_mode(agent: Agent):
            yield agent
            yield agent  # Second yield - error!

        async with agent:
            with pytest.raises(RuntimeError, match="yielded more than once"):
                async with agent.modes["bad"]:
                    pass

    @pytest.mark.asyncio
    async def test_generator_that_returns_early(self):
        """Generator that returns before yielding should not crash."""
        agent = Agent("Test")
        setup_ran = False

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            nonlocal setup_ran
            setup_ran = True
            if True:  # Condition that prevents yield
                return
            yield agent  # Never reached, but makes it a generator

        async with agent:
            async with agent.modes["gen"]:
                pass

        # Setup code ran before the early return
        assert setup_ran is True

    @pytest.mark.asyncio
    async def test_generator_state_accessible_during_active(self):
        """State set during setup is accessible during active phase."""
        agent = Agent("Test")

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            agent.mode.state["setup_value"] = 42
            yield agent

        async with agent:
            async with agent.modes["gen"]:
                assert agent.mode.state["setup_value"] == 42


class TestNestedModeGenerators:
    """Test stacked mode behavior with generators."""

    @pytest.mark.asyncio
    async def test_nested_setup_cleanup_order(self):
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            events.append("outer:setup")
            yield agent
            events.append("outer:cleanup")

        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            events.append("inner:setup")
            yield agent
            events.append("inner:cleanup")

        async with agent:
            async with agent.modes["outer"]:
                events.append("outer:active")
                async with agent.modes["inner"]:
                    events.append("inner:active")
                events.append("outer:after_inner")

        assert events == [
            "outer:setup",
            "outer:active",
            "inner:setup",
            "inner:active",
            "inner:cleanup",
            "outer:after_inner",
            "outer:cleanup",
        ]

    @pytest.mark.asyncio
    async def test_nested_cleanup_on_exception(self):
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            events.append("outer:setup")
            try:
                yield agent
            finally:
                events.append("outer:cleanup")

        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            events.append("inner:setup")
            try:
                yield agent
            finally:
                events.append("inner:cleanup")

        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["outer"]:
                    async with agent.modes["inner"]:
                        raise ValueError("boom")

        # Both cleanups should have run, inner first
        assert events == [
            "outer:setup",
            "inner:setup",
            "inner:cleanup",
            "outer:cleanup",
        ]

    @pytest.mark.asyncio
    async def test_inner_mode_sees_outer_state(self):
        agent = Agent("Test")
        inner_saw = None

        @agent.modes("outer")
        async def outer_mode(agent: Agent):
            agent.mode.state["outer_value"] = 42
            yield agent

        @agent.modes("inner")
        async def inner_mode(agent: Agent):
            nonlocal inner_saw
            inner_saw = agent.mode.state.get("outer_value")
            yield agent

        async with agent:
            async with agent.modes["outer"]:
                async with agent.modes["inner"]:
                    pass

        assert inner_saw == 42


class TestSimpleHandlerBackwardCompat:
    """Test that simple handlers still work via execute() loop."""

    @pytest.mark.asyncio
    async def test_simple_handler_runs_during_execute(self):
        """Simple handlers run during execute(), not at mode entry."""
        agent = Agent("Test")
        handler_runs: list[str] = []

        @agent.modes("simple")
        async def simple_mode(agent: Agent):
            handler_runs.append("handler")

        async with agent:
            async with agent.modes["simple"]:
                # Handler hasn't run yet - it runs during execute()
                assert handler_runs == []

                with agent.mock("response"):
                    await agent.call("test")

                # Now handler should have run
                assert handler_runs == ["handler"]
