import pytest
from typing import Literal
from ulid import ULID

from good_agent import Agent
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from good_agent.messages.validation import (
    MessageSequenceValidator,
    ValidationError,
    ValidationMode,
)
from good_agent.tools import ToolCall, ToolCallFunction


class TestMessageSequenceValidator:
    """Test the MessageSequenceValidator class directly."""

    def test_validation_modes(self):
        """Test different validation modes."""
        # Silent mode should not raise or log
        validator = MessageSequenceValidator(mode=ValidationMode.SILENT)
        messages = [
            UserMessage(content="Hello"),
            UserMessage(content="World"),  # Invalid: consecutive user messages
        ]
        issues = validator.validate(messages)
        assert issues == []  # Silent mode returns no issues

        # Warn mode should return issues but not raise
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)
        issues = validator.validate(messages)
        assert len(issues) > 0
        assert any("Consecutive user messages" in issue for issue in issues)

        # Strict mode should raise ValidationError
        validator = MessageSequenceValidator(mode=ValidationMode.STRICT)
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(messages)
        assert "Consecutive user messages" in str(exc_info.value)

    def test_tool_call_response_sequencing(self):
        """Test that tool responses must immediately follow tool calls."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        # Valid sequence: tool response immediately follows tool call
        tool_call_id = str(ULID())
        messages = [
            UserMessage(content="Get the weather"),
            AssistantMessage(
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(
                            name="get_weather", arguments='{"location": "NYC"}'
                        ),
                    )
                ],
            ),
            ToolMessage(
                content="Sunny, 72°F",
                tool_call_id=tool_call_id,
                tool_name="get_weather",
            ),
            AssistantMessage(content="The weather in NYC is sunny and 72°F"),
        ]
        issues = validator.validate(messages)
        assert len(issues) == 0

        # Invalid: tool response not immediately after tool call
        invalid_messages = [
            UserMessage(content="Get the weather"),
            AssistantMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(
                            name="get_weather", arguments='{"location": "NYC"}'
                        ),
                    )
                ],
            ),
            UserMessage(content="Actually, never mind"),  # Interrupts sequence
            ToolMessage(
                content="Sunny, 72°F",
                tool_call_id=tool_call_id,
                tool_name="get_weather",
            ),
        ]
        issues = validator.validate(invalid_messages)
        assert len(issues) > 0
        assert any("Expected tool response" in issue for issue in issues)

    def test_parallel_tool_calls(self):
        """Test validation of parallel tool calls."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        tool_call_id1 = str(ULID())
        tool_call_id2 = str(ULID())

        # Valid: multiple tool responses after parallel tool calls
        messages = [
            UserMessage(content="Get weather for NYC and Paris"),
            AssistantMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        id=tool_call_id1,
                        type="function",
                        function=ToolCallFunction(
                            name="get_weather", arguments='{"location": "NYC"}'
                        ),
                    ),
                    ToolCall(
                        id=tool_call_id2,
                        type="function",
                        function=ToolCallFunction(
                            name="get_weather", arguments='{"location": "Paris"}'
                        ),
                    ),
                ],
            ),
            ToolMessage(
                content="NYC: Sunny, 72°F",
                tool_call_id=tool_call_id1,
                tool_name="get_weather",
            ),
            ToolMessage(
                content="Paris: Cloudy, 18°C",
                tool_call_id=tool_call_id2,
                tool_name="get_weather",
            ),
            AssistantMessage(content="NYC is sunny at 72°F, Paris is cloudy at 18°C"),
        ]
        issues = validator.validate(messages)
        assert len(issues) == 0

    def test_unresolved_tool_calls(self):
        """Test detection of unresolved tool calls."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        tool_call_id = str(ULID())
        messages = [
            UserMessage(content="Get the weather"),
            AssistantMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(
                            name="get_weather", arguments='{"location": "NYC"}'
                        ),
                    )
                ],
            ),
            # Missing tool response!
        ]
        issues = validator.validate(messages)
        assert len(issues) > 0
        assert any("Unresolved tool calls" in issue for issue in issues)

    def test_tool_message_without_call(self):
        """Test tool messages without corresponding tool calls."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        messages = [
            UserMessage(content="Hello"),
            ToolMessage(
                content="Random tool response",
                tool_call_id="non_existent_id",
                tool_name="some_tool",
            ),
        ]
        issues = validator.validate(messages)
        assert len(issues) > 0
        assert any("no corresponding tool call" in issue for issue in issues)

    def test_role_alternation(self):
        """Test role alternation validation."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        # Valid alternation
        messages = [
            UserMessage(content="Hello"),
            AssistantMessage(content="Hi there!"),
            UserMessage(content="How are you?"),
            AssistantMessage(content="I'm doing well, thanks!"),
        ]
        issues = validator.validate(messages)
        assert len(issues) == 0

        # Consecutive user messages
        messages_with_consecutive = [
            UserMessage(content="Hello"),
            UserMessage(content="Are you there?"),
            AssistantMessage(content="Yes, I'm here!"),
        ]
        issues = validator.validate(messages_with_consecutive)
        assert len(issues) > 0
        assert any("Consecutive user messages" in issue for issue in issues)

    def test_system_message_placement(self):
        """Test system message placement validation."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        # Valid: system messages at beginning
        messages = [
            SystemMessage(content="You are a helpful assistant"),
            SystemMessage(content="Be concise"),
            UserMessage(content="Hello"),
            AssistantMessage(content="Hi!"),
        ]
        issues = validator.validate(messages)
        assert len(issues) == 0

        # Warning: system message after conversation starts
        messages_with_late_system = [
            UserMessage(content="Hello"),
            AssistantMessage(content="Hi!"),
            SystemMessage(content="New instruction"),  # Late system message
            UserMessage(content="Another question"),
        ]
        issues = validator.validate(messages_with_late_system)
        assert len(issues) > 0
        assert any("System message" in issue and "after" in issue for issue in issues)

    def test_validate_before_append(self):
        """Test validation before appending a message."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        messages = [
            UserMessage(content="Hello"),
            AssistantMessage(content="Hi!"),
        ]

        # Valid append
        new_message = UserMessage(content="Another question")
        issues = validator.validate_before_append(messages, new_message)
        assert len(issues) == 0

        # Invalid append (would create consecutive user messages)
        messages_with_user = messages + [UserMessage(content="Wait")]
        new_message = UserMessage(content="Another user message")
        issues = validator.validate_before_append(messages_with_user, new_message)
        assert len(issues) > 0

    def test_partial_sequence_validation(self):
        """Test validation of partial/incomplete sequences."""
        validator = MessageSequenceValidator(mode=ValidationMode.WARN)

        tool_call_id = str(ULID())
        messages = [
            UserMessage(content="Get weather"),
            AssistantMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(
                            name="get_weather", arguments='{"location": "NYC"}'
                        ),
                    )
                ],
            ),
            # Incomplete - missing tool response
        ]

        # Should report unresolved tool calls
        issues = validator.validate_partial_sequence(
            messages, allow_pending_tools=False
        )
        assert len(issues) > 0
        assert any("Unresolved tool calls" in issue for issue in issues)

        # Should not report unresolved tool calls when allowed
        issues = validator.validate_partial_sequence(messages, allow_pending_tools=True)
        # Filter out unresolved tool call issues
        non_tool_issues = [
            issue for issue in issues if "Unresolved tool calls" not in issue
        ]
        assert len(non_tool_issues) == 0


@pytest.mark.asyncio
class TestAgentMessageSequenceValidation:
    """Test message sequence validation integrated with Agent."""

    async def test_agent_validates_before_llm_call(self):
        """Test that Agent validates messages before LLM calls."""
        # Create agent with strict validation
        async with Agent("Test agent", message_validation_mode="strict") as agent:
            # Create an invalid sequence
            agent.messages.append(UserMessage(content="First"))
            agent.messages.append(UserMessage(content="Second"))  # Invalid

            # Should raise ValidationError when calling LLM
            with pytest.raises(ValidationError) as exc_info:
                await agent.call()

            assert "Consecutive user messages" in str(exc_info.value)

    async def test_agent_warn_mode(self):
        """Test agent with warn validation mode."""
        async with Agent("Test agent", message_validation_mode="warn") as agent:
            # Create a slightly invalid sequence
            agent.messages.append(UserMessage(content="First"))
            agent.messages.append(UserMessage(content="Second"))

            # Should not raise, just warn
            issues = agent.validate_message_sequence()
            assert len(issues) > 0
            assert any("Consecutive user messages" in issue for issue in issues)

    async def test_agent_silent_mode(self):
        """Test agent with silent validation mode."""
        async with Agent("Test agent", message_validation_mode="silent") as agent:
            # Create an invalid sequence
            agent.messages.append(UserMessage(content="First"))
            agent.messages.append(UserMessage(content="Second"))

            # Should not raise or return issues
            issues = agent.validate_message_sequence()
            assert len(issues) == 0

    async def test_agent_tool_sequence_validation(self):
        """Test that agent validates tool call/response sequences."""
        async with Agent("Test agent", message_validation_mode="warn") as agent:
            tool_call_id = str(ULID())

            # Add a tool call
            agent.messages.append(
                AssistantMessage(
                    content="",
                    tool_calls=[
                        ToolCall(
                            id=tool_call_id,
                            type="function",
                            function=ToolCallFunction(name="test_tool", arguments="{}"),
                        )
                    ],
                )
            )

            # Validate with pending tools allowed
            issues = agent.validate_message_sequence(allow_pending_tools=True)
            assert len(issues) == 0

            # Validate with pending tools not allowed
            issues = agent.validate_message_sequence(allow_pending_tools=False)
            assert len(issues) > 0
            assert any("Unresolved tool calls" in issue for issue in issues)

            # Add the tool response
            agent.messages.append(
                ToolMessage(
                    content="Tool result",
                    tool_call_id=tool_call_id,
                    tool_name="test_tool",
                )
            )

            # Now should be valid
            issues = agent.validate_message_sequence()
            assert len(issues) == 0

    async def test_filtered_message_list_maintains_valid_sequence(self):
        """Test that FilteredMessageList operations maintain valid sequences."""
        async with Agent("Test agent", message_validation_mode="warn") as agent:
            # Use FilteredMessageList to add messages
            agent.user.append("Hello")
            agent.assistant.append("Hi there!")

            # Add tool call and response
            tool_call_id = str(ULID())
            agent.assistant.append(
                "",
                tool_calls=[
                    ToolCall(
                        id=tool_call_id,
                        type="function",
                        function=ToolCallFunction(name="test_tool", arguments="{}"),
                    )
                ],
            )
            agent.tool.append(
                "Tool result",
                tool_call_id=tool_call_id,
                tool_name="test_tool",
            )

            # Validate the sequence
            issues = agent.validate_message_sequence()
            assert len(issues) == 0

    async def test_config_parameter_validation_mode(self):
        """Test that validation mode can be set via config parameter."""
        # Test each mode
        modes: tuple[
            Literal["strict"], Literal["warn"], Literal["silent"]
        ] = ("strict", "warn", "silent")
        for mode in modes:
            async with Agent("Test", message_validation_mode=mode) as agent:
                assert agent._sequence_validator.mode == ValidationMode(mode)

    async def test_default_validation_mode(self):
        """Test that default validation mode is 'warn'."""
        async with Agent("Test") as agent:
            assert agent._sequence_validator.mode == ValidationMode.WARN
