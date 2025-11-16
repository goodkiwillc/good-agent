# Pytest Testing Approach for good-agent

## Philosophy

Good testing for the agent library requires testing **library functionality** (message management, tool execution, context handling) while **mocking only the LLM**. Everything else should run as it would in production.

### Key Principles

1. **Mock only the LLM, not the library** - Test real message history, tool calls, context management
2. **Fixtures should be data, not logic** - Store LLM responses, not test behavior
3. **Tests should read like documentation** - Clear, obvious, self-documenting
4. **Fast by default** - No LLM calls in standard test runs
5. **Easy to update** - Recording mode to capture real LLM responses

## Test Hierarchy

```
Unit Tests (0.1-1ms each)
├─ Message management (append, indexing, filtering)
├─ Tool registration (decorator, function, component)
├─ Context operations (set, get, scoped)
├─ Template rendering (variables, filters, functions)
└─ Component system (registration, initialization)

Integration Tests (1-10ms each)
├─ Conversation flows (multi-turn with tools)
├─ Tool execution chains (sequential, parallel)
├─ Multi-agent interactions (pipe operator)
├─ Stateful resources (EditableYAML, etc.)
└─ Error handling (tool failures, retries)

E2E Tests (100ms-1s each) - Optional/Recording Mode
├─ Real LLM calls for golden test generation
├─ Property validation with live models
└─ Regression detection
```

## Approach: Pytest Fixtures + LLM Response Mocking

### Core Testing Pattern

```python
# conftest.py
import pytest
from good_agent import Agent
from good_agent.testing import LLMResponseFixture

@pytest.fixture
def mock_llm():
    """Provides a mock LLM that returns queued responses."""
    return LLMResponseFixture()

@pytest.fixture
def agent(mock_llm):
    """Provides a test agent with mocked LLM."""
    agent = Agent("You are a helpful assistant")
    agent._inject_mock_llm(mock_llm)  # Inject at the LLM layer
    return agent
```

### Unit Test Example

```python
# tests/unit/test_message_management.py

@pytest.mark.unit
async def test_message_indexing(agent, mock_llm):
    """Test that message history supports indexing and role filtering."""

    # Mock LLM to return specific response
    mock_llm.queue_response("I can help with that!")

    # Interaction
    agent.append("Hello")
    result = await agent.call()

    # Test library functionality, not LLM output
    assert len(agent.messages) == 3  # system, user, assistant
    assert agent[-1].role == "assistant"
    assert agent.user[-1].content == "Hello"
    assert agent.assistant[-1].content == "I can help with that!"

    # No LLM was actually called
    assert mock_llm.call_count == 1
```

### Integration Test Example

```python
# tests/integration/test_tool_execution.py

@pytest.mark.integration
async def test_multi_turn_tool_calling(agent, mock_llm):
    """Test complete tool calling flow."""

    # Define test tool
    async def get_weather(city: str) -> str:
        return f"Weather in {city}: Sunny, 72°F"

    agent.tools.add(get_weather)

    # Queue responses
    mock_llm.queue_responses([
        # Turn 1: Agent decides to call tool
        {
            "content": "I'll check the weather for you",
            "tool_calls": [{"name": "get_weather", "arguments": {"city": "NYC"}}]
        },
        # Turn 2: Agent responds with result
        {
            "content": "The weather in NYC is sunny and 72°F!"
        }
    ])

    # Run interaction
    agent.append("What's the weather in NYC?")
    async for message in agent.execute():
        pass  # Let it run

    # Verify tool was called correctly
    assert agent.tools.was_called("get_weather")
    assert agent.tools.last_call("get_weather").args == {"city": "NYC"}

    # Verify final state
    assert "sunny" in agent.assistant[-1].content.lower()

    # Verify message sequence
    assert agent.messages[0].role == "system"
    assert agent.messages[1].role == "user"
    assert agent.messages[2].role == "assistant"  # Tool call
    assert agent.messages[2].tool_calls is not None
    assert agent.messages[3].role == "tool"
    assert agent.messages[4].role == "assistant"  # Final response
```

## Implementation: LLMResponseFixture

