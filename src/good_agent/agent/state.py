"""Agent state management module.

Manages agent state transitions and validation.
"""

from __future__ import annotations

import asyncio
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from good_agent.agent import Agent


class AgentState(IntEnum):
    """Enumeration for agent states with numerical ordering for comparisons"""

    INITIALIZING = 0
    READY = 1
    PENDING_RESPONSE = 2
    PENDING_TOOLS = 3
    PROCESSING = 4


# Valid state transitions
STATE_FLOWS = {
    AgentState.INITIALIZING: {AgentState.READY},
    AgentState.READY: {AgentState.PENDING_RESPONSE, AgentState.PENDING_TOOLS},
    AgentState.PENDING_RESPONSE: {AgentState.PROCESSING, AgentState.READY},
    AgentState.PENDING_TOOLS: {AgentState.PROCESSING, AgentState.READY},
    AgentState.PROCESSING: {
        AgentState.READY,
        AgentState.PENDING_RESPONSE,
        AgentState.PENDING_TOOLS,
    },
}


class AgentStateMachine:
    """Manages agent state transitions and validation."""

    def __init__(self, agent: Agent):
        """Initialize the state machine.

        Args:
            agent: The agent instance this state machine manages
        """
        self.agent = agent
        self._state: AgentState = AgentState.INITIALIZING
        self._ready_event: asyncio.Event = asyncio.Event()
        self._init_task: asyncio.Task | None = None

    @property
    def state(self) -> AgentState:
        """Get the current agent state.

        Returns:
            Current agent state
        """
        return self._state

    @property
    def is_ready(self) -> bool:
        """Check if agent is in READY state or higher.

        Returns:
            True if agent is ready for operations
        """
        return self._state >= AgentState.READY

    def update_state(self, state: AgentState) -> None:
        """Update the agent's state.

        Args:
            state: New state to set

        Raises:
            ValueError: If state transition is invalid
        """
        current_state = self._state

        # Validate state transition
        if state not in STATE_FLOWS[current_state]:
            raise ValueError(f"Invalid state transition from {current_state} to {state}")

        self._state = state

        # Set ready event when transitioning to READY or higher
        if state >= AgentState.READY and current_state < AgentState.READY:
            self._ready_event.set()

        # Emit state change event via agent
        from good_agent.events.agent import AgentEvents

        self.agent.do(
            AgentEvents.AGENT_STATE_CHANGE,
            agent=self.agent,
            new_state=state,
            old_state=current_state,
        )

    async def wait_for_ready(self, timeout: float = 10.0) -> None:
        """Wait until agent is ready.

        Args:
            timeout: Maximum seconds to wait for ready state

        Raises:
            TimeoutError: If agent doesn't become ready within timeout
        """
        if self._state >= AgentState.READY:
            return

        try:
            await asyncio.wait_for(self._ready_event.wait(), timeout=timeout)
        except TimeoutError as e:
            raise TimeoutError(
                f"Agent did not become ready within {timeout} seconds. Current state: {self._state}"
            ) from e
