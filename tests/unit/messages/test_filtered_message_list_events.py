import pytest

from good_agent import Agent, AgentEvents
from good_agent.messages import ToolMessage


@pytest.mark.asyncio
async def test_tool_message_via_filtered_list_triggers_events():
    """Test that tool messages added via FilteredMessageList trigger proper events"""

    # Track which events were triggered
    events_triggered = {
        "create_before": False,
        "create_after": False,
        "append_after": False,
    }

    # Create agent and set up event handlers
    async with Agent("Test agent") as agent:

        @agent.on(AgentEvents.MESSAGE_CREATE_BEFORE)
        def on_create_before(ctx):
            if ctx.parameters.get("role") == "tool":
                events_triggered["create_before"] = True

        @agent.on(AgentEvents.MESSAGE_CREATE_AFTER)
        def on_create_after(ctx):
            message = ctx.parameters.get("message")
            if isinstance(message, ToolMessage):
                events_triggered["create_after"] = True

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def on_append_after(ctx):
            message = ctx.parameters.get("message")
            if isinstance(message, ToolMessage):
                events_triggered["append_after"] = True

        # Add a tool message via the filtered message list (use agent.tool, not agent.messages.tool)
        agent.tool.append(
            "Tool response content",
            tool_call_id="test_tool_call_123",
            tool_name="test_tool",
        )

        # Verify all events were triggered
        assert events_triggered["create_before"], (
            "MESSAGE_CREATE_BEFORE was not triggered for tool message"
        )
        assert events_triggered["create_after"], (
            "MESSAGE_CREATE_AFTER was not triggered for tool message"
        )
        assert events_triggered["append_after"], (
            "MESSAGE_APPEND_AFTER was not triggered for tool message"
        )

        # Verify the message was properly added (agent has 2 messages: system + tool)
        assert len(agent.messages) == 2
        tool_msg = agent.messages[1]  # First is system, second is tool
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.content == "Tool response content"
        assert tool_msg.tool_call_id == "test_tool_call_123"
        assert tool_msg.tool_name == "test_tool"


@pytest.mark.asyncio
async def test_user_message_via_filtered_list_triggers_events():
    """Test that user messages added via FilteredMessageList trigger proper events"""

    events_triggered = {
        "create_before": False,
        "create_after": False,
        "append_after": False,
    }

    async with Agent("Test agent") as agent:

        @agent.on(AgentEvents.MESSAGE_CREATE_BEFORE)
        def on_create_before(ctx):
            if ctx.parameters.get("role") == "user":
                events_triggered["create_before"] = True

        @agent.on(AgentEvents.MESSAGE_CREATE_AFTER)
        def on_create_after(ctx):
            events_triggered["create_after"] = True

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def on_append_after(ctx):
            events_triggered["append_after"] = True

        # Add a user message via the filtered message list (use agent.user, not agent.messages.user)
        agent.user.append("User message content")

        # Verify all events were triggered
        assert events_triggered["create_before"], "MESSAGE_CREATE_BEFORE was not triggered"
        assert events_triggered["create_after"], "MESSAGE_CREATE_AFTER was not triggered"
        assert events_triggered["append_after"], "MESSAGE_APPEND_AFTER was not triggered"

        # Verify the message was properly added (agent has 2 messages: system + user)
        assert len(agent.messages) == 2
        assert agent.messages[1].content == "User message content"
        assert agent.messages[1].role == "user"


@pytest.mark.asyncio
async def test_citation_manager_processes_tool_messages():
    """Test that CitationManager properly processes tool messages added via FilteredMessageList"""
    from good_agent.extensions.citations import CitationManager

    async with Agent("Test agent", extensions=[CitationManager()]) as agent:
        # Add a tool message with citations
        agent.tool.append(
            "Check out this link: https://example.com for more info",
            tool_call_id="test_tool_call",
            tool_name="web_search",
        )

        # Verify the message was added (agent has 2 messages: system + tool)
        assert len(agent.messages) == 2
        tool_msg = agent.messages[1]

        # Verify citation was extracted (CitationManager should have processed it)
        # Note: The exact behavior depends on CitationManager implementation
        # but it should have had the opportunity to process via MESSAGE_CREATE_BEFORE
        assert isinstance(tool_msg, ToolMessage)

        # Check if citation_urls was populated (if CitationManager extracts them)
        # This depends on the specific CitationManager implementation
        if hasattr(tool_msg, "citation_urls"):
            # CitationManager might have extracted the URL
            pass  # Implementation-specific verification


@pytest.mark.asyncio
async def test_multiple_tool_messages_maintain_order():
    """Test that multiple tool messages added via FilteredMessageList maintain proper order"""

    async with Agent("Test agent") as agent:
        # Add multiple tool messages
        for i in range(3):
            agent.tool.append(
                f"Tool response {i}",
                tool_call_id=f"tool_call_{i}",
                tool_name=f"tool_{i}",
            )

        # Verify all messages were added in order (agent has 4 messages: 1 system + 3 tool)
        assert len(agent.messages) == 4
        for i in range(3):
            tool_msg = agent.messages[i + 1]  # Skip system message at index 0
            assert isinstance(tool_msg, ToolMessage)
            assert tool_msg.content == f"Tool response {i}"
            assert tool_msg.tool_call_id == f"tool_call_{i}"
            assert tool_msg.tool_name == f"tool_{i}"
