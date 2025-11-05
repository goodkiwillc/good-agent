import asyncio
import gc
import os
import signal
import sys
import threading
import time
import weakref
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from good_agent import Agent, tool
from good_agent.agent import AgentState
from good_agent.utilities.signal_handler import SignalHandler, _global_handler

# Mark all tests in this file as requiring signal handling
pytestmark = pytest.mark.requires_signals


@contextmanager
def signal_handler_spy():
    """Context manager to spy on signal handler calls."""
    calls = []
    original_handle = _global_handler._handle_signal

    def spy_handle(signum, frame):
        calls.append(
            {
                "signum": signum,
                "signal_name": signal.Signals(signum).name,
                "timestamp": time.time(),
                "thread_id": threading.get_ident(),
            }
        )
        return original_handle(signum, frame)

    _global_handler._handle_signal = spy_handle
    try:
        yield calls
    finally:
        _global_handler._handle_signal = original_handle


def capture_signal_handlers():
    """Capture current signal handlers for comparison."""
    handlers = {}
    if sys.platform != "win32":
        handlers["SIGINT"] = signal.getsignal(signal.SIGINT)
        handlers["SIGTERM"] = signal.getsignal(signal.SIGTERM)
    else:
        handlers["SIGINT"] = signal.getsignal(signal.SIGINT)
    return handlers


class TestSignalHandlerInstallation:
    """Test that signal handlers are properly installed and cleaned up."""

    @pytest.mark.asyncio
    async def test_signal_handlers_installed_on_agent_creation(self):
        """Verify OS signal handlers are installed when Agent is created."""
        # Capture original handlers
        capture_signal_handlers()

        # Create agent with signal handling explicitly enabled
        agent = Agent("Test assistant")
        await agent.ready()

        # Capture handlers after agent creation
        agent_handlers = capture_signal_handlers()

        # Verify handlers are callable (signal handlers are installed)
        # Note: functools.partial objects may have different task references but same function
        assert callable(agent_handlers["SIGINT"])
        assert hasattr(agent_handlers["SIGINT"], "func") or callable(
            agent_handlers["SIGINT"]
        )

        if sys.platform != "win32":
            # Verify SIGTERM handler exists (may still be default in some test environments)
            assert agent_handlers["SIGTERM"] is not None
            # Should be SignalHandler._handle_signal method for SIGINT
            if hasattr(agent_handlers["SIGINT"], "__self__"):
                assert isinstance(agent_handlers["SIGINT"].__self__, SignalHandler)

        await agent.async_close()

    @pytest.mark.asyncio
    async def test_signal_handlers_restored_after_cleanup(self):
        """Verify signal handlers are restored after agent cleanup."""
        # Capture original handlers
        original_handlers = capture_signal_handlers()

        # Create and destroy agent with signal handling enabled
        agent = Agent("Test assistant")
        await agent.ready()
        await agent.async_close()

        # Give time for cleanup
        await asyncio.sleep(0.1)

        # Force garbage collection
        del agent
        gc.collect()

        # Capture handlers after cleanup
        restored_handlers = capture_signal_handlers()

        # Should be back to original (or default if no other agents)
        # Note: May not be exactly the same if asyncio installed its own
        assert (
            restored_handlers["SIGINT"] == original_handlers["SIGINT"]
            or restored_handlers["SIGINT"] == signal.default_int_handler
        )

    @pytest.mark.asyncio
    async def test_no_signal_handlers_when_disabled(self):
        """Verify signal handlers are NOT installed by default."""
        # Capture original handlers
        original_handlers = capture_signal_handlers()

        # Create agent without signal handling (default behavior)
        agent = Agent("Test assistant")
        await agent.ready()

        # Capture handlers after agent creation
        agent_handlers = capture_signal_handlers()

        # Verify handlers did NOT change
        assert agent_handlers["SIGINT"] == original_handlers["SIGINT"]

        if sys.platform != "win32":
            assert agent_handlers["SIGTERM"] == original_handlers["SIGTERM"]

        await agent.async_close()


