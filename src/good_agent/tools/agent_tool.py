from __future__ import annotations

import itertools
import threading
from typing import TYPE_CHECKING

from good_agent.tools.tools import Tool

if TYPE_CHECKING:
    from good_agent.agent.core import Agent


class SessionIdGenerator:
    """Generates short, unique session identifiers."""

    _counter = itertools.count(1)
    _lock = threading.Lock()

    @classmethod
    def next_id(cls) -> str:
        """Get the next unique session ID."""
        with cls._lock:
            return str(next(cls._counter))


class AgentAsTool:
    """
    Wraps an Agent to be used as a tool by another Agent.

    Supports both one-shot interactions and multi-turn conversations via session identifiers.
    """

    def __init__(
        self,
        agent: Agent,
        name: str | None = None,
        description: str | None = None,
        multi_turn: bool = True,
    ):
        """
        Initialize the AgentAsTool wrapper.

        Args:
            agent: The base agent to wrap.
            name: The name of the tool (defaults to agent.name).
            description: The description of the tool.
            multi_turn: Whether to support multi-turn sessions.
        """
        self.base_agent = agent
        self.name = name or agent.name or "sub_agent"
        self.description = description or f"Delegate task to {self.name}"
        self.multi_turn = multi_turn
        self.sessions: dict[str, Agent] = {}

    async def __call__(
        self,
        prompt: str,
        session_id: str | None = None,
    ) -> str:
        """
        Delegate a task to the sub-agent.

        Args:
            prompt: The instruction or message for the sub-agent.
            session_id: Optional ID to maintain conversation context across calls.

        Returns:
            The response content from the sub-agent.
        """
        # If multi-turn is enabled but no session_id provided, generate one
        # so we can persist this conversation and allow the parent to reference it later.
        current_session_id = session_id
        if self.multi_turn and not current_session_id:
            current_session_id = SessionIdGenerator.next_id()

        target_agent = self._get_agent_for_session(current_session_id)

        # Execute the sub-agent
        # Note: We use agent.call() which returns a message, so we extract content
        response = await target_agent.call(prompt)
        content = str(response.content)

        # If multi-turn is enabled, wrap the response in XML tags with the session ID
        # This provides consistent context to the parent agent and easy reference
        if self.multi_turn and current_session_id:
            return f'<{self.name} session_id="{current_session_id}">\n{content}\n</{self.name}>'

        return content

    def _get_agent_for_session(self, session_id: str | None) -> Agent:
        """
        Retrieve or create an agent instance for the given session.
        """
        if not self.multi_turn or not session_id:
            # One-shot: Fork a fresh agent every time
            return self.base_agent.fork(include_messages=True)

        if session_id not in self.sessions:
            # New session: Fork from base and store it
            self.sessions[session_id] = self.base_agent.fork(include_messages=True)

        return self.sessions[session_id]

    def as_tool(self) -> Tool:
        """
        Return a configured Tool instance that can be registered with an Agent.
        """
        # We construct the tool instance from the __call__ method
        # The Tool class handles inspection and parameter extraction
        tool = Tool(
            fn=self.__call__,
            name=self.name,
            description=self.description,
        )

        return tool
