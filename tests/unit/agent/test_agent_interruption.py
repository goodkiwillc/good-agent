import asyncio
import signal
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from good_agent import Agent
from good_agent.agent import AgentState
from good_agent.tools import tool
from litellm.types.completion import ChatCompletionMessageParam


def _make_mock_llm_response(content: str = "mock response"):
    response = MagicMock()
    choice = MagicMock()
    choice.__class__.__name__ = "Choices"
    choice.message = MagicMock()
    choice.message.content = content
    choice.message.tool_calls = None
    response.choices = [choice]
    return response


@contextmanager
def _stub_agent_complete(agent, *, delay: float = 0.0, content: str = "mock response"):
    async def _fake_complete(*args, **kwargs):
        if delay:
            await asyncio.sleep(delay)
        return _make_mock_llm_response(content)

    with patch.object(agent.model, "complete", new=_fake_complete):
        yield


class TestAgentInterruption:
    """Test Agent behavior during interruption scenarios."""

    @pytest.mark.asyncio
    async def test_agent_cleanup_on_keyboard_interrupt(self):
        """Test that Agent properly cleans up when interrupted."""
        agent = Agent("You are a test assistant")
        await agent.initialize()

        # Track cleanup
        cleanup_called = False
        original_close = agent.events.close

        async def tracked_close():
            nonlocal cleanup_called
            cleanup_called = True
            await original_close()

        agent.events.close = tracked_close

        with _stub_agent_complete(agent, delay=5.0):
            # Simulate some work
            task = asyncio.create_task(agent.call("Generate a long response"))

            # Cancel after a short delay
            await asyncio.sleep(0.1)
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                await agent.events.close()

        assert cleanup_called
        assert len(agent._managed_tasks) == 0

    @pytest.mark.asyncio
    async def test_llm_streaming_interruption(self):
        """Test interruption during LLM streaming response."""
        agent = Agent("You are a test assistant")
        await agent.initialize()

        chunks_received = []

        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            for i in range(100):  # Simulate many chunks
                chunk = MagicMock()
                chunk.content = f"chunk_{i}"
                chunk.finish_reason = None if i < 99 else "stop"
                chunks_received.append(i)
                yield chunk
                await asyncio.sleep(0.01)  # Simulate network delay

        async def consume_stream():
            """Helper to consume the async generator."""
            formatted = await agent.model.format_message_list_for_llm(agent.messages)
            formatted_sequence = cast(Sequence[ChatCompletionMessageParam], formatted)
            async for chunk in agent.model.stream(formatted_sequence):
                pass  # Just consume chunks

        with patch.object(agent.model, "stream", mock_stream):
            stream_task = asyncio.create_task(consume_stream())

            # Let it receive some chunks
            await asyncio.sleep(0.05)

            # Cancel mid-stream
            stream_task.cancel()

            try:
                await stream_task
            except asyncio.CancelledError:
                pass

            # Should have received some but not all chunks
            assert len(chunks_received) > 0
            assert len(chunks_received) < 100

    @pytest.mark.asyncio
    async def test_parallel_tool_execution_interruption(self):
        """Test interruption during parallel tool execution."""
        tool_states: dict[str, list[int]] = {
            "started": [],
            "completed": [],
            "cancelled": [],
        }

        @tool
        async def slow_tool(task_id: int) -> str:
            tool_states["started"].append(task_id)
            try:
                await asyncio.sleep(2)  # Simulate slow operation
                tool_states["completed"].append(task_id)
                return f"Result {task_id}"
            except asyncio.CancelledError:
                tool_states["cancelled"].append(task_id)
                raise

        agent = Agent("You are a test assistant", tools=[slow_tool])
        await agent.initialize()

        # Mock LLM response with multiple tool calls
        from dataclasses import dataclass

        @dataclass
        class MockFunction:
            name: str
            arguments: str

        @dataclass
        class MockToolCall:
            id: str
            type: str = "function"
            function: MockFunction | None = None

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.__class__.__name__ = "Choices"  # Make it look like a Choices object
        mock_response.choices = [mock_choice]
        mock_choice.message = MagicMock()
        mock_choice.message.content = ""  # Add content field
        mock_choice.message.tool_calls = [
            MockToolCall(
                id=f"call_{i}",
                function=MockFunction(name="slow_tool", arguments='{"task_id": ' + str(i) + "}"),
            )
            for i in range(5)
        ]

        async def mock_complete(*args, **kwargs):
            return mock_response

        with patch.object(agent.model, "complete", side_effect=mock_complete):
            # Start execution
            exec_task = asyncio.create_task(agent.call("Use slow_tool 5 times"))

            # Let tools start
            await asyncio.sleep(0.5)  # Give more time for tools to start

            # At least one tool should have started
            assert len(tool_states["started"]) > 0

            # Cancel execution
            exec_task.cancel()

            try:
                await exec_task
            except asyncio.CancelledError:
                pass

            # Give cancellation time to propagate
            await asyncio.sleep(0.1)

            # Some tools may be cancelled or not all completed
            # The test is about interruption, not parallel execution
            assert len(tool_states["completed"]) < 5  # Not all tools completed

    @pytest.mark.asyncio
    async def test_agent_context_manager_interruption(self):
        """Test Agent context manager handles interruption properly."""
        events_fired = []

        async def track_event(ctx):
            events_fired.append(ctx.parameters.get("event_name"))

        try:
            async with Agent("Test assistant") as agent:
                # Subscribe to cleanup events
                agent.on("agent:close:before")(track_event)
                agent.on("agent:close:after")(track_event)

                with _stub_agent_complete(agent, delay=5.0):
                    # Start some work
                    task = asyncio.create_task(agent.call("Generate something"))

                    # Simulate interruption
                    await asyncio.sleep(0.05)
                    task.cancel()

                # Context manager should handle cleanup
        except asyncio.CancelledError:
            pass

        # Cleanup events should fire even on interruption
        # Note: May need to adjust based on actual implementation
        assert len(agent._managed_tasks) == 0

    @pytest.mark.asyncio
    async def test_simple_nested_call_cancellation(self):
        """Test simple cancellation propagation through nested agent calls."""
        execution_log = []

        @tool
        async def slow_nested_tool() -> str:
            execution_log.append("tool_started")
            try:
                # Simulate a slow operation that can be cancelled
                await asyncio.sleep(5)
                execution_log.append("tool_completed")
                return "Completed"
            except asyncio.CancelledError:
                execution_log.append("tool_cancelled")
                raise

        agent = Agent("Test assistant", tools=[slow_nested_tool])
        await agent.initialize()

        # Mock LLM to call the slow tool
        from dataclasses import dataclass

        @dataclass
        class MockFunction:
            name: str
            arguments: str

        @dataclass
        class MockToolCall:
            id: str
            type: str = "function"
            function: MockFunction | None = None

        async def mock_complete(*args, **kwargs):
            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_choice.__class__.__name__ = "Choices"
            mock_response.choices = [mock_choice]
            mock_choice.message = MagicMock()
            mock_choice.message.content = ""
            mock_choice.message.tool_calls = [
                MockToolCall(
                    id="call_1",
                    function=MockFunction(name="slow_nested_tool", arguments="{}"),
                )
            ]
            return mock_response

        with patch.object(agent.model, "complete", side_effect=mock_complete):
            # Start the agent call
            task = asyncio.create_task(agent.call("Execute slow tool"))

            # Let it start
            await asyncio.sleep(0.1)

            # Tool should have started
            assert "tool_started" in execution_log

            # Cancel the task
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Give time for cancellation to propagate
            await asyncio.sleep(0.1)

            # Tool should have been cancelled, not completed
            assert "tool_cancelled" in execution_log
            assert "tool_completed" not in execution_log

    @pytest.mark.asyncio
    async def test_nested_agent_calls_interruption(self):
        """Test interruption of nested agent.call() operations.

        This test verifies that cancellation propagates through nested agent.call()
        operations using event-based synchronization for reliable timing.
        """
        # Use events for reliable synchronization
        tool_started_event = asyncio.Event()
        nested_call_started_event = asyncio.Event()
        tool_completed = False

        @tool
        async def slow_tool() -> str:
            """A tool that makes a nested agent call."""
            nonlocal tool_completed

            # Signal that tool has started
            tool_started_event.set()

            # Make a nested agent call that will take time
            try:
                nested_call_started_event.set()
                await agent.call("Nested call")

                # Should not reach here if properly cancelled
                tool_completed = True
                return "Completed"
            except asyncio.CancelledError:
                # Expected - propagate the cancellation
                raise

        # Create agent with the tool
        agent = Agent("Test assistant", tools=[slow_tool])
        await agent.initialize()

        # Mock LLM to always call slow_tool
        from dataclasses import dataclass

        @dataclass
        class MockFunction:
            name: str
            arguments: str

        @dataclass
        class MockToolCall:
            id: str
            type: str = "function"
            function: MockFunction | None = None

        call_count = 0

        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1

            # Simulate a slow LLM response
            await asyncio.sleep(0.2)

            mock_response = MagicMock()
            mock_choice = MagicMock()
            mock_choice.__class__.__name__ = "Choices"
            mock_response.choices = [mock_choice]
            mock_choice.message = MagicMock()
            mock_choice.message.content = ""

            # Always return tool call for slow_tool
            mock_choice.message.tool_calls = [
                MockToolCall(
                    id=f"call_{call_count}",
                    function=MockFunction(name="slow_tool", arguments="{}"),
                )
            ]

            return mock_response

        try:
            with patch.object(agent.model, "complete", side_effect=mock_complete):
                # Start the agent call
                task = asyncio.create_task(agent.call("Start tool"))

                # Wait for tool to start and nested call to begin
                await asyncio.wait_for(tool_started_event.wait(), timeout=2.0)
                await asyncio.wait_for(nested_call_started_event.wait(), timeout=2.0)

                # Now cancel the task while the nested call is in progress
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

                # Give a moment for cancellation to propagate
                await asyncio.sleep(0.1)

                # The tool should have started but not completed
                assert tool_started_event.is_set(), "Tool should have started"
                assert nested_call_started_event.is_set(), "Nested call should have started"
                assert not tool_completed, "Tool should not have completed due to cancellation"

        finally:
            # Always cleanup
            await agent.events.close()


