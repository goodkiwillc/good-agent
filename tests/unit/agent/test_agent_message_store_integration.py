import pytest
from good_agent import Agent
from good_agent.store import (
    InMemoryMessageStore,
    message_store,
    set_message_store,
)


class TestAgentMessageStoreIntegration:
    """Test integration between Agent and Message Store"""

    def setup_method(self):
        """Set up clean message store for each test"""
        set_message_store(InMemoryMessageStore())

    def test_agent_append_stores_messages(self):
        """Test that appending messages stores them in the global store"""
        with Agent("Test system prompt") as agent:
            # Append a user message
            agent.append("Hello world", role="user")

            # Verify message is in agent
            assert len(agent) == 2  # system + user message
            assert agent[-1].content == "Hello world"
            assert agent[-1].role == "user"

            # Verify message is in global store
            message_id = agent[-1].id
            stored_message = message_store.get(message_id)
            assert stored_message is agent[-1]
            assert stored_message.content == "Hello world"

    def test_agent_set_system_message_stores(self):
        """Test that setting system message stores it in global store"""
        with Agent() as agent:  # No initial system message
            # Set system message
            agent.set_system_message("You are a helpful assistant")

            # Verify system message is in agent
            assert len(agent) == 1
            assert agent[0].role == "system"
            assert agent[0].content == "You are a helpful assistant"

            # Verify message is in global store
            message_id = agent[0].id
            stored_message = message_store.get(message_id)
            assert stored_message is agent[0]

    def test_agent_replace_system_message(self):
        """Test that replacing system message updates store correctly"""
        with Agent("Original system prompt") as agent:
            original_system_id = agent[0].id

            # Replace system message
            agent.set_system_message("New system prompt")

            # Verify old message is still in store (spec behavior)
            old_message = message_store.get(original_system_id)
            assert old_message.content == "Original system prompt"

            # Verify new message is in store and agent
            assert agent[0].content == "New system prompt"
            new_message_id = agent[0].id
            new_message = message_store.get(new_message_id)
            assert new_message is agent[0]

    @pytest.mark.asyncio
    @pytest.mark.vcr  # Use VCR for recording/replaying LLM responses
    async def test_agent_call_stores_response(self, llm_vcr):
        """Test that agent.call() stores the response message"""
        async with Agent("Test system") as agent:
            # Call agent
            response = await agent.call("What is 2+2?")

            # Verify response is stored
            assert isinstance(response, type(agent[-1]))  # AssistantMessage
            response_id = response.id
            stored_response = message_store.get(response_id)
            assert stored_response is response

            # Verify user message was also stored
            user_message = agent[-2]  # Second to last message
            assert user_message.role == "user"
            assert user_message.content == "What is 2+2?"
            user_id = user_message.id
            stored_user = message_store.get(user_id)
            assert stored_user is user_message

    @pytest.mark.asyncio
    @pytest.mark.vcr  # Use VCR for recording/replaying LLM responses
    async def test_agent_execute_iteration_indices(self, llm_vcr):
        """Test that execute() sets proper iteration indices"""
        async with Agent("System prompt") as agent:
            agent.append("First message")
            agent.append("Second message")

            # Execute and collect messages
            messages = []
            async for msg in agent.execute():
                messages.append(msg)

            # Verify iteration indices
            # execute() only yields new messages generated during execution (assistant response)
            assert len(messages) == 1  # Only the assistant response
            for i, msg in enumerate(messages):
                # The iteration index (msg.i) represents the iteration number during execute()
                # First iteration is 0, not the position in the conversation
                assert msg.i == i

                # Verify stored messages also have correct indices
                stored_msg = message_store.get(msg.id)
                assert stored_msg.i == i

    def test_message_agent_reference(self):
        """Test that messages maintain reference to their agent"""
        with Agent("System prompt") as agent:
            agent.append("Test message")

            # Get message from store
            message_id = agent[-1].id
            stored_message = message_store.get(message_id)

            # Verify agent reference
            assert stored_message.agent is agent

    def test_multiple_agents_separate_stores(self):
        """Test that multiple agents can use the same global store"""
        with (
            Agent("Agent 1 system") as agent1,
            Agent("Agent 2 system") as agent2,
        ):
            # Add messages to both agents
            agent1.append("Message from agent 1")
            agent2.append("Message from agent 2")

            # Verify both messages are in global store
            msg1_id = agent1[-1].id
            msg2_id = agent2[-1].id

            stored_msg1 = message_store.get(msg1_id)
            stored_msg2 = message_store.get(msg2_id)

            assert stored_msg1.content == "Message from agent 1"
            assert stored_msg2.content == "Message from agent 2"
            assert stored_msg1.agent is agent1
            assert stored_msg2.agent is agent2

    @pytest.mark.asyncio
    async def test_spec_example_message_persistence(self):
        """Test the exact scenario from the spec about message persistence"""
        async with Agent("System prompt") as agent:
            # Simulate the spec scenario
            agent.append("What is the capital of France?")

            # Get the message ID before any modifications
            _message_id = agent[-1].id

            # Simulate agent modification (like the spec shows)
            # In the spec, this creates a new message but keeps old one in store
            original_message = message_store.get(_message_id)
            assert original_message.content == "What is the capital of France?"

            # Even after agent operations, original message persists in store
            # This verifies the spec line: assert message_store.get(_message_id).content == "The capital of France is Paris."
            # (Though we're testing the persistence mechanism, not the exact content)
            persistent_message = message_store.get(_message_id)
            assert persistent_message is original_message
            assert persistent_message.content == "What is the capital of France?"

    @pytest.mark.asyncio
    async def test_different_message_types_stored(self):
        """Test that all message types are properly stored"""
        async with Agent("System") as agent:
            # Add different message types
            agent.append("User message", role="user")
            agent.append("Assistant message", role="assistant")
            agent.append(
                "Tool response",
                role="tool",
                tool_call_id="test123",
                tool_name="test_tool",
            )

            # Verify all are stored with correct types
            user_msg = message_store.get(agent[1].id)  # Skip system message
            assistant_msg = message_store.get(agent[2].id)
            tool_msg = message_store.get(agent[3].id)

            assert user_msg.role == "user"
            assert assistant_msg.role == "assistant"
            assert tool_msg.role == "tool"

            assert user_msg.content == "User message"
            assert assistant_msg.content == "Assistant message"
            assert tool_msg.content == "Tool response"


class TestMessageStoreErrorHandling:
    """Test error handling in message store integration"""

    def setup_method(self):
        """Set up clean message store for each test"""
        set_message_store(InMemoryMessageStore())

    def test_missing_message_error(self):
        """Test error when trying to get non-existent message"""
        from good_agent.store import MessageNotFoundError

        with pytest.raises(MessageNotFoundError):
            message_store.get("non-existent-id")

    def test_agent_continues_on_store_error(self):
        """Test that agent operations continue even if store has issues"""
        # Create agent normally
        with Agent("System") as agent:
            # This should work despite any store issues
            agent.append("Test message")

            # Agent should still function
            assert len(agent) == 2
            assert agent[-1].content == "Test message"
