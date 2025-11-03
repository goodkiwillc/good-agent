"""
Chat-specific types for LLM client.

These types are used for chat completion requests and responses.
"""

from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict

from .common import Message, Usage


class ChatRequest(BaseModel):
    """Request for a chat completion."""
    
    model_config = ConfigDict(extra="allow")
    
    model: str = Field(description="The model to use for completion")
    messages: list[Message] = Field(description="List of messages in the conversation")
    temperature: float | None = Field(default=None, description="Sampling temperature")
    max_tokens: int | None = Field(default=None, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Whether to stream the response")
    tools: list[dict[str, Any]] | None = Field(default=None, description="Available tools")
    tool_choice: str | dict[str, Any] | None = Field(
        default=None, 
        description="Tool choice strategy"
    )


class StreamChunk(BaseModel):
    """A chunk from a streaming response."""
    
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(description="Unique identifier for this chunk")
    model: str = Field(description="The model used")
    choices: list[dict[str, Any]] = Field(description="Delta choices")
    created: int = Field(description="Unix timestamp")
    raw_response: dict[str, Any] | None = Field(
        default=None,
        description="Raw response from the provider, preserving all fields"
    )
    
    def get_content(self) -> str | None:
        """Extract content from the first choice delta."""
        if self.choices and len(self.choices) > 0:
            delta = self.choices[0].get("delta", {})
            return delta.get("content")
        return None


class ChatResponse(BaseModel):
    """Response from a chat completion."""
    
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(description="Unique identifier")
    model: str = Field(description="The model used")
    choices: list[dict[str, Any]] = Field(description="Completion choices")
    usage: Usage = Field(description="Token usage")
    created: int = Field(description="Unix timestamp")
    raw_response: dict[str, Any] | None = Field(
        default=None,
        description="Raw response from the provider, preserving all fields"
    )
    
    def get_content(self) -> str | None:
        """Extract content from the first choice."""
        if self.choices and len(self.choices) > 0:
            message = self.choices[0].get("message", {})
            if isinstance(message, dict):
                return message.get("content")
            return getattr(message, "content", None)
        return None
