"""Context Manager - Manages fork, thread, and context operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

import orjson
from ulid import ULID

from good_agent.agent.config import AGENT_CONFIG_KEYS
from good_agent.agent.pool import AgentPool
from good_agent.events import AgentEvents
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from good_agent.tools import ToolCall, ToolCallFunction, ToolResponse

if TYPE_CHECKING:
    from good_agent.agent.core import Agent
    from good_agent.agent.thread_context import ForkContext, ThreadContext

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages fork, thread, and context operations.

    This manager handles all agent context operations including:
    - Forking agents with configuration cloning
    - Fork context creation for isolated operations
    - Thread context creation for temporary modifications
    """

    def __init__(self, agent: Agent) -> None:
        """Initialize context manager.

        Args:
            agent: Parent Agent instance
        """
        self.agent = agent

    def fork(
        self,
        include_messages: bool = True,
        **kwargs: Any,
    ) -> Agent:
        """
        Fork the agent into a new agent with the same configuration (or modified).

        Creates a new agent with:
        - New session_id (different from parent)
        - Same version_id (until modified)
        - Optionally copied messages (with new IDs)
        - Same or modified configuration

        Args:
            include_messages: Whether to copy messages to the forked agent
            **kwargs: Configuration overrides for the new agent
        """
        # Avoid circular import
        from good_agent.agent.core import Agent

        # Get current config and update with kwargs
        config = self.agent.config.as_dict()
        config.update(kwargs)

        # Filter config to only include valid AgentConfigParameters
        valid_params = AGENT_CONFIG_KEYS
        filtered_config = {k: v for k, v in config.items() if k in valid_params}

        override_keys = {
            key
            for key in kwargs
            if key
            in {
                "language_model",
                "mock",
                "tool_manager",
                "template_manager",
                "extensions",
            }
        }
        self.agent._component_registry.clone_extensions_for_config(filtered_config, override_keys)

        # Create new agent using the constructor
        new_agent = Agent(**filtered_config)

        # Copy messages if requested
        if include_messages:
            for msg in self.agent._messages:
                # Create new message with same content but new ID
                # We need to create a new instance to get a new ID
                msg_data = msg.model_dump(exclude={"id", "role"})

                # Preserve content_parts directly to avoid triggering render
                # which would cause event loop conflicts in async contexts
                if hasattr(msg, "content_parts"):
                    msg_data["content_parts"] = msg.content_parts

                # Create new message of the same type and add via proper methods
                match msg:
                    case SystemMessage():
                        # Use set_system_message for system messages
                        new_msg = new_agent.model.create_message(**msg_data, role="system")
                        new_agent.set_system_message(new_msg)
                    case UserMessage():
                        new_msg = new_agent.model.create_message(**msg_data, role="user")
                        new_agent.append(new_msg)
                    case AssistantMessage():
                        new_msg = new_agent.model.create_message(**msg_data, role="assistant")
                        new_agent.append(new_msg)
                    case ToolMessage():
                        new_msg = new_agent.model.create_message(**msg_data, role="tool")
                        new_agent.append(new_msg)
                    case _:
                        raise ValueError(f"Unknown message type: {type(msg).__name__}")

        # Set version to match source (until modified)
        new_agent._versioning_manager._version_id = self.agent._versioning_manager._version_id

        # Initialize version history with current state
        if new_agent._messages:
            new_agent._versioning_manager._versions = [[msg.id for msg in new_agent._messages]]

        # Emit agent:fork event
        # @TODO: event naming
        self.agent.do(
            AgentEvents.AGENT_FORK_AFTER,
            parent=self.agent,
            child=new_agent,
            config_changes=kwargs,
        )

        return new_agent

    def fork_context(self, truncate_at: int | None = None, **fork_kwargs) -> ForkContext:
        """Create a fork context for isolated operations.

        Args:
            truncate_at: Optional index to truncate messages at
            **fork_kwargs: Additional arguments to pass to fork()

        Returns:
            ForkContext instance to use with async with

        Example:
            async with agent.fork_context(truncate_at=5) as forked:
                response = await forked.call("Summarize")
                # Response only exists in fork
        """
        from good_agent.agent.thread_context import ForkContext

        return ForkContext(self.agent, truncate_at, **fork_kwargs)

    def thread_context(self, truncate_at: int | None = None) -> ThreadContext:
        """Create a thread context for temporary modifications.

        Args:
            truncate_at: Optional index to truncate messages at

        Returns:
            ThreadContext instance to use with async with

        Example:
            async with agent.thread_context(truncate_at=5) as ctx_agent:
                response = await ctx_agent.call("Summarize")
                # After context, agent has original messages + response
        """
        from good_agent.agent.thread_context import ThreadContext

        return ThreadContext(self.agent, truncate_at)

    def copy(self, include_messages: bool = True, **config: Any) -> Agent:
        """Clone the underlying agent with optional configuration overrides."""

        copied = self.agent.__class__(**config)

        if len(self.agent.system) > 0 and not include_messages:
            copied.set_system_message(self.agent.system[0])

        if include_messages:
            for message in self.agent._messages:
                msg_copy = message.model_copy()
                msg_copy._set_agent(copied)
                copied.append(msg_copy)

        return copied

    async def spawn(
        self,
        n: int | None = None,
        prompts: list[str] | None = None,
        **configuration: Any,
    ) -> AgentPool:
        """Spawn multiple forks as an :class:`AgentPool`."""

        if prompts:
            num_agents = len(prompts)
        elif n:
            num_agents = n
        else:
            raise ValueError("Either 'n' or 'prompts' must be provided")

        agents = []
        for i in range(num_agents):
            forked = self.fork(**configuration)

            if prompts and i < len(prompts):
                forked.append(prompts[i])

            agents.append(forked)

        return AgentPool(agents)

    def context_provider(self, name: str):
        """Register an instance-specific context provider via TemplateManager."""

        return self.agent.template.context_provider(name)

    @staticmethod
    def context_providers(name: str):
        """Register a global context provider."""

        from good_agent.extensions.template_manager import global_context_provider

        return global_context_provider(name)

    async def merge(
        self,
        *agents: Agent,
        method: Literal["tool_call", "interleaved"] = "tool_call",
        **kwargs: Any,
    ) -> None:
        """Merge multiple agents into the parent agent's thread."""

        if not agents:
            return

        self.agent.do(
            AgentEvents.AGENT_MERGE_AFTER,
            target=self.agent,
            sources=list(agents),
            strategy=method,
            result=None,
        )

        if method == "tool_call":
            await self._merge_as_tool_calls(*agents, **kwargs)
        elif method == "interleaved":
            raise NotImplementedError("Interleaved merge strategy not yet implemented")
        else:
            raise ValueError(f"Unknown merge method: {method}")

        self.agent._update_version()

        self.agent.do(
            AgentEvents.AGENT_MERGE_AFTER,
            target=self.agent,
            sources=list(agents),
            strategy=method,
            result="success",
        )

    async def _merge_as_tool_calls(self, *agents: Agent, **_kwargs: Any) -> None:
        """Helper that converts child outputs into tool calls on the parent."""

        tool_calls: list[ToolCall] = []
        tool_messages = []

        for i, agent in enumerate(agents):
            last_assistant = None
            for msg in reversed(agent.messages):
                match msg:
                    case AssistantMessage() as assistant_msg:
                        last_assistant = assistant_msg
                        break
                    case _:
                        continue

            if last_assistant is None:
                continue

            tool_call_id = f"merge_{ULID()}"
            tool_name = f"agent_merge_{i}"
            arguments = {
                "agent_id": str(agent.id),
                "content": last_assistant.content,
                "reasoning": getattr(last_assistant, "reasoning", None),
                "citations": getattr(last_assistant, "citations", None),
            }

            tool_call = ToolCall(
                id=tool_call_id,
                type="function",
                function=ToolCallFunction(
                    name=tool_name,
                    arguments=orjson.dumps(arguments).decode("utf-8"),
                ),
            )
            tool_calls.append(tool_call)

            tool_response = ToolResponse(
                tool_name=tool_name,
                tool_call_id=tool_call_id,
                response=last_assistant.content,
                parameters=arguments,
                success=True,
                error=None,
            )

            tool_message = self.agent.model.create_message(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                tool_response=tool_response,
                role="tool",
            )
            tool_messages.append(tool_message)

        if tool_calls:
            assistant_message = self.agent.model.create_message(
                content="Merging results from sub-agents",
                tool_calls=tool_calls,
                role="assistant",
            )
            self.agent.append(assistant_message)

            for tool_message in tool_messages:
                self.agent.append(tool_message)
