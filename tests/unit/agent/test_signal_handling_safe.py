import asyncio
import gc
import signal
import sys
import threading
import time
import weakref
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from good_agent import Agent, tool
from good_agent.agent import AgentState
from good_agent.components.component import AgentComponent
from good_agent.core.signal_handler import SignalHandler, _global_handler

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

    setattr(_global_handler, "_handle_signal", spy_handle)
    try:
        yield calls
    finally:
        setattr(_global_handler, "_handle_signal", original_handle)


class TestSignalHandlerInstallation:
    """Test that signal handlers are properly installed and cleaned up."""

    @pytest.mark.asyncio
    async def test_signal_handlers_installed_on_agent_creation(self):
        """Verify OS signal handlers are installed when Agent is created."""
        # Capture original handlers
        original_sigint = signal.getsignal(signal.SIGINT)

        # Create agent with signal handling enabled (default)
        agent = Agent("Test assistant")
        await agent.initialize()

        # Capture handler after agent creation
        agent_sigint = signal.getsignal(signal.SIGINT)

        # Verify handler changed
        assert agent_sigint != original_sigint, "Signal handler should be installed"

        # Verify it's the SignalHandler
        if sys.platform != "win32":
            assert callable(agent_sigint), "Handler should be callable"
            handler_self = getattr(agent_sigint, "__self__", None)
            assert isinstance(handler_self, SignalHandler), (
                "Should be SignalHandler instance"
            )

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_signal_handlers_restored_after_cleanup(self):
        """Verify signal handlers are restored after agent cleanup."""
        # Capture original handler
        original_sigint = signal.getsignal(signal.SIGINT)

        # Create and destroy agent
        agent = Agent("Test assistant")
        await agent.initialize()

        # Verify handler was changed
        during_sigint = signal.getsignal(signal.SIGINT)
        assert during_sigint != original_sigint, (
            "Handler should change during agent lifetime"
        )

        # Clean up
        await agent.events.close()
        del agent
        gc.collect()
        await asyncio.sleep(0.1)

        # Capture handler after cleanup
        restored_sigint = signal.getsignal(signal.SIGINT)

        # Should be restored (or default if no other agents)
        assert (
            restored_sigint == original_sigint
            or restored_sigint == signal.default_int_handler
        ), "Handler should be restored after cleanup"

    @pytest.mark.asyncio
    async def test_global_handler_registration_tracking(self):
        """Test that agents are properly tracked in global handler."""
        # Check initial state
        with _global_handler._lock:
            initial_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )

        # Create agent
        agent = Agent("Test")
        await agent.initialize()

        # Check registration
        with _global_handler._lock:
            during_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )

        assert during_count > initial_count, "Agent should be registered"

        # Clean up
        await agent.events.close()
        await asyncio.sleep(0.1)

        # Check unregistration
        with _global_handler._lock:
            after_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )

        assert after_count <= initial_count, "Agent should be unregistered"


class TestSignalPropagation:
    """Test signal propagation without sending real signals."""

    @pytest.mark.asyncio
    async def test_signal_handler_cancels_tasks(self):
        """Test that signal handler cancels agent tasks."""
        tasks_cancelled = []

        @tool
        async def long_operation() -> str:
            try:
                await asyncio.sleep(10)
                return "completed"
            except asyncio.CancelledError:
                tasks_cancelled.append("cancelled")
                raise

        agent = Agent("Test", tools=[long_operation])
        await agent.initialize()

        # Start operation
        task = asyncio.create_task(agent.call("Execute long_operation"))
        await asyncio.sleep(0.1)  # Let it start

        # Manually trigger signal handler logic
        with patch.object(_global_handler, "_shutdown_initiated", False):
            # Simulate what happens when signal is received
            _global_handler._cancel_all_tasks()

        # Wait for cancellation
        await asyncio.sleep(0.1)

        try:
            await task
        except asyncio.CancelledError:
            pass

        await agent.events.close()

        # Verify cancellation happened
        assert len(tasks_cancelled) > 0, "Task should have been cancelled"

    @pytest.mark.asyncio
    async def test_double_signal_force_exit(self):
        """Test that second signal forces exit."""
        agent = Agent("Test")
        await agent.initialize()

        with patch("sys.exit") as mock_exit:
            # First signal - sets shutdown flag
            _global_handler._shutdown_initiated = False
            _global_handler._handle_signal(signal.SIGINT, None)

            # Second signal - should force exit
            _global_handler._handle_signal(signal.SIGINT, None)

            # Verify forced exit
            mock_exit.assert_called_once_with(1)

        # Reset for cleanup
        _global_handler._shutdown_initiated = False
        await agent.events.close()


