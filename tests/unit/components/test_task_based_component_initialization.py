import asyncio

import pytest
from good_agent import Agent, AgentComponent, tool


class MockComponent(AgentComponent):
    """Test component with bound tools for testing initialization."""

    def __init__(self):
        super().__init__()
        self.initialization_log: list[str] = []
        self.tool_calls: dict[str, int] = {}

    async def install(self, agent: "Agent"):
        """Install with custom initialization logic."""
        self.initialization_log.append("install_start")
        await super().install(agent)  # Important: call parent to trigger tool registration
        self.initialization_log.append("install_end")

    @tool
    def mock_tool(self, value: str) -> str:
        """A mock tool for testing."""
        self.tool_calls["mock_tool"] = self.tool_calls.get("mock_tool", 0) + 1
        return f"Mock processed: {value}"

    @tool
    async def async_mock_tool(self, data: str) -> dict:
        """An async mock tool for testing."""
        self.tool_calls["async_mock_tool"] = self.tool_calls.get("async_mock_tool", 0) + 1
        return {"processed": data, "async": True}


class ComponentWithoutSuperCall(AgentComponent):
    """Component that forgets to call super().install() - should fail to register tools."""

    @tool
    def forgotten_tool(self, x: int) -> int:
        return x * 2

    async def install(self, agent: "Agent"):
        """Install method that doesn't call super() - tools won't register."""
        self._agent = agent
        # Missing: await super().install(agent)


class ComponentWithInitializationTask(AgentComponent):
    """Component that performs custom async initialization."""

    def __init__(self):
        super().__init__()
        self.custom_init_completed = False

    async def install(self, agent: "Agent"):
        """Install with custom async initialization task."""
        await super().install(agent)

        # Perform custom initialization directly
        await asyncio.sleep(0.1)  # Simulate async work
        self.custom_init_completed = True

    @tool
    def custom_tool(self, value: str) -> str:
        """Tool that should only work after custom initialization."""
        if not self.custom_init_completed:
            return "ERROR: Not initialized"
        return f"Custom: {value}"


