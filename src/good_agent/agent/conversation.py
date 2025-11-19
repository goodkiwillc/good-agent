import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Self, TypeVar, Union

from ulid import ULID

if TYPE_CHECKING:
    ConversationSelf = TypeVar("ConversationSelf", bound="Conversation")

from good_agent.events import AgentEvents
from good_agent.messages import AssistantMessage, Message, UserMessage

from .core import Agent


class Conversation:
    """
    Context manager for agent-to-agent conversations.

    When entered, sets up message forwarding between agents:
    - Assistant messages from one agent become user messages in the other
    - Supports both 2-agent and multi-agent conversations

    Usage:
        async with agent_one | agent_two as conversation:
            agent_one.append(AssistantMessage("Hello from agent one"))
            # This will be forwarded as a user message to agent_two
    """

    def __init__(self, *agents: Agent):
        self.id: ULID = ULID()
        self.participants = list(agents)
        self.conversation_id: str = str(uuid.uuid4())
        self._active = False
        self._handler_ids: dict[Agent, list[int]] = {}

    def __or__(self, other: Union[Agent, "Conversation"]) -> "Conversation":
        """Chain agents or conversations together using the | operator."""
        if isinstance(other, Agent):
            # Add agent to this conversation
            return self.__class__(*self.participants, other)
        elif isinstance(other, Conversation):
            # Merge conversations
            return self.__class__(*self.participants, *other.participants)
        else:
            raise TypeError(f"Cannot chain Conversation with {type(other)}")

    def __len__(self) -> int:
        """Return the number of agents in the conversation"""
        return len(self.participants)

    async def __aenter__(self) -> Self:
        """Enter the conversation context and set up message forwarding."""
        self._active = True

        # Register event handlers for message forwarding
        self._handler_ids.clear()

        for source_agent in self.participants:
            self._register_forwarding_handler(source_agent)

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the conversation context and clean up message forwarding."""
        self._active = False

        # Deregister event handlers
        for agent, handler_ids in list(self._handler_ids.items()):
            for handler_id in handler_ids:
                try:
                    agent._handler_registry.deregister(handler_id)  # type: ignore[attr-defined]
                except Exception:
                    continue

        self._handler_ids.clear()

    def _register_forwarding_handler(self, source_agent: Agent) -> None:
        """Register an event handler that forwards assistant messages from source_agent."""

        def handle_append(ctx):
            self._handle_message_append(source_agent, ctx)

        registered_handler = source_agent.on(AgentEvents.MESSAGE_APPEND_AFTER)(
            handle_append
        )

        handler_id = getattr(registered_handler, "_handler_id", None)
        if handler_id is None:
            raise RuntimeError("Failed to register conversation handler")

        self._handler_ids.setdefault(source_agent, []).append(handler_id)

    def _handle_message_append(self, source_agent: Agent, ctx: Any) -> None:
        """Forward assistant messages from source_agent to other participants."""

        if not self._active:
            return

        if ctx.parameters.get("agent") is not source_agent:
            return

        message = ctx.parameters.get("message")
        if not isinstance(message, AssistantMessage):
            return

        if getattr(message, "_conversation_forwarded", False):
            return

        # Mark source message to avoid re-forwarding
        message._conversation_forwarded = True  # type: ignore[attr-defined]

        for target_agent in self.participants:
            if target_agent is source_agent:
                continue

            forwarded_message = UserMessage(content=message.content)
            forwarded_message._conversation_forwarded = True  # type: ignore[attr-defined]
            target_agent.append(forwarded_message)

    async def execute(
        self,
        max_iterations: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[Message]:
        """
        Execute the conversation by alternating between agents.

        Args:
            max_iterations: Maximum number of iterations to prevent infinite loops
            **kwargs: Additional arguments passed to agent.execute()

        Yields:
            Messages generated during the conversation
        """
        if max_iterations is None:
            max_iterations = 20  # Default reasonable limit

        iteration = 0
        current_agent_idx = 0

        while iteration < max_iterations and self.participants:
            current_agent = self.participants[current_agent_idx]

            # Execute current agent
            message_generated = False
            async for message in current_agent.execute(**kwargs):
                yield message
                message_generated = True

                # If it's an assistant message, it will be automatically forwarded
                # to other agents via our event handlers
                if isinstance(message, AssistantMessage):
                    # Move to next agent for next iteration
                    current_agent_idx = (current_agent_idx + 1) % len(self.participants)
                    break

            if not message_generated:
                # No more messages from current agent, try next one
                current_agent_idx = (current_agent_idx + 1) % len(self.participants)

                # If we've tried all agents and none generated messages, stop
                if current_agent_idx == 0:
                    break

            iteration += 1

    @property
    def messages(self) -> list[Message]:
        """Get all messages from all agents in chronological order."""
        all_messages: list[tuple[Message, float]] = []

        # Collect messages with timestamps from all agents
        for agent in self.participants:
            for msg in agent.messages:
                # Use message ID as ordering (ULIDs are chronologically ordered)
                timestamp = float(msg.id.timestamp)
                all_messages.append((msg, timestamp))

        # Sort by timestamp and return just the messages
        all_messages.sort(key=lambda x: x[1])
        return [msg for msg, _ in all_messages]
