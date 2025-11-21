"""Message utility classes and functions."""

from __future__ import annotations

from typing import Any

from good_agent.messages.base import Message, deserialize_content_part
from good_agent.messages.roles import (
    AssistantMessage,
    AssistantMessageStructuredOutput,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


class MessageFactory:
    """Factory for creating messages from dictionaries."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """Create a message from a dictionary representation.

        Args:
            data: Dictionary containing message data including role and content

        Returns:
            Appropriate message instance based on role
        """
        # Handle legacy content format
        if "content" in data and "content_parts" not in data:
            # Legacy format - convert string content to new format
            content = data.pop("content")
            if isinstance(content, str):
                data["content_parts"] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                # Already structured - assume it's content parts
                data["content_parts"] = content

        # Parse content_parts if present
        if "content_parts" in data:
            content_parts = []
            for part_data in data["content_parts"]:
                if isinstance(part_data, dict):
                    content_parts.append(deserialize_content_part(part_data))
                else:
                    content_parts.append(part_data)
            data["content_parts"] = content_parts

        # Support both 'type' and 'role' field names
        message_type = data.get("type") or data.get("role")

        # Create appropriate message type
        if message_type == "user":
            return UserMessage(**data)
        elif message_type == "system":
            return SystemMessage(**data)
        elif message_type == "assistant":
            # Check for structured output
            if "output" in data:
                return AssistantMessageStructuredOutput(**data)
            return AssistantMessage(**data)
        elif message_type == "tool":
            return ToolMessage(**data)
        else:
            raise ValueError(f"Unknown message type: {message_type}")


__all__ = ["MessageFactory"]
