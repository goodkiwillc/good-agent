"""Message utility classes and functions."""

from __future__ import annotations

from typing import Any

from .base import Message, deserialize_content_part
from .roles import (
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
        role = data.get("role")

        # Parse content_parts if present
        if "content_parts" in data:
            content_parts = []
            for part_data in data["content_parts"]:
                if isinstance(part_data, dict):
                    content_parts.append(deserialize_content_part(part_data))
                else:
                    content_parts.append(part_data)
            data["content_parts"] = content_parts

        # Create appropriate message type
        if role == "user":
            return UserMessage(**data)
        elif role == "system":
            return SystemMessage(**data)
        elif role == "assistant":
            # Check for structured output
            if "output" in data:
                return AssistantMessageStructuredOutput(**data)
            return AssistantMessage(**data)
        elif role == "tool":
            return ToolMessage(**data)
        else:
            raise ValueError(f"Unknown message role: {role}")


__all__ = ["MessageFactory"]
