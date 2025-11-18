import pytest
from good_agent import Agent, tool


@pytest.mark.asyncio
async def test_full_integration_with_thread_context_and_tools():
    """Test that StatefulResource properly uses both thread_context and tools."""
    from good_agent.resources import EditableResource

    # Create an agent with some default tools
    @tool
    async def default_tool() -> str:
        return "default"

    agent = Agent("System prompt", tools=[default_tool])
    await agent.initialize()

    # Create a resource
    resource = EditableResource("Hello world", name="doc")

    # Verify initial state
    assert "default_tool" in agent.tools
    assert len(agent.messages) == 1  # Just system message

    # Track what happens inside the context
    messages_modified = False
    tools_replaced = False

    # Mock thread_context to track calls
    original_thread_context = agent.context_manager.thread_context

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def tracking_thread_context(truncate_at: int | None = None):
        nonlocal messages_modified
        async with original_thread_context(truncate_at) as messages:
            original_content = messages[0].content if messages else None
            yield messages
            # Check if system message was modified
            if messages and messages[0].content != original_content:
                messages_modified = True

    setattr(agent.context_manager, "thread_context", tracking_thread_context)

    # Use the resource
    async with resource(agent):
        # Tools should be replaced
        assert "default_tool" not in agent.tools
        assert "read" in agent.tools
        assert "replace" in agent.tools
        tools_replaced = True

        # Test a tool works
        read_tool = agent.tools["read"]
        result = await read_tool(_agent=agent)
        assert "Hello world" in result.response

        # Modify content
        replace_tool = agent.tools["replace"]
        result = await replace_tool(_agent=agent, old_text="world", new_text="universe")
        assert resource.state == "Hello universe"

    # After context: tools should be restored
    assert "default_tool" in agent.tools
    assert "read" not in agent.tools

    # Verify tracking flags
    assert messages_modified, "System message should have been modified"
    assert tools_replaced, "Tools should have been replaced"

    # Resource should maintain its state
    assert resource.state == "Hello universe"

    # Restore original thread_context
    setattr(agent.context_manager, "thread_context", original_thread_context)


@pytest.mark.asyncio
async def test_nested_resource_contexts():
    """Test that nested resource contexts work correctly."""
    from good_agent.resources import EditableResource

    agent = Agent("Test agent")
    await agent.initialize()

    resource1 = EditableResource("Document 1", name="doc1")
    resource2 = EditableResource("Document 2", name="doc2")

    # Nested contexts should work but are unusual
    async with resource1(agent):
        assert "read" in agent.tools

        # Nested context would replace tools again
        # This is an edge case but should work
        async with resource2(agent):
            # doc2 tools should be available (same tool names)
            assert "read" in agent.tools

            # Can edit doc2
            replace_tool = agent.tools["replace"]
            await replace_tool(
                _agent=agent, old_text="Document 2", new_text="Modified Doc 2"
            )
            assert resource2.state == "Modified Doc 2"

        # Back to doc1 context - tools restored to doc1
        assert "read" in agent.tools

    # All tools restored
    assert len(agent.tools) == 0  # Agent had no initial tools


@pytest.mark.asyncio
async def test_resource_with_agent_call():
    """Test that resources work with agent.call() for natural language."""
    from good_agent.resources import EditableResource

    # This test is more of a smoke test since we can't easily test
    # the full LLM interaction without mocking

    agent = Agent("You are a helpful editor")
    await agent.initialize()

    resource = EditableResource(
        "This is a test dokument with misteaks.", name="document"
    )

    async with resource(agent):
        # Agent should have editing tools available
        assert "read" in agent.tools
        assert "replace" in agent.tools
        assert "save" in agent.tools

        # The agent could now be called with:
        # response = await agent.call("Fix the spelling mistakes")
        # But we can't test this without an actual LLM

        # Instead, verify the tools work manually
        read_tool = agent.tools["read"]
        content = await read_tool(_agent=agent)
        assert "dokument" in content.response

        # Fix a typo manually
        replace_tool = agent.tools["replace"]
        await replace_tool(_agent=agent, old_text="dokument", new_text="document")
        await replace_tool(_agent=agent, old_text="misteaks", new_text="mistakes")

        assert resource.state == "This is a test document with mistakes."


@pytest.mark.asyncio
async def test_resource_error_handling():
    """Test that resources handle errors gracefully."""
    from good_agent.resources import StatefulResource

    class FailingResource(StatefulResource[str]):
        async def initialize(self):
            raise ValueError("Initialization failed")

        async def persist(self):
            pass

        def get_tools(self):
            return {}

    resource = FailingResource("test")
    agent = Agent("Test")
    await agent.initialize()

    # Should raise the initialization error
    with pytest.raises(ValueError, match="Initialization failed"):
        async with resource(agent):
            pass

    # Agent should still be in valid state
    from good_agent.agent import AgentState

    assert agent.state == AgentState.READY


@pytest.mark.asyncio
async def test_resource_state_persistence():
    """Test that resource state persists across multiple uses."""
    from good_agent.resources import EditableResource

    agent = Agent("Test agent")
    await agent.initialize()

    resource = EditableResource("Initial content", name="doc")

    # First use - modify content
    async with resource(agent):
        replace_tool = agent.tools["replace"]
        await replace_tool(_agent=agent, old_text="Initial", new_text="Modified")

    assert resource.state == "Modified content"

    # Second use - content should be preserved
    async with resource(agent):
        read_tool = agent.tools["read"]
        result = await read_tool(_agent=agent)
        assert "Modified content" in result.response

        # Further modify
        replace_tool = agent.tools["replace"]
        await replace_tool(_agent=agent, old_text="content", new_text="text")

    assert resource.state == "Modified text"

    # Resource only initializes once
    assert resource._initialized is True


@pytest.mark.asyncio
async def test_multiple_resources_sequential():
    """Test using multiple resources sequentially."""
    from good_agent.resources import EditableResource

    agent = Agent("Test agent")
    await agent.initialize()

    doc1 = EditableResource("Document 1", name="doc1")
    doc2 = EditableResource("Document 2", name="doc2")

    # Edit first document
    async with doc1(agent):
        replace = agent.tools["replace"]
        await replace(_agent=agent, old_text="1", new_text="One")

    assert doc1.state == "Document One"

    # Edit second document
    async with doc2(agent):
        replace = agent.tools["replace"]
        await replace(_agent=agent, old_text="2", new_text="Two")

    assert doc2.state == "Document Two"

    # Both documents maintain their state
    assert doc1.state == "Document One"
    assert doc2.state == "Document Two"
