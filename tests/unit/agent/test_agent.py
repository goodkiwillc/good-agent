import warnings

import pytest

from good_agent import Agent
from good_agent.content import FileContentPart, ImageContentPart, TextContentPart


class TestAgentInitialization:
    @pytest.mark.asyncio
    async def test_set_system_prompt(self):
        system_prompt = "System Prompt: You are a helpful assistant."
        async with Agent(system_prompt) as agent:
            assert agent[0].role == "system"
            # The content should match the input (whitespace may be trimmed)
            assert agent[0].content.strip() == system_prompt.strip()

            assert len(agent) == 1

    @pytest.mark.asyncio
    async def test_no_system_prompt(self):
        async with Agent() as agent:
            # These warnings are expected when accessing agent[0] without a system message
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="No system message set", category=UserWarning
                )
                assert agent[0] is None  # agent[0] always system prompt
            assert len(agent) == 0

            agent.append(
                "This is a user message.",
            )

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="No system message set", category=UserWarning
                )
                assert agent[0] is None

            assert len(agent) == 1
            assert agent[-1].role == "user"
            assert agent[-1].content == "This is a user message."

    @pytest.mark.asyncio
    async def test_configuration_values(self):
        async with Agent(
            "This is a system prompt",
            model="gpt-4.1-mini",
            temperature=0.7,
            max_tokens=1500,
            top_p=0.9,
        ) as agent:
            assert agent.config.model == "gpt-4.1-mini"
            assert agent.config.temperature == 0.7
            assert agent.config.max_tokens == 1500
            assert agent.config.top_p == 0.9

            assert agent.model.model == "gpt-4.1-mini"

    @pytest.mark.asyncio
    async def test_configuration_session_id_no_system_prompt(self):
        async with Agent(
            # "This is a system prompt",
            model="gpt-4.1-mini",
            temperature=0.7,
            max_tokens=1500,
            top_p=0.9,
        ) as agent:
            # Expected warning when accessing agent[0] without system message
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="No system message set", category=UserWarning
                )
                assert agent[0] is None
            assert agent.session_id is not None
            _initial_session_id = agent.session_id
            _initial_version_id = agent.version_id

            agent.set_system_message(
                "This is a system prompt",
            )
            assert agent[0].role == "system"
            assert agent[0].content == "This is a system prompt"
            assert agent.session_id == _initial_session_id
            assert agent.version_id > _initial_version_id

    """
    @TODO: fix ulid monotonic issue https://pypi.org/project/py-ulid/
    """

    @pytest.mark.asyncio
    async def test_configuration_context(self):
        async with Agent(
            "This is a system prompt",
            model="gpt-4.1-mini",
            temperature=0.7,
            max_tokens=1500,
            top_p=0.9,
        ) as agent:
            _initial_session_id = agent.session_id
            _initial_version_id = agent.version_id

            # Session ID should be consistent and independent of message IDs
            assert agent.session_id == _initial_session_id

            assert agent.config.model == "gpt-4.1-mini"
            assert agent.config.temperature == 0.7
            assert agent.config.max_tokens == 1500
            assert agent.config.top_p == 0.9

            with agent.config(
                model="gpt-4.1-nano",
                temperature=0.3,
                max_tokens=500,
                top_p=0.4,
            ):
                assert agent.session_id == _initial_session_id
                assert agent.version_id > _initial_version_id
                _new_context_version_id = agent.version_id

                assert agent.config.model == "gpt-4.1-nano"
                assert agent.config.temperature == 0.3
                assert agent.config.max_tokens == 500
                assert agent.config.top_p == 0.4

                assert agent.model.model == "gpt-4.1-nano"

            # context should return to normal

            assert agent.session_id == _initial_session_id
            assert agent.version_id > _new_context_version_id
            assert agent.version_id > _initial_version_id

            assert agent.config.model == "gpt-4.1-mini"
            assert agent.config.temperature == 0.7
            assert agent.config.max_tokens == 1500
            assert agent.config.top_p == 0.9

    @pytest.mark.asyncio
    async def test_context_inheritance(self):
        async with Agent(
            "System Prompt",
            context={"a": 1, "b": 10, "c": 15},
            undefined_behavior="silent",
        ) as agent:
            assert agent.vars["a"] == 1
            assert agent.vars["b"] == 10
            assert agent.vars["c"] == 15

            with agent.config(context={"a": 2, "b": 12, "c": 15}):
                assert agent.vars["a"] == 2
                assert agent.vars["b"] == 12
                assert agent.vars["c"] == 15

            assert agent.vars["a"] == 1
            assert agent.vars["b"] == 10
            assert agent.vars["c"] == 15

            with agent.vars(a=3, b=14, d=20):
                assert agent.vars["a"] == 3
                assert agent.vars["b"] == 14
                assert agent.vars["c"] == 15
                assert agent.vars["d"] == 20

            # message level inheritance

            assert agent.vars["a"] == 1
            assert agent.vars["b"] == 10
            assert agent.vars["c"] == 15

            agent.append(
                "This is a user message with context {{a}} {{b}} {{c}} {{d}}.",
                context={"a": 5, "d": 35},
            )

            assert agent[-1].role == "user"
            assert agent[-1].content == "This is a user message with context 5 10 15 35."

            agent.append(
                "This is a user message with context {{a}} {{b}} {{c}} {{d}}.",
            )

            assert agent[-1].role == "user"
            assert (
                agent[-1].content
                == "This is a user message with context 1 10 15 ."  # d is not defined anymore, rendered as empty string
            )

    @pytest.mark.asyncio
    async def test_context_providers(self):
        """
        Custom context providers can be used to provide dynamic context values at compile/render time
        """
        from datetime import datetime, timedelta

        # global context providers
        from good_agent.agent.context import ContextManager

        @ContextManager.context_providers("ten")
        def return_10():
            return 10

        # return
        async with Agent(
            "System Prompt: You are a helpful assistant.",
        ) as agent:
            _mock_current_time = datetime.now()

            @agent.context_provider("current_time")
            def current_time_provider():
                return str(_mock_current_time)  # Return string representation, not isoformat

            agent.append(
                "Current time is {{current_time}}.",
            )

            assert agent[-1].role == "user"
            assert agent[-1].content == f"Current time is {_mock_current_time}."

            _mock_current_time += timedelta(hours=1)

            assert agent[-1].content == f"Current time is {_mock_current_time}."

    @pytest.mark.asyncio
    async def test_agent_context_manager(self):
        """Test Agent as async context manager for automatic task cleanup"""
        # Test single agent in context manager
        async with Agent("System prompt") as agent:
            agent.append("Test message 1")
            agent.append("Test message 2")
            assert len(agent.messages) == 3  # system + 2 messages
        # No manual join() needed - handled by context manager

        # Test multiple agents in context manager
        async with Agent("Agent 1") as agent1, Agent("Agent 2") as agent2:
            agent1.append("Message from agent 1")
            agent2.append("Message from agent 2")
            assert len(agent1.messages) == 2
            assert len(agent2.messages) == 2
        # Both agents automatically cleaned up


