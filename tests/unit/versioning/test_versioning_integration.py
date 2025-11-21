import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio
from good_agent import Agent, tool
from good_agent.content.parts import TextContentPart
from good_agent.messages import AssistantMessage, SystemMessage, UserMessage
from good_agent.messages.versioning import MessageRegistry
from openai.types.completion_usage import CompletionUsage


class TestVersioningWithAgentOperations:
    """Test versioning with real Agent operations."""

    @pytest_asyncio.fixture
    async def mock_llm_response(self):
        """Create a mock LLM response."""
        # Create mock message
        message = Mock()
        message.content = "Test response"
        message.tool_calls = None
        message.model_extra = {}
        message.citations = None  # Explicitly set None to satisfy validation
        message.annotations = None  # Explicitly set None to satisfy validation

        # Create mock choice
        choice = Mock()
        choice.__class__.__name__ = "Choices"  # Match litellm Choices class
        choice.message = message
        choice.finish_reason = "stop"

        # Create mock response
        response = Mock()
        response.choices = [choice]
        response.usage = CompletionUsage(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )
        return response

    @pytest_asyncio.fixture
    async def agent_with_mock_llm(self, mock_llm_response):
        """Create an agent with mocked LLM."""
        async with Agent("You are a test assistant") as agent:
            # Mock the language model's complete method
            with patch.object(
                agent.model, "complete", new_callable=AsyncMock
            ) as mock_complete:
                mock_complete.return_value = mock_llm_response
                yield agent, mock_complete

    @pytest.mark.asyncio
    async def test_versioning_with_call(self, agent_with_mock_llm):
        """Test that call() creates proper versions."""
        agent, _ = agent_with_mock_llm

        # Initial state - should have system message
        initial_version_count = agent._version_manager.version_count
        initial_message_count = len(agent.messages)

        # Make a call
        await agent.call("Hello, how are you?")

        # Should have created versions for user message and assistant response
        assert agent._version_manager.version_count == initial_version_count + 2
        assert len(agent.messages) == initial_message_count + 2

        # Check message types
        assert isinstance(agent.messages[-2], UserMessage)
        assert isinstance(agent.messages[-1], AssistantMessage)

        # Check content
        assert "Hello, how are you?" in str(agent.messages[-2])
        assert "Test response" in str(agent.messages[-1])

        # All messages should be in registry
        for msg in agent.messages:
            assert agent._message_registry.get(msg.id) is not None

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_versioning_with_multiple_calls(self, agent_with_mock_llm):
        """Test versioning across multiple call() operations."""
        agent, _ = agent_with_mock_llm

        # Make multiple calls
        await agent.call("First question")
        await agent.call("Second question")
        await agent.call("Third question")

        # Should have system + 3 user + 3 assistant messages
        assert len(agent.messages) == 7

        # Each call should create 2 versions (user + assistant)
        # Plus initial system message version
        assert agent._version_manager.version_count == 7

        # Verify we can revert to any point
        agent.revert_to_version(
            2
        )  # After first Q&A (version 2 = system + user + assistant)
        assert len(agent.messages) == 3  # system + first Q&A

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_thread_context_with_call(self, agent_with_mock_llm):
        """Test ThreadContext with actual call() operations."""
        agent, _ = agent_with_mock_llm

        # Add some initial messages
        await agent.call("Question 1")
        await agent.call("Question 2")

        original_count = len(agent.messages)

        # Use thread context to truncate and add new message
        async with agent.context_manager.thread_context(truncate_at=3) as ctx_agent:
            # Should only see system + first Q&A
            assert len(ctx_agent.messages) == 3

            # Add new message in truncated context
            await ctx_agent.call("Summary question")

            # Should have truncated messages + new Q&A
            assert len(ctx_agent.messages) == 5

        # After context: should have all original + summary
        assert len(agent.messages) == original_count + 2
        assert "Summary question" in str(agent.messages[-2])

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_fork_context_with_call(self, agent_with_mock_llm):
        """Test ForkContext with actual call() operations."""
        agent, _ = agent_with_mock_llm

        # Add initial messages
        await agent.call("Original question")
        original_count = len(agent.messages)
        original_version_count = agent._version_manager.version_count

        # Use fork context
        async with agent.context_manager.fork_context() as forked:
            # Forked agent should have same messages
            assert len(forked.messages) == original_count

            # But different version manager
            assert forked._version_manager is not agent._version_manager

            # Add messages to fork
            await forked.call("Fork question")
            assert len(forked.messages) == original_count + 2

        # Original unchanged
        assert len(agent.messages) == original_count
        assert agent._version_manager.version_count == original_version_count

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_versioning_with_tools(self):
        """Test versioning with tool usage."""

        # Define a test tool
        @tool
        def test_tool(value: str) -> str:
            """Test tool for versioning."""
            return f"Processed: {value}"

        # Create agent with tool
        async with Agent("You are a test assistant", tools=[test_tool]) as agent:
            # Mock LLM to return tool call
            tool_function = Mock()
            tool_function.name = "test_tool"  # Set as attribute, not Mock argument
            tool_function.arguments = json.dumps({"value": "test"})

            tool_call = Mock()
            tool_call.id = "call_123"
            tool_call.function = tool_function
            tool_call.type = "function"

            tool_message = Mock()
            tool_message.content = ""
            tool_message.tool_calls = [tool_call]
            tool_message.model_extra = {}
            tool_message.citations = None  # Explicitly set None
            tool_message.annotations = None  # Explicitly set None

            tool_choice = Mock()
            tool_choice.__class__.__name__ = "Choices"
            tool_choice.message = tool_message
            tool_choice.finish_reason = "tool_calls"

            tool_response = Mock()
            tool_response.choices = [tool_choice]
            tool_response.usage = CompletionUsage(
                prompt_tokens=10, completion_tokens=5, total_tokens=15
            )

            with patch.object(
                agent.model, "complete", new_callable=AsyncMock
            ) as mock_complete:
                # Final response after tool execution
                final_message = Mock()
                final_message.content = "Tool executed successfully"
                final_message.tool_calls = None
                final_message.model_extra = {}
                final_message.citations = None  # Explicitly set None
                final_message.annotations = None  # Explicitly set None

                final_choice = Mock()
                final_choice.__class__.__name__ = "Choices"
                final_choice.message = final_message
                final_choice.finish_reason = "stop"

                final_response = Mock()
                final_response.choices = [final_choice]
                final_response.usage = CompletionUsage(
                    prompt_tokens=15, completion_tokens=8, total_tokens=23
                )

                mock_complete.side_effect = [tool_response, final_response]

                # Execute with tool
                await agent.call("Use the test tool")

            # Should have: system + user + assistant (tool call) + tool response + assistant (final)
            assert len(agent.messages) == 5

            # Each message should create a version
            assert agent._version_manager.version_count == 5

            # Verify message types in order
            assert isinstance(agent.messages[0], SystemMessage)
            assert isinstance(agent.messages[1], UserMessage)
            assert isinstance(agent.messages[2], AssistantMessage)  # Tool call
            # Tool messages are complex, just check they exist
            assert len(agent.messages) == 5

            await agent.events.close()

    @pytest.mark.asyncio
    async def test_version_consistency_after_error(self, agent_with_mock_llm):
        """Test that versioning remains consistent even after errors."""
        agent, mock_complete = agent_with_mock_llm

        initial_version_count = agent._version_manager.version_count
        initial_message_count = len(agent.messages)

        # Make mock raise an error
        mock_complete.side_effect = Exception("LLM error")

        # Call should fail
        with pytest.raises(Exception, match="LLM error"):
            await agent.call("This will fail")

        # User message should still be added (happens before LLM call)
        assert len(agent.messages) == initial_message_count + 1
        assert agent._version_manager.version_count == initial_version_count + 1

        # Reset mock to work again
        recovery_message = Mock()
        recovery_message.content = "Recovery response"
        recovery_message.tool_calls = None
        recovery_message.model_extra = {}
        recovery_message.citations = None  # Explicitly set None
        recovery_message.annotations = None  # Explicitly set None

        recovery_choice = Mock()
        recovery_choice.__class__.__name__ = "Choices"
        recovery_choice.message = recovery_message
        recovery_choice.finish_reason = "stop"

        recovery_response = Mock()
        recovery_response.choices = [recovery_choice]
        recovery_response.usage = CompletionUsage(
            prompt_tokens=10, completion_tokens=5, total_tokens=15
        )

        mock_complete.side_effect = None
        mock_complete.return_value = recovery_response

        # Should be able to continue
        await agent.call("Recover from error")

        # Should have added both messages
        assert len(agent.messages) == initial_message_count + 3
        assert agent._version_manager.version_count == initial_version_count + 3

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_version_persistence_simulation(self):
        """Test that versions could be persisted and restored (simulation)."""
        # Create agent and add messages
        agent1 = Agent("Test system")
        await agent1.initialize()

        agent1.append("Message 1")
        agent1.append("Message 2")
        agent1.append("Message 3")

        # Capture state
        version_data = {
            "versions": agent1._version_manager._versions.copy(),
            "current_index": agent1._version_manager._current_version_index,
            "messages": {msg.id: msg.model_dump() for msg in agent1.messages},
        }

        await agent1.close()

        # Simulate restoration in new agent
        agent2 = Agent("Test system")
        await agent2.initialize()

        # Restore versions (in real implementation, this would be from storage)
        agent2._version_manager._versions = version_data["versions"]
        agent2._version_manager._current_version_index = version_data["current_index"]

        # Note: In real implementation, messages would be restored from storage
        # This is just demonstrating the concept

        # Verify version structure was preserved
        # Should have 4 versions: system, system+msg1, system+msg1+msg2, system+msg1+msg2+msg3
        assert len(agent2._version_manager._versions) == 4
        assert agent2._version_manager._current_version_index == 3

        await agent2.close()


