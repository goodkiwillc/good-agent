import uuid
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any, Self, Union

from typing import TypeVar
from ulid import ULID

if TYPE_CHECKING:
    ConversationSelf = TypeVar("ConversationSelf", bound="Conversation")

from .agent import Agent
from .messages import AssistantMessage, Message, UserMessage


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
        self._original_append_methods: dict[Agent, Any] = {}

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

        # Set up direct message forwarding by wrapping append methods
        for source_agent in self.participants:
            # Store original append method
            self._original_append_methods[source_agent] = source_agent.append

            # Get other agents (all except current)
            target_agents = [a for a in self.participants if a != source_agent]

            # Create a wrapper for this specific agent
            def create_wrapper(src: Agent, targets: list[Agent], original_append: Any):
                def wrapped_append(*args, **kwargs):
                    # Call original append method
                    original_append(*args, **kwargs)

                    # If active and it's an assistant message, forward it
                    if self._active and src.messages:
                        last_message = src.messages[-1]
                        if isinstance(last_message, AssistantMessage):
                            # Check if already forwarded
                            if not getattr(
                                last_message, "_conversation_forwarded", False
                            ):
                                # Mark as forwarded
                                last_message._conversation_forwarded = True  # type: ignore[attr-defined]

                                # Forward to all other agents
                                for target in targets:
                                    user_msg = UserMessage(content=last_message.content)
                                    user_msg._conversation_forwarded = True  # type: ignore[attr-defined]

                                    # Use the original append method of the target
                                    if target in self._original_append_methods:
                                        self._original_append_methods[target](user_msg)
                                    else:
                                        target.append(user_msg)

                return wrapped_append

            # Replace append method with wrapper
            source_agent.append = create_wrapper(  # type: ignore[method-assign]
                source_agent, target_agents, self._original_append_methods[source_agent]
            )

        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the conversation context and clean up message forwarding."""
        self._active = False

        # Restore original append methods
        if hasattr(self, "_original_append_methods"):
            for agent, original_append in self._original_append_methods.items():
                agent.append = original_append  # type: ignore[method-assign]
            self._original_append_methods.clear()

    async def execute(
        self, max_iterations: int | None = None
    ) -> AsyncIterator[Message]:
        """
        Execute the conversation by alternating between agents.

        Args:
            max_iterations: Maximum number of iterations to prevent infinite loops

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
            async for message in current_agent.execute():
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