```python
# src/good_agent/testing/__init__.py

from dataclasses import dataclass
from typing import Any, Literal
from collections import deque

@dataclass
class MockLLMResponse:
    """A single mocked LLM response."""
    content: str | None = None
    tool_calls: list[dict] | None = None
    refusal: str | None = None
    reasoning: str | None = None

class LLMResponseFixture:
    """Mock LLM for testing that returns queued responses."""

    def __init__(self):
        self._responses: deque[MockLLMResponse] = deque()
        self.call_count = 0
        self.calls: list[dict] = []  # Record all calls

    def queue_response(
        self,
        content: str | None = None,
        *,
        tool_calls: list[dict] | None = None,
        refusal: str | None = None
    ):
        """Queue a single response."""
        self._responses.append(MockLLMResponse(
            content=content,
            tool_calls=tool_calls,
            refusal=refusal
        ))

    def queue_responses(self, responses: list[dict | str]):
        """Queue multiple responses."""
        for resp in responses:
            if isinstance(resp, str):
                self.queue_response(resp)
            else:
                self.queue_response(**resp)

    async def complete(self, messages: list[dict], **kwargs) -> Any:
        """Mock LLM completion call."""
        self.call_count += 1
        self.calls.append({
            "messages": messages,
            "kwargs": kwargs
        })

        if not self._responses:
            raise RuntimeError(
                f"No more mock responses available (called {self.call_count} times)"
            )

        response = self._responses.popleft()

        # Return mock in litellm format
        return self._create_litellm_response(response)

    def _create_litellm_response(self, response: MockLLMResponse):
        """Create a litellm-compatible response object."""
        from unittest.mock import MagicMock

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]

        choice = mock_response.choices[0]
        choice.message.content = response.content
        choice.message.refusal = response.refusal

        if response.tool_calls:
            choice.message.tool_calls = [
                self._create_tool_call(tc)
                for tc in response.tool_calls
            ]
        else:
            choice.message.tool_calls = None

        # Add usage
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        return mock_response

    def _create_tool_call(self, tc_dict: dict):
        """Create a tool call object."""
        from unittest.mock import MagicMock
        import json

        tc = MagicMock()
        tc.id = f"call_{self.call_count}"
        tc.function.name = tc_dict["name"]
        tc.function.arguments = json.dumps(tc_dict.get("arguments", {}))
        return tc
```

## Fixture Files: YAML Format

For more complex scenarios, store fixtures in YAML files:

```yaml
# tests/fixtures/weather_query.yaml
name: "weather_query_sunny_nyc"
description: "User asks about weather in NYC, gets sunny response"

responses:
  - content: "I'll check the weather for you"
    tool_calls:
      - name: get_weather
        arguments:
          city: "NYC"

  - content: "The weather in NYC is sunny and 72°F!"

# Optional: assertions to run
assertions:
  - tool_called: get_weather
  - tool_args: {city: "NYC"}
  - final_response_contains: "sunny"
```

### Loading Fixture Files

```python
# src/good_agent/testing/fixtures.py

import yaml
from pathlib import Path

class FixtureLoader:
    """Load test fixtures from YAML files."""

    @staticmethod
    def load(fixture_path: str | Path) -> LLMResponseFixture:
        """Load fixture from YAML file."""
        with open(fixture_path) as f:
            data = yaml.safe_load(f)

        fixture = LLMResponseFixture()
        fixture.queue_responses(data["responses"])

        # Store assertions for later verification
        fixture.assertions = data.get("assertions", [])

        return fixture

# Usage in tests
@pytest.fixture
def weather_fixture():
    return FixtureLoader.load("tests/fixtures/weather_query.yaml")

async def test_weather_query(agent, weather_fixture):
    agent._inject_mock_llm(weather_fixture)

    # Run test
    agent.append("What's the weather in NYC?")
    result = await agent.execute()

    # Verify assertions from fixture
    for assertion in weather_fixture.assertions:
        if "tool_called" in assertion:
            assert agent.tools.was_called(assertion["tool_called"])
        # ... other assertions
```

## Recording Mode: Capture Real LLM Responses

```python
# conftest.py

def pytest_addoption(parser):
    parser.addoption(
        "--record",
        action="store_true",
        help="Record LLM responses to fixture files"
    )
    parser.addoption(
        "--update-fixtures",
        action="store_true",
        help="Update existing fixture files with new responses"
    )

@pytest.fixture
def mock_llm(request):
    """
    Returns either a mock LLM (default) or real LLM (record mode).
    """
    if request.config.getoption("--record"):
        # Use real LLM and record responses
        return RecordingLLMFixture(
            output_dir="tests/fixtures/recordings"
        )
    else:
        # Use mock
        return LLMResponseFixture()
```

