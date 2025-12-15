from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from good_agent.messages import Message

# Lazy import litellm to avoid import overhead
_token_counter = None


def _get_token_counter():
    """Lazy load litellm token_counter."""
    global _token_counter
    if _token_counter is None:
        from litellm.utils import token_counter

        _token_counter = token_counter
    return _token_counter


@lru_cache(maxsize=1024)
def count_text_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in plain text with caching.

    Args:
        text: Text to count tokens for
        model: Model name for tokenizer selection

    Returns:
        Number of tokens in the text
    """
    token_counter = _get_token_counter()
    try:
        return token_counter(model=model, text=text)
    except Exception as e:
        logger.warning(f"Failed to count tokens for text: {e}")
        # Fallback to rough estimation (4 chars per token)
        return len(text) // 4


def count_message_tokens(
    message_dict: dict[str, Any],
    model: str = "gpt-4o",
    include_tools: bool = True,
) -> int:
    """Count tokens in a message dictionary.

    Args:
        message_dict: Message in dictionary format (LLM API format)
        model: Model name for tokenizer selection
        include_tools: Whether to include tool call tokens

    Returns:
        Number of tokens in the message
    """
    token_counter = _get_token_counter()

    try:
        # Extract tool calls if present
        tool_calls = None
        if include_tools and "tool_calls" in message_dict:
            tool_calls = message_dict.get("tool_calls")

        # Count tokens using litellm
        return token_counter(
            model=model,
            messages=[message_dict],
            tools=tool_calls if tool_calls else None,
        )
    except Exception as e:
        logger.warning(f"Failed to count tokens for message: {e}")
        # Fallback to content-based counting
        content = message_dict.get("content", "")
        if isinstance(content, str):
            return count_text_tokens(content, model)
        return 0


def count_messages_tokens(
    messages: list[dict[str, Any]],
    model: str = "gpt-4o",
    include_tools: bool = True,
) -> int:
    """Count tokens across multiple messages.

    Args:
        messages: List of messages in dictionary format
        model: Model name for tokenizer selection
        include_tools: Whether to include tool call tokens

    Returns:
        Total number of tokens across all messages
    """
    token_counter = _get_token_counter()

    try:
        # Extract tools from assistant messages if present
        tools = []
        if include_tools:
            for msg in messages:
                if msg.get("role") == "assistant" and "tool_calls" in msg:
                    msg_tools = msg.get("tool_calls", [])
                    if msg_tools:
                        tools.extend(msg_tools)

        return token_counter(
            model=model,
            messages=messages,
            tools=tools if tools else None,
        )
    except Exception as e:
        logger.warning(f"Failed to count tokens for messages: {e}")
        # Fallback to sum of individual message counts
        return sum(count_message_tokens(msg, model, include_tools) for msg in messages)


def message_to_dict(message: Message, include_tools: bool = True) -> dict[str, Any]:
    """Convert Message to dictionary format for token counting.

    Args:
        message: Message object to convert
        include_tools: Whether to include tool calls

    Returns:
        Dictionary representation suitable for litellm token counting
    """
    from good_agent.content import RenderMode
    from good_agent.messages import AssistantMessage, ToolMessage

    # Render content without firing events to avoid recursion
    # Use direct part rendering instead of message.render() which fires events
    rendered_parts = []
    for part in message.content_parts:
        try:
            rendered = message._render_part(part, RenderMode.LLM)
            rendered_parts.append(rendered)
        except Exception:
            # Fallback to string representation
            rendered_parts.append(str(part))

    content = "\n".join(rendered_parts) if rendered_parts else ""

    # Base message structure
    msg_dict: dict[str, Any] = {
        "role": message.role,
        "content": content,
    }

    # Add tool-specific fields
    if isinstance(message, ToolMessage):
        msg_dict["tool_call_id"] = message.tool_call_id
        msg_dict["name"] = message.tool_name

    # Add assistant-specific fields
    if isinstance(message, AssistantMessage):
        if include_tools and message.tool_calls:
            # Convert tool calls to litellm format
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

    return msg_dict


def get_message_token_count(
    message: Message,
    model: str = "gpt-4o",
    include_tools: bool = True,
) -> int:
    """Get token count for a message, using cached value if available.

    This function is the main interface for counting tokens in a message.
    It uses the message's internal cache (via _token_count private attribute)
    since messages are immutable.

    Args:
        message: Message object to count tokens for
        model: Model name for tokenizer selection
        include_tools: Whether to include tool call tokens

    Returns:
        Number of tokens in the message
    """
    # Check if message has cached token count for this model/config
    cache_key = f"{model}:{include_tools}"

    token_cache = message._token_count_cache

    if cache_key in token_cache:
        return token_cache[cache_key]

    # Convert message to dictionary format for litellm
    message_dict = message_to_dict(message, include_tools)

    # Count tokens
    count = count_message_tokens(message_dict, model, include_tools)

    # Cache result on message object
    token_cache[cache_key] = count

    return count
