"""
Common types used across providers.

These types provide a unified interface for LLM responses.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class Usage(BaseModel):
    """Token usage information."""
    
    model_config = ConfigDict(extra="allow")
    
    prompt_tokens: int = Field(description="Number of tokens in the prompt")
    completion_tokens: int = Field(description="Number of tokens in the completion")
    total_tokens: int = Field(description="Total number of tokens used")
    prompt_tokens_details: dict[str, Any] | None = Field(
        default=None, 
        description="Details about prompt tokens (e.g., cached_tokens)"
    )
    completion_tokens_details: dict[str, Any] | None = Field(
        default=None,
        description="Details about completion tokens (e.g., reasoning_tokens)"
    )


class Message(BaseModel):
    """A message in a conversation."""
    
    model_config = ConfigDict(extra="allow")
    
    role: Literal["system", "user", "assistant", "tool"] = Field(
        description="The role of the message sender"
    )
    content: str | list[dict[str, Any]] | None = Field(
        default=None,
        description="The content of the message (string or list of content parts)"
    )
    name: str | None = Field(
        default=None,
        description="The name of the author of this message"
    )
    tool_calls: list[dict[str, Any]] | None = Field(
        default=None,
        description="Tool calls made by the assistant"
    )
    tool_call_id: str | None = Field(
        default=None,
        description="The ID of the tool call this message is responding to"
    )


class ModelResponse(BaseModel):
    """
    Unified response format from any provider.
    
    This is compatible with OpenAI's response format but can be
    adapted to other providers.
    """
    
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(description="Unique identifier for this completion")
    model: str = Field(description="The model used for this completion")
    choices: list[dict[str, Any]] = Field(
        description="List of completion choices"
    )
    usage: Usage = Field(description="Token usage information")
    created: int = Field(description="Unix timestamp of when the completion was created")
    system_fingerprint: str | None = Field(
        default=None,
        description="System fingerprint for this completion"
    )
    response_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional metadata from the provider"
    )