### RecordingLLMFixture

```python
# src/good_agent/testing/recording.py

class RecordingLLMFixture:
    """Real LLM that records responses to files."""

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.responses: list[dict] = []
        self.test_name: str | None = None

    async def complete(self, messages: list[dict], **kwargs):
        """Make real LLM call and record response."""
        from good_agent.model.llm import LanguageModel

        # Use real LLM
        llm = LanguageModel(**kwargs)
        response = await llm.complete(messages, **kwargs)

        # Extract and record response
        choice = response.choices[0]
        recorded = {
            "content": choice.message.content,
            "tool_calls": None
        }

        if choice.message.tool_calls:
            recorded["tool_calls"] = [
                {
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments)
                }
                for tc in choice.message.tool_calls
            ]

        self.responses.append(recorded)

        return response

    def save(self, test_name: str):
        """Save recorded responses to fixture file."""
        fixture_file = self.output_dir / f"{test_name}.yaml"

        data = {
            "name": test_name,
            "description": f"Recorded from test {test_name}",
            "responses": self.responses
        }

        with open(fixture_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False)

        print(f"✓ Recorded {len(self.responses)} responses to {fixture_file}")
```

### Using Recording Mode

```bash
# Record fixtures from tests
$ pytest tests/integration/test_weather.py --record

# Output:
# ✓ Recorded 2 responses to tests/fixtures/recordings/test_weather_query.yaml
# ✓ Recorded 3 responses to tests/fixtures/recordings/test_multi_city.yaml

# Now edit the YAML files if needed, then use them in normal test runs
$ pytest tests/integration/test_weather.py
# Uses recorded fixtures, no LLM calls
```

## Parametrized Tests with Fixtures

```python
# tests/integration/test_weather_variations.py

import pytest

@pytest.mark.parametrize("fixture_name,city,expected", [
    ("weather_nyc_sunny", "NYC", "sunny"),
    ("weather_la_cloudy", "LA", "cloudy"),
    ("weather_seattle_rainy", "Seattle", "rainy"),
])
async def test_weather_variations(agent, fixture_name, city, expected):
    """Test weather queries for different cities."""

    # Load specific fixture
    fixture = FixtureLoader.load(f"tests/fixtures/{fixture_name}.yaml")
    agent._inject_mock_llm(fixture)

    # Run
    agent.append(f"What's the weather in {city}?")
    result = await agent.call()

    # Verify
    assert expected in result.content.lower()
```

## Testing Complex Flows

### Multi-Agent Conversations

```python
# tests/integration/test_multi_agent.py

async def test_researcher_writer_conversation(mock_llm):
    """Test multi-agent pipe conversation."""

    # Set up fixtures for both agents
    researcher_responses = LLMResponseFixture()
    researcher_responses.queue_responses([
        "I found information about AI frameworks",
        "Here are my research findings: PyTorch, TensorFlow..."
    ])

    writer_responses = LLMResponseFixture()
    writer_responses.queue_responses([
        "I'll write a summary based on the research",
        "Summary: The top AI frameworks in 2025 are..."
    ])

    # Create agents
    researcher = Agent("Research assistant", name="Researcher")
    writer = Agent("Technical writer", name="Writer")

    # Inject mocks
    researcher._inject_mock_llm(researcher_responses)
    writer._inject_mock_llm(writer_responses)

    # Test conversation
    async with (researcher | writer) as conversation:
        researcher.append("Research AI frameworks", role="assistant")

        messages = []
        async for message in conversation.execute():
            messages.append((message.agent.name, message.content))

        # Verify both agents participated
        assert any(name == "Researcher" for name, _ in messages)
        assert any(name == "Writer" for name, _ in messages)
```

### Stateful Resources

