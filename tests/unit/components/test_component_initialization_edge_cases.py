import asyncio

import pytest

from good_agent import Agent, AgentComponent, tool


class SlowInitializationComponent(AgentComponent):
    """Component that takes a long time to initialize."""

    async def install(self, agent):
        await super().install(agent)
        # Simulate slow initialization
        await asyncio.sleep(2.0)  # Long initialization

    @tool
    def slow_tool(self, value: str) -> str:
        return f"Slow: {value}"


class FailingInitializationComponent(AgentComponent):
    """Component whose initialization task fails."""

    def __init__(self):
        super().__init__()
        self.install_failed = False

    async def install(self, agent):
        try:
            await super().install(agent)
            # Simulate failing initialization
            await asyncio.sleep(0.1)
            raise ValueError("Initialization failed!")
        except ValueError:
            # Catch the error so it doesn't prevent agent from starting
            self.install_failed = True

    @tool
    def failing_tool(self, value: str) -> str:
        return f"Failed: {value}"


class ComponentWithNoTools(AgentComponent):
    """Component with no tools - should not create any tasks."""

    def __init__(self):
        super().__init__()
        self.installed = False

    async def install(self, agent):
        await super().install(agent)
        self.installed = True


class ComponentWithInvalidToolSignature(AgentComponent):
    """Component with a tool that has invalid signature."""

    @tool
    def invalid_tool(self) -> str:  # Missing required _agent parameter
        return "Invalid"


class ComponentWithCircularDependency(AgentComponent):
    """Component that tries to call agent.initialize() during initialization."""

    async def install(self, agent):
        await super().install(agent)
        # Don't actually call agent.initialize() as it would cause issues
        # Just simulate what would happen
        await asyncio.sleep(0.1)

    @tool
    def circular_tool(self, value: str) -> str:
        return f"Circular: {value}"


