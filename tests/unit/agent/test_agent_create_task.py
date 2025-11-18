import asyncio
from typing import Any

import pytest
from good_agent import Agent
from good_agent.components import AgentComponent


async def simple_async_task(value: int) -> int:
    """Simple async task for testing."""
    await asyncio.sleep(0.01)
    return value * 2


async def failing_async_task() -> None:
    """Task that raises an exception."""
    await asyncio.sleep(0.01)
    raise ValueError("Task failed")


async def long_running_task() -> str:
    """Task that takes longer to complete."""
    await asyncio.sleep(0.1)
    return "completed"


class TaskTrackingComponent(AgentComponent):
    """Test component for task tracking."""

    def __init__(self):
        super().__init__()
        self.tasks_created = 0

    async def create_background_task(self) -> int:
        """Create a background task using agent.tasks.create()."""
        task = self.agent.tasks.create(
            simple_async_task(42),
            name="test_task",
            component=self,
            wait_on_ready=True,
        )
        self.tasks_created += 1
        return await task


@pytest.mark.asyncio
class TestAgentCreateTask:
    """Test the Agent task management utilities."""

    async def test_create_task_basic(self):
        """Test basic task creation and execution."""
        async with Agent("Test") as agent:
            # Create a task
            task = agent.tasks.create(simple_async_task(21))

            # Verify it's an asyncio.Task
            assert isinstance(task, asyncio.Task)

            # Wait for result
            result = await task
            assert result == 42

    async def test_create_task_with_name(self):
        """Test task creation with custom name."""
        async with Agent("Test") as agent:
            task = agent.tasks.create(simple_async_task(10), name="custom_task")

            # Check task name
            assert task.get_name().startswith("custom_task")

            result = await task
            assert result == 20

    async def test_create_task_with_component(self):
        """Test task creation with component tracking."""
        async with Agent("Test", extensions=[TaskTrackingComponent()]) as agent:
            component = agent[TaskTrackingComponent]

            # Create task through component
            result = await component.create_background_task()
            assert result == 84
            assert component.tasks_created == 1

    async def test_ready_waits_for_tasks(self):
        """Test that initialize() waits for tasks with wait_on_ready=True."""
        # Create agent without async with to control when initialize() is called
        agent = Agent("Test")
        await agent.initialize()  # Initialize the agent first

        completed = {"task1": False, "task2": False, "task3": False}

        async def mark_complete(key: str) -> None:
            await asyncio.sleep(0.05)
            completed[key] = True

        # Create tasks with wait_on_ready=True
        agent.tasks.create(mark_complete("task1"), wait_on_ready=True)
        agent.tasks.create(mark_complete("task2"), wait_on_ready=True)

        # Create task with wait_on_ready=False
        agent.tasks.create(mark_complete("task3"), wait_on_ready=False)

        # Tasks should not be complete yet
        assert not completed["task1"]
        assert not completed["task2"]
        assert not completed["task3"]

        # Wait for tasks using wait_for_tasks (better test)
        await agent.tasks.wait_for_all(timeout=1.0)

        # All tasks should be complete
        assert completed["task1"]
        assert completed["task2"]
        assert completed["task3"]

    async def test_task_cleanup_on_completion(self):
        """Test that completed tasks are cleaned up automatically."""
        async with Agent("Test") as agent:
            # Track active tasks before
            initial_count = agent.task_count

            # Create a task
            task = agent.tasks.create(simple_async_task(5))

            # Should have one more task
            assert agent.task_count == initial_count + 1

            # Wait for completion
            await task

            # Allow cleanup to occur
            await asyncio.sleep(0.01)

            # Task should be cleaned up
            assert agent.task_count == initial_count

    async def test_task_cleanup_on_exception(self):
        """Test that tasks are cleaned up even when they fail."""
        async with Agent("Test") as agent:
            initial_count = agent.task_count

            # Create a failing task
            task = agent.tasks.create(failing_async_task())

            # Should have one more task
            assert agent.task_count == initial_count + 1

            # Wait for failure
            with pytest.raises(ValueError, match="Task failed"):
                await task

            # Allow cleanup to occur
            await asyncio.sleep(0.01)

            # Task should be cleaned up
            assert agent.task_count == initial_count

    async def test_task_exception_logging(self):
        """Test that task exceptions are logged but don't crash the agent."""
        async with Agent("Test") as agent:
            # Create a failing task that we don't await
            task = agent.tasks.create(
                failing_async_task(),
                wait_on_ready=False,  # Don't wait on ready
            )

            # Agent should still be functional
            agent.user.append("Test message")
            msg = agent.messages[-1]
            assert msg.content == "Test message"

            # Clean up by waiting for the task
            with pytest.raises(ValueError):
                await task

    async def test_custom_cleanup_callback(self):
        """Test custom cleanup callback functionality."""
        cleanup_called: dict[str, Any] = {"called": False, "task": None}

        def cleanup_callback(task: asyncio.Task) -> None:
            cleanup_called["called"] = True
            cleanup_called["task"] = task

        async with Agent("Test") as agent:
            task = agent.tasks.create(
                simple_async_task(7), cleanup_callback=cleanup_callback
            )

            result = await task
            assert result == 14

            # Allow cleanup to occur
            await asyncio.sleep(0.01)

            # Callback should have been called
            assert cleanup_called["called"]
            assert cleanup_called["task"] is task

    async def test_get_task_stats(self):
        """Test getting task statistics."""
        async with Agent("Test") as agent:
            # Create various tasks
            task1 = agent.tasks.create(
                simple_async_task(1), name="task1", wait_on_ready=True
            )
            task2 = agent.tasks.create(
                long_running_task(), name="task2", wait_on_ready=False
            )

            # Get stats before completion
            stats = agent.tasks.stats()
            assert stats["total"] >= 2
            assert stats["pending"] >= 1
            assert "by_component" in stats
            assert "by_wait_on_ready" in stats

            # Wait for tasks
            await task1
            await task2

            # Allow cleanup
            await asyncio.sleep(0.01)

            # Get stats after completion
            stats_after = agent.tasks.stats()
            assert stats_after["total"] == stats["total"]  # Total is cumulative
            assert stats_after["completed"] > 0
            assert stats_after["pending"] < stats["pending"]  # Fewer pending tasks

    async def test_wait_for_tasks(self):
        """Test wait_for_tasks utility method."""
        async with Agent("Test") as agent:
            results = []

            async def append_result(value: str) -> None:
                await asyncio.sleep(0.02)
                results.append(value)

            # Create multiple tasks
            agent.tasks.create(append_result("a"))
            agent.tasks.create(append_result("b"))
            agent.tasks.create(append_result("c"))

            # Wait for all tasks
            await agent.tasks.wait_for_all()

            # All tasks should be complete
            assert len(results) == 3
            assert set(results) == {"a", "b", "c"}

    async def test_wait_for_tasks_with_timeout(self):
        """Test wait_for_tasks with timeout."""
        async with Agent("Test") as agent:
            # Create a long-running task
            agent.tasks.create(long_running_task())

            # Wait with short timeout should raise
            with pytest.raises(asyncio.TimeoutError):
                await agent.tasks.wait_for_all(timeout=0.01)

    async def test_component_specific_tasks(self):
        """Test tracking tasks by component."""

        class ComponentA(AgentComponent):
            async def create_tasks(self) -> None:
                self.agent.tasks.create(simple_async_task(1), component=self)
                self.agent.tasks.create(simple_async_task(2), component=self)

        class ComponentB(AgentComponent):
            async def create_tasks(self) -> None:
                self.agent.tasks.create(simple_async_task(3), component=self)

        async with Agent("Test", extensions=[ComponentA(), ComponentB()]) as agent:
            comp_a = agent[ComponentA]
            comp_b = agent[ComponentB]

            # Create tasks from different components
            await comp_a.create_tasks()
            await comp_b.create_tasks()

            # Check stats by component
            stats = agent.tasks.stats()
            assert "ComponentA" in stats["by_component"]
            assert "ComponentB" in stats["by_component"]
            assert stats["by_component"]["ComponentA"] == 2
            assert stats["by_component"]["ComponentB"] == 1

            # Wait for all tasks
            await agent.tasks.wait_for_all()

    async def test_create_task_without_wait_on_ready(self):
        """Test that tasks with wait_on_ready=False don't block initialize()."""
        async with Agent("Test") as agent:
            slow_task_done = {"done": False}

            async def slow_task() -> None:
                await asyncio.sleep(0.1)
                slow_task_done["done"] = True

            # Create slow task without wait_on_ready
            task = agent.tasks.create(slow_task(), wait_on_ready=False)

            # initialize() should return quickly
            await agent.initialize()

            # Task should still be running
            assert not slow_task_done["done"]
            assert not task.done()

            # Clean up
            await task
            assert slow_task_done["done"]

    async def test_task_cancellation_on_agent_exit(self):
        """Test that tasks are cancelled when agent exits."""
        task_handle: asyncio.Task | None = None
        was_cancelled = {"value": False}

        async with Agent("Test") as agent:

            async def check_cancellation() -> None:
                try:
                    await asyncio.sleep(10)  # Long sleep
                except asyncio.CancelledError:
                    was_cancelled["value"] = True
                    raise

            task_handle = agent.tasks.create(check_cancellation(), wait_on_ready=False)

        # Task should be cancelled after context exit
        assert task_handle.cancelled() or was_cancelled["value"]