```python
# tests/integration/test_stateful_resources.py

async def test_editable_yaml_resource(agent, mock_llm, tmp_path):
    """Test EditableYAML stateful resource."""

    from good_agent.resources import EditableYAML

    # Create test file
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
setting1: value1
options:
  - opt1
  - opt2
""")

    # Queue responses for file manipulation
    mock_llm.queue_responses([
        {
            "content": "I'll add the new setting",
            "tool_calls": [{"name": "yaml_update", "arguments": {"key": "setting2", "value": "value2"}}]
        },
        {
            "content": "Done! Added setting2"
        }
    ])

    # Test resource usage
    file = EditableYAML(str(config_file))

    async with file(agent, context_mode='full'):
        await agent.call("Add setting2 with value value2")
        await file.save(str(config_file))

    # Verify file was modified
    updated = yaml.safe_load(config_file.read_text())
    assert updated["setting2"] == "value2"
```

## Assertion Helpers

```python
# src/good_agent/testing/assertions.py

class AgentAssertions:
    """Helper assertions for agent testing."""

    def __init__(self, agent):
        self.agent = agent

    def assert_message_sequence(self, *roles):
        """Assert message roles in sequence."""
        actual = [m.role for m in self.agent.messages]
        assert actual == list(roles), \
            f"Expected {roles}, got {actual}"

    def assert_tool_called(self, tool_name: str, *, times: int | None = None):
        """Assert a tool was called."""
        calls = [
            msg for msg in self.agent.messages
            if msg.role == "assistant" and msg.tool_calls
            for tc in msg.tool_calls
            if tc.function.name == tool_name
        ]

        assert len(calls) > 0, f"Tool {tool_name} was not called"

        if times is not None:
            assert len(calls) == times, \
                f"Expected {tool_name} called {times} times, was {len(calls)}"

    def assert_tool_args(self, tool_name: str, **expected_args):
        """Assert last tool call had specific arguments."""
        # Find last call to this tool
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.function.name == tool_name:
                        actual_args = json.loads(tc.function.arguments)
                        for key, value in expected_args.items():
                            assert actual_args.get(key) == value, \
                                f"Expected {key}={value}, got {actual_args.get(key)}"
                        return

        raise AssertionError(f"Tool {tool_name} was not called")

    def assert_no_errors(self):
        """Assert no error messages in conversation."""
        for msg in self.agent.messages:
            if msg.role == "tool" and hasattr(msg, "error"):
                if msg.error:
                    raise AssertionError(f"Tool error: {msg.error}")

# Usage
async def test_with_assertions(agent, mock_llm):
    mock_llm.queue_response("I'll help", tool_calls=[{"name": "search", "arguments": {"q": "test"}}])

    await agent.call("Search for test")

    assertions = AgentAssertions(agent)
    assertions.assert_tool_called("search", times=1)
    assertions.assert_tool_args("search", q="test")
    assertions.assert_no_errors()
```

## Testing Template Rendering

```python
# tests/unit/test_templates.py

async def test_template_rendering_with_context():
    """Test template rendering with agent context."""

    from good_agent import Agent, Template

    agent = Agent("You are {{ role }}")
    agent.context.update(role="assistant", timestamp="2025-01-13")

    # Test system message rendering
    assert "You are assistant" in agent.messages[0].content

    # Test dynamic templates
    tmpl = Template("Current time: {{ timestamp }}")
    rendered = tmpl.render(**agent.context.as_dict())
    assert "2025-01-13" in rendered
```

## Pytest Configuration

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

markers =
    unit: Unit tests (fast, isolated)
    integration: Integration tests (multi-component)
    e2e: End-to-end tests (optional, with real LLM)
    slow: Slow tests (run less frequently)

# Async support
asyncio_mode = auto

# Coverage
addopts =
    --cov=good_agent
    --cov-report=html
    --cov-report=term-missing
    --strict-markers
    -v

# Test output
console_output_style = progress
```

## Example Test Suite Structure

```
tests/
├── conftest.py                 # Shared fixtures
├── fixtures/                   # YAML fixture files
│   ├── weather_nyc_sunny.yaml
│   ├── weather_error.yaml
│   └── multi_turn_tools.yaml
│
├── unit/                       # Fast, isolated tests
│   ├── test_messages.py        # Message management
│   ├── test_context.py         # Context operations
│   ├── test_tools.py           # Tool registration
│   ├── test_templates.py       # Template rendering
│   └── test_components.py      # Component system
│
├── integration/                # Multi-component tests
│   ├── test_tool_execution.py  # Tool calling flows
│   ├── test_multi_agent.py     # Agent conversations
│   ├── test_streaming.py       # Streaming responses
│   ├── test_resources.py       # Stateful resources
│   └── test_error_handling.py  # Error scenarios
│
└── e2e/                        # Optional real LLM tests
    └── test_regression.py      # Regression detection
