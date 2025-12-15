"""Streaming response handling for LLM completions."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Sequence
from typing import TYPE_CHECKING, Any, Protocol, Unpack

from good_agent.events import AgentEvents
from good_agent.model.protocols import StreamChunk

if TYPE_CHECKING:
    from litellm.types.completion import ChatCompletionMessageParam

    from good_agent.agent.config import ModelConfig

logger = logging.getLogger(__name__)


class SupportsStreamingLanguageModel(Protocol):
    model: str
    fallback_models: list[str]
    router: Any
    litellm: Any
    api_stream_responses: list[Any]
    api_responses: list[Any]
    api_errors: list[Any]

    def _prepare_request_config(self, **kwargs: Unpack[ModelConfig]) -> dict[str, Any]: ...

    def _update_usage(self, response_obj: Any) -> None: ...

    def do(self, event: AgentEvents, **kwargs: Any) -> None: ...


class StreamingHandler:
    """Handles streaming LLM responses with retry and fallback support.

    Provides real-time streaming of LLM responses, yielding chunks as they
    arrive from the API with automatic retry logic for failed streams.
    """

    def __init__(self, language_model: SupportsStreamingLanguageModel):
        """Initialize streaming handler.

        Args:
            language_model: Parent LanguageModel instance
        """
        self.llm = language_model

    async def stream(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        **kwargs: Unpack[ModelConfig],
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion response token by token.

        This method enables real-time streaming of LLM responses, yielding
        chunks as they arrive from the API. Each chunk contains partial
        content and optional finish reason.

        Args:
            messages: Sequence of chat messages
            **kwargs: Additional model configuration options

        Yields:
            StreamChunk: Individual response chunks with content and metadata

        Example:
            >>> async for chunk in handler.stream(messages):
            ...     if chunk.content:
            ...         print(chunk.content, end='', flush=True)
        """

        # Force streaming in config
        kwargs["stream"] = True  # type: ignore[typeddict-item]
        config = self.llm._prepare_request_config(**kwargs)
        model = config.get("model", self.llm.model)

        # Ensure parallel_tool_calls is only sent when tools are specified
        if "parallel_tool_calls" in config and not config.get("tools"):
            # Some providers reject this flag without accompanying tools
            config.pop("parallel_tool_calls", None)

        # Fire before event
        start_time = time.time()
        self.llm.do(
            AgentEvents.LLM_STREAM_BEFORE,
            model=model,
            messages=messages,
            parameters=config,
            language_model=self.llm,
        )

        # Streaming with retry support
        models_to_try = [self.llm.model] + self.llm.fallback_models
        last_exception = None

        for attempt, model in enumerate(models_to_try):
            try:
                # Update config with current model
                config["model"] = model

                # Ensure parallel_tool_calls is still not present after event handlers
                if "parallel_tool_calls" in config and not config.get("tools"):
                    config.pop("parallel_tool_calls", None)

                # Use the router's streaming completion
                stream_response = await self.llm.router.acompletion(
                    messages=list(messages), **config
                )

                # Ensure we have a valid streaming response
                if not hasattr(stream_response, "__aiter__"):
                    raise RuntimeError(
                        f"Router returned non-iterable response: {type(stream_response)}"
                    )

                # Track chunks for rebuilding complete response
                chunks = []

                # Yield chunks as they arrive
                # Cast to AsyncIterator to satisfy type checker after our runtime check
                stream_iter: AsyncIterator = stream_response
                async for chunk in stream_iter:
                    chunks.append(chunk)

                    # Extract content and finish reason from chunk
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        content = (
                            delta.get("content")
                            if hasattr(delta, "get")
                            else getattr(delta, "content", None)
                        )
                        finish_reason = (
                            chunk.choices[0].finish_reason
                            if hasattr(chunk.choices[0], "finish_reason")
                            else None
                        )

                        # Create and yield StreamChunk
                        stream_chunk = StreamChunk(content=content, finish_reason=finish_reason)

                        # Track for debugging
                        self.llm.api_stream_responses.append(stream_chunk)  # type: ignore[arg-type]

                        yield stream_chunk

                # Build complete response from chunks for tracking
                if chunks:
                    try:
                        # Use litellm's chunk builder to reconstruct the full response
                        complete_response = self.llm.litellm.stream_chunk_builder(chunks)

                        # Update usage tracking
                        self.llm._update_usage(complete_response)
                        self.llm.api_responses.append(complete_response)

                        # Fire after event with complete response
                        end_time = time.time()
                        self.llm.do(
                            AgentEvents.LLM_STREAM_AFTER,
                            response=complete_response,
                            chunks=chunks,
                            parameters=config,
                            start_time=start_time,
                            end_time=end_time,
                            language_model=self.llm,
                        )
                    except Exception as e:
                        logger.debug(f"Could not build complete response from chunks: {e}")

                # If we made it here, streaming succeeded
                if attempt > 0:
                    logger.info(f"Successfully used fallback model: {model}")

                return  # Exit the retry loop on success

            except (asyncio.CancelledError, KeyboardInterrupt):
                # Immediate cancellation for streaming; propagate upwards
                raise
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {model} failed during streaming: {e}")

                if attempt < len(models_to_try) - 1:
                    logger.info("Trying fallback model...")
                    continue
                else:
                    logger.error(f"All models failed during streaming. Last error: {e}")
                    break

        # If we exhausted all models, fire error event and raise
        end_time = time.time()
        self.llm.api_errors.append(last_exception)
        self.llm.do(
            AgentEvents.LLM_STREAM_ERROR,
            error=last_exception,
            parameters=config,
            start_time=start_time,
            end_time=end_time,
            language_model=self.llm,
        )

        if last_exception:
            raise last_exception
        else:
            raise Exception("All model attempts failed during streaming")


__all__ = ["StreamingHandler"]