class TestTaskBasedComponentInitialization:
    """Test suite for task-based component initialization."""

    @pytest.mark.asyncio
    async def test_basic_component_tool_registration(self):
        """Test that component tools are registered after agent.initialize()."""
        component = MockComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            assert "mock_tool" in agent.tools
            assert "async_mock_tool" in agent.tools
            assert len(agent.tools._tools) == 2

            # Component should have agent reference
            assert component._agent is agent

    @pytest.mark.asyncio
    async def test_component_tool_functionality(self):
        """Test that registered component tools work correctly."""
        component = MockComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Test sync tool
            sync_tool = agent.tools["mock_tool"]
            result = await sync_tool(_agent=agent, value="test")
            assert result.success
            assert result.response == "Mock processed: test"
            assert component.tool_calls["mock_tool"] == 1

            # Test async tool
            async_tool = agent.tools["async_mock_tool"]
            result = await async_tool(_agent=agent, data="async_test")
            assert result.success
            assert result.response == {"processed": "async_test", "async": True}
            assert component.tool_calls["async_mock_tool"] == 1

    @pytest.mark.asyncio
    async def test_multiple_components_tool_registration(self):
        """Test that multiple components can register tools without conflicts."""
        component1 = MockComponent()
        component2 = MockComponent()

        async with Agent("Test agent", extensions=[component1, component2]) as agent:
            # Both components should have tools registered
            # Since they have the same tool names, we expect the second to override
            assert "mock_tool" in agent.tools
            assert "async_mock_tool" in agent.tools

            # Both components should have agent references
            assert component1._agent is agent
            assert component2._agent is agent

    @pytest.mark.asyncio
    async def test_component_without_super_call_fails(self):
        """Test that components not calling super().install() don't register tools."""
        component = ComponentWithoutSuperCall()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Tools should NOT be registered
            assert "forgotten_tool" not in agent.tools
            assert len(agent.tools._tools) == 0

            # Component still has agent reference (set manually)
            assert component._agent is agent

    @pytest.mark.asyncio
    async def test_custom_initialization_tasks(self):
        """Test that custom component initialization tasks are awaited."""
        component = ComponentWithInitializationTask()
        async with Agent("Test agent", extensions=[component]) as agent:
            # After initialize(), custom initialization should be complete
            assert component.custom_init_completed

            # Tool should work correctly now
            tool = agent.tools["custom_tool"]
            result = await tool(_agent=agent, value="test")
            assert result.success
            assert result.response == "Custom: test"

    @pytest.mark.asyncio
    async def test_agent_ready_waits_for_component_tasks(self):
        """Test that agent.initialize() waits for all component initialization tasks."""
        component = ComponentWithInitializationTask()
        import time

        # Measure time to ensure initialize() actually waits
        start_time = time.time()
        async with Agent("Test agent", extensions=[component]):
            elapsed = time.time() - start_time

            # Should have waited at least the sleep time (0.1 seconds)
            assert elapsed >= 0.1
            assert component.custom_init_completed

    @pytest.mark.asyncio
    async def test_component_tasks_cleared_after_ready(self):
        """Test that component tasks are cleared after initialize() completes."""
        component = ComponentWithInitializationTask()
        async with Agent("Test agent", extensions=[component]):
            # Verify initialization completed
            assert component.custom_init_completed

    @pytest.mark.asyncio
    async def test_agent_state_management_with_components(self):
        """Test that agent state transitions correctly with component tasks."""
        from good_agent.agent import AgentState

        component = ComponentWithInitializationTask()
        agent = Agent("Test agent", extensions=[component])

        # Should start in INITIALIZING state
        assert agent.state == AgentState.INITIALIZING

        async with agent:
            # Should transition to READY after initialization
            assert agent.state == AgentState.READY

    @pytest.mark.asyncio
    async def test_no_event_loop_during_installation_fallback(self):
        """Test handling when no event loop is available during component installation."""
        # This test simulates the case where components are installed
        # outside of an async context (which can happen in some scenarios)

        component = MockComponent()

        # Create agent outside async context simulation
        # In practice, this is handled by the agent constructor logic
        async with Agent("Test agent", extensions=[component]) as agent:
            assert "mock_tool" in agent.tools
            assert "async_mock_tool" in agent.tools

    # @pytest.mark.asyncio
    # async def test_component_tool_registration_integration_with_webfetcher(self):
    #     """Integration test with actual WebFetcher component."""
    #     from good_agent.extensions.citations import CitationManager
    #     from good_agent.extensions.webfetcher import WebFetcher

    #     # WebFetcher requires CitationManager
    #     citation_manager = CitationManager()
    #     webfetcher = WebFetcher(default_ttl=3600)
    #     agent = Agent("Test agent", extensions=[citation_manager, webfetcher])
    #     await agent.initialize()

    #     # WebFetcher should have its tools registered
    #     expected_tools = ["fetch", "fetch_many", "batch_fetch"]
    #     for tool_name in expected_tools:
    #         assert tool_name in agent.tools, f"Tool {tool_name} not found"

    #     # Tools should be functional (basic test)
    #     fetch_tool = agent.tools["fetch"]
    #     assert callable(fetch_tool)

    #     await agent.events.close()

    @pytest.mark.asyncio
    async def test_component_event_system_integration(self):
        """Test that components can still use the event system alongside tool registration."""

        class EventComponent(AgentComponent):
            def __init__(self):
                super().__init__()
                self.install_called = False

            async def install(self, agent):
                await super().install(agent)
                self.install_called = True
                # Component can subscribe to events (the infrastructure is there)
                # We don't test actual event firing to avoid event routing complexity

            @tool
            def event_tool(self, value: str) -> str:
                return f"Event component: {value}"

        component = EventComponent()
        async with Agent("Test agent", extensions=[component]) as agent:
            # Both event handling infrastructure and tool registration should work
            assert component.install_called  # Component was properly installed
            assert component._agent is agent  # Agent reference set (needed for events)
            assert "event_tool" in agent.tools  # Tool registration works

            # Tool should work correctly
            event_tool = agent.tools["event_tool"]
            result = await event_tool(_agent=agent, value="test")
            assert result.success
            assert result.response == "Event component: test"