```

## Running Tests

```bash
# Run all unit tests (fast)
$ pytest -m unit

# Run all tests (unit + integration)
$ pytest

# Run with coverage
$ pytest --cov=good_agent --cov-report=html

# Run specific test file
$ pytest tests/integration/test_tool_execution.py

# Run with real LLM (recording mode)
$ pytest --record tests/integration/test_weather.py

# Run only tests that touch a specific module
$ pytest --co tests/unit/test_tools.py

# Verbose output
$ pytest -vv

# Stop on first failure
$ pytest -x

# Run tests matching pattern
$ pytest -k "weather"
```

## Best Practices

### 1. One Fixture Per Scenario

```python
# Good: Specific fixture for specific scenario
@pytest.fixture
def weather_sunny_nyc():
    fixture = LLMResponseFixture()
    fixture.queue_responses([
        {"content": "I'll check", "tool_calls": [{"name": "weather", "arguments": {"city": "NYC"}}]},
        {"content": "It's sunny!"}
    ])
    return fixture

# Avoid: Generic fixture used for everything
@pytest.fixture
def generic_responses():
    return LLMResponseFixture()  # Forces manual setup in each test
```

### 2. Test Library Behavior, Not LLM Content

```python
# Good: Test that library correctly handles responses
async def test_tool_calling(agent, mock_llm):
    mock_llm.queue_response("I'll help", tool_calls=[{"name": "search", "arguments": {}}])

    result = await agent.call("Search for X")

    # Test library functionality
    assert len(agent.messages) == 3
    assert agent.messages[1].tool_calls is not None
    assert agent.tools.was_called("search")

# Avoid: Testing exact LLM output
async def test_tool_calling_bad(agent, mock_llm):
    mock_llm.queue_response("I'll help")

    result = await agent.call("Search for X")

    assert result.content == "I'll help"  # Brittle, tests mock not library
```

### 3. Use Descriptive Test Names

```python
# Good
async def test_tool_execution_records_message_in_history():
    ...

async def test_parallel_tool_calls_execute_concurrently():
    ...

# Avoid
async def test_tools():
    ...

async def test_case_1():
    ...
```

### 4. Keep Tests Focused

```python
# Good: One concept per test
async def test_message_indexing_supports_negative_indices():
    agent = Agent("You are helpful")
    agent.append("Hello")
    assert agent[-1].content == "Hello"

async def test_message_indexing_supports_role_filtering():
    agent = Agent("You are helpful")
    agent.append("Hello")
    assert agent.user[-1].content == "Hello"

# Avoid: Testing multiple things
async def test_message_operations():
    agent = Agent("You are helpful")
    agent.append("Hello")
    assert agent[-1].content == "Hello"
    assert agent.user[-1].content == "Hello"
    assert len(agent.messages) == 2
    # ... 20 more assertions
```

### 5. Use Fixture Files for Complex Scenarios

```python
# Good: Complex multi-turn flows in YAML
async def test_complex_workflow(agent):
    fixture = FixtureLoader.load("fixtures/complex_workflow.yaml")
    agent._inject_mock_llm(fixture)
    # Test runs with clear fixture

# Avoid: Complex setup in test code
async def test_complex_workflow(agent, mock_llm):
    mock_llm.queue_response(...)
    mock_llm.queue_response(...)
    mock_llm.queue_response(...)
    # 50 lines of setup
```

## Summary

This approach provides:

✅ **Fast tests** - No LLM calls by default
✅ **Isolated tests** - Mock only LLM, test real library behavior
✅ **Easy to write** - Simple fixture API
✅ **Easy to maintain** - Recording mode captures real responses
✅ **Good coverage** - Test units and integration
✅ **Documentation** - Tests read like examples
✅ **Flexible** - Can use real LLM when needed

The key insight: **Test the library, mock the LLM**. All the complexity (message management, tool execution, context handling) is library code that should be tested with real implementations, not mocks.
