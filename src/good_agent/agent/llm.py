"""LLM Coordinator - Manages all LLM API interactions, streaming, and structured output."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, TypeGuard, TypeVar

from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents
from good_agent.messages import AssistantMessage, AssistantMessageStructuredOutput
from good_agent.messages.validation import ValidationError
from good_agent.model.protocols import ResponseWithUsage
from good_agent.tools import Tool, ToolSignature

if TYPE_CHECKING:
    from litellm.types.utils import Choices

    from good_agent.agent import Agent

logger = logging.getLogger(__name__)

T_Output = TypeVar("T_Output")


def _is_choices_instance(obj: Any) -> TypeGuard[Choices]:
    """Type guard to check if an object is a Choices instance for type narrowing.

    This allows us to keep Choices behind TYPE_CHECKING while still
    providing proper type narrowing at runtime.
    """
    # At runtime, check the class name since we can't import Choices directly
    return obj.__class__.__name__ == "Choices"


class LLMCoordinator:
    """Coordinates LLM API calls, streaming, and structured output.

    This manager handles all interactions with language models, including:
    - Tool definition generation
    - Structured output extraction
    - Standard completions
    - Parallel tool call configuration
    - Usage tracking
    """

    def __init__(self, agent: Agent) -> None:
        """Initialize LLM coordinator.

        Args:
            agent: Parent Agent instance
        """
        self.agent = agent

    async def get_tool_definitions(self) -> list[ToolSignature] | None:
        """Get tool definitions for the LLM call.

        Returns:
            List of tool signatures or None if no tools available
        """
        tool_definitions: list[ToolSignature] = []

        tools_ctx: EventContext[Any, list[Tool]] = await self.agent.events.apply_typed(
            AgentEvents.TOOLS_PROVIDE,
            return_type=list,  # type: ignore[arg-type]
            output=self.agent.tools.as_list(),
            agent=self.agent,
        )

        tools = tools_ctx.return_value

        if tools and len(tools) > 0:
            for tool in tools:
                tool_ctx = await self.agent.events.apply_typed(
                    AgentEvents.TOOLS_GENERATE_SIGNATURE,
                    params_type=dict,  # type: ignore[arg-type]
                    return_type=ToolSignature,
                    output=tool.signature,
                    tool=tool,
                    agent=self.agent,
                )

                if signature := tool_ctx.return_value:
                    tool_definitions.append(signature)
                else:
                    tool_definitions.append(tool.signature)

        if tool_definitions:
            return tool_definitions
        return None

    async def llm_call(
        self,
        response_model: type[T_Output] | None = None,
        **kwargs: Any,
    ) -> AssistantMessage | AssistantMessageStructuredOutput:
        """Make a single LLM call without tool execution.

        Args:
            response_model: Optional structured output model
            **kwargs: Additional model parameters

        Returns:
            Assistant message response (may contain tool calls)

        Raises:
            ValidationError: If message sequence validation fails
            Exception: LLM API errors are propagated after events
        """
        # Update kwargs with tools if available
        if tool_definitions := await self.get_tool_definitions():
            kwargs["tools"] = tool_definitions
            if "parallel_tool_calls" not in kwargs:
                supports_parallel = getattr(
                    self.agent.model, "supports_parallel_function_calling", None
                )
                should_enable = False
                if callable(supports_parallel):
                    should_enable = supports_parallel()
                elif isinstance(supports_parallel, bool):
                    should_enable = supports_parallel

                if should_enable:
                    kwargs["parallel_tool_calls"] = True

        # Prepare parameters for event
        llm_params = {
            "model": self.agent.model.config.model,
            **kwargs,
        }

        # Validate message sequence before LLM call
        # When requesting structured output (response_model provided), allow pending tool calls
        # since we may inject synthetic tool responses only in the outbound API payload.
        try:
            if response_model is not None:
                self.agent._sequence_validator.validate_partial_sequence(
                    self.agent.messages, allow_pending_tools=True
                )
            else:
                self.agent._sequence_validator.validate(self.agent.messages)
        except ValidationError as e:
            logger.error(f"Message sequence validation failed: {e}")
            raise

        try:
            output = None
            response: AssistantMessage | AssistantMessageStructuredOutput
            if response_model:
                # Use extract for structured output
                output = await self.agent.model.extract(
                    await self.agent.model.format_message_list_for_llm(  # type: ignore[arg-type]
                        self.agent.messages
                    ),
                    response_model,  # type: ignore[arg-type]
                    **kwargs,
                )

                self.agent.model.api_requests[-1]
                llm_response = self.agent.model.api_responses[-1]

            else:
                # Use complete for regular chat
                _messages = await self.agent.model.format_message_list_for_llm(self.agent.messages)

                llm_response = await self.agent.model.complete(
                    _messages,
                    **kwargs,
                )

            choice = llm_response.choices[0]

            assert _is_choices_instance(choice)

            if isinstance(llm_response, ResponseWithUsage):  # type: ignore[misc]
                # Check if it's a real Pydantic model (not MagicMock)
                # MagicMock will have __class__.__module__ starting with 'unittest.mock'
                usage = llm_response.usage
                if hasattr(usage, "__class__") and hasattr(usage.__class__, "__module__"):
                    is_mock = usage.__class__.__module__.startswith("unittest.mock")
                else:
                    is_mock = False

                if (
                    not is_mock
                    and usage
                    and hasattr(usage, "model_dump")
                    and callable(usage.model_dump)
                ):
                    # It's a real Pydantic model, use model_dump
                    kwargs["usage"] = usage.model_dump()
                else:
                    # It's a mock or doesn't have model_dump, extract attributes
                    kwargs["usage"] = {
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage, "completion_tokens", 0),
                        "total_tokens": getattr(usage, "total_tokens", 0),
                    }

            if choice.message.model_extra:
                kwargs.update(choice.message.model_extra)

            # Normalize provider-specific reasoning field to our schema
            # OpenRouter may return `reasoning_content`; map it to `reasoning`
            # Ensure the value is always a string to satisfy pydantic validators
            def _normalize_reasoning(value: Any) -> str | None:
                if value is None:
                    return None
                if isinstance(value, str):
                    return value
                # Some SDKs expose an object with a `content` attribute
                try:
                    content = getattr(value, "content", None)
                except Exception:
                    content = None
                if isinstance(content, str):
                    return content
                # Fallback: string cast (handles Mocks cleanly)
                try:
                    return str(value)
                except Exception:
                    return None

            reasoning_attr = None
            try:
                reasoning_attr = getattr(choice.message, "reasoning_content", None)
            except Exception:
                reasoning_attr = None
            if reasoning_attr is not None and "reasoning" not in kwargs:
                norm = _normalize_reasoning(reasoning_attr)
                if norm:
                    kwargs["reasoning"] = norm
            # If model_extra included `reasoning_content`, map it too
            if "reasoning" not in kwargs and "reasoning_content" in kwargs:
                norm = _normalize_reasoning(kwargs.pop("reasoning_content"))
                if norm:
                    kwargs["reasoning"] = norm
            # Check provider_specific_fields on both message and choice
            psf = None
            try:
                psf = getattr(choice.message, "provider_specific_fields", None)
            except Exception:
                psf = None
            if not psf:
                psf = getattr(choice, "provider_specific_fields", None)
            if isinstance(psf, dict) and psf.get("reasoning_content") and "reasoning" not in kwargs:
                norm = _normalize_reasoning(psf.get("reasoning_content"))
                if norm:
                    kwargs["reasoning"] = norm

            # Extract citations and annotations from message if present
            if hasattr(choice.message, "citations") and choice.message.citations:
                kwargs["citations"] = choice.message.citations
            if hasattr(choice.message, "annotations") and choice.message.annotations:
                kwargs["annotations"] = choice.message.annotations

            if output:
                response = self.agent.model.create_message(
                    role="assistant",
                    output=output,
                    tool_calls=choice.message.tool_calls,
                    provider_specific_fields=choice.provider_specific_fields,
                    **kwargs,
                )
            else:
                response = self.agent.model.create_message(
                    choice.message.content,
                    output=None,
                    role="assistant",
                    tool_calls=choice.message.tool_calls,
                    provider_specific_fields=choice.provider_specific_fields,
                    **kwargs,
                )

            # Add to message list using centralized method
            self.agent._append_message(response)

            return response

        except (asyncio.CancelledError, KeyboardInterrupt):
            # Propagate cancellations immediately so outer callers can stop
            raise
        except Exception as e:
            self.agent.do(AgentEvents.LLM_ERROR, error=e, parameters=llm_params, agent=self.agent)
            raise
