import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from box import Box
from good_agent import Agent
from good_agent.resources import EditableYAML


class MockLLMResponse:
    """Minimal mock of litellm response for Agent.call() integration"""

    def __init__(self, content: str, tool_calls=None):
        from litellm import Choices
        from litellm import Message as LiteLLMMessage

        message = LiteLLMMessage()
        message.content = content
        message.tool_calls = tool_calls or []

        choice = Choices()
        choice.message = message
        choice.provider_specific_fields = {}

        self.choices = [choice]


@pytest.mark.asyncio
async def test_resource_tools_edit_state_via_invoke():
    """EditableYAML integrates with Agent tools and edits Box state via direct invoke."""
    initial = """
    a:
      b: 1
    arr:
      - x
    """

    res = EditableYAML(initial, name="cfg")
    agent = Agent("You are a YAML editor")
    await agent.initialize()

    async with res(agent):
        available = list(agent.tools.keys())
        assert "read" in available and "set" in available and "get" in available

        r = await agent.tool_calls.invoke("set", path="a.c", value={"d": 2})
        assert r.success and r.response == "ok"

        assert isinstance(res.state, Box)
        assert res.state.a.c.d == 2

        g = await agent.tool_calls.invoke("get", path="a")
        assert "b: 1" in g.response
        assert "c:\n  d: 2" in g.response or "c:\n    d: 2" in g.response

        pr = await agent.tool_calls.invoke(
            "patch",
            ops=[{"op": "merge", "path": "a", "value": {"e": 3}}],
        )
        assert pr.success and pr.response["ok"] is True
        assert res.state.a.e == 3


@pytest.mark.asyncio
async def test_llm_tool_call_edits_resource_state():
    """Agent.call() executes tool call (mocked LLM) that edits EditableYAML state."""
    initial = """
    info:
      name: demo
    """

    res = EditableYAML(initial, name="cfg")
    agent = Agent("You can edit YAML using tools.")
    await agent.initialize()

    async with res(agent):
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_set_1"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "set"
        mock_tool_call.function.arguments = json.dumps(
            {
                "path": "meta.version",
                "value": "2.0",
                "create_missing": True,
                "strategy": "assign",
            }
        )

        responses = [
            MockLLMResponse("I'll update the version.", tool_calls=[mock_tool_call]),
            MockLLMResponse("Updated version to 2.0."),
        ]

        with patch.object(agent.model, "complete", AsyncMock(side_effect=responses)):
            final = await agent.call("Please set meta.version to 2.0")
            assert "Updated" in final.content

        assert isinstance(res.state, Box)
        assert res.state.meta.version == "2.0"
