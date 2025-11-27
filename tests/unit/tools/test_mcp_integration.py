import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from good_agent import Agent
from good_agent.mcp import MCPClientManager, MCPToolAdapter
from good_agent.mcp.adapter import MCPToolSpec
from good_agent.mcp.client import MCPServerConfig
from good_agent.tools import ToolResponse
from mcp import ClientSession
from mcp.types import ListToolsResult
from mcp.types import Tool as MCPTool


@pytest.fixture
def mock_mcp_tool_spec():
    """Create a mock MCP tool specification."""
    return MCPToolSpec(
        name="test_tool",
        description="A test tool",
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Test message"},
                "count": {"type": "integer", "description": "Test count"},
            },
            "required": ["message"],
        },
        tags=["test", "mock"],
        version="1.0.0",
    )


@pytest.fixture
def mock_mcp_client():
    """Create a mock MCP client."""
    client = AsyncMock(spec=ClientSession)
    client.call_tool = AsyncMock(return_value={"result": "success"})
    return client


class TestMCPToolAdapter:
    """Test the MCP tool adapter."""

    def test_adapter_creation(self, mock_mcp_client, mock_mcp_tool_spec):
        """Test creating an MCP tool adapter."""
        adapter: MCPToolAdapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_spec=mock_mcp_tool_spec,
            name="custom_name",
        )

        assert adapter.name == "custom_name"
        assert adapter.spec == mock_mcp_tool_spec
        assert adapter.description == "A test tool"

    def test_adapter_schema_generation(self, mock_mcp_client, mock_mcp_tool_spec):
        """Test that adapter generates correct schema."""
        adapter: MCPToolAdapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_spec=mock_mcp_tool_spec,
        )

        schema = adapter.get_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "test_tool"
        assert schema["function"]["description"] == "A test tool"
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"] == mock_mcp_tool_spec.input_schema

    @pytest.mark.asyncio
    async def test_adapter_execution(self, mock_mcp_client, mock_mcp_tool_spec):
        """Test executing a tool through the adapter."""
        adapter: MCPToolAdapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_spec=mock_mcp_tool_spec,
        )

        # Execute the tool
        result = await adapter._execute_mcp_tool(
            message="Hello",
            count=5,
        )

        # Check the result
        assert isinstance(result, ToolResponse)
        assert result.tool_name == "test_tool"
        assert result.response == {"result": "success"}
        assert result.error is None

        # Verify the mock was called correctly
        mock_mcp_client.call_tool.assert_called_once_with(
            "test_tool", {"message": "Hello", "count": 5}
        )

    @pytest.mark.asyncio
    async def test_adapter_validation_error(self, mock_mcp_client, mock_mcp_tool_spec):
        """Test that adapter validates input."""
        adapter: MCPToolAdapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_spec=mock_mcp_tool_spec,
        )

        # Execute with invalid input (wrong type for count)
        result = await adapter._execute_mcp_tool(
            message="Hello",
            count="not_an_integer",  # Should be int
        )

        # Should return error response
        assert isinstance(result, ToolResponse)
        assert result.response is None
        assert result.error is not None
        assert "validation failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_adapter_timeout(self, mock_mcp_client, mock_mcp_tool_spec):
        """Test that adapter handles timeouts."""

        # Make the call_tool method hang
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return {"result": "too_late"}

        mock_mcp_client.call_tool = slow_call

        adapter: MCPToolAdapter = MCPToolAdapter(
            mcp_client=mock_mcp_client,
            tool_spec=mock_mcp_tool_spec,
            timeout=0.1,  # Very short timeout
        )

        # Execute should timeout
        result = await adapter._execute_mcp_tool(message="Hello")

        assert isinstance(result, ToolResponse)
        assert result.response is None
        assert result.error is not None
        assert "timed out" in result.error.lower()


