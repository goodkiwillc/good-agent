import asyncio

import pytest
from good_agent import Agent, Conversation
from good_agent.messages import AssistantMessage, UserMessage


class TestConversation:
    """Test suite for conversation mode functionality."""

    @pytest.mark.asyncio
    async def test_conversation_creation(self):
        """Test basic conversation creation with | operator."""
        async with (
            Agent("You are agent 1") as agent1,
            Agent("You are agent 2") as agent2,
        ):
            # Test | operator creates conversation
            conversation = agent1 | agent2
            assert isinstance(conversation, Conversation)
            assert len(conversation) == 2
            assert conversation.participants == [agent1, agent2]

    @pytest.mark.asyncio
    async def test_conversation_chaining(self):
        """Test chaining multiple agents with | operator."""
        async with (
            (agent1 := Agent("Agent 1", name="agent1")),
            (agent2 := Agent("Agent 2", name="agent2")),
            (agent3 := Agent("Agent 3", name="agent3")),
        ):
            # Test chaining
            conversation = agent1 | agent2 | agent3
            assert isinstance(conversation, Conversation)
            assert len(conversation) == 3
            assert conversation.participants == [agent1, agent2, agent3]

    @pytest.mark.asyncio
    async def test_message_forwarding(self):
        """Test that assistant messages are forwarded as user messages."""
        async with (
            (agent1 := Agent("You are agent 1", name="agent1")),
            (agent2 := Agent("You are agent 2", name="agent2")),
            agent1 | agent2,
        ):
            # Initially, both agents should have only system messages
            assert len(agent1.messages) == 1  # system message
            assert len(agent2.messages) == 1  # system message

            # Add assistant message to agent1
            agent1.assistant.append("Hello from agent 1")

            # Give event system time to process
            await asyncio.sleep(0.01)

            # Agent1 should have system + assistant message
            assert len(agent1.messages) == 2

            # Agent2 should have system + forwarded user message
            assert len(agent2.messages) == 2
            assert isinstance(agent2.messages[1], UserMessage)
            assert agent2.messages[1].content == "Hello from agent 1"

    @pytest.mark.asyncio
    async def test_bidirectional_forwarding(self):
        """Test that messages are forwarded in both directions."""
        async with (
            (agent1 := Agent("You are agent 1", name="agent1")),
            (agent2 := Agent("You are agent 2", name="agent2")),
            agent1 | agent2,
        ):
            # Agent1 sends message
            agent1.assistant.append("Message from agent 1")
            await asyncio.sleep(0.01)

            # Agent2 sends message
            agent2.assistant.append("Message from agent 2")
            await asyncio.sleep(0.01)

            # Check agent1 received agent2's message
            user_messages_in_agent1 = [m for m in agent1.messages if isinstance(m, UserMessage)]
            assert len(user_messages_in_agent1) == 1
            assert user_messages_in_agent1[0].content == "Message from agent 2"

            # Check agent2 received agent1's message
            user_messages_in_agent2 = [m for m in agent2.messages if isinstance(m, UserMessage)]
            assert len(user_messages_in_agent2) == 1
            assert user_messages_in_agent2[0].content == "Message from agent 1"

    @pytest.mark.asyncio
    async def test_multi_agent_forwarding(self):
        """Test message forwarding in 3-agent conversation."""
        async with (
            (agent1 := Agent("Agent 1", name="agent1")),
            (agent2 := Agent("Agent 2", name="agent2")),
            (agent3 := Agent("Agent 3", name="agent3")),
            agent1 | agent2 | agent3,
        ):
            # Agent1 sends message
            agent1.append(AssistantMessage(content="Hello from agent 1"))
            await asyncio.sleep(0.01)

            # Both agent2 and agent3 should receive the message
            user_messages_agent2 = [m for m in agent2.messages if isinstance(m, UserMessage)]
            user_messages_agent3 = [m for m in agent3.messages if isinstance(m, UserMessage)]

            assert len(user_messages_agent2) == 1
            assert len(user_messages_agent3) == 1
            # In group chat (>2 agents), messages are wrapped with author metadata
            assert "Hello from agent 1" in user_messages_agent2[0].content
            assert "Hello from agent 1" in user_messages_agent3[0].content
            # Verify author metadata
            assert "author=@agent1" in user_messages_agent2[0].content
            assert "author=@agent1" in user_messages_agent3[0].content

    @pytest.mark.asyncio
    async def test_conversation_events(self):
        """Test that conversation properly manages message forwarding state."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            # Track that conversation is set up properly
            conversation = agent1 | agent2
            assert conversation.conversation_id is not None
            assert len(conversation.participants) == 2

            async with conversation:
                # Verify conversation is active
                assert conversation._active is True
                assert agent1 in conversation._handler_ids
                assert agent2 in conversation._handler_ids

                # Send a message
                agent1.append(AssistantMessage(content="Test message"))
                await asyncio.sleep(0.01)

                # Verify message was forwarded
                assert len(agent2.messages) == 2  # system + forwarded message
                assert isinstance(agent2.messages[1], UserMessage)
                assert agent2.messages[1].content == "Test message"

            # Verify conversation is cleaned up
            assert conversation._active is False
            assert conversation._handler_ids == {}

    @pytest.mark.asyncio
    async def test_conversation_cleanup(self):
        """Test that event handlers are cleaned up after conversation."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            async with agent1 | agent2 as conversation:
                assert agent1 in conversation._handler_ids
                assert agent2 in conversation._handler_ids
                assert len(conversation._handler_ids[agent1]) == 1
                assert len(conversation._handler_ids[agent2]) == 1

            assert conversation._handler_ids == {}

    @pytest.mark.asyncio
    async def test_conversation_execution(self):
        """Test conversation execution method."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            # Set up mock responses
            with agent1.mock("Hello from agent 1"), agent2.mock("Hello from agent 2"):
                async with agent1 | agent2 as conversation:
                    messages = []
                    async for message in conversation.execute(max_iterations=2):
                        messages.append(message)
                        if len(messages) >= 4:  # Prevent infinite loop
                            break

                    # Give forwarding handlers time to run
                    await asyncio.sleep(0.01)

                    # Should have collected messages from both agents
                    assert len(messages) > 0

                    user_messages_agent2 = [
                        m for m in agent2.messages if isinstance(m, UserMessage)
                    ]
                    user_messages_agent1 = [
                        m for m in agent1.messages if isinstance(m, UserMessage)
                    ]

                    assert any(msg.content == "Hello from agent 1" for msg in user_messages_agent2)
                    assert any(msg.content == "Hello from agent 2" for msg in user_messages_agent1)

    @pytest.mark.asyncio
    async def test_conversation_messages_property(self):
        """Test conversation messages property returns chronological order."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            # Add messages at different times
            agent1.append(AssistantMessage(content="First message"))
            agent2.append(AssistantMessage(content="Second message"))

            conversation = agent1 | agent2
            all_messages = conversation.messages

            # Should have system messages plus the assistant messages
            assert len(all_messages) == 4  # 2 system + 2 assistant

            # Messages should be in chronological order
            # (exact order depends on timing, but structure should be preserved)
            assistant_messages = [m for m in all_messages if isinstance(m, AssistantMessage)]
            assert len(assistant_messages) == 2

    @pytest.mark.asyncio
    async def test_no_forwarding_outside_context(self):
        """Test that messages are not forwarded outside conversation context."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            # Create conversation but don't enter context
            _conversation = agent1 | agent2

            # Add message outside context
            agent1.append(AssistantMessage(content="No forwarding"))
            await asyncio.sleep(0.01)

            # Agent2 should not receive the message
            user_messages = [m for m in agent2.messages if isinstance(m, UserMessage)]
            assert len(user_messages) == 0

    @pytest.mark.asyncio
    async def test_user_messages_not_forwarded(self):
        """Test that only assistant messages are forwarded, not user messages."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2, agent1 | agent2:
            # Add user message (should not be forwarded)
            agent1.append(UserMessage(content="User message"))
            await asyncio.sleep(0.01)

            # Add assistant message (should be forwarded)
            agent1.append(AssistantMessage(content="Assistant message"))
            await asyncio.sleep(0.01)

            # Agent2 should only have the forwarded assistant message (as user message)
            user_messages_in_agent2 = [m for m in agent2.messages if isinstance(m, UserMessage)]
            assert len(user_messages_in_agent2) == 1
            assert user_messages_in_agent2[0].content == "Assistant message"

    @pytest.mark.asyncio
    async def test_llm_generated_messages_forwarded(self):
        """Test that LLM (mocked) assistant messages are forwarded via events."""
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            with (
                agent1.mock("LLM response from agent 1"),
                agent2.mock("LLM response from agent 2"),
            ):
                async with agent1 | agent2:
                    await agent1.call("Hello there")
                    await asyncio.sleep(0.01)

                    agent2_user_messages = [
                        m for m in agent2.messages if isinstance(m, UserMessage)
                    ]
                    assert any(
                        msg.content == "LLM response from agent 1" for msg in agent2_user_messages
                    )

                    await agent2.call("Replying now")
                    await asyncio.sleep(0.01)

                    agent1_user_messages = [
                        m for m in agent1.messages if isinstance(m, UserMessage)
                    ]
                    assert any(
                        msg.content == "LLM response from agent 2" for msg in agent1_user_messages
                    )
