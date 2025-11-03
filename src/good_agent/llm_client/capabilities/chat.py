"""
Chat capability protocol.

Defines the interface for providers that support chat completions.
"""

from typing import Protocol, AsyncIterator, Any, runtime_checkable

from ..types.chat import ChatResponse, StreamChunk
from ..types.common import Message


@runtime_checkable
class ChatCapability(Protocol):
    """
    Protocol for providers that support chat completions.
    
    Any provider implementing this protocol can be used for chat-based
    interactions with language models.
    """
    
    async def chat_complete(
        self,
        messages: list[Message],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """
        Complete a chat conversation.
        
        Args:
            messages: List of conversation messages
            model: Model identifier to use
            **kwargs: Additional provider-specific parameters
                (temperature, max_tokens, tools, etc.)
        
        Returns:
            ChatResponse with the model's completion
            
        Raises:
            ProviderError: If the API call fails
        """
        ...
    
    async def chat_stream(
        self,
        messages: list[Message],
        model: str,
        **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a chat conversation response.
        
        Args:
            messages: List of conversation messages
            model: Model identifier to use
            **kwargs: Additional provider-specific parameters
        
        Yields:
            StreamChunk objects as the response is generated
            
        Raises:
            ProviderError: If the API call fails
        """
        ...
        # This is a protocol, so we need to make it a generator
        yield  # type: ignore
