"""
Router with fallback, retry, and hooks.

Provides router functionality similar to litellm but with:
- Fallback logic
- Retry with exponential backoff
- Hooks for monitoring and testing
- Mock mode for easy testing
"""

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator, Callable, Union, overload

from .providers.openai import OpenAIProvider
from .types.chat import ChatResponse, StreamChunk
from .types.common import Message


class Router:
    """
    Router for managing multiple models with fallback and retry logic.

    Features:
    - Automatic fallback to backup models on failure
    - Retry with exponential backoff
    - Hooks for before_request, after_response, on_error
    - Mock mode for testing without API calls
    - Statistics tracking
    """

    def __init__(
        self,
        models: list[str] | None = None,
        model_list: list[dict] | None = None,
        fallback_models: list[str] | None = None,
        api_key: str | None = None,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        timeout: float | None = None,
        **kwargs: Any,
    ):
        """
        Initialize router.

        Args:
            models: List of primary model names (simple format)
            model_list: List of model dicts with config (litellm-compatible)
            fallback_models: List of fallback models if primary fails
            api_key: API key for providers
            max_retries: Maximum number of retries per model
            retry_delay: Initial delay between retries (seconds)
            timeout: Request timeout
            **kwargs: Additional provider configuration
        """
        # Support both simple models list and litellm-style model_list
        if model_list:
            # Extract model names from litellm-style config
            self.models = [
                m.get("model_name") or m.get("litellm_params", {}).get("model") or m.get("params", {}).get("model")
                for m in model_list
            ]
            self.model_list = model_list
        elif models:
            self.models = models
            self.model_list = [{"model_name": m, "params": {"model": m}} for m in models]
        else:
            self.models = []
            self.model_list = []
            
        self.fallback_models = fallback_models or []
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.extra_config = kwargs

        # Hooks
        self._hooks: dict[str, list[Callable]] = defaultdict(list)

        # Mock mode
        self._mock_response: Any = None

        # Statistics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "fallback_used": 0,
            "total_retries": 0,
        }

        # Provider cache
        self._providers: dict[str, Any] = {}

    def add_hook(self, hook_name: str, callback: Callable) -> None:
        """
        Add a hook callback.

        Args:
            hook_name: One of 'before_request', 'after_response', 'on_error'
            callback: Function to call
        """
        self._hooks[hook_name].append(callback)

    def remove_hook(self, hook_name: str, callback: Callable) -> None:
        """Remove a hook callback."""
        if callback in self._hooks[hook_name]:
            self._hooks[hook_name].remove(callback)

    def set_mock_response(self, response: Any) -> None:
        """
        Set mock response for testing.

        Args:
            response: Either a ChatResponse or a callable that returns one
        """
        self._mock_response = response

    def clear_mock_response(self) -> None:
        """Clear mock response."""
        self._mock_response = None

    def _get_provider(self, model: str) -> Any:
        """Get or create provider for model."""
        # Determine provider from model name
        provider_name = self._get_provider_name(model)

        # Cache providers
        cache_key = f"{provider_name}:{model}"
        if cache_key not in self._providers:
            if provider_name == "openai" or "gpt" in model.lower():
                self._providers[cache_key] = OpenAIProvider(
                    api_key=self.api_key or "",
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                    **self.extra_config,
                )
            else:
                # For now, default to OpenAI for unknown models
                # In the future, add more provider detection
                self._providers[cache_key] = OpenAIProvider(
                    api_key=self.api_key or "",
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                    **self.extra_config,
                )

        return self._providers[cache_key]

    def _get_provider_name(self, model: str) -> str:
        """Determine provider name from model."""
        model_lower = model.lower()

        if any(prefix in model_lower for prefix in ["gpt-", "o1-", "text-"]):
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        else:
            # Default to OpenAI for unknown
            return "openai"

    async def _call_hooks(self, hook_name: str, **kwargs: Any) -> None:
        """Call all registered hooks for an event."""
        for callback in self._hooks.get(hook_name, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(**kwargs)
                else:
                    callback(**kwargs)
            except Exception as e:
                # Don't let hook errors break the request
                print(f"Hook {hook_name} failed: {e}")

    @overload
    async def completion(
        self,
        messages: list[Message],
        model: str | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> ChatResponse: ...

    @overload
    async def completion(
        self,
        messages: list[Message],
        model: str | None = None,
        stream: bool = True,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]: ...

    async def completion(
        self,
        messages: list[Message],
        model: str | None = None,
        stream: bool = False,
        **kwargs: Any,
    ):
        """
        Complete a chat request with fallback and retry logic.

        Args:
            messages: List of conversation messages
            model: Model to use (overrides router models)
            stream: Whether to stream response
            **kwargs: Additional parameters

        Returns:
            ChatResponse or AsyncIterator[StreamChunk]
        """
        self.stats["total_requests"] += 1

        # Check mock mode
        if self._mock_response is not None:
            if callable(self._mock_response):
                return self._mock_response(
                    messages=messages, model=model or self.models[0], **kwargs
                )
            return self._mock_response

        # For streaming, use different logic
        if stream:
            return self._stream_with_fallback(messages, model, **kwargs)

        # Determine models to try
        models_to_try = [model] if model else self.models + self.fallback_models

        last_error = None

        for model_name in models_to_try:
            # Call before_request hook
            await self._call_hooks(
                "before_request", model=model_name, messages=messages, kwargs=kwargs
            )

            # Try with retries
            for attempt in range(self.max_retries + 1):
                try:
                    provider = self._get_provider(model_name)

                    response = await provider.chat_complete(
                        messages=messages, model=model_name, **kwargs
                    )

                    # Success!
                    self.stats["successful_requests"] += 1
                    if model_name in self.fallback_models:
                        self.stats["fallback_used"] += 1
                    if attempt > 0:
                        self.stats["total_retries"] += attempt

                    # Call after_response hook
                    await self._call_hooks(
                        "after_response",
                        response=response,
                        model=model_name,
                        messages=messages,
                    )

                    return response

                except Exception as e:
                    last_error = e

                    # Call on_error hook
                    await self._call_hooks(
                        "on_error",
                        error=e,
                        model=model_name,
                        attempt=attempt,
                        messages=messages,
                    )

                    # If not last attempt, retry with backoff
                    if attempt < self.max_retries:
                        delay = self.retry_delay * (2**attempt)  # Exponential backoff
                        await asyncio.sleep(delay)
                    else:
                        # Move to next model
                        break

        # All models failed
        self.stats["failed_requests"] += 1
        raise Exception(f"All models failed. Last error: {last_error}")

    async def _stream_with_fallback(
        self, messages: list[Message], model: str | None = None, **kwargs: Any
    ):
        """
        Stream completion with fallback (simplified - no retry on stream).

        For streaming, we can't easily retry since we start yielding immediately.
        We just try the first available model.
        """
        model_name = model or self.models[0]

        # Call before_request hook
        await self._call_hooks(
            "before_request", model=model_name, messages=messages, kwargs=kwargs
        )

        try:
            provider = self._get_provider(model_name)

            async for chunk in provider.chat_stream(
                messages=messages, model=model_name, **kwargs
            ):
                yield chunk

            self.stats["successful_requests"] += 1

        except Exception as e:
            self.stats["failed_requests"] += 1
            await self._call_hooks(
                "on_error", error=e, model=model_name, attempt=0, messages=messages
            )
            raise

    # Alias for compatibility
    async def async_completion(self, *args: Any, **kwargs: Any) -> ChatResponse:
        """Alias for completion."""
        return await self.completion(*args, **kwargs)
    
    async def acompletion(self, *args: Any, **kwargs: Any) -> ChatResponse:
        """Alias for completion() for litellm compatibility."""
        return await self.completion(*args, **kwargs)  # type: ignore

    def get_stats(self) -> dict[str, int]:
        """Get router statistics."""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reset statistics."""
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "fallback_used": 0,
            "total_retries": 0,
        }