class TestMemoryAndPerformance:
    """Test for memory leaks and performance issues."""

    @pytest.mark.asyncio
    async def test_weakref_cleanup(self):
        """Test that agent references are properly cleaned up."""
        registry = MessageRegistry()

        # Create agent in a scope
        async def create_agent_and_messages():
            agent = Agent("Test")
            await agent.initialize()

            agent.append("Message 1")
            agent.append("Message 2")

            # Get message IDs before agent is destroyed
            msg_ids = [msg.id for msg in agent.messages]

            # Register with the test registry too
            for msg in agent.messages:
                registry.register(msg, agent)

            await agent.events.close()
            return msg_ids

        msg_ids = await create_agent_and_messages()

        # Force garbage collection
        import gc

        gc.collect()

        # Agent references should be gone
        for msg_id in msg_ids:
            assert registry.get_agent(msg_id) is None

        # Cleanup should remove dead references
        cleaned = registry.cleanup_dead_references()
        assert cleaned >= len(msg_ids)

    @pytest.mark.asyncio
    async def test_version_memory_growth(self):
        """Test that versions don't cause excessive memory growth."""
        agent = Agent()
        await agent.initialize()

        # Add many messages
        for i in range(100):
            agent.append(f"Message {i}")

        # Should have 100 versions
        assert agent._version_manager.version_count == 100

        # Each version should only store IDs, not full messages
        import sys

        # Get size of version storage
        version_size = sys.getsizeof(agent._version_manager._versions)

        # Should be reasonable (each ULID is ~26 bytes as string)
        # 100 versions * average 50 messages * 26 bytes = ~130KB
        # Allow up to 500KB for overhead
        assert version_size < 500_000

        # Clear messages
        agent.messages.clear()

        # Should create empty version
        assert agent._version_manager.current_version == []
        assert agent._version_manager.version_count == 101

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_large_message_handling(self):
        """Test versioning with large messages."""
        agent = Agent("Test system")
        await agent.initialize()

        # Create a large message (1MB of text)
        large_content = "x" * (1024 * 1024)
        agent.append(large_content)

        # Should handle large content (system + user message)
        assert len(agent.messages) == 2
        assert agent._version_manager.version_count == 2

        # Registry should store the message
        msg_id = agent.messages[1].id  # User message is at index 1
        retrieved = agent._message_registry.get(msg_id)
        assert retrieved is not None
        # Check the content itself is preserved
        assert retrieved.content_parts
        content_part = retrieved.content_parts[0]
        assert isinstance(content_part, TextContentPart)
        assert len(content_part.text) == 1024 * 1024

        # Version manager only stores IDs, not content
        version_ids = agent._version_manager.current_version
        assert len(version_ids) == 2  # system + user
        assert version_ids[1] == msg_id  # User message is at index 1

        await agent.events.close()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_agent_operations(self):
        """Test operations on empty agent."""
        agent = Agent()
        await agent.initialize()

        # Empty agent should have no versions
        assert agent._version_manager.version_count == 0
        assert agent.current_version == []

        # Revert on empty should fail
        with pytest.raises(IndexError):
            agent.revert_to_version(0)

        # Thread context should work
        async with agent.context_manager.thread_context() as ctx:
            assert len(ctx.messages) == 0
            ctx.append("New message")

        assert len(agent.messages) == 1

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_concurrent_modifications(self):
        """Test concurrent message modifications (should be safe due to GIL)."""
        agent = Agent()
        await agent.initialize()

        import asyncio

        async def add_messages(prefix: str, count: int):
            for i in range(count):
                agent.append(f"{prefix}-{i}")
                await asyncio.sleep(0)  # Yield control

        # Run concurrent additions
        await asyncio.gather(
            add_messages("A", 10), add_messages("B", 10), add_messages("C", 10)
        )

        # Should have all messages
        assert len(agent.messages) == 30

        # Should have version for each append
        assert agent._version_manager.version_count == 30

        # All messages should be in registry
        for msg in agent.messages:
            assert agent._message_registry.get(msg.id) is not None

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_version_index_bounds(self):
        """Test version index boundary conditions."""
        agent = Agent()
        await agent.initialize()

        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Valid indices
        agent.revert_to_version(0)  # First version
        assert len(agent.messages) == 1

        agent.revert_to_version(-1)  # Last version (the revert created a new one)
        assert len(agent.messages) == 1

        # Invalid indices
        with pytest.raises(IndexError):
            agent.revert_to_version(100)

        with pytest.raises(IndexError):
            agent.revert_to_version(-100)

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_message_id_uniqueness(self):
        """Test that message IDs are unique within each version."""
        agent = Agent("Test system")
        await agent.initialize()

        # Add and modify messages
        agent.append("Original 1")
        agent.append("Original 2")

        # Replace a message
        agent.messages[1] = UserMessage(
            content_parts=[TextContentPart(text="Replaced")]
        )

        # Add more
        agent.append("New 1")

        # Each version should have unique IDs within itself
        for i, version_ids in enumerate(agent._version_manager._versions):
            # Within a version, all IDs should be unique
            assert len(version_ids) == len(set(version_ids)), (
                f"Duplicate ID in version {i}"
            )

        # All current messages should have unique IDs
        current_ids = [msg.id for msg in agent.messages]
        assert len(current_ids) == len(set(current_ids))

        # The same message ID can appear across versions (that's expected)
        # But within a version, each ID should be unique

        await agent.events.close()
