"""Typed hooks accessor for Agent events.

Usage examples:
    async with Agent("System") as agent:
        @agent.hooks.on_message_append_before
        def capture(ctx: EventContext[MessageAppendBeforeParams, Message]):
            return ctx.parameters["message"]

        agent.hooks.on_tool_call_before(
            lambda ctx: {"parameters": ctx.parameters.get("parameters", {})}
        )
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents
from good_agent.events.types import (
    AgentCloseParams,
    AgentInitializeParams,
    AgentStateChangeParams,
    AgentVersionChangeParams,
    ExecuteAfterParams,
    ExecuteBeforeParams,
    ExecuteErrorParams,
    ExecuteIterationAfterParams,
    ExecuteIterationParams,
    LLMCompleteParams,
    LLMErrorParams,
    LLMExtractParams,
    LLMStreamParams,
    MessageAppendBeforeParams,
    MessageAppendParams,
    MessageCreateParams,
    MessageRenderParams,
    MessageReplaceParams,
    MessageSetSystemParams,
    ToolCallAfterParams,
    ToolCallBeforeParams,
    ToolCallErrorParams,
    ToolsGenerateSignature,
)

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.messages import Message
    from good_agent.tools import Tool, ToolResponse, ToolSignature


Handler = TypeVar("Handler", bound=Callable[..., Any])


class HooksAccessor:
    """Type-safe event registration helpers via ``agent.hooks``."""

    def __init__(self, agent: Agent):
        self._agent = agent

    def _register(
        self,
        event: AgentEvents,
        func: Handler | None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[Any, Any]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        def decorator(fn: Handler) -> Handler:
            return self._agent.on(event, priority=priority, predicate=predicate)(fn)

        if func is not None:
            return decorator(func)
        return decorator

    # ======================================================================
    # Message Events
    # ======================================================================

    def on_message_append_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageAppendBeforeParams, Message | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: replace or mutate a message before it is appended."""

        return self._register(
            AgentEvents.MESSAGE_APPEND_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_append_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageAppendParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe messages after they have been appended."""

        return self._register(
            AgentEvents.MESSAGE_APPEND_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_create_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageCreateParams, dict[str, Any] | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: adjust message creation inputs before instantiation."""

        return self._register(
            AgentEvents.MESSAGE_CREATE_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_create_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageCreateParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe newly created messages."""

        return self._register(
            AgentEvents.MESSAGE_CREATE_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_render_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageRenderParams, list[Any] | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: modify renderable content parts before formatting."""

        return self._register(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_render_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageRenderParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe rendered content parts."""

        return self._register(
            AgentEvents.MESSAGE_RENDER_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_replace_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageReplaceParams, Message | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: replace messages before substitution."""

        return self._register(
            AgentEvents.MESSAGE_REPLACE_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_replace_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageReplaceParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe replaced messages."""

        return self._register(
            AgentEvents.MESSAGE_REPLACE_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_set_system_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageSetSystemParams, Message | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: adjust the system message before it is stored."""

        return self._register(
            AgentEvents.MESSAGE_SET_SYSTEM_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_message_set_system_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[MessageSetSystemParams, None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe system message updates."""

        return self._register(
            AgentEvents.MESSAGE_SET_SYSTEM_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    # ======================================================================
    # Tool Events
    # ======================================================================

    def on_tool_call_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ToolCallBeforeParams, dict[str, Any] | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: modify tool call parameters before execution."""

        return self._register(
            AgentEvents.TOOL_CALL_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_tool_call_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ToolCallAfterParams, None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe tool responses after execution."""

        return self._register(
            AgentEvents.TOOL_CALL_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_tool_call_error(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ToolCallErrorParams, ToolResponse | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: provide fallback tool responses when errors occur."""

        return self._register(
            AgentEvents.TOOL_CALL_ERROR,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_tools_provide(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ToolsGenerateSignature, list[Tool] | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: filter or replace tool lists before LLM exposure."""

        return self._register(
            AgentEvents.TOOLS_PROVIDE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_tools_generate_signature(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ToolsGenerateSignature, ToolSignature | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: customize tool signatures before LLM calls."""

        return self._register(
            AgentEvents.TOOLS_GENERATE_SIGNATURE,
            func,
            priority=priority,
            predicate=predicate,
        )

    # ======================================================================
    # LLM Events
    # ======================================================================

    def on_llm_complete_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMCompleteParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: adjust completion payloads before LLM invocation."""

        return self._register(
            AgentEvents.LLM_COMPLETE_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_complete_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMCompleteParams, Any]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: inspect or override completion responses."""

        return self._register(
            AgentEvents.LLM_COMPLETE_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_complete_error(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMErrorParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe LLM completion failures."""

        return self._register(
            AgentEvents.LLM_COMPLETE_ERROR,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_extract_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMExtractParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: adjust extraction inputs before structured output calls."""

        return self._register(
            AgentEvents.LLM_EXTRACT_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_extract_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMExtractParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe structured extraction results."""

        return self._register(
            AgentEvents.LLM_EXTRACT_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_stream_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMStreamParams, dict[str, Any] | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: tweak streaming parameters before dispatch."""

        return self._register(
            AgentEvents.LLM_STREAM_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_stream_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMStreamParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe completed stream assemblies."""

        return self._register(
            AgentEvents.LLM_STREAM_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_stream_chunk(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMStreamParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe individual streaming chunks."""

        return self._register(
            AgentEvents.LLM_STREAM_CHUNK,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_llm_error(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[LLMErrorParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe general LLM errors."""

        return self._register(
            AgentEvents.LLM_ERROR,
            func,
            priority=priority,
            predicate=predicate,
        )

    # ======================================================================
    # Execution Events
    # ======================================================================

    def on_execute_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ExecuteBeforeParams, int | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: override iteration limits before execution."""

        return self._register(
            AgentEvents.EXECUTE_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_execute_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ExecuteAfterParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe execution completion and final messages."""

        return self._register(
            AgentEvents.EXECUTE_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_execute_error(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ExecuteErrorParams, Any]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: supply recovery messages when execution fails."""

        return self._register(
            AgentEvents.EXECUTE_ERROR,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_execute_iteration_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ExecuteIterationParams, dict[str, Any] | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: control per-iteration behavior before each loop."""

        return self._register(
            AgentEvents.EXECUTE_ITERATION_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_execute_iteration_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[ExecuteIterationAfterParams, None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe iteration results after each loop."""

        return self._register(
            AgentEvents.EXECUTE_ITERATION_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    # ======================================================================
    # Agent Lifecycle Events
    # ======================================================================

    def on_agent_init_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[AgentInitializeParams, None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe agent initialization completion."""

        return self._register(
            AgentEvents.AGENT_INIT_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_agent_close_before(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[AgentCloseParams, str | None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Interceptable: adjust close reasons before shutdown."""

        return self._register(
            AgentEvents.AGENT_CLOSE_BEFORE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_agent_close_after(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[AgentCloseParams, None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe agent shutdown completion."""

        return self._register(
            AgentEvents.AGENT_CLOSE_AFTER,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_agent_state_change(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[AgentStateChangeParams, None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe state transitions."""

        return self._register(
            AgentEvents.AGENT_STATE_CHANGE,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_agent_version_change(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[AgentVersionChangeParams, None]], bool]
        | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe version ID updates."""

        return self._register(
            AgentEvents.AGENT_VERSION_CHANGE,
            func,
            priority=priority,
            predicate=predicate,
        )

    # ======================================================================
    # Mode Events
    # ======================================================================

    def on_mode_entering(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[dict[str, Any], None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe mode entry before setup runs."""

        return self._register(
            AgentEvents.MODE_ENTERING,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_mode_entered(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[dict[str, Any], None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe mode entry completion."""

        return self._register(
            AgentEvents.MODE_ENTERED,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_mode_exiting(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[dict[str, Any], None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe mode exit before cleanup."""

        return self._register(
            AgentEvents.MODE_EXITING,
            func,
            priority=priority,
            predicate=predicate,
        )

    def on_mode_exited(
        self,
        func: Handler | None = None,
        *,
        priority: int = 100,
        predicate: Callable[[EventContext[dict[str, Any], None]], bool] | None = None,
    ) -> Handler | Callable[[Handler], Handler]:
        """Signal: observe mode exit after cleanup."""

        return self._register(
            AgentEvents.MODE_EXITED,
            func,
            priority=priority,
            predicate=predicate,
        )