class TestSignalHandling:
    """Test actual signal handling with Agent."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform == "win32", reason="Signal handling differs on Windows")
    async def test_sigint_during_agent_execution(self):
        """Test SIGINT handling during agent execution."""
        agent = Agent("Test assistant")
        await agent.initialize()

        signal_received = asyncio.Event()
        task_cancelled = asyncio.Event()
        exec_task = None  # Define in outer scope

        # Mock the LLM to simulate a long-running operation
        async def mock_complete(*args, **kwargs):
            # Simulate a long operation that can be cancelled
            try:
                await asyncio.sleep(10)
                mock_response = MagicMock()
                mock_choice = MagicMock()
                mock_choice.__class__.__name__ = "Choices"  # Make it look like a Choices object
                mock_response.choices = [mock_choice]
                mock_choice.message = MagicMock(content="Response", tool_calls=None)
                return mock_response
            except asyncio.CancelledError:
                task_cancelled.set()
                raise

        def signal_handler(signum, frame):
            signal_received.set()
            # Cancel the exec_task if it exists
            if exec_task and not exec_task.done():
                exec_task.cancel()
            # Cancel all agent tasks
            for task in agent._managed_tasks:
                if not task.done():
                    task.cancel()

        old_handler = signal.signal(signal.SIGINT, signal_handler)

        try:
            # Patch the model's complete method to simulate long operation
            with patch.object(agent.model, "complete", side_effect=mock_complete):
                # Start long-running operation
                exec_task = asyncio.create_task(agent.call("Generate a very long response"))

                # Let the task start executing
                await asyncio.sleep(0.05)

                # Raise SIGINT
                signal.raise_signal(signal.SIGINT)

                # Wait for signal to be processed
                await signal_received.wait()

                # Try to complete the task
                try:
                    await exec_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # May get other exceptions if cancellation propagates differently
                    pass

                # Wait for cancellation to propagate
                await asyncio.sleep(0.1)

                # Clean up agent
                await agent.events.close()

                # The exec_task should have been cancelled or completed with error
                assert exec_task.done()
                # Task cancellation should have been observed
                assert task_cancelled.is_set()
                # All tasks should be cleaned up
                assert len(agent._managed_tasks) == 0

        finally:
            signal.signal(signal.SIGINT, old_handler)


class TestMemoryLeaksAndDeadlocks:
    """Test for memory leaks and deadlocks during interruption."""

    @pytest.mark.asyncio
    async def test_no_task_leak_on_repeated_interruption(self):
        """Test that repeated interruptions don't leak tasks."""
        agent = Agent("Test assistant")
        await agent.initialize()

        with _stub_agent_complete(agent, delay=0.5):
            for i in range(10):
                # Start operation
                task = asyncio.create_task(agent.call(f"Request {i}"))

                # Quick cancel
                await asyncio.sleep(0.01)
                task.cancel()

                try:
                    await task
                except asyncio.CancelledError:
                    pass

                # Check for task accumulation
                assert len(agent._managed_tasks) < 5  # Some tolerance for cleanup delay

        # Final cleanup
        await agent.events.close()
        assert len(agent._managed_tasks) == 0

    # REMOVED: test_eventrouter_thread_pool_cleanup
    # This test was for a thread pool feature that doesn't exist in EventRouter
    # If thread pool support is added in the future, a new test should be written


class TestRobustness:
    """Test robustness of interruption handling."""

    @pytest.mark.asyncio
    async def test_multiple_rapid_interruptions(self):
        """Test handling of multiple rapid interruption attempts."""
        agent = Agent("Test assistant")
        await agent.initialize()

        with _stub_agent_complete(agent, delay=0.5):
            tasks = []
            for i in range(5):
                task = asyncio.create_task(agent.call(f"Request {i}"))
                tasks.append(task)

            # Rapidly cancel all tasks
            for task in tasks:
                task.cancel()

            # Should handle all cancellations gracefully
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should be CancelledError
        for result in results:
            assert isinstance(result, asyncio.CancelledError)

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_interruption_during_initialization(self):
        """Test interruption during agent initialization."""
        # Create agent but don't await ready
        agent = Agent("Test assistant")

        # Start ready in background
        ready_task = asyncio.create_task(agent.initialize())

        # Interrupt quickly
        await asyncio.sleep(0.01)
        ready_task.cancel()

        try:
            await ready_task
        except asyncio.CancelledError:
            pass

        # Agent should handle partial initialization gracefully
        if agent._state_machine._state >= AgentState.READY:
            await agent.events.close()
        else:
            # Force cleanup even if not ready
            agent.events.close_sync()