class TestAgentIndexing:
    """Test agent indexing operations and filtered message lists"""

    @pytest.mark.asyncio
    async def test_agent_indexing_basic(self):
        """Test basic indexing operations on agent"""
        async with Agent("System prompt") as agent:
            # Test with system message
            assert agent[0].role == "system"
            assert agent[0].content == "System prompt"

            # Add messages
            agent.append("First user message")
            agent.append("First assistant message", role="assistant")
            agent.append("Second user message")

            # Test positive indexing
            assert agent[0].role == "system"
            assert agent[1].role == "user"
            assert agent[2].role == "assistant"
            assert agent[3].role == "user"

            # Test negative indexing
            assert agent[-1].role == "user"
            assert agent[-1].content == "Second user message"
            assert agent[-2].role == "assistant"
            assert agent[-3].role == "user"
            assert agent[-4].role == "system"

    @pytest.mark.asyncio
    async def test_agent_indexing_no_system(self):
        """Test indexing when no system message exists"""
        async with Agent() as agent:  # No system prompt
            # These warnings are expected when accessing agent[0] without system message
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="No system message set", category=UserWarning
                )
                assert agent[0] is None

            assert len(agent) == 0

            agent.append("User message")
            agent.append("Assistant message", role="assistant")

            # agent[0] still None, messages start at index 1
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="No system message set", category=UserWarning
                )
                assert agent[0] is None
            assert agent[1].role == "user"
            assert agent[2].role == "assistant"
            assert agent[-1].role == "assistant"
            assert agent[-2].role == "user"

    @pytest.mark.asyncio
    async def test_agent_slicing(self):
        """Test slicing operations on agent"""
        async with Agent("System prompt") as agent:
            agent.append("Message 1")
            agent.append("Message 2", role="assistant")
            agent.append("Message 3")
            agent.append("Message 4", role="assistant")

            # Test slice operations - preserve system message indexing
            messages = agent[1:3]
            assert len(messages) == 2
            import warnings

            with warnings.catch_warnings(record=True) as w:
                assert messages[0] is None
                assert messages[1].content == "Message 1"
                assert messages[2].content == "Message 2"

            # Check that warnings were emitted when accessing messages[0]
            warning_messages = [str(warning.message) for warning in w]
            expected_message = "No system message set. messages[0] is None"
            assert any(expected_message in msg for msg in warning_messages), (
                f"Expected warning not found. Got: {warning_messages}"
            )

            # Test slice with step
            messages = agent[::2]
            assert len(messages) == 3
            assert messages[0].role == "system"
            assert messages[1].role == "assistant"
            assert messages[2].role == "assistant"

    @pytest.mark.asyncio
    async def test_filtered_message_lists(self):
        """Test filtered message list properties"""
        async with Agent("You are a helpful assistant") as agent:
            # Add various messages
            agent.user.append("First user message")
            agent.assistant.append("First assistant response")
            agent.user.append("Second user message")
            agent.assistant.append("Second assistant response")
            agent.tool.append("Tool response", tool_name="calculator", tool_call_id="123")
            agent.user.append("Third user message")

            # Test user message filtering
            assert len(agent.user) == 3
            assert agent.user[0].content == "First user message"
            assert agent.user[1].content == "Second user message"
            assert agent.user[2].content == "Third user message"
            assert agent.user[-1].content == "Third user message"

            # Test assistant message filtering
            assert len(agent.assistant) == 2
            assert agent.assistant[0].content == "First assistant response"
            assert agent.assistant[1].content == "Second assistant response"
            assert agent.assistant[-1].content == "Second assistant response"

            # Test system message access
            assert agent.system is not None
            assert agent.system[0].content == "You are a helpful assistant"

            # Test tool message filtering
            assert len(agent.tool) == 1
            assert agent.tool[0].content == "Tool response"
            assert agent.tool[0].name == "calculator"

    @pytest.mark.asyncio
    async def test_filtered_lists_empty(self):
        """Test filtered lists when no messages of that type exist"""
        async with Agent() as agent:  # No system prompt
            # All filtered lists should be empty
            assert len(agent.system) == 0
            assert len(agent.user) == 0
            assert len(agent.assistant) == 0
            assert len(agent.tool) == 0

            # Add only user messages
            agent.user.append("User message 1")
            agent.user.append("User message 2")

            assert len(agent.system) == 0
            assert len(agent.user) == 2
            assert len(agent.assistant) == 0
            assert len(agent.tool) == 0

    @pytest.mark.asyncio
    async def test_filtered_list_iteration(self):
        """Test iteration over filtered message lists"""
        async with Agent("System prompt") as agent:
            # Add messages
            for i in range(3):
                agent.user.append(f"User message {i}")
                agent.assistant.append(f"Assistant response {i}")

            # Test iteration over user messages
            user_contents = [msg.content for msg in agent.user]
            assert user_contents == [
                "User message 0",
                "User message 1",
                "User message 2",
            ]

            # Test iteration over assistant messages
            assistant_contents = [msg.content for msg in agent.assistant]
            assert assistant_contents == [
                "Assistant response 0",
                "Assistant response 1",
                "Assistant response 2",
            ]

    @pytest.mark.asyncio
    async def test_attach_image_helpers(self):
        async with Agent() as agent:
            agent.attach_image(
                "https://example.com/cat.png",
                text="Check out this cat",
                detail="high",
            )

            image_message = agent[-1]
            assert image_message.role == "user"
            assert isinstance(image_message.content_parts[0], TextContentPart)
            assert isinstance(image_message.content_parts[1], ImageContentPart)
            assert image_message.content_parts[1].image_url == "https://example.com/cat.png"
            assert image_message.content_parts[1].detail == "high"

            agent.attach_image(
                "rawbase64==",
                detail="low",
                mime_type="image/png",
            )

            base64_message = agent[-1]
            image_part = base64_message.content_parts[0]
            assert isinstance(image_part, ImageContentPart)
            assert image_part.image_base64.startswith("data:image/png;base64,rawbase64")

    @pytest.mark.asyncio
    async def test_attach_file_helpers(self):
        async with Agent() as agent:
            agent.attach_file(
                "file-123",
                text="See attached",
                mime_type="application/pdf",
                file_name="report.pdf",
            )

            file_message = agent[-1]
            assert isinstance(file_message.content_parts[0], TextContentPart)
            file_part = file_message.content_parts[1]
            assert isinstance(file_part, FileContentPart)
            assert file_part.file_path == "file-123"
            assert file_part.mime_type == "application/pdf"
            assert file_part.file_name == "report.pdf"

            agent.attach_file(
                "Inline text content",
                inline=True,
                mime_type="text/plain",
            )

            inline_message = agent[-1]
            inline_part = inline_message.content_parts[0]
            assert isinstance(inline_part, FileContentPart)
            assert inline_part.file_content == "Inline text content"
            assert inline_part.mime_type == "text/plain"

    @pytest.mark.asyncio
    async def test_system_message_operations(self):
        """Test system message specific operations"""
        # Test setting system message on empty agent
        async with Agent() as agent:
            assert len(agent.system) == 0

            agent.system.set("New system prompt")
            assert len(agent.system) == 1
            assert agent.system.content == "New system prompt"
            assert agent[0].role == "system"

            # Test updating system message
            agent.system.set("Updated system prompt")
            assert agent.system.content == "Updated system prompt"
            assert len(agent) == 1  # Should replace, not add

            # Test system message with configuration
            agent.system.set("Configured system prompt", temperature=0.7, max_tokens=1000)
            assert agent.system.content == "Configured system prompt"
            assert agent.config.temperature == 0.7
            assert agent.config.max_tokens == 1000

    @pytest.mark.asyncio
    async def test_message_counting(self):
        """Test counting messages by type"""
        async with Agent("System prompt") as agent:
            # Add various messages
            for i in range(5):
                agent.user.append(f"User {i}")
            for i in range(3):
                agent.assistant.append(f"Assistant {i}")
            for i in range(2):
                agent.tool.append(f"Tool {i}", tool_name=f"tool_{i}", tool_call_id=str(i))

            # Test counts
            assert len(agent) == 11  # 1 system + 5 user + 3 assistant + 2 tool
            assert len(agent.user) == 5
            assert len(agent.assistant) == 3
            assert len(agent.tool) == 2
            assert agent.system is not None

    @pytest.mark.asyncio
    async def test_message_access_bounds(self):
        """Test bounds checking for message access"""
        async with Agent("System prompt") as agent:
            agent.append("User message")

            # Test out of bounds access
            with pytest.raises(IndexError):
                _ = agent[10]

            with pytest.raises(IndexError):
                _ = agent[-10]

            # Test filtered list bounds
            with pytest.raises(IndexError):
                _ = agent.user[5]

            with pytest.raises(IndexError):
                _ = agent.assistant[0]  # No assistant messages yet
