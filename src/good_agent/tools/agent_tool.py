from __future__ import annotations

from typing import TYPE_CHECKING, Any

from good_agent.tools.tools import Tool, ToolParameter

if TYPE_CHECKING:
    from good_agent.agent.core import Agent


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
        **kwargs: Any,
    ) -> str:
        """
        Delegate a task to the sub-agent.

        Args:
            prompt: The instruction or message for the sub-agent.
            session_id: Optional ID to maintain conversation context across calls.
            **kwargs: Additional arguments.

        Returns:
            The response content from the sub-agent.
        """
        target_agent = self._get_agent_for_session(session_id)

        # Execute the sub-agent
        # Note: We use agent.call() which returns a message, so we extract content
        response = await target_agent.call(prompt)
        return str(response.content)

    def _get_agent_for_session(self, session_id: str | None) -> Agent:
        """
        Retrieve or create an agent instance for the given session.
        """
        if not self.multi_turn or not session_id:
            # One-shot: Fork a fresh agent every time (or just use a clean fork)
            # We fork to ensure we don't pollute the base agent's state or other sessions
            # include_messages=True means we keep the system prompt/history of the base agent
            return self.base_agent.fork(include_messages=True)

        if session_id not in self.sessions:
            # New session: Fork from base
            self.sessions[session_id] = self.base_agent.fork(include_messages=True)

        return self.sessions[session_id]

    def as_tool(self) -> Tool:
        """
        Return a configured Tool instance that can be registered with an Agent.
        """
        # We manually construct the tool instance to avoid signature inspection issues
        # with the __call__ method which might not be fully introspectable in tests
        tool = Tool(
            fn=self.__call__,
            name=self.name,
            description=self.description,
        )

        # Manually inject parameters to ensure they are correct regardless of inspection
        # This overrides whatever the Tool constructor inferred
        tool._tool_metadata.parameters = {
            "prompt": ToolParameter(
                name="prompt",
                type=str,
                description="The task or question for the sub-agent",
            ),
            "session_id": ToolParameter(
                name="session_id",
                type=str | None,
                description="Session ID for multi-turn context (optional)",
                default=None,
                required=False,
            ),
        }
        return tool
