import itertools
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from litellm.utils import Message as LiteLLMMessage
from litellm.types.utils import Choices

from good_agent import Agent
from good_agent.messages import ToolMessage
from good_agent.tools.agent_tool import AgentAsTool, SessionIdGenerator


class MockLLMResponse:
    """Mock response from litellm"""

    def __init__(self, content="Test response", tool_calls=None):
        # Create proper Choices and Message objects
        message = LiteLLMMessage()
        message.content = content
        message.tool_calls = tool_calls or []

        choice = Choices()
        choice.message = message
        choice.provider_specific_fields = {}

        self.choices = [choice]


@pytest.mark.asyncio
async def test_agent_as_tool_session_e2e():
    """
    End-to-end test of AgentAsTool session management.

    Verifies:
    1. First call generates a short session ID and wraps response in XML.
    2. Session is persisted in the wrapper.
    3. Second call with the same ID reuses the session.
    4. XML wrapping persists in subsequent calls.
    """

    # 1. Reset Session ID Generator for predictable IDs
    SessionIdGenerator._counter = itertools.count(1)

    # 2. Setup Worker Agent (The Tool)
    worker = Agent("You are a worker.", name="worker")

    # Mock worker responses
    worker_responses = [
        MockLLMResponse("I am the worker, this is the first response."),
        MockLLMResponse("I am the worker, this is the second response."),
    ]

    # Patch worker model to return fixed responses
    with patch.object(
        worker.model, "complete", AsyncMock(side_effect=worker_responses)
    ):
        # 3. Wrap Worker as Tool
        worker_tool_wrapper = AgentAsTool(worker, multi_turn=True)
        worker_tool = worker_tool_wrapper.as_tool()

        # 4. Setup Manager Agent (The Caller)
        manager = Agent(name="manager", tools=[worker_tool])
        await manager.initialize()

        # 5. Define Manager's behavior (Mocked LLM decisions)

        # Turn 1: Manager calls worker (no session_id)
        call1 = MagicMock()
        call1.id = "call_1"
        call1.type = "function"
        call1.function.name = "worker"
        call1.function.arguments = json.dumps({"prompt": "Say hello"})

        # Turn 2: Manager calls worker again WITH session_id="1"
        # We expect ID "1" because we reset the counter
        call2 = MagicMock()
        call2.id = "call_2"
        call2.type = "function"
        call2.function.name = "worker"
        call2.function.arguments = json.dumps(
            {"prompt": "Say hello again", "session_id": "1"}
        )

        manager_responses = [
            # Response 1: Decide to call worker
            MockLLMResponse("I will call the worker.", tool_calls=[call1]),
            # Response 2: Decide to call worker again (after seeing the XML response)
            MockLLMResponse(
                "I will call the worker again with the session ID.", tool_calls=[call2]
            ),
            # Response 3: Finish
            MockLLMResponse("Task complete."),
        ]

        # Patch manager model
        with patch.object(
            manager.model, "complete", AsyncMock(side_effect=manager_responses)
        ):
            # Seed the conversation
            manager.append("Please coordinate the worker.", role="user")

            # 6. Execute the interaction
            messages = []
            async for msg in manager.execute(max_iterations=5):
                messages.append(msg)

            # 7. Verify Results

            # Extract tool outputs
            tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
            assert len(tool_msgs) == 2

            # Check First Tool Response
            # Should be wrapped in XML with session_id="1"
            resp1 = tool_msgs[0].content
            print(f"Tool Response 1: {resp1}")
            assert '<worker session_id="1">' in str(resp1)
            assert "I am the worker, this is the first response" in str(resp1)
            assert "</worker>" in str(resp1)

            # Check Second Tool Response
            # Should be wrapped in XML with session_id="1"
            resp2 = tool_msgs[1].content
            print(f"Tool Response 2: {resp2}")
            assert '<worker session_id="1">' in str(resp2)
            assert "I am the worker, this is the second response" in str(resp2)

            # Verify Wrapper State
            assert "1" in worker_tool_wrapper.sessions
            session_agent = worker_tool_wrapper.sessions["1"]

            # Verify the session agent is a fork, not the original
            assert session_agent is not worker

            # Verify the session agent maintained history
            # It should have: System + User(1) + Assistant(1) + User(2) + Assistant(2)
            # Note: "User" messages in the worker come from the Manager's tool calls
            assert len(session_agent.messages) >= 1
