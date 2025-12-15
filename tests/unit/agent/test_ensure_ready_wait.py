import asyncio

import pytest

from good_agent.agent.core import Agent, ensure_ready


class TestEnsureReadyWait:
    @pytest.mark.asyncio
    async def test_ensure_ready_waits_for_tasks(self):
        """Test that ensure_ready(wait_for_tasks=True) waits for pending tasks."""

        # Create a task that takes some time
        task_completed = False

        async def slow_task():
            nonlocal task_completed
            await asyncio.sleep(0.1)
            task_completed = True

        class MyAgent(Agent):
            def __init__(self):
                # Minimal init
                super().__init__(model="gpt-4o-mini")

            @ensure_ready(wait_for_tasks=True)
            async def my_method(self):
                return task_completed

        agent = MyAgent()
        await agent.initialize()

        # Create a managed task
        agent.create_task(slow_task(), name="slow_task", wait_on_ready=False)

        # Verify task is not done yet (we just started it and haven't yielded execution much)
        assert not task_completed

        # Call method which should wait for the task
        result = await agent.my_method()

        assert result is True
        assert task_completed

    @pytest.mark.asyncio
    async def test_ensure_ready_default_does_not_wait(self):
        """Test that ensure_ready() by default does not wait for tasks."""

        task_completed = False

        async def slow_task():
            nonlocal task_completed
            await asyncio.sleep(0.2)
            task_completed = True

        class MyAgent(Agent):
            def __init__(self):
                super().__init__(model="gpt-4o-mini")

            @ensure_ready
            async def my_method(self):
                return task_completed

        agent = MyAgent()
        await agent.initialize()

        agent.create_task(slow_task(), name="slow_task", wait_on_ready=False)

        # Call method which should NOT wait
        result = await agent.my_method()

        assert result is False
        assert not task_completed

        # Clean up
        await agent.wait_for_tasks()

    @pytest.mark.asyncio
    async def test_ensure_ready_waits_for_events(self):
        """Test that ensure_ready(wait_for_events=True) waits for events."""

        event_processed = False

        class MyAgent(Agent):
            def __init__(self):
                super().__init__(model="gpt-4o-mini")

            @ensure_ready(wait_for_events=True)
            async def my_method(self):
                return event_processed

        agent = MyAgent()
        await agent.initialize()

        # Register an async handler
        @agent.on("test_event")
        async def handle_event(ctx):
            nonlocal event_processed
            await asyncio.sleep(0.1)
            event_processed = True

        # Fire event
        await agent.events.apply_async("test_event")

        # Call method which should wait for events
        result = await agent.my_method()

        assert result is True
        assert event_processed

    @pytest.mark.asyncio
    async def test_ensure_ready_async_generator(self):
        """Test that ensure_ready works with async generators."""

        task_completed = False

        async def slow_task():
            nonlocal task_completed
            await asyncio.sleep(0.1)
            task_completed = True

        class MyAgent(Agent):
            def __init__(self):
                super().__init__(model="gpt-4o-mini")

            @ensure_ready(wait_for_tasks=True)
            async def my_generator(self):
                yield task_completed
                yield "done"

        agent = MyAgent()
        await agent.initialize()

        agent.create_task(slow_task(), name="slow_task", wait_on_ready=False)

        # Consume generator
        results = []
        async for item in agent.my_generator():
            results.append(item)

        assert results[0] is True
        assert results[1] == "done"
        assert task_completed

    @pytest.mark.asyncio
    async def test_ensure_ready_timeout(self):
        """Test that ensure_ready raises TimeoutError when operations take too long."""

        async def very_slow_task():
            await asyncio.sleep(1.0)

        class MyAgent(Agent):
            def __init__(self):
                super().__init__(model="gpt-4o-mini")

            @ensure_ready(wait_for_tasks=True, timeout=0.1)
            async def my_method(self):
                return "success"

        agent = MyAgent()
        await agent.initialize()

        agent.create_task(very_slow_task(), name="slow_task", wait_on_ready=False)

        # Should raise TimeoutError
        with pytest.raises(asyncio.TimeoutError):
            await agent.my_method()

        # Clean up
        await agent.tasks.cancel_all()

    @pytest.mark.asyncio
    async def test_ensure_ready_combined_wait(self):
        """Test ensure_ready with both tasks and events waiting."""

        task_done = False
        event_done = False

        async def slow_task():
            nonlocal task_done
            await asyncio.sleep(0.1)
            task_done = True

        class MyAgent(Agent):
            def __init__(self):
                super().__init__(model="gpt-4o-mini")

            @ensure_ready(wait_for_tasks=True, wait_for_events=True)
            async def my_method(self):
                return task_done and event_done

        agent = MyAgent()
        await agent.initialize()

        @agent.on("test_event")
        async def handle_event(ctx):
            nonlocal event_done
            await asyncio.sleep(0.1)
            event_done = True

        # Start both
        agent.create_task(slow_task(), wait_on_ready=False)
        await agent.events.apply_async("test_event")

        result = await agent.my_method()

        assert result is True
        assert task_done
        assert event_done