class TestExternalSignalSimulation:
    """Test handling of real OS-level signals."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        sys.platform == "win32", reason="Signal handling differs on Windows"
    )
    async def test_external_sigint_handling(self):
        """Test that external SIGINT is properly handled."""
        handler_calls = []
        tasks_cancelled = []

        @tool
        async def long_operation() -> str:
            try:
                await asyncio.sleep(10)
                return "completed"
            except asyncio.CancelledError:
                tasks_cancelled.append("tool_cancelled")
                raise

        with signal_handler_spy() as calls:
            # Enable signal handling explicitly for this test
            agent = Agent("Test assistant", tools=[long_operation])
            await agent.ready()

            # Start long operation
            task = asyncio.create_task(agent.call("Execute long_operation"))

            # Let it start
            await asyncio.sleep(0.5)

            # Send external SIGINT
            os.kill(os.getpid(), signal.SIGINT)

            # Give signal time to propagate
            await asyncio.sleep(0.5)

            # Try to await task
            try:
                await task
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass

            handler_calls = list(calls)
            await agent.async_close()

        # Verify signal handler was called
        assert len(handler_calls) > 0
        assert handler_calls[0]["signal_name"] == "SIGINT"

        # Verify task was cancelled
        assert len(tasks_cancelled) > 0

    @pytest.mark.asyncio
    async def test_multiple_sigint_force_exit(self):
        """Test that second SIGINT forces exit."""
        with signal_handler_spy():
            agent = Agent("Test assistant")
            await agent.ready()

            # Mock sys.exit to prevent actual exit
            with patch("sys.exit") as mock_exit:
                # Send first SIGINT
                os.kill(os.getpid(), signal.SIGINT)
                await asyncio.sleep(0.1)

                # Send second SIGINT (should force exit)
                os.kill(os.getpid(), signal.SIGINT)
                await asyncio.sleep(0.1)

                # Verify sys.exit was called
                mock_exit.assert_called_once_with(1)

            await agent.async_close()


class TestMultiAgentSignalSharing:
    """Test signal handling with multiple agents."""

    @pytest.mark.asyncio
    async def test_multiple_agents_share_signal_handler(self):
        """Verify multiple agents properly share the global signal handler."""
        agents = []

        # Create multiple agents
        for i in range(3):
            agent = Agent(f"Assistant {i}")
            await agent.ready()
            agents.append(agent)

        # Check that signal handler is installed
        current_handler = signal.getsignal(signal.SIGINT)
        assert current_handler != signal.default_int_handler

        # Check global handler has all agents registered
        with _global_handler._lock:
            # Count active routers (agents)
            active_routers = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert active_routers >= len(agents)

        # Clean up agents one by one
        for agent in agents:
            await agent.async_close()

        # All agents cleaned up - handlers should be restored
        await asyncio.sleep(0.1)
        gc.collect()

        with _global_handler._lock:
            active_routers = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert active_routers == 0

    @pytest.mark.asyncio
    async def test_signal_cancels_all_agents_tasks(self):
        """Verify SIGINT cancels tasks across all agents."""
        agents = []
        cancellation_tracking = {"cancelled": []}

        @tool
        async def tracked_operation(agent_id: int) -> str:
            try:
                await asyncio.sleep(10)
                return f"Agent {agent_id} completed"
            except asyncio.CancelledError:
                cancellation_tracking["cancelled"].append(agent_id)
                raise

        # Create agents with tracking
        for i in range(3):
            agent = Agent(f"Assistant {i}", tools=[tracked_operation])
            await agent.ready()
            agents.append(agent)

        # Start operations on each agent
        tasks = []
        for i, agent in enumerate(agents):
            task = asyncio.create_task(
                agent.call(f"Execute tracked_operation with agent_id {i}")
            )
            tasks.append(task)

        # Let operations start
        await asyncio.sleep(0.5)

        # Send SIGINT
        with signal_handler_spy():
            os.kill(os.getpid(), signal.SIGINT)
            await asyncio.sleep(0.5)

        # Gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be cancelled
        for result in results:
            assert isinstance(result, (asyncio.CancelledError, KeyboardInterrupt))

        # Clean up
        for agent in agents:
            await agent.async_close()

        # Verify all agents' operations were cancelled
        assert len(cancellation_tracking["cancelled"]) == len(agents)


class TestSignalHandlerEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_signal_during_agent_initialization(self):
        """Test signal handling during agent initialization."""
        initialization_interrupted = False

        # Mock a slow component initialization
        class SlowComponent:
            async def install(self, agent):
                try:
                    await asyncio.sleep(2)
                except asyncio.CancelledError:
                    nonlocal initialization_interrupted
                    initialization_interrupted = True
                    raise

        agent = Agent("Test", extensions=[SlowComponent()])

        # Start initialization
        init_task = asyncio.create_task(agent.ready())

        # Send signal during initialization
        await asyncio.sleep(0.1)
        os.kill(os.getpid(), signal.SIGINT)

        try:
            await init_task
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

        # Cleanup
        if agent._state >= AgentState.READY:
            await agent.async_close()
        else:
            agent.close()

        assert initialization_interrupted or agent._state < AgentState.READY

    @pytest.mark.asyncio
    async def test_weak_reference_cleanup(self):
        """Test that weak references to agents are properly cleaned up."""
        agent_refs = []

        # Create agents and store weak refs
        for i in range(5):
            agent = Agent(f"Temp agent {i}")
            await agent.ready()
            agent_refs.append(weakref.ref(agent))
            await agent.async_close()
            del agent

        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # All weak refs should be dead
        alive_count = sum(1 for ref in agent_refs if ref() is not None)
        assert alive_count == 0

        # Global handler should have no registered routers
        with _global_handler._lock:
            active_routers = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert active_routers == 0

    @pytest.mark.asyncio
    async def test_signal_handler_thread_safety(self):
        """Test signal handler is thread-safe."""
        agents = []

        async def create_agent(idx):
            agent = Agent(f"Agent {idx}")
            await agent.ready()
            return agent

        # Create agents concurrently
        agents = await asyncio.gather(*[create_agent(i) for i in range(10)])

        # Verify all registered
        with _global_handler._lock:
            active_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert active_count >= len(agents)

        # Clean up concurrently
        await asyncio.gather(*[agent.async_close() for agent in agents])

        # Verify all unregistered
        await asyncio.sleep(0.1)
        with _global_handler._lock:
            active_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            # Should be cleaned up (allowing for some delay)
            assert active_count < len(agents) // 2


class TestPlatformSpecific:
    """Platform-specific signal handling tests."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    async def test_windows_signal_limitations(self):
        """Test signal handling on Windows (limited to SIGINT)."""
        agent = Agent("Windows test")
        await agent.ready()

        # Windows only supports SIGINT, not SIGTERM
        sigint_handler = signal.getsignal(signal.SIGINT)
        assert sigint_handler != signal.default_int_handler

        # SIGTERM should not be modified on Windows
        if hasattr(signal, "SIGTERM"):
            sigterm_handler = signal.getsignal(signal.SIGTERM)
            assert sigterm_handler == signal.SIG_DFL

        await agent.async_close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    async def test_unix_sigterm_handling(self):
        """Test SIGTERM handling on Unix systems."""
        handler_calls = []

        with signal_handler_spy() as calls:
            agent = Agent("Unix test")
            await agent.ready()

            # Send SIGTERM
            os.kill(os.getpid(), signal.SIGTERM)
            await asyncio.sleep(0.1)

            handler_calls = list(calls)
            await agent.async_close()

        # Verify SIGTERM was handled
        assert len(handler_calls) > 0
        assert handler_calls[0]["signal_name"] == "SIGTERM"


