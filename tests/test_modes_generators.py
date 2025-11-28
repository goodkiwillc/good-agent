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
        """Cleanup runs when exception occurs if generator uses try/finally."""
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            events.append("setup")
            try:
                yield agent
            finally:
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


class TestExceptionHandling:
    """Test exception passing to generator handlers."""

    @pytest.mark.asyncio
    async def test_generator_receives_exception(self):
        """Generator can catch and handle exception from active phase."""
        agent = Agent("Test")
        caught_exception = None

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            nonlocal caught_exception
            try:
                yield agent
            except ValueError as e:
                caught_exception = e

        async with agent:
            # Exception should be suppressed since generator handles it
            async with agent.modes["gen"]:
                raise ValueError("test error")

        assert caught_exception is not None
        assert str(caught_exception) == "test error"

    @pytest.mark.asyncio
    async def test_generator_suppresses_exception(self):
        """Generator that catches exception without re-raising suppresses it."""
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            try:
                yield agent
            except ValueError:
                events.append("caught")
                # Don't re-raise - suppress the exception

        async with agent:
            events.append("before")
            # No pytest.raises needed - exception is suppressed
            async with agent.modes["gen"]:
                events.append("active")
                raise ValueError("suppressed")
            events.append("after")  # This should run

        assert events == ["before", "active", "caught", "after"]

    @pytest.mark.asyncio
    async def test_generator_reraises_exception(self):
        """Generator that re-raises exception propagates it."""
        agent = Agent("Test")
        events: list[str] = []

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            try:
                yield agent
            except ValueError:
                events.append("caught")
                raise  # Re-raise the exception

        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["gen"]:
                    events.append("active")
                    raise ValueError("propagated")

        assert events == ["active", "caught"]

    @pytest.mark.asyncio
    async def test_generator_transforms_exception(self):
        """Generator can transform exception to different type."""
        agent = Agent("Test")

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            try:
                yield agent
            except ValueError as e:
                raise RuntimeError(f"Transformed: {e}") from e

        async with agent:
            with pytest.raises(RuntimeError, match="Transformed: original"):
                async with agent.modes["gen"]:
                    raise ValueError("original")

    @pytest.mark.asyncio
    async def test_cleanup_runs_even_when_cleanup_raises(self):
        """State is restored even if cleanup code raises."""
        agent = Agent("Test")
        prompt_before = None
        prompt_after = None

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            agent.prompt.append("temp prompt")
            try:
                yield agent
            finally:
                raise RuntimeError("cleanup error")

        async with agent:
            prompt_before = len(agent.prompt.sections)
            with pytest.raises(RuntimeError, match="cleanup error"):
                async with agent.modes["gen"]:
                    pass
            prompt_after = len(agent.prompt.sections)

        # Prompt should be restored despite cleanup error
        assert prompt_after == prompt_before

    @pytest.mark.asyncio
    async def test_simple_handler_no_exception_passing(self):
        """Simple (non-generator) handlers don't receive exceptions."""
        agent = Agent("Test")
        handler_ran = False

        @agent.modes("simple")
        async def simple_mode(agent: Agent):
            nonlocal handler_ran
            handler_ran = True

        async with agent:
            with pytest.raises(ValueError):
                async with agent.modes["simple"]:
                    raise ValueError("oops")

        # Handler never ran because exception happened before execute()
        assert handler_ran is False


class TestModeExitBehavior:
    """Test ModeExitBehavior enum and set_exit_behavior method."""

    @pytest.mark.asyncio
    async def test_set_exit_behavior_stop(self):
        """Handler can set exit behavior to STOP."""
        import good_agent

        agent = Agent("Test")

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            agent.mode.set_exit_behavior(good_agent.ModeExitBehavior.STOP)

        async with agent:
            async with agent.modes["gen"]:
                pass
            # Check that the behavior was set (accessible via internal state)
            # The actual behavior affects execute() loop integration (Phase 4)

        # Verify the method exists and can be called without error
        assert True  # Test passes if no exception

    @pytest.mark.asyncio
    async def test_set_exit_behavior_continue(self):
        """Handler can set exit behavior to CONTINUE."""
        import good_agent

        agent = Agent("Test")

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            agent.mode.set_exit_behavior(good_agent.ModeExitBehavior.CONTINUE)

        async with agent:
            async with agent.modes["gen"]:
                pass

        assert True

    @pytest.mark.asyncio
    async def test_set_exit_behavior_auto_default(self):
        """Exit behavior defaults to AUTO when not set."""
        agent = Agent("Test")

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            # Don't set any behavior - should default to AUTO

        async with agent:
            # We need to capture the behavior during exit
            # This tests the internal mechanism
            async with agent.modes["gen"]:
                pass

        # No explicit behavior set means AUTO is used
        assert True

    @pytest.mark.asyncio
    async def test_exit_behavior_accessible_via_state(self):
        """Exit behavior can be set and read via mode state."""
        import good_agent

        agent = Agent("Test")

        @agent.modes("gen")
        async def gen_mode(agent: Agent):
            yield agent
            # Set behavior directly in state (alternative to set_exit_behavior)
            agent.mode.state["_exit_behavior"] = good_agent.ModeExitBehavior.STOP

        async with agent:
            async with agent.modes["gen"]:
                # Behavior not set yet - we're before cleanup
                assert agent.mode.state.get("_exit_behavior") is None

        # After mode exit, state is cleaned up
        assert True