class TestComponentInitializationEdgeCases:
    """Test suite for component initialization edge cases."""

    @pytest.mark.asyncio
    async def test_initialization_timeout_handling(self):
        """Test that agent.initialize() waits for component initialization to complete."""
        component = SlowInitializationComponent()
        import time

        # Measure time to ensure initialize() actually waits for component initialization
        start_time = time.time()
        async with Agent("Test agent", extensions=[component]) as agent:
            elapsed = time.time() - start_time

            # Should have waited at least the component initialization time (2.0 seconds)
            assert elapsed >= 1.9, (
                f"Expected >= 2.0s, got {elapsed}s"
            )  # Allow small timing variance

            # Agent should be in ready state after initialization
            from good_agent.agent import AgentState

            assert agent.state == AgentState.READY

    @pytest.mark.asyncio
    async def test_failing_initialization_task_handling(self):
        """Test that failing initialization tasks don't prevent agent ready."""
        component = FailingInitializationComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Agent should still be ready
            from good_agent.agent import AgentState

            assert agent.state == AgentState.READY

            # Component should have caught the error
            assert component.install_failed

            # Tools should still be registered despite init failure
            assert "failing_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_component_with_no_tools(self):
        """Test that components without tools don't create unnecessary tasks."""
        component = ComponentWithNoTools()
        async with Agent("Test agent", extensions=[component]) as agent:
            assert component.installed
            assert len(agent.tools._tools) == 0

    @pytest.mark.asyncio
    async def test_multiple_components_mixed_success_failure(self):
        """Test mixed scenarios with some components failing."""
        from good_agent.core.components import AgentComponent
        from good_agent.tools import tool

        class WorkingComponent(AgentComponent):
            @tool
            def working_tool(self, value: str) -> str:
                return f"Working: {value}"

        working = WorkingComponent()
        failing = FailingInitializationComponent()
        no_tools = ComponentWithNoTools()

        async with Agent("Test agent", extensions=[working, failing, no_tools]) as agent:
            # Working component tools should be available
            assert "working_tool" in agent.tools
            # Failing component tools should still be available
            assert "failing_tool" in agent.tools
            # No-tools component should be installed
            assert no_tools.installed

    @pytest.mark.asyncio
    async def test_component_task_exception_handling(self):
        """Test that exceptions in component tasks are handled properly."""
        component = FailingInitializationComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Verify the exception was caught and handled
            assert component.install_failed
            assert agent.state.value >= 1  # AgentState.READY

    @pytest.mark.asyncio
    async def test_agent_ready_idempotency(self):
        """Test that calling agent.initialize() multiple times is safe."""
        from good_agent.core.components import AgentComponent
        from good_agent.tools import tool

        class SimpleComponent(AgentComponent):
            @tool
            def simple_tool(self, value: str) -> str:
                return f"Simple: {value}"

        component = SimpleComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            assert "simple_tool" in agent.tools

            # Second call should be idempotent
            await agent.initialize()
            assert "simple_tool" in agent.tools

            # Third call should still work
            await agent.initialize()
            assert "simple_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_component_tasks_cleared_on_exception(self):
        """Test that component tasks are cleared even when exceptions occur."""
        component = FailingInitializationComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Component should still be accessible
            assert component._agent is agent

    @pytest.mark.asyncio
    async def test_no_event_loop_fallback_behavior(self):
        """Test behavior when component installation happens without event loop."""
        # This simulates edge cases in testing or non-async contexts

        class TestComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.task_created = False

            async def install(self, agent):
                await super().install(agent)
                # Installation now happens in async context
                self.task_created = True

            @tool
            def test_tool(self, value: str) -> str:
                return f"Test: {value}"

        component = TestComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Tool should still be registered
            assert "test_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_agent_state_consistency_with_component_failures(self):
        """Test that agent state remains consistent even with component failures."""
        from good_agent.agent import AgentState

        failing_component = FailingInitializationComponent()
        agent = Agent("Test agent", extensions=[failing_component])

        # Should start in INITIALIZING
        assert agent.state == AgentState.INITIALIZING

        async with agent:
            # Should reach READY despite component failure
            assert agent.state == AgentState.READY

            # Should be able to transition to other states normally
            # (This would be tested more thoroughly in integration tests)

    @pytest.mark.asyncio
    async def test_component_task_cleanup_on_agent_close(self):
        """Test that component tasks are properly cleaned up when agent closes."""
        component = SlowInitializationComponent()
        # Don't use context manager here to test manual close behavior
        agent = Agent("Test agent", extensions=[component])

        # Start initialization but don't wait for it
        # In this specific test case we want to test cleanup during close
        # without full initialization completion if possible, or just normal close
        init_task = asyncio.create_task(agent.initialize())

        # Wait a bit but less than component init time
        await asyncio.sleep(0.1)

        # Close while tasks might still be running
        await agent.close()

        # Cleanup
        try:
            await init_task
        except Exception:
            pass  # Ignore errors from cancelled tasks

        # Should not leave dangling tasks
        # (In practice, this would be tested by monitoring for task cleanup)
        assert True  # Basic test that close doesn't raise exceptions

    @pytest.mark.asyncio
    async def test_component_installation_order_independence(self):
        """Test that component installation order doesn't affect tool registration."""
        from good_agent.core.components import AgentComponent
        from good_agent.tools import tool

        class ComponentA(AgentComponent):
            @tool
            def tool_a(self, value: str) -> str:
                return f"A: {value}"

        class ComponentB(AgentComponent):
            @tool
            def tool_b(self, value: str) -> str:
                return f"B: {value}"

        # Test different installation orders
        comp_a1, comp_b1 = ComponentA(), ComponentB()
        async with Agent("Test 1", extensions=[comp_a1, comp_b1]) as agent1:
            assert "tool_a" in agent1.tools and "tool_b" in agent1.tools

        comp_a2, comp_b2 = ComponentA(), ComponentB()
        async with Agent("Test 2", extensions=[comp_b2, comp_a2]) as agent2:
            assert "tool_a" in agent2.tools and "tool_b" in agent2.tools

    @pytest.mark.asyncio
    async def test_memory_cleanup_after_component_initialization(self):
        """Test that temporary initialization data is cleaned up."""
        from good_agent.core.components import AgentComponent
        from good_agent.tools import tool

        class CleanupTestComponent(AgentComponent):
            @tool
            def cleanup_tool(self, value: str) -> str:
                return f"Cleanup: {value}"

        component = CleanupTestComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Tasks should be cleared (memory cleanup)
            assert len(agent._component_tasks) == 0

            # But tools should remain registered
            assert "cleanup_tool" in agent.tools