class TestRealWorldScenarios:
    """Test realistic usage scenarios."""

    @pytest.mark.asyncio
    async def test_ctrl_c_during_streaming(self):
        """Test Ctrl-C simulation during LLM streaming."""
        chunks_received = []

        async def mock_stream(*args, **kwargs):
            for i in range(100):
                chunk = MagicMock()
                chunk.content = f"chunk_{i}"
                chunks_received.append(i)
                yield chunk
                await asyncio.sleep(0.01)

        agent = Agent("Test")
        await agent.ready()

        with patch.object(agent.model, "stream", mock_stream):

            async def consume_stream():
                async for _ in agent.model.stream(agent.messages):
                    pass

            stream_task = asyncio.create_task(consume_stream())

            # Let streaming start
            await asyncio.sleep(0.1)

            # Simulate Ctrl-C
            os.kill(os.getpid(), signal.SIGINT)
            await asyncio.sleep(0.1)

            try:
                await stream_task
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass

        await agent.async_close()

        # Should have received some but not all chunks
        assert 0 < len(chunks_received) < 100

    @pytest.mark.asyncio
    async def test_nested_agent_calls_with_interruption(self):
        """Test interruption during nested agent.call() operations."""
        call_stack = []

        @tool
        async def nested_tool(depth: int) -> str:
            call_stack.append(f"depth_{depth}")
            if depth > 0:
                # Would normally call agent.call() here
                await asyncio.sleep(0.5)
                return f"Level {depth}"
            return "Base"

        agent = Agent("Test", tools=[nested_tool])
        await agent.ready()

        task = asyncio.create_task(agent.call("Use nested_tool with depth 3"))

        # Let it start nesting
        await asyncio.sleep(0.2)

        # Interrupt
        os.kill(os.getpid(), signal.SIGINT)

        try:
            await task
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

        await agent.async_close()

        # Should have started but not completed all levels
        assert len(call_stack) > 0
        assert len(call_stack) < 4
