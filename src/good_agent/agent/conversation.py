import uuid
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, Any, Self, TypeVar

from ulid import ULID

if TYPE_CHECKING:
    ConversationSelf = TypeVar("ConversationSelf", bound="Conversation")

from good_agent.agent.core import Agent
from good_agent.events import AgentEvents
from good_agent.messages import AssistantMessage, Message, UserMessage


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
        self._exit_stack = AsyncExitStack()

    def __or__(self, other: Agent | Conversation) -> Conversation:
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
        self._original_system_messages: dict[Agent, Any] = {}

        # Register event handlers for message forwarding
        self._handler_ids.clear()

        # Setup context for >2 participants
        is_group_chat = len(self.participants) > 2

        for i, source_agent in enumerate(self.participants):
            # Manage agent lifecycle if not already ready
            if not source_agent.is_ready:
                await self._exit_stack.enter_async_context(source_agent)

            self._register_forwarding_handler(source_agent)

            if is_group_chat:
                # 1. Save original system message
                current_sys = source_agent.system[-1] if source_agent.system else None
                if current_sys:
                    self._original_system_messages[source_agent] = current_sys

                    # 2. Generate suffix
                    my_name = source_agent.name or f"Agent_{i}"
                    others = []
                    for j, p in enumerate(self.participants):
                        if p is not source_agent:
                            p_name = p.name or f"Agent_{j}"
                            others.append(f"@{p_name}")

                    suffix = (
                        f"\n\nYou are @{my_name} in a chat-room style conversation with "
                        f"{len(others)} other agents: {', '.join(others)}. "
                        "Conversations happen in a round-robin form. "
                        "You may directly tag other agents using the @name syntax. "
                        "You may skip responding to a particular round if you wish by responding `skip`."
                    )

                    # 3. Create new message with suffix appended
                    # We copy the original message to preserve metadata/id, but update content
                    from good_agent.content import TextContentPart

                    # Create new content parts list
                    new_parts = list(current_sys.content_parts)
                    new_parts.append(TextContentPart(text=suffix))

                    # Create replacement message
                    # We use create_message to ensure proper validation/id generation
                    # but we might want to preserve ID? usually replacing implies new ID/version
                    new_sys = source_agent.model.create_message(
                        *new_parts,
                        role="system",
                        citations=current_sys.citations,
                        # Copy other attributes if needed
                    )  # type: ignore[call-overload]

                    # 4. Update agent
                    source_agent.set_system_message(message=new_sys)

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the conversation context and clean up message forwarding."""
        self._active = False

        # Restore original system messages
        if hasattr(self, "_original_system_messages"):
            for agent, original_sys in self._original_system_messages.items():
                agent.set_system_message(message=original_sys)
            self._original_system_messages.clear()

        # Deregister event handlers
        for agent, handler_ids in list(self._handler_ids.items()):
            for handler_id in handler_ids:
                try:
                    agent._handler_registry.deregister(handler_id)  # type: ignore[attr-defined]
                except Exception:
                    continue

        self._handler_ids.clear()

        # Clean up managed agents
        await self._exit_stack.aclose()

    def _register_forwarding_handler(self, source_agent: Agent) -> None:
        """Register an event handler that forwards assistant messages from source_agent."""

        def handle_append(ctx):
            self._handle_message_append(source_agent, ctx)

        registered_handler = source_agent.on(AgentEvents.MESSAGE_APPEND_AFTER)(handle_append)

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

        is_group_chat = len(self.participants) > 2
        source_name = source_agent.name or "Unknown"

        for target_agent in self.participants:
            if target_agent is source_agent:
                continue

            # Prepare content
            content = message.content
            if is_group_chat:
                # Wrap content for group chat context
                content = f"!# section message author=@{source_name}\n{content}\n!# end section"

            forwarded_message = UserMessage(content=content)
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
