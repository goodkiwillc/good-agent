"""
Token counting utilities.

Provides token counting for different LLM providers with lazy-loaded tiktoken.
"""

from typing import Any
from ..types.common import Message


# Model to encoding mapping
_MODEL_TO_ENCODING = {
    # GPT-4 models
    "gpt-4": "cl100k_base",
    "gpt-4-32k": "cl100k_base",
    "gpt-4-turbo": "cl100k_base",
    "gpt-4-turbo-preview": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4o-2024-11-20": "o200k_base",
    "gpt-4o-2024-08-06": "o200k_base",
    "gpt-4o-2024-05-13": "o200k_base",
    "gpt-4o-mini-2024-07-18": "o200k_base",
    
    # GPT-3.5 models
    "gpt-3.5-turbo": "cl100k_base",
    "gpt-3.5-turbo-16k": "cl100k_base",
    "gpt-3.5-turbo-instruct": "cl100k_base",
    
    # Text models
    "text-davinci-003": "p50k_base",
    "text-davinci-002": "p50k_base",
    "text-curie-001": "r50k_base",
    "text-babbage-001": "r50k_base",
    "text-ada-001": "r50k_base",
}

# Tokens per message for different models
_TOKENS_PER_MESSAGE = {
    "gpt-4": 3,
    "gpt-4o": 3,
    "gpt-3.5-turbo": 4,  # Every message has <|start|>role/name\n{content}<|end|>\n
}

_TOKENS_PER_NAME = 1  # If there's a name, the role is omitted


def get_encoding_for_model(model: str) -> str:
    """
    Get the encoding name for a given model.
    
    Args:
        model: Model identifier
    
    Returns:
        Encoding name (e.g., "cl100k_base", "o200k_base")
    """
    # Check exact match
    if model in _MODEL_TO_ENCODING:
        return _MODEL_TO_ENCODING[model]
    
    # Check prefixes for versioned models
    for model_prefix, encoding in _MODEL_TO_ENCODING.items():
        if model.startswith(model_prefix):
            return encoding
    
    # Default to cl100k_base for unknown OpenAI models
    if any(prefix in model for prefix in ["gpt-4", "gpt-3.5"]):
        return "cl100k_base"
    
    # For unknown models, we'll fall back to approximation
    return "cl100k_base"


def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """
    Count tokens in a text string.
    
    Uses tiktoken for OpenAI models, approximation for others.
    Tiktoken is lazily loaded to avoid import overhead.
    
    Args:
        text: Text to count tokens for
        model: Model identifier (used to select encoding)
    
    Returns:
        Number of tokens
    """
    if not text:
        return 0
    
    # Check if this is an Anthropic or unknown model
    if "claude" in model.lower() or model not in _MODEL_TO_ENCODING:
        # Check if it's a known OpenAI-ish model
        is_openai = any(prefix in model for prefix in ["gpt-", "text-", "davinci", "curie", "babbage", "ada"])
        
        if not is_openai:
            # Use approximation for non-OpenAI models
            # Rough estimate: ~1 token per 4 characters
            return len(text) // 4 + 1
    
    # Lazy load tiktoken
    try:
        import tiktoken
    except ImportError:
        # Fallback if tiktoken not available
        return len(text) // 4 + 1
    
    try:
        # Get encoding for model
        encoding_name = get_encoding_for_model(model)
        encoding = tiktoken.get_encoding(encoding_name)
        
        # Count tokens
        tokens = encoding.encode(text)
        return len(tokens)
    except Exception:
        # Fallback to approximation on any error
        return len(text) // 4 + 1


def count_message_tokens(
    messages: list[Message],
    model: str = "gpt-4o-mini"
) -> int:
    """
    Count tokens in a list of messages.
    
    Accounts for message formatting overhead (role tokens, etc.).
    Based on OpenAI's token counting logic.
    
    Args:
        messages: List of messages
        model: Model identifier
    
    Returns:
        Total token count including overhead
    """
    if not messages:
        return 0
    
    # For non-OpenAI models, use simple approximation
    if "claude" in model.lower():
        total = 0
        for msg in messages:
            if msg.content:
                total += len(msg.content) // 4 + 1
            # Add overhead for role
            total += 3
        return total
    
    # Lazy load tiktoken
    try:
        import tiktoken
    except ImportError:
        # Fallback: count content tokens + overhead
        total = 0
        for msg in messages:
            if msg.content:
                total += len(msg.content) // 4 + 1
            total += 4  # Message overhead
        return total + 3  # Conversation overhead
    
    try:
        encoding_name = get_encoding_for_model(model)
        encoding = tiktoken.get_encoding(encoding_name)
    except Exception:
        # Fallback if encoding fails
        total = 0
        for msg in messages:
            if msg.content:
                total += len(msg.content) // 4 + 1
            total += 4
        return total + 3
    
    # Get tokens per message for this model
    tokens_per_message = 3  # Default
    for model_prefix, tpm in _TOKENS_PER_MESSAGE.items():
        if model.startswith(model_prefix):
            tokens_per_message = tpm
            break
    
    num_tokens = 0
    
    for message in messages:
        num_tokens += tokens_per_message
        
        # Count role
        num_tokens += len(encoding.encode(message.role))
        
        # Count content
        if message.content:
            num_tokens += len(encoding.encode(message.content))
        
        # Count name if present
        if message.name:
            num_tokens += len(encoding.encode(message.name))
            num_tokens += _TOKENS_PER_NAME
        
        # Count tool calls if present
        if message.tool_calls:
            # Approximate token count for tool calls
            for tool_call in message.tool_calls:
                if isinstance(tool_call, dict):
                    # Count function name and arguments
                    func = tool_call.get("function", {})
                    if func:
                        name = func.get("name", "")
                        args = func.get("arguments", "")
                        num_tokens += len(encoding.encode(name))
                        num_tokens += len(encoding.encode(args))
                        num_tokens += 5  # Overhead for tool call structure
    
    # Add overhead for conversation
    num_tokens += 3  # Every reply is primed with <|start|>assistant<|message|>
    
    return num_tokens