class TestMultiAgentCoordination:
    """Test signal handling with multiple agents."""

    @pytest.mark.asyncio
    async def test_multiple_agents_share_handler(self):
        """Test that multiple agents share the global signal handler."""
        agents = []

        # Create multiple agents
        for i in range(3):
            agent = Agent(f"Agent {i}")
            await agent.initialize()
            agents.append(agent)

        # Check handler is installed once
        sigint_handler = signal.getsignal(signal.SIGINT)
        assert sigint_handler != signal.default_int_handler

        # All agents should be registered
        with _global_handler._lock:
            registered_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert registered_count >= len(agents)

        # Clean up one agent
        await agents[0].close()
        await asyncio.sleep(0.1)

        # Handler should still be installed
        assert signal.getsignal(signal.SIGINT) == sigint_handler

        # Clean up remaining agents
        for agent in agents[1:]:
            await agent.events.close()

        await asyncio.sleep(0.1)

        # Now handler might be restored
        final_handler = signal.getsignal(signal.SIGINT)
        assert (
            final_handler == signal.default_int_handler
            or final_handler != sigint_handler
        )

    @pytest.mark.asyncio
    async def test_signal_affects_all_agents(self):
        """Test that signal affects all registered agents."""
        agents = []
        cancellations = {"count": 0}

        @tool
        async def tracked_operation() -> str:
            try:
                await asyncio.sleep(10)
                return "done"
            except asyncio.CancelledError:
                cancellations["count"] += 1
                raise

        # Create agents
        for i in range(3):
            agent = Agent(f"Agent {i}", tools=[tracked_operation])
            await agent.initialize()
            agents.append(agent)

        # Start operations
        tasks = []
        for agent in agents:
            task = asyncio.create_task(agent.call("Execute tracked_operation"))
            tasks.append(task)

        await asyncio.sleep(0.1)

        # Trigger cancellation via handler
        _global_handler._cancel_all_tasks()

        # Wait for cancellations
        await asyncio.sleep(0.1)

        # Gather results
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be cancelled
        for result in results:
            assert isinstance(result, asyncio.CancelledError)

        # Clean up
        for agent in agents:
            await agent.events.close()

        # Verify all operations were cancelled
        assert cancellations["count"] == len(agents)


class TestWeakReferenceManagement:
    """Test weak reference cleanup in signal handler."""

    @pytest.mark.asyncio
    async def test_agent_garbage_collection(self):
        """Test that agents are properly garbage collected."""
        agent_refs = []

        # Create and destroy agents
        for i in range(5):
            agent = Agent(f"Agent {i}")
            await agent.initialize()
            agent_refs.append(weakref.ref(agent))
            await agent.events.close()
            del agent

        # Force garbage collection
        gc.collect()
        await asyncio.sleep(0.1)
        gc.collect()

        # All should be collected
        alive = sum(1 for ref in agent_refs if ref() is not None)
        assert alive == 0, f"All agents should be garbage collected, but {alive} remain"

        # Registry should be empty
        with _global_handler._lock:
            registered = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert registered == 0, "No agents should be registered"

    @pytest.mark.asyncio
    async def test_weak_ref_cleanup_on_deletion(self):
        """Test that weak references are cleaned when agents are deleted."""
        # Create agent
        agent = Agent("Test")
        await agent.initialize()

        # Verify registration
        with _global_handler._lock:
            before_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert before_count > 0

        # Delete without explicit close
        id(agent)
        del agent
        gc.collect()
        await asyncio.sleep(0.1)

        # Should be cleaned up
        with _global_handler._lock:
            after_count = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            # Should have one less registered
            assert after_count < before_count


class TestThreadSafety:
    """Test thread safety of signal handling."""

    @pytest.mark.asyncio
    async def test_concurrent_agent_creation(self):
        """Test creating agents concurrently."""

        async def create_agent(idx):
            agent = Agent(f"Agent {idx}")
            await agent.initialize()
            return agent

        # Create agents concurrently
        agents = await asyncio.gather(*[create_agent(i) for i in range(10)])

        # All should be registered
        with _global_handler._lock:
            registered = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert registered >= len(agents)

        # Clean up concurrently
        await asyncio.gather(*[agent.events.close() for agent in agents])

        await asyncio.sleep(0.2)

        # All should be unregistered
        with _global_handler._lock:
            remaining = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert remaining == 0

    @pytest.mark.asyncio
    async def test_signal_handler_lock_safety(self):
        """Test that signal handler operations are thread-safe."""
        agent = Agent("Test")
        await agent.initialize()

        # Simulate concurrent access to handler
        def access_handler():
            with _global_handler._lock:
                # Simulate some work
                time.sleep(0.001)
                return len(_global_handler._registered_routers)

        # Run in threads
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(access_handler) for _ in range(20)]
            results = [f.result() for f in futures]

        # All should see consistent state
        assert all(r == results[0] for r in results)

        await agent.events.close()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_signal_during_initialization(self):
        """Test handling signals during agent initialization."""
        slow_init_called = False

        class SlowComponent(AgentComponent):
            async def install(self, agent):
                await super().install(agent)
                nonlocal slow_init_called
                slow_init_called = True
                await asyncio.sleep(0.5)

        agent = Agent("Test", extensions=[SlowComponent()])
        init_task = asyncio.create_task(agent.initialize())

        # Cancel during init
        await asyncio.sleep(0.1)
        init_task.cancel()

        try:
            await init_task
        except asyncio.CancelledError:
            pass

        # Verify partial initialization
        assert slow_init_called
        assert agent.state < AgentState.READY

        # Clean up
        if agent.state >= AgentState.READY:
            await agent.events.close()
        else:
            agent.events.close_sync()

    @pytest.mark.asyncio
    async def test_handler_with_no_agents(self):
        """Test signal handler behavior with no agents."""
        # Ensure no agents registered
        with _global_handler._lock:
            _global_handler._registered_routers.clear()

        # Handler should do nothing harmful
        _global_handler._cancel_all_tasks()

        # Should not crash
        assert True

    @pytest.mark.asyncio
    async def test_rapid_registration_unregistration(self):
        """Test rapid registration and unregistration cycles."""
        for _ in range(10):
            agent = Agent("Rapid test")
            await agent.initialize()
            await agent.events.close()
            del agent

        # Final cleanup
        gc.collect()
        await asyncio.sleep(0.1)

        # Should be clean
        with _global_handler._lock:
            remaining = sum(
                1 for ref in _global_handler._registered_routers if ref() is not None
            )
            assert remaining == 0
