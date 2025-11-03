"""
OpenAI provider implementation.

Wraps the official OpenAI SDK and implements ChatCapability.
"""

from typing import Any, AsyncIterator
from openai import AsyncOpenAI

from ..base import BaseProvider
from ...capabilities.chat import ChatCapability
from ...types.chat import ChatResponse, StreamChunk
from ...types.common import Message, Usage


class OpenAIProvider(BaseProvider, ChatCapability):
    """
    Provider for OpenAI API.
    
    Implements ChatCapability using the official OpenAI SDK.
    """
    
    provider_name = "openai"
    
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        **kwargs: Any
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            base_url: Optional custom base URL
            **kwargs: Additional parameters passed to BaseProvider
        """
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)
        
        # Initialize OpenAI client
        client_kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
        }
        
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        
        self._client = AsyncOpenAI(**client_kwargs)
    
    async def chat_complete(
        self,
        messages: list[Message],
        model: str,
        **kwargs: Any
    ) -> ChatResponse:
        """
        Complete a chat conversation using OpenAI.
        
        Args:
            messages: List of conversation messages
            model: OpenAI model identifier (e.g., "gpt-4o-mini")
            **kwargs: Additional parameters (temperature, max_tokens, tools, etc.)
        
        Returns:
            ChatResponse with the completion
        """
        # Convert our Message objects to OpenAI format
        openai_messages = [
            self._message_to_dict(msg) for msg in messages
        ]
        
        # Call OpenAI API
        response = await self._client.chat.completions.create(
            model=model,
            messages=openai_messages,  # type: ignore
            **kwargs
        )
        
        # Convert response to our format
        return self._convert_response(response)
    
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
            model: OpenAI model identifier
            **kwargs: Additional parameters
        
        Yields:
            StreamChunk objects as the response is generated
        """
        # Convert messages
        openai_messages = [
            self._message_to_dict(msg) for msg in messages
        ]
        
        # Call OpenAI API with streaming
        stream = await self._client.chat.completions.create(
            model=model,
            messages=openai_messages,  # type: ignore
            stream=True,
            **kwargs
        )
        
        # Yield chunks
        async for chunk in stream:
            yield self._convert_stream_chunk(chunk)
    
    def _message_to_dict(self, message: Message) -> dict[str, Any]:
        """Convert our Message to OpenAI format."""
        result: dict[str, Any] = {"role": message.role}
        
        if message.content is not None:
            result["content"] = message.content
        
        if message.name is not None:
            result["name"] = message.name
        
        if message.tool_calls is not None:
            result["tool_calls"] = message.tool_calls
        
        if message.tool_call_id is not None:
            result["tool_call_id"] = message.tool_call_id
        
        return result
    
    def _convert_response(self, response: Any) -> ChatResponse:
        """Convert OpenAI response to our ChatResponse format."""
        # Preserve raw response - use model_dump if available, else convert to dict
        raw_response = None
        if hasattr(response, 'model_dump') and callable(response.model_dump):
            try:
                dumped = response.model_dump()
                # Verify it's actually a dict (not a Mock or other object)
                if isinstance(dumped, dict):
                    raw_response = dumped
                else:
                    raw_response = self._response_to_dict(response)
            except Exception:
                # Fallback: try to convert manually
                raw_response = self._response_to_dict(response)
        else:
            raw_response = self._response_to_dict(response)
        
        # Convert choices
        choices = []
        for choice in response.choices:
            choice_dict: dict[str, Any] = {
                "message": self._convert_message(choice.message)
            }
            choices.append(choice_dict)
        
        # Convert usage
        usage = Usage(
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            prompt_tokens_details=getattr(response.usage, 'prompt_tokens_details', None),
            completion_tokens_details=getattr(response.usage, 'completion_tokens_details', None)
        )
        
        # Build response
        return ChatResponse(
            id=response.id,
            model=response.model,
            choices=choices,
            usage=usage,
            created=response.created,
            system_fingerprint=getattr(response, 'system_fingerprint', None),
            raw_response=raw_response
        )
    
    def _convert_message(self, message: Any) -> Message:
        """Convert OpenAI message to our Message format."""
        tool_calls = None
        if hasattr(message, 'tool_calls') and message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        
        # Get name only if it exists and is not None
        name = None
        if hasattr(message, 'name'):
            name_val = getattr(message, 'name', None)
            # Check if it's actually set (not a Mock or empty)
            if name_val is not None and isinstance(name_val, str):
                name = name_val
        
        return Message(
            role=message.role,
            content=message.content,
            name=name,
            tool_calls=tool_calls
        )
    
    def _response_to_dict(self, obj: Any) -> dict[str, Any]:
        """
        Convert response object to dict, preserving all attributes.
        
        This is a fallback for when model_dump() doesn't work.
        """
        if isinstance(obj, dict):
            return obj
        
        result: dict[str, Any] = {}
        
        # Try to get all attributes
        for attr in dir(obj):
            # Skip private/magic methods
            if attr.startswith('_'):
                continue
            
            try:
                value = getattr(obj, attr)
                # Skip methods
                if callable(value):
                    continue
                
                # Recursively convert nested objects
                if hasattr(value, '__dict__') and not isinstance(value, (str, int, float, bool)):
                    result[attr] = self._response_to_dict(value)
                elif isinstance(value, list):
                    result[attr] = [
                        self._response_to_dict(item) if hasattr(item, '__dict__') else item
                        for item in value
                    ]
                else:
                    result[attr] = value
            except Exception:
                # Skip attributes that can't be accessed
                continue
        
        return result
    
    def _convert_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Convert OpenAI stream chunk to our StreamChunk format."""
        # Preserve raw chunk
        raw_response = None
        if hasattr(chunk, 'model_dump') and callable(chunk.model_dump):
            try:
                dumped = chunk.model_dump()
                # Verify it's actually a dict (not a Mock or other object)
                if isinstance(dumped, dict):
                    raw_response = dumped
                else:
                    raw_response = self._response_to_dict(chunk)
            except Exception:
                raw_response = self._response_to_dict(chunk)
        else:
            raw_response = self._response_to_dict(chunk)
        
        # Convert delta choices
        choices = []
        for choice in chunk.choices:
            delta_dict: dict[str, Any] = {}
            
            if hasattr(choice.delta, 'content') and choice.delta.content is not None:
                delta_dict["content"] = choice.delta.content
            
            if hasattr(choice.delta, 'role') and choice.delta.role is not None:
                delta_dict["role"] = choice.delta.role
            
            if hasattr(choice.delta, 'tool_calls') and choice.delta.tool_calls:
                delta_dict["tool_calls"] = choice.delta.tool_calls
            
            choices.append({"delta": delta_dict, "index": choice.index})
        
        return StreamChunk(
            id=chunk.id,
            model=chunk.model,
            choices=choices,
            created=chunk.created,
            raw_response=raw_response
        )
