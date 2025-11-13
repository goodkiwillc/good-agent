from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar
from weakref import WeakKeyDictionary, ref

import logging

import logfire
from good_agent.core.event_router import EventContext, on
from logfire import ConsoleOptions
from logfire._internal.config import GLOBAL_CONFIG

from ..components import AgentComponent
from ..content import RenderMode
from ..events import AgentEvents
from ..events.types import (
    AgentForkParams,
    AgentInitializeParams,
    AgentStateChangeParams,
    ExecuteAfterParams,
    ExecuteBeforeParams,
    LLMCompleteParams,
    LLMExtractParams,
    MessageAppendParams,
    MessageRenderParams,
    ToolCallAfterParams,
    ToolCallBeforeParams,
    ToolCallErrorParams,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..agent import Agent


@dataclass
class AgentMetadata:
    """Metadata tracked for each agent instance."""

    agent_id: str
    parent_id: str | None = None
    fork_count: int = 0
    context_snapshot: dict[str, Any] | None = None
    config_snapshot: dict[str, Any] | None = None
    creation_timestamp: float | None = None
    state_history: list[tuple[str, float]] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for logging."""
        return {
            "agent_id": self.agent_id,
            "parent_id": self.parent_id,
            "fork_count": self.fork_count,
            "context": self.context_snapshot,
            "config": self.config_snapshot,
            "creation_timestamp": self.creation_timestamp,
            "state_history": self.state_history,
        }


class LogfireExtension(AgentComponent):
    """
    Logfire integration for Agent observability.

    This extension subscribes to agent events and logs comprehensive data to Logfire,
    including actual rendered content sent to LLMs, agent state transitions, and
    inheritance relationships.
    """

    # Class-level metadata storage using weak references
    _agent_metadata: ClassVar[WeakKeyDictionary[Agent, AgentMetadata]] = (
        WeakKeyDictionary()
    )

    def __init__(
        self,
        *,
        service_name: str = "goodintel-agent",
        environment: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        log_level: str = "INFO",
        send_to_logfire: bool = True,
        console: bool | ConsoleOptions | None = False,
        **logfire_kwargs: Any,
    ):
        """
        Initialize Logfire extension.

        Args:
            service_name: Service identifier for logs
            environment: Environment name (dev, staging, prod, etc.)
            api_key: Logfire API key (defaults to LOGFIRE_TOKEN env var)
            base_url: Logfire API base URL
            log_level: Logging level
            send_to_logfire: Whether to send logs to Logfire cloud
            console: Whether to print logs to console (True for defaults, False to disable,
                    or ConsoleOptions instance for custom configuration)
            **logfire_kwargs: Additional Logfire configuration options
        """
        super().__init__()

        self.service_name = service_name
        self.environment = environment or os.getenv("ENVIRONMENT", "development")

        # Handle console parameter properly
        if console is True:
            # Use None to let Logfire use its defaults for console output
            console_config = None
        elif console is False:
            # Explicitly disable console output
            console_config = False
        elif isinstance(console, ConsoleOptions):
            # Use the provided ConsoleOptions instance
            console_config = console
        else:
            # console is None, use as-is
            console_config = console

        # Only configure Logfire if it hasn't been configured yet
        # Check if global config is already initialized
        if not GLOBAL_CONFIG._initialized:
            # Configure Logfire
            config = {
                "service_name": service_name,
                "send_to_logfire": send_to_logfire,
                "console": console_config,
                "inspect_arguments": False,  # Prevent introspection warnings
            }

            if api_key or os.getenv("LOGFIRE_TOKEN"):
                config["token"] = api_key or os.getenv("LOGFIRE_TOKEN")

            if base_url:
                config["base_url"] = base_url

            config.update(logfire_kwargs)

            # Initialize Logfire
            logfire.configure(**config)
            logger.info(
                f"Configured Logfire with service_name={service_name}, "
                f"environment={self.environment}"
            )
        else:
            # Logfire is already configured, just log that we're using existing config
            logger.debug(
                f"LogfireExtension using existing Logfire configuration "
                f"(service_name={service_name} requested but not applied)"
            )

        # Store weak references to track agent relationships
        self._current_agent_ref = None

        logger.debug(f"LogfireExtension initialized (environment={self.environment})")

    async def install(self, agent: Agent) -> None:
        """Install the extension on an agent."""
        await super().install(agent)

        # Store weak reference to the agent
        self._current_agent_ref = ref(agent)

    def _get_agent_metadata(self, agent: Agent) -> AgentMetadata:
        """Get or create metadata for an agent."""
        if agent not in self._agent_metadata:
            import time

            # Create new metadata
            metadata = AgentMetadata(
                agent_id=str(agent.id),
                creation_timestamp=time.time(),
                state_history=[(agent.state.name, time.time())],
            )

            # Capture initial context and config
            if hasattr(agent, "context") and agent.context:
                try:
                    # Convert ChainMap to dict
                    metadata.context_snapshot = dict(agent.context._chainmap)
                except Exception:
                    metadata.context_snapshot = {}

            if hasattr(agent, "config"):
                try:
                    metadata.config_snapshot = {
                        "model": agent.config.model,
                        "temperature": agent.config.temperature,
                        "max_tokens": agent.config.max_tokens,
                        "tools": [t.name for t in agent.tools.values()]
                        if agent.tools
                        else [],
                    }
                except Exception:
                    metadata.config_snapshot = {}

            self._agent_metadata[agent] = metadata

        return self._agent_metadata[agent]

    def _get_timestamp_from_context(self, ctx: EventContext) -> float | None:
        """Extract timestamp from EventContext if available."""
        return getattr(ctx, "invocation_timestamp", None)

    def _format_timestamp(self, timestamp: float) -> str:
        """Format Unix timestamp as ISO string."""
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        return dt.isoformat()

    @on(AgentEvents.AGENT_INIT_AFTER)
    def _on_agent_init(self, ctx: EventContext[AgentInitializeParams, Any]) -> None:
        """Log agent initialization."""
        # Handle both typed params and EventContext
        params = ctx.parameters if isinstance(ctx, EventContext) else ctx.parameters
        timestamp = self._get_timestamp_from_context(ctx)

        agent = params.get("agent")
        if not agent:
            return

        metadata = self._get_agent_metadata(agent)

        with logfire.span("agent.init", _span_name="Agent Initialized") as span:
            attrs = {
                "agent.id": metadata.agent_id,
                "agent.model": agent.config.model if hasattr(agent, "config") else None,
                "agent.message_count": len(agent),
                "agent.has_tools": bool(agent.tools)
                if hasattr(agent, "tools")
                else False,
                "agent.tool_count": len(agent.tools) if hasattr(agent, "tools") else 0,
                "environment": self.environment,
                "service": self.service_name,
            }

            # Add event timestamp if available
            if timestamp:
                attrs["event.timestamp"] = timestamp
                attrs["event.timestamp_iso"] = self._format_timestamp(timestamp)

            span.set_attributes(attrs)

            # Log context if available
            if metadata.context_snapshot:
                span.set_attribute(
                    "agent.context", json.dumps(metadata.context_snapshot)
                )

            logfire.info("Agent initialized", **metadata.to_dict())

    @on(AgentEvents.AGENT_FORK_AFTER)
    def _on_agent_fork(self, ctx: EventContext[AgentForkParams, Any]) -> None:
        """Log agent forking to track inheritance."""
        parent_agent = ctx.parameters.get("parent")
        child_agent = ctx.parameters.get("child")

        if not parent_agent or not child_agent:
            return

        parent_metadata = self._get_agent_metadata(parent_agent)
        child_metadata = self._get_agent_metadata(child_agent)

        # Update child metadata with parent relationship
        child_metadata.parent_id = parent_metadata.agent_id
        parent_metadata.fork_count += 1

        with logfire.span("agent.fork", _span_name="Agent Forked") as span:
            span.set_attributes(
                {
                    "parent.id": parent_metadata.agent_id,
                    "parent.fork_count": parent_metadata.fork_count,
                    "child.id": child_metadata.agent_id,
                    "child.message_count": len(child_agent),
                    "environment": self.environment,
                    "service": self.service_name,
                }
            )

            logfire.info(
                "Agent forked",
                parent=parent_metadata.to_dict(),
                child=child_metadata.to_dict(),
            )

    @on(AgentEvents.AGENT_STATE_CHANGE)
    def _on_state_change(self, ctx: EventContext[AgentStateChangeParams, Any]) -> None:
        """Log agent state transitions."""
        agent = ctx.parameters.get("agent")
        old_state = ctx.parameters.get("old_state")
        new_state = ctx.parameters.get("new_state")

        if not agent:
            return

        metadata = self._get_agent_metadata(agent)

        # Track state history
        import time

        if metadata.state_history and new_state:
            metadata.state_history.append((new_state.name, time.time()))

        with logfire.span(
            "agent.state_change", _span_name="Agent State Changed"
        ) as span:
            span.set_attributes(
                {
                    "agent.id": metadata.agent_id,
                    "state.old": old_state.name if old_state else None,
                    "state.new": new_state.name if new_state else None,
                    "state.value": new_state.value if new_state else None,
                    "environment": self.environment,
                    "service": self.service_name,
                }
            )

            # Format state names safely
            old_state_name = (
                old_state.name
                if old_state and hasattr(old_state, "name")
                else str(old_state)
                if old_state
                else "None"
            )
            new_state_name = (
                new_state.name
                if new_state and hasattr(new_state, "name")
                else str(new_state)
                if new_state
                else "None"
            )

            logfire.info(
                f"Agent state: {old_state_name} -> {new_state_name}",
                agent_id=metadata.agent_id,
                old_state=old_state_name,
                new_state=new_state_name,
            )

    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    def _on_message_append(self, ctx: EventContext[MessageAppendParams, Any]) -> None:
        """Log message additions to track conversation flow."""
        agent = ctx.parameters.get("agent")
        message = ctx.parameters.get("message")

        if not agent or not message:
            return

        metadata = self._get_agent_metadata(agent)

        # Don't log full content here, just metadata
        logfire.debug(
            f"Message appended: {message.role}",
            agent_id=metadata.agent_id,
            message_id=str(message.id) if hasattr(message, "id") else None,
            message_role=message.role,
            message_index=len(agent) - 1,
            has_content_parts=hasattr(message, "content_parts"),
            content_part_count=len(message.content_parts)
            if hasattr(message, "content_parts")
            else 0,
        )

    @on(AgentEvents.LLM_COMPLETE_BEFORE)
    def _on_llm_complete_before(
        self, ctx: EventContext[LLMCompleteParams, Any]
    ) -> None:
        """Log the actual content being sent to the LLM."""
        # Handle both typed params and EventContext
        params = ctx.parameters if isinstance(ctx, EventContext) else ctx.parameters
        timestamp = self._get_timestamp_from_context(ctx)

        messages = params.get("messages")
        config: dict[str, Any] = params.get("config", {})
        params.get("language_model")

        if not messages:
            return

        # Get agent metadata if available
        agent = params.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        with logfire.span(
            "llm.complete.request", _span_name="LLM Completion Request"
        ) as span:
            # Set basic attributes
            attrs: dict[str, Any] = {
                "llm.model": config.get("model") if isinstance(config, dict) else None,
                "llm.temperature": config.get("temperature")
                if isinstance(config, dict)
                else None,
                "llm.max_tokens": config.get("max_tokens")
                if isinstance(config, dict)
                else None,
                "llm.message_count": len(messages),
                "environment": self.environment,
                "service": self.service_name,
            }

            if metadata:
                attrs["agent.id"] = metadata.agent_id
                attrs["agent.parent_id"] = metadata.parent_id

            # Add event timestamp if available
            if timestamp:
                attrs["event.timestamp"] = timestamp
                attrs["event.timestamp_iso"] = self._format_timestamp(timestamp)

            span.set_attributes(attrs)

            # Log the actual rendered messages
            rendered_messages = []
            for msg in messages:
                rendered_content = msg.get("content", "")
                rendered_messages.append(
                    {
                        "role": msg.get("role"),
                        "content": rendered_content[:1000],  # Truncate for logging
                        "content_length": len(str(rendered_content)),
                    }
                )

            logfire.info(
                "LLM request",
                model=config.get("model"),
                messages=rendered_messages,
                agent_id=metadata.agent_id if metadata else None,
                has_tools=bool(config.get("tools")),
                tool_count=len(config.get("tools", [])),
            )

    @on(AgentEvents.LLM_COMPLETE_AFTER)
    def _on_llm_complete_after(self, ctx: EventContext[LLMCompleteParams, Any]) -> None:
        """Log LLM response with usage statistics."""
        # Handle both typed params and EventContext
        params = ctx.parameters if isinstance(ctx, EventContext) else ctx.parameters
        self._get_timestamp_from_context(ctx)

        response = params.get("response")
        usage = params.get("usage")

        if not response:
            return

        # Get agent metadata if available
        agent = ctx.parameters.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        with logfire.span(
            "llm.complete.response", _span_name="LLM Completion Response"
        ) as span:
            attrs = {
                "llm.response_id": getattr(response, "id", None),
                "llm.model_used": getattr(response, "model", None),
                "environment": self.environment,
                "service": self.service_name,
            }

            if usage:
                attrs.update(
                    {
                        "llm.usage.prompt_tokens": getattr(
                            usage, "prompt_tokens", None
                        ),
                        "llm.usage.completion_tokens": getattr(
                            usage, "completion_tokens", None
                        ),
                        "llm.usage.total_tokens": getattr(usage, "total_tokens", None),
                    }
                )

            if metadata:
                attrs["agent.id"] = metadata.agent_id

            span.set_attributes(attrs)

            # Extract response content
            response_content = None
            if hasattr(response, "choices") and response.choices:
                choice = response.choices[0]
                if hasattr(choice, "message"):
                    response_content = getattr(choice.message, "content", None)

            logfire.info(
                "LLM response received",
                agent_id=metadata.agent_id if metadata else None,
                response_length=len(response_content) if response_content else 0,
                usage=attrs.get("llm.usage.total_tokens"),
            )

    @on(AgentEvents.LLM_EXTRACT_BEFORE)
    def _on_llm_extract_before(self, ctx: EventContext[LLMExtractParams, Any]) -> None:
        """Log structured extraction requests."""
        messages = ctx.parameters.get("messages")
        response_model = ctx.parameters.get("response_model")
        config = ctx.parameters.get("config", {})

        if not messages:
            return

        # Get agent metadata if available
        agent = ctx.parameters.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        with logfire.span(
            "llm.extract.request", _span_name="LLM Extract Request"
        ) as span:
            attrs: dict[str, Any] = {
                "llm.model": config.get("model") if isinstance(config, dict) else None,
                "llm.response_model": response_model.__name__
                if response_model
                else None,
                "llm.message_count": len(messages),
                "environment": self.environment,
                "service": self.service_name,
            }

            if metadata:
                attrs["agent.id"] = metadata.agent_id

            span.set_attributes(attrs)

            logfire.info(
                f"LLM extraction: {response_model.__name__ if response_model else 'Unknown'}",
                agent_id=metadata.agent_id if metadata else None,
                model=config.get("model") if isinstance(config, dict) else None,
            )

    @on(AgentEvents.LLM_EXTRACT_AFTER)
    def _on_llm_extract_after(self, ctx: EventContext[LLMExtractParams, Any]) -> None:
        """Log structured extraction results."""
        response = ctx.parameters.get("response")
        usage = ctx.parameters.get("usage")

        # Get agent metadata if available
        agent = ctx.parameters.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        logfire.info(
            "LLM extraction completed",
            agent_id=metadata.agent_id if metadata else None,
            response_type=type(response).__name__ if response else None,
            usage_tokens=getattr(usage, "total_tokens", None) if usage else None,
        )

    @on(AgentEvents.TOOL_CALL_BEFORE)
    def _on_tool_call_before(
        self, ctx: EventContext[ToolCallBeforeParams, Any]
    ) -> None:
        """Log tool invocation requests."""
        tool_call = ctx.parameters.get("tool_call")

        if not tool_call:
            return

        # Get agent metadata if available
        agent = ctx.parameters.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        with logfire.span("tool.call", _span_name=f"Tool: {tool_call.name}") as span:
            span.set_attributes(
                {
                    "tool.name": tool_call.name,
                    "tool.call_id": tool_call.id,
                    "environment": self.environment,
                    "service": self.service_name,
                }
            )

            if metadata:
                span.set_attribute("agent.id", metadata.agent_id)

            # Log tool arguments (be careful with sensitive data)
            try:
                # Use getattr for safe attribute access on tool_call
                arguments = getattr(tool_call, "arguments", None)
                args = (
                    json.loads(arguments) if isinstance(arguments, str) else arguments
                )
                logfire.info(
                    f"Tool call: {tool_call.name}",
                    agent_id=metadata.agent_id if metadata else None,
                    tool_name=tool_call.name,
                    tool_args=args,
                )
            except Exception:
                logfire.info(
                    f"Tool call: {tool_call.name}",
                    agent_id=metadata.agent_id if metadata else None,
                    tool_name=tool_call.name,
                )

    @on(AgentEvents.TOOL_CALL_AFTER)
    def _on_tool_call_after(self, ctx: EventContext[ToolCallAfterParams, Any]) -> None:
        """Log tool execution results."""
        response = ctx.parameters.get("response")
        tool_call = ctx.parameters.get("tool_call")

        if not response:
            return

        # Get agent metadata if available
        agent = ctx.parameters.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        logfire.info(
            f"Tool completed: {tool_call.name if tool_call else 'Unknown'}",
            agent_id=metadata.agent_id if metadata else None,
            tool_name=tool_call.name if tool_call else None,
            success=response.success if hasattr(response, "success") else True,
            response_length=len(str(response.response))
            if hasattr(response, "response")
            else 0,
        )

    @on(AgentEvents.TOOL_CALL_ERROR)
    def _on_tool_call_error(self, ctx: EventContext[ToolCallErrorParams, Any]) -> None:
        """Log tool execution errors."""
        error = ctx.parameters.get("error")
        tool_call = ctx.parameters.get("tool_call")

        # Get agent metadata if available
        agent = ctx.parameters.get("agent")
        metadata = self._get_agent_metadata(agent) if agent else None

        logfire.error(
            f"Tool error: {tool_call.name if tool_call else 'Unknown'}",
            agent_id=metadata.agent_id if metadata else None,
            tool_name=tool_call.name if tool_call else None,
            error_type=type(error).__name__ if error else None,
            error_message=str(error) if error else None,
        )

    @on(AgentEvents.EXECUTE_BEFORE)
    def _on_execute_before(self, ctx: EventContext[ExecuteBeforeParams, Any]) -> None:
        """Log agent execution start."""
        agent = ctx.parameters.get("agent")
        max_iterations = ctx.parameters.get("max_iterations")

        if not agent:
            return

        metadata = self._get_agent_metadata(agent)

        with logfire.span("agent.execute", _span_name="Agent Execution") as span:
            span.set_attributes(
                {
                    "agent.id": metadata.agent_id,
                    "agent.parent_id": metadata.parent_id,
                    "execute.max_iterations": max_iterations,
                    "environment": self.environment,
                    "service": self.service_name,
                }
            )

            logfire.info(
                "Agent execution started",
                agent_id=metadata.agent_id,
                max_iterations=max_iterations,
            )

    @on(AgentEvents.EXECUTE_AFTER)
    def _on_execute_after(self, ctx: EventContext[ExecuteAfterParams, Any]) -> None:
        """Log agent execution completion."""
        agent = ctx.parameters.get("agent")
        iterations = ctx.parameters.get("iterations")

        if not agent:
            return

        metadata = self._get_agent_metadata(agent)

        logfire.info(
            "Agent execution completed",
            agent_id=metadata.agent_id,
            iterations=iterations,
            final_message_count=len(agent),
        )

    @on(AgentEvents.MESSAGE_RENDER_BEFORE)
    def _on_message_render_before(
        self, ctx: EventContext[MessageRenderParams, Any]
    ) -> None:
        """Log message rendering start."""
        message = ctx.parameters.get("message")
        mode = ctx.parameters.get("mode", RenderMode.DISPLAY)

        # Handle both RenderMode enum and string literals
        render_mode_str = mode.value if isinstance(mode, RenderMode) else str(mode)

        logfire.debug(
            "Message rendering",
            message_role=message.role if message else None,
            render_mode=render_mode_str,
        )

    @on(AgentEvents.MESSAGE_RENDER_AFTER)
    def _on_message_render_after(
        self, ctx: EventContext[MessageRenderParams, Any]
    ) -> None:
        """Log rendered message content."""
        message = ctx.parameters.get("message")
        output = ctx.parameters.get("output")
        mode = ctx.parameters.get(
            "context", RenderMode.DISPLAY
        )  # mode is in context param

        if not message or not output:
            return

        # Only log LLM mode renders in detail (actual content sent to LLM)
        if mode == RenderMode.LLM:
            logfire.debug(
                "Message rendered for LLM",
                message_role=message.role,
                rendered_length=len(output),
                rendered_preview=output[:500],  # First 500 chars
            )
