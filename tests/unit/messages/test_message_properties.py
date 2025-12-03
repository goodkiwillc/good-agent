import weakref
from collections import ChainMap
from typing import cast

import pytest
from good_agent.agent import Agent
from good_agent.content import TextContentPart
from good_agent.messages import (
    AssistantMessage,
    AssistantMessageStructuredOutput,
    Message,
    ToolMessage,
    UserMessage,
)
from pydantic import BaseModel


class DummyAgent:
    """Mock agent for testing message properties"""

    def __init__(self):
        self.messages = []
        # Create a mock context object with _chainmap attribute
        self.context = type(
            "MockContext",
            (),
            {
                "_chainmap": ChainMap({}),
                "get": lambda self, key, default=None: self._chainmap.get(key, default),
                "as_dict": lambda self: dict(self._chainmap),
            },
        )()

    def do(self, event_name, **kwargs):
        """Mock do method for event firing"""
        pass

    def apply_sync(self, event_name, **kwargs):
        """Mock apply_sync method for event chains"""
        # Return a mock result with the output
        return type("ChainResult", (), {"output": kwargs.get("output", "")})()


class TestMessageProperties:
    """Test the execution context properties of messages"""

    def test_private_attributes_initialization(self):
        """Test that private attributes are initialized correctly"""
        msg = UserMessage(content="Hello")

        # Check defaults
        assert msg.ok is True
        assert msg.attempt == 1
        assert msg.retry is False
        assert msg.last_attempt is False
        assert msg.i == 0  # Property returns 0 when _i is None
        assert msg.agent is None

    def test_private_attributes_custom_values(self):
        """Test setting custom values for private attributes"""
        msg = UserMessage(content="Hello", ok=False, attempt=3, retry=True, last_attempt=True, i=5)

        assert msg.ok is False
        assert msg.attempt == 3
        assert msg.retry is True
        assert msg.last_attempt is True
        assert msg.i == 5

    def test_attempt_validation(self):
        """Test that attempt number must be positive"""
        with pytest.raises(ValueError, match="Attempt number must be >= 1"):
            UserMessage(content="Hello", attempt=0)

        with pytest.raises(ValueError, match="Attempt number must be >= 1"):
            UserMessage(content="Hello", attempt=-1)

    def test_agent_reference(self):
        """Test weak reference to agent"""
        agent = DummyAgent()
        msg = UserMessage(content="Hello")

        # Set agent reference
        msg._set_agent(cast(Agent, agent))
        assert msg.agent is agent

        # Test weak reference behavior
        agent_ref = weakref.ref(agent)
        assert agent_ref() is agent

        # Delete agent and check reference is None
        del agent
        assert msg.agent is None

    def test_index_property(self):
        """Test dynamic index property"""
        agent = DummyAgent()
        msg1 = UserMessage(content="First")
        msg2 = AssistantMessage(content="Second")
        msg3 = UserMessage(content="Third")

        # Add messages to agent
        agent.messages.extend([msg1, msg2, msg3])

        # Set agent references
        msg1._set_agent(cast(Agent, agent))
        msg2._set_agent(cast(Agent, agent))
        msg3._set_agent(cast(Agent, agent))

        # Check indices
        assert msg1.index == 0
        assert msg2.index == 1
        assert msg3.index == 2

        # Test message not in list
        msg4 = UserMessage(content="Not in list")
        msg4._set_agent(cast(Agent, agent))
        with pytest.raises(ValueError, match="Message not attached to agent"):
            _ = msg4.index

    def test_index_without_agent(self):
        """Test index property without agent reference"""
        msg = UserMessage(content="Hello")
        with pytest.raises(ValueError, match="Message not attached to agent"):
            _ = msg.index

    def test_pattern_matching_attributes(self):
        """Test that __match_args__ includes all necessary attributes"""
        expected_attrs = (
            "role",
            "content",
            "tool_response",
            "output",
            "i",
            "ok",
            "index",
            "attempt",
            "retry",
            "last_attempt",
            "agent",
        )
        assert Message.__match_args__ == expected_attrs

    def test_tool_message_properties(self):
        """Test ToolMessage with tool_response"""
        from good_agent.tools import ToolResponse

        tool_resp = ToolResponse(
            tool_name="calculator", tool_call_id="123", response="42", success=True
        )

        msg = ToolMessage(
            content="42",
            tool_call_id="123",
            tool_name="calculator",
            tool_response=tool_resp,
            ok=True,
            attempt=1,
        )

        assert msg.tool_response is tool_resp
        assert msg.ok is True

    def test_structured_output_message(self):
        """Test AssistantMessageStructuredOutput with typed output"""

        class WeatherResponse(BaseModel):
            location: str
            temperature: float
            condition: str

        weather = WeatherResponse(location="New York", temperature=25.0, condition="sunny")

        msg = AssistantMessageStructuredOutput[WeatherResponse](
            content_parts=[TextContentPart(text="The weather in New York is 25.0°C with sunny.")],
            output=weather,
        )

        assert msg.output is weather
        assert isinstance(msg.output, WeatherResponse)
        assert msg.output.location == "New York"

    def test_context_and_raw_content(self):
        """Test context and raw content properties"""
        msg = UserMessage(
            content="Hello {{name}}",
            raw_content="Hello {{name}}",
            context={"name": "World"},
        )

        assert msg.raw_content == "Hello {{name}}"
        assert msg.context == {"name": "World"}
        # Note: Template rendering is not yet implemented
        # When implemented, msg.content should return "Hello World"
