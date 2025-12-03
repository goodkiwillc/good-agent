import logging
from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING

from good_agent.messages import (
    AssistantMessage,
    Message,
    MessageList,
    SystemMessage,
    ToolMessage,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


class ValidationMode(Enum):
    """Validation mode for message sequencing."""

    STRICT = "strict"  # Raise exceptions on invalid sequences
    WARN = "warn"  # Log warnings but allow
    SILENT = "silent"  # No validation


class ValidationError(Exception):
    """Raised when message sequence validation fails in strict mode."""

    pass


class MessageSequenceValidator:
    """Validates message sequences for LLM compatibility."""

    def __init__(self, mode: ValidationMode = ValidationMode.WARN):
        """Initialize the validator with a specific mode.

        Args:
            mode: Validation mode (strict, warn, or silent)
        """
        self.mode = mode

    def validate(self, messages: MessageList | Sequence[Message]) -> list[str]:
        """Validate a message sequence for LLM compatibility.

        Args:
            messages: List of messages to validate

        Returns:
            List of validation issues found

        Raises:
            ValidationError: If validation fails in strict mode
        """
        if self.mode == ValidationMode.SILENT:
            return []

        issues = []

        # Check tool call/response sequencing
        issues.extend(self._validate_tool_sequencing(messages))

        # Check role alternation patterns
        issues.extend(self._validate_role_alternation(messages))

        # Check system message placement
        issues.extend(self._validate_system_messages(messages))

        agent_name = "AnonymousAgent"  # Default name
        if messages[-1].agent and messages[-1].agent.name:
            agent_name = messages[-1].agent.name

        # Handle issues based on mode
        if issues:
            if self.mode == ValidationMode.STRICT:
                raise ValidationError(
                    f"Message sequence validation failed for {agent_name}:\n"
                    + "\n".join(f"  - {issue}" for issue in issues)
                )
            elif self.mode == ValidationMode.WARN:
                for issue in issues:
                    logger.warning(f"Message sequence issue for {agent_name}: {issue}")

        return issues

    def _validate_tool_sequencing(self, messages: Sequence[Message]) -> list[str]:
        """Validate that tool responses immediately follow their tool calls.

        Rules:
        1. Every assistant message with tool_calls must be immediately followed by
           the corresponding tool response messages
        2. Tool response messages must reference valid tool_call_ids
        3. All tool calls must have corresponding responses before the next non-tool message
        """
        issues = []
        pending_tool_calls = {}  # tool_call_id -> (message_index, tool_name)
        processed_tool_responses = set()  # Track tool messages we've already validated

        for i, msg in enumerate(messages):
            # Track assistant messages with tool calls
            if isinstance(msg, AssistantMessage) and msg.tool_calls:
                # Record all tool calls from this message
                for tool_call in msg.tool_calls:
                    if tool_call.id in pending_tool_calls:
                        issues.append(f"Duplicate tool_call_id '{tool_call.id}' at index {i}")
                    pending_tool_calls[tool_call.id] = (
                        i,
                        tool_call.function.name,
                    )

                # The next messages should be tool responses
                expected_responses = len(msg.tool_calls)
                j = 1
                while j <= expected_responses and i + j < len(messages):
                    next_msg = messages[i + j]

                    if not isinstance(next_msg, ToolMessage):
                        issues.append(
                            f"Expected tool response at index {i + j}, "
                            f"but found {next_msg.role} message"
                        )
                        break

                    # Mark this tool message as processed
                    processed_tool_responses.add(i + j)

                    # Verify the tool response references a pending tool call
                    if next_msg.tool_call_id not in pending_tool_calls:
                        issues.append(
                            f"Tool response at index {i + j} references "
                            f"unknown tool_call_id '{next_msg.tool_call_id}'"
                        )
                    else:
                        # Mark this tool call as resolved
                        del pending_tool_calls[next_msg.tool_call_id]

                    j += 1

            # Check for tool messages without preceding tool calls
            elif isinstance(msg, ToolMessage):
                # Skip if we've already processed this tool message
                if i in processed_tool_responses:
                    continue

                if msg.tool_call_id not in pending_tool_calls:
                    # Check if this might be from a previous assistant message
                    found = False
                    for prev_i in range(i - 1, -1, -1):
                        prev_msg = messages[prev_i]
                        if isinstance(prev_msg, AssistantMessage) and prev_msg.tool_calls:
                            if any(tc.id == msg.tool_call_id for tc in prev_msg.tool_calls):
                                found = True
                                # But it should have been handled already
                                issues.append(
                                    f"Tool response at index {i} appears out of sequence "
                                    f"(should immediately follow assistant message at index {prev_i})"
                                )
                                break
                    if not found:
                        issues.append(f"Tool response at index {i} has no corresponding tool call")

            # Non-tool message with pending tool calls
            elif pending_tool_calls and not isinstance(msg, ToolMessage):
                # Some models might be OK with this, but most aren't
                unresolved = list(pending_tool_calls.keys())
                if unresolved:
                    issues.append(
                        f"Unresolved tool calls {unresolved} before {msg.role} message at index {i}"
                    )

        # Check for any remaining unresolved tool calls
        if pending_tool_calls:
            unresolved = [
                f"{tool_id} (from message {idx})"
                for tool_id, (idx, _) in pending_tool_calls.items()
            ]
            issues.append(f"Unresolved tool calls at end of sequence: {unresolved}")

        return issues

    def _validate_role_alternation(self, messages: Sequence[Message]) -> list[str]:
        """Validate role alternation patterns.

        Rules:
        1. Generally, user and assistant messages should alternate
        2. System messages can appear at the beginning
        3. Tool messages are allowed after assistant messages with tool calls
        """
        issues = []

        # Skip system messages at the beginning
        start_idx = 0
        while start_idx < len(messages) and isinstance(messages[start_idx], SystemMessage):
            start_idx += 1

        last_non_tool_role = None
        last_non_tool_idx = None

        for i in range(start_idx, len(messages)):
            msg = messages[i]
            current_role = msg.role

            # Tool messages are special - they follow assistant messages
            # Skip them for role alternation checks
            if current_role == "tool":
                continue

            # Check for consecutive same-role messages (except system)
            if last_non_tool_role == current_role and current_role != "system":
                # Some models allow consecutive assistant messages, but flag it
                if current_role == "assistant":
                    # This might be OK if:
                    # 1. There were tool messages between the two assistant messages
                    # 2. The current assistant has tool calls (continuing conversation to make tool calls)
                    # 3. The previous assistant had tool calls (but they haven't been resolved yet)
                    if last_non_tool_idx is not None:
                        # Check if there were tool messages between the two assistant messages
                        has_tool_messages_between = any(
                            messages[j].role == "tool" for j in range(last_non_tool_idx + 1, i)
                        )
                        # Check if current assistant has tool calls
                        current_has_tool_calls = (
                            isinstance(msg, AssistantMessage) and msg.tool_calls
                        )
                        # Check if previous assistant had tool calls
                        prev_msg = messages[last_non_tool_idx]
                        prev_has_tool_calls = (
                            isinstance(prev_msg, AssistantMessage) and prev_msg.tool_calls
                        )

                        # Only report issue if none of these conditions are met
                        if not (
                            has_tool_messages_between
                            or current_has_tool_calls
                            or prev_has_tool_calls
                        ):
                            issues.append(
                                f"Consecutive {current_role} messages at indices {last_non_tool_idx} and {i}"
                            )
                else:
                    if last_non_tool_idx is not None:
                        issues.append(
                            f"Consecutive {current_role} messages at indices {last_non_tool_idx} and {i}"
                        )

            last_non_tool_role = current_role
            last_non_tool_idx = i

        return issues

    def _validate_system_messages(self, messages: Sequence[Message]) -> list[str]:
        """Validate system message placement.

        Rules:
        1. System messages typically appear at the beginning
        2. Some models support system messages throughout, but this is model-specific
        """
        issues: list[str] = []

        # Find all system message indices
        system_indices = [i for i, msg in enumerate(messages) if isinstance(msg, SystemMessage)]

        if not system_indices:
            return issues

        # Check if system messages are only at the beginning
        last_system_idx = system_indices[-1]
        first_non_system_idx = None

        for i, msg in enumerate(messages):
            if not isinstance(msg, SystemMessage):
                first_non_system_idx = i
                break

        if first_non_system_idx is not None and last_system_idx > first_non_system_idx:
            # System messages appear after non-system messages
            issues.append(
                f"System message at index {last_system_idx} appears after "
                f"non-system messages (consider model compatibility)"
            )

        return issues

    def validate_before_append(
        self,
        messages: MessageList | list[Message],
        new_message: Message,
    ) -> list[str]:
        """Validate that appending a new message would maintain valid sequencing.

        Args:
            messages: Current message list
            new_message: Message to be appended

        Returns:
            List of validation issues that would occur
        """
        # Create a temporary list with the new message
        temp_messages = list(messages) + [new_message]
        return self.validate(temp_messages)

    def validate_partial_sequence(
        self,
        messages: MessageList | list[Message],
        allow_pending_tools: bool = False,
    ) -> list[str]:
        """Validate a potentially incomplete message sequence.

        Args:
            messages: Message list that might be incomplete
            allow_pending_tools: Whether to allow unresolved tool calls

        Returns:
            List of validation issues found
        """
        if self.mode == ValidationMode.SILENT:
            return []

        # Run validators WITHOUT logging first (avoid warn spam for filtered issues)
        issues: list[str] = []
        issues.extend(self._validate_tool_sequencing(messages))
        issues.extend(self._validate_role_alternation(messages))
        issues.extend(self._validate_system_messages(messages))

        # If pending tool calls are allowed (e.g., instructor tool-call mode where
        # dummy tool responses are injected only in outbound payload), suppress all
        # tool-sequencing related issues that are expected to be resolved at send-time.
        if allow_pending_tools:
            suppress_patterns = [
                "Unresolved tool calls",
                "Expected tool response",
                "appears out of sequence",
                "Tool response at index",
                "before user message",
                "before assistant message",
            ]
            issues = [issue for issue in issues if not any(p in issue for p in suppress_patterns)]

        # Handle logging/raising for the REMAINING issues only
        if issues:
            agent_name = "AnonymousAgent"
            try:
                if messages and messages[-1].agent and messages[-1].agent.name:
                    agent_name = messages[-1].agent.name  # type: ignore[assignment]
            except Exception:
                pass

            if self.mode == ValidationMode.STRICT:
                raise ValidationError(
                    f"Message sequence validation failed for {agent_name}:\n"
                    + "\n".join(f"  - {issue}" for issue in issues)
                )
            elif self.mode == ValidationMode.WARN:
                for issue in issues:
                    logger.warning(f"Message sequence issue for {agent_name}: {issue}")

        return issues
