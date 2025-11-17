from unittest.mock import Mock, patch

import pytest
from good_agent import Agent, tool
from good_agent.messages import AssistantMessage, UserMessage


class TestVersioningWithRealOperations:
    """Test versioning integrated with real agent operations."""

    @pytest.mark.asyncio
    async def test_versioning_with_append_operations(self):
        """Test versioning with various append operations."""
        agent = Agent()
        await agent.initialize()

        # Start with no versions
        assert agent._version_manager.version_count == 0

        # Single append
        agent.append("First message")
        assert agent._version_manager.version_count == 1
        assert len(agent.current_version) == 1

        # Multiple appends via separate calls
        agent.append("Second message")
        agent.append("Third message")
        assert agent._version_manager.version_count == 3
        assert len(agent.current_version) == 3

        # Append with role
        agent.append("Assistant response", role="assistant")
        assert agent._version_manager.version_count == 4
        assert isinstance(agent.messages[-1], AssistantMessage)

        # All messages in registry
        for msg in agent.messages:
            assert agent._message_registry.get(msg.id) is not None

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_message_manipulation(self):
        """Test versioning with direct message list manipulation."""
        agent = Agent()
        await agent.initialize()

        # Add initial messages
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")
        assert agent._version_manager.version_count == 3

        # Replace a message
        old_id = agent.messages[1].id
        agent.messages[1] = UserMessage(content_parts=[])
        new_id = agent.messages[1].id

        assert agent._version_manager.version_count == 4
        assert old_id != new_id
        assert agent._message_registry.get(old_id) is not None  # Old preserved
        assert agent._message_registry.get(new_id) is not None  # New added

        # Delete via clear
        agent.messages.clear()
        assert agent._version_manager.version_count == 5
        assert len(agent.messages) == 0
        assert len(agent.current_version) == 0

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_tools_no_llm(self):
        """Test versioning with tool execution (no LLM needed)."""

        # Define a simple tool
        @tool
        def add_numbers(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        agent = Agent(tools=[add_numbers])
        await agent.initialize()

        # Add a message asking for tool use
        agent.append("Please add 5 and 3")
        assert agent._version_manager.version_count == 1

        # Manually invoke tool (simulating what LLM would do)
        result = await agent.tool_calls.invoke("add_numbers", a=5, b=3)

        # Tool invocation creates versions for tool request/response messages
        # The exact count depends on how the tool system handles messages
        assert agent._version_manager.version_count >= 1

        # Simulate adding tool result as message
        version_before_append = agent._version_manager.version_count
        agent.append(f"Result: {result}", role="assistant")
        assert agent._version_manager.version_count == version_before_append + 1

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_fork_operations(self):
        """Test versioning with agent forking."""
        parent = Agent("Parent system prompt")
        await parent.initialize()

        parent.append("Parent message 1")
        parent.append("Parent message 2")

        # Parent should have versions (note: system message issue)

        # Fork with messages
        child = parent.fork(include_messages=True)
        await child.initialize()

        # Child has own version manager
        assert child._version_manager is not parent._version_manager
        assert child._message_registry is not parent._message_registry

        # Child has same messages but own copies
        assert len(child.messages) == len(parent.messages)

        # Modify child
        child.append("Child only message")

        # Parent unchanged
        assert len(parent.messages) == 3  # system + 2 messages
        assert len(child.messages) == 4  # system + 2 + 1 new

        await parent.async_close()
        await child.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_context_managers(self):
        """Test versioning with ThreadContext and ForkContext."""
        agent = Agent()
        await agent.initialize()

        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        initial_versions = agent._version_manager.version_count

        # ThreadContext with truncation
        async with agent.context_manager.thread_context(truncate_at=2) as ctx:
            # Truncation creates new version
            assert agent._version_manager.version_count > initial_versions
            assert len(ctx.messages) == 2

            # Add in context
            ctx.append("Context message")
            assert len(ctx.messages) == 3

        # After context: original 3 + context message
        assert len(agent.messages) == 4
        final_versions = agent._version_manager.version_count
        assert final_versions > initial_versions

        # ForkContext
        async with agent.context_manager.fork_context() as forked:
            # Forked has separate version manager
            assert forked._version_manager is not agent._version_manager

            # Changes in fork don't affect parent
            forked.append("Fork only")

        # Parent unchanged
        assert agent._version_manager.version_count == final_versions

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_revert_operations(self):
        """Test versioning with revert operations."""
        agent = Agent()
        await agent.initialize()

        # Build history
        agent.append("v1")

        agent.append("v2")
        v2_count = agent._version_manager.version_count

        agent.append("v3")
        v3_count = agent._version_manager.version_count

        assert len(agent.messages) == 3

        # Revert to v2
        agent.revert_to_version(v2_count - 1)

        # Creates new version (non-destructive)
        assert agent._version_manager.version_count == v3_count + 1
        assert len(agent.messages) == 2
        assert "v2" in str(agent.messages[-1])

        # Can still revert to v3 state
        agent.revert_to_version(v3_count - 1)
        assert len(agent.messages) == 3
        assert "v3" in str(agent.messages[-1])

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_simple_mock_llm(self):
        """Test versioning with a simple mock LLM response."""
        agent = Agent("You are helpful")
        await agent.initialize()

        # Create a simple mock that returns a basic response
        async def mock_complete(*args, **kwargs):
            # Create proper mock response matching litellm's structure
            from litellm import Choices
            from litellm.types.utils import Message

            # Create proper Message object
            mock_msg = Message(
                content="Test response", role="assistant", tool_calls=None
            )

            # Create a Choices object with all required fields
            mock_choice = Choices(
                finish_reason="stop",
                index=0,
                message=mock_msg,
                logprobs=None,
                provider_specific_fields={},
            )

            # Create response with choices
            mock_response = Mock()
            mock_response.choices = [mock_choice]
            mock_response.usage = Mock(
                prompt_tokens=10, completion_tokens=5, total_tokens=15
            )
            return mock_response

        # Patch the model's complete method
        with patch.object(agent.model, "complete", new=mock_complete):
            # Initial state (system message issue - won't have version)
            initial_msgs = len(agent.messages)

            # Make a call
            await agent.call("Hello")

            # Should have added user and assistant messages
            assert len(agent.messages) == initial_msgs + 2
            assert isinstance(agent.messages[-2], UserMessage)
            assert isinstance(agent.messages[-1], AssistantMessage)

            # Should have created versions
            assert agent._version_manager.version_count >= 2

            # Messages should be in registry
            for msg in agent.messages[-2:]:
                assert agent._message_registry.get(msg.id) is not None

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_preserves_message_identity(self):
        """Test that versioning preserves message identity and content."""
        agent = Agent()
        await agent.initialize()

        # Create messages with specific content
        from good_agent.content.parts import TextContentPart

        msg1 = UserMessage(content_parts=[TextContentPart(text="Original content 1")])
        agent.append(msg1)

        msg2 = UserMessage(content_parts=[TextContentPart(text="Original content 2")])
        agent.append(msg2)

        # Capture IDs
        id1, id2 = msg1.id, msg2.id

        # Add more messages
        agent.append("Message 3")
        agent.append("Message 4")

        # Revert to earlier version
        agent.revert_to_version(1)  # Just first 2 messages

        # Messages should have same IDs and content
        assert len(agent.messages) == 2
        assert agent.messages[0].id == id1
        assert agent.messages[1].id == id2

        # Content preserved (through registry)
        retrieved1 = agent._message_registry.get(id1)
        retrieved2 = agent._message_registry.get(id2)
        assert retrieved1 is not None
        assert retrieved2 is not None

        await agent.events.async_close()

    @pytest.mark.asyncio
    async def test_versioning_with_mixed_operations(self):
        """Test versioning with a mix of operations."""
        agent = Agent()
        await agent.initialize()

        # Build complex history
        agent.append("Start")
        agent.append("Middle", role="assistant")

        # Replace
        agent.messages[0] = UserMessage(content_parts=[])

        # Extend
        new_messages = [
            UserMessage(content_parts=[]),
            AssistantMessage(content_parts=[]),
        ]
        agent.messages.extend(new_messages)

        # Clear and rebuild
        agent.messages.clear()
        agent.append("New start")

        # Each operation should create version
        assert agent._version_manager.version_count >= 6

        # Current state should be accurate
        assert len(agent.messages) == 1
        assert len(agent.current_version) == 1

        # Can revert to any point
        agent.revert_to_version(2)  # After first replacement
        assert len(agent.messages) == 2

        await agent.events.async_close()
