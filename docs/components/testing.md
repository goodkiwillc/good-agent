# Testing Components

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

## Unit Testing Component Tools

```python
import pytest
from good_agent import Agent, AgentComponent, tool

class TestableComponent(AgentComponent):
    def __init__(self):
        super().__init__()
        self.call_count = 0
    
    @tool
    async def test_tool(self, value: str) -> str:
        """A tool for testing."""
        self.call_count += 1
        return f"Called {self.call_count} times with '{value}'"

@pytest.mark.asyncio
async def test_component_tool_registration():
    """Test that component tools are registered correctly."""
    component = TestableComponent()
    agent = Agent("Test agent", extensions=[component])
    await agent.initialize()
    
    # Tool should be registered
    assert "test_tool" in agent.tools
    
    # Tool should work
    result = await agent.tools["test_tool"](_agent=agent, value="test")
    assert result.success
    assert "Called 1 times" in result.response
    
    # Component state should be updated
    assert component.call_count == 1

@pytest.mark.asyncio
async def test_component_enable_disable():
    """Test component enable/disable functionality."""
    component = TestableComponent()
    agent = Agent("Test agent", extensions=[component])
    await agent.initialize()
    
    # Initially enabled
    assert component.enabled
    assert "test_tool" in agent.tools
    
    # Disable component
    component.enabled = False
    assert "test_tool" not in agent.tools
    
    # Re-enable component
    component.enabled = True
    assert "test_tool" in agent.tools
```

## Integration Testing with Events

```python
@pytest.mark.asyncio
async def test_component_event_handling():
    """Test component event handling."""
    events_received = []
    
    class EventTestComponent(AgentComponent):
        @on(AgentEvents.MESSAGE_APPEND_AFTER)
        def track_messages(self, ctx):
            events_received.append(ctx.parameters["message"].content)
    
    agent = Agent("Test", extensions=[EventTestComponent()])
    await agent.initialize()
    
    # Add messages
    agent.append("Hello")
    agent.append("World")
    
    # Events should have been received
    assert len(events_received) == 2
    assert "Hello" in events_received
    assert "World" in events_received
```

## Mocking Component Dependencies

```python
from unittest.mock import Mock

@pytest.mark.asyncio
async def test_component_with_mocked_dependency():
    """Test component with mocked external dependencies."""
    
    class ExternalServiceComponent(AgentComponent):
        def __init__(self, service_client=None):
            super().__init__()
            self.service_client = service_client or self._create_client()
        
        def _create_client(self):
            # In real code, this would create actual service client
            return Mock()
        
        @tool
        async def call_service(self, data: str) -> str:
            """Call external service."""
            result = await self.service_client.call_api(data)
            return f"Service returned: {result}"
    
    # Create component with mocked client
    mock_client = Mock()
    mock_client.call_api.return_value = "mocked_response"
    
    component = ExternalServiceComponent(service_client=mock_client)
    agent = Agent("Test", extensions=[component])
    await agent.initialize()
    
    # Test tool with mock
    result = await agent.tools["call_service"](_agent=agent, data="test")
    assert "mocked_response" in result.response
    
    # Verify mock was called
    mock_client.call_api.assert_called_once_with("test")
```