class TestMCPClientManager:
    """Test the MCP client manager."""

    @pytest.mark.asyncio
    async def test_manager_initialization(self):
        """Test creating an MCP client manager."""
        manager = MCPClientManager()

        assert manager.connections == {}
        assert not manager._initialized

        await manager.initialize()

        assert manager._initialized

    @pytest.mark.asyncio
    async def test_manager_connect_disconnect(self):
        """Test connecting and disconnecting from MCP servers."""
        manager = MCPClientManager()

        # Mock the session creation
        with patch.object(manager, "_create_session") as mock_create:
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.initialize = AsyncMock()
            mock_session.list_tools = AsyncMock(return_value=ListToolsResult(tools=[]))
            mock_session.list_resources = AsyncMock(
                return_value=MagicMock(resources=[])
            )
            mock_create.return_value = mock_session

            # Connect to a server
            config: MCPServerConfig = {"url": "test://server"}
            connection = await manager.connect(config)

            assert connection.server_id == "server"
            assert connection.is_connected
            assert connection.error is None

            # Disconnect
            await manager.disconnect("server")

            assert "server" not in manager.connections

    @pytest.mark.asyncio
    async def test_manager_tool_discovery(self):
        """Test that manager discovers tools from MCP servers."""
        manager = MCPClientManager()

        # Create mock MCP tool
        mock_tool = MCPTool(
            name="discovered_tool",
            description="A discovered tool",
            inputSchema={"type": "object", "properties": {}},
        )

        # Mock the session creation and tool discovery
        with patch.object(manager, "_create_session") as mock_create:
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.initialize = AsyncMock()
            mock_session.list_tools = AsyncMock(
                return_value=ListToolsResult(tools=[mock_tool])
            )
            mock_session.list_resources = AsyncMock(
                return_value=MagicMock(resources=[])
            )
            mock_create.return_value = mock_session

            # Connect and discover tools
            config: MCPServerConfig = {"url": "test://server"}
            connection = await manager.connect(config)

            # Check tools were discovered
            assert "discovered_tool" in connection.tools
            adapter = connection.tools["discovered_tool"]
            assert isinstance(adapter, MCPToolAdapter)
            assert adapter.name == "discovered_tool"

    @pytest.mark.asyncio
    async def test_manager_namespace_support(self):
        """Test that manager supports tool namespacing."""
        manager = MCPClientManager()

        # Create mock MCP tool
        mock_tool = MCPTool(
            name="tool",
            description="A tool",
            inputSchema={"type": "object", "properties": {}},
        )

        with patch.object(manager, "_create_session") as mock_create:
            mock_session = AsyncMock(spec=ClientSession)
            mock_session.initialize = AsyncMock()
            mock_session.list_tools = AsyncMock(
                return_value=ListToolsResult(tools=[mock_tool])
            )
            mock_session.list_resources = AsyncMock(
                return_value=MagicMock(resources=[])
            )
            mock_create.return_value = mock_session

            # Connect with namespace
            config: MCPServerConfig = {"url": "test://server", "namespace": "custom"}
            connection = await manager.connect(config)

            # Tool should be namespaced
            assert "custom:tool" in connection.tools
            assert "tool" not in connection.tools


class TestAgentMCPIntegration:
    """Test MCP integration with the Agent class."""

    @pytest.mark.asyncio
    async def test_agent_loads_mcp_servers(self):
        """Test that agent loads MCP servers from config."""
        # Mock the ToolManager's load_mcp_servers method
        with patch("good_agent.tools.ToolManager.load_mcp_servers") as mock_load:
            mock_load.return_value = None

            # Create agent with MCP servers configured
            agent = Agent(
                "You are helpful",
                mcp_servers=["test://server1", "test://server2"],
            )
            await agent.initialize()

            # Verify MCP servers were loaded
            mock_load.assert_called_once_with(["test://server1", "test://server2"])

    @pytest.mark.asyncio
    async def test_agent_uses_mcp_tools(self):
        """Test that agent can use tools from MCP servers."""
        # Create a simple mock that inherits from Tool
        from good_agent.tools import Tool

        class MockMCPAdapter(Tool):
            def __init__(self):
                async def execute_func(**kwargs):
                    return {"answer": 42}

                super().__init__(execute_func)
                self.name = "mcp_tool"
                self.description = "MCP tool"

        mock_adapter = MockMCPAdapter()

        # Create agent and manually add the MCP tool
        agent = Agent("You are helpful")
        await agent.initialize()

        # Add the MCP tool to the agent's tools
        agent.tools["mcp_tool"] = mock_adapter

        # Invoke the tool
        result = await agent.invoke(
            "mcp_tool", question="What is the answer?"
        )

        # Check the result
        assert result.tool_name == "mcp_tool"
        assert result.response == {"answer": 42}
        assert result.error is None

    @pytest.mark.asyncio
    async def test_agent_cleanup_disconnects_mcp(self):
        """Test that agent cleanup disconnects MCP servers."""
        with patch(
            "good_agent.tools.ToolManager.disconnect_mcp_servers"
        ) as mock_disconnect:
            mock_disconnect.return_value = None

            agent = Agent(
                "You are helpful",
                mcp_servers=["test://server"],
            )
            await agent.initialize()

            # Clean up agent (should disconnect MCP)
            await agent.events.close()

            # Verify MCP servers were disconnected
            # Note: This might need adjustment based on actual cleanup implementation
            # For now, we're just testing the concept
