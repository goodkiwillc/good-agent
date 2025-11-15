"""Structured output extraction using instructor."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Unpack

from ..events import AgentEvents
from .protocols import CompletionEvent

if TYPE_CHECKING:
    from litellm.types.completion import ChatCompletionMessageParam
    from pydantic import BaseModel

    from ..config_types import ModelConfig
    from .llm import LanguageModel


class StructuredOutputExtractor:
    """Handles structured output extraction from LLM responses.

    Uses the instructor library to convert LLM responses into validated
    Pydantic models with automatic retry logic.
    """

    def __init__(self, language_model: LanguageModel):
        """Initialize extractor.

        Args:
            language_model: Parent LanguageModel instance
        """
        self.llm = language_model

    async def extract(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        response_model: type[BaseModel],
        **kwargs: Unpack[ModelConfig],
    ) -> BaseModel:
        """Extract structured data from LLM responses using instructor library.

        Converts unstructured LLM responses into validated Pydantic models
        with automatic retry logic, fallback model support, and comprehensive
        error handling.

        Args:
            messages: Sequence of chat messages for extraction context
            response_model: Pydantic BaseModel class for response validation
            **kwargs: Additional model configuration parameters

        Returns:
            Validated instance of the response_model

        Raises:
            ValueError: If instructor returns None instead of BaseModel
            ValidationError: If response cannot be validated against schema
            Exception: When all extraction attempts fail across models

        Example:
            >>> from pydantic import BaseModel
            >>> class UserInfo(BaseModel):
            ...     name: str
            ...     age: int
            >>> messages = [{"role": "user", "content": "John is 25"}]
            >>> user = await extractor.extract(messages, UserInfo)
        """
        from .overrides import model_override_registry

        # Note: messages already have tool call pairs ensured by format_message_list_for_llm()

        config = self.llm._prepare_request_config(**kwargs)

        # Apply model-specific overrides LAST so they take precedence
        model_name = str(config.get("model", self.llm.model))
        config = model_override_registry.apply(model_name, config)

        # Fire before event (using apply_typed for type safety)
        from ..core.event_router import EventContext

        start_time = time.time()
        ctx: EventContext[CompletionEvent, None] = await self.llm.agent.apply_typed(
            AgentEvents.LLM_EXTRACT_BEFORE,
            CompletionEvent,
            None,  # No specific return type expected for 'before' event
            messages=messages,
            config=config,
            response_model=response_model,
            llm=self.llm,
        )

        try:
            # Router already handles retries/fallbacks via model_list configuration
            response = await self.llm.instructor.aextract(
                messages=list(ctx.parameters["messages"]),  # Use modified messages
                response_model=response_model,
                **ctx.parameters["config"],  # Use modified config
            )

            # Ensure response is not None (instructor should always return a BaseModel)
            if response is None:
                raise ValueError("Instructor returned None instead of BaseModel")

            # Fire after event
            end_time = time.time()
            self.llm.do(
                AgentEvents.LLM_EXTRACT_AFTER,
                response=response,
                response_model=response_model,
                parameters=config,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                language_model=self.llm,
            )

            return response

        except (asyncio.CancelledError, KeyboardInterrupt):
            # Propagate cancellations immediately
            raise
        except Exception as e:
            # Fire error event
            end_time = time.time()
            self.llm.do(
                AgentEvents.LLM_EXTRACT_ERROR,
                error=e,
                response_model=response_model,
                parameters=config,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                language_model=self.llm,
            )
            raise


__all__ = ["StructuredOutputExtractor"]
