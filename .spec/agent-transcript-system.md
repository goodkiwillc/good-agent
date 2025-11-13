# Agent Transcript System Specification

## Overview

The Agent Transcript System is a comprehensive testing and debugging framework for the good-agent library that enables recording, replaying, and manually creating deterministic agent execution traces.

Unlike simple HTTP mocking (VCR.py) or basic LLM response queuing, this system captures the full complexity of good-agent's architecture including:
- Dynamic context management (state external to chat history)
- Message visibility and transformation
- Multi-agent conversations and agent-as-tool patterns
- Tool execution with state changes
- Structured outputs
- Message store vs. visible messages distinction

## Motivation

### Current Limitations

The existing mock system (`agent.mock()`) has several limitations:
1. **Response-only mocking**: Only mocks LLM responses, not full execution context
2. **No state capture**: Doesn't capture agent context, message visibility, or state changes
3. **No reusability**: Can't save/load mock scenarios for reuse
4. **Limited testing modes**: Only supports strict replay, not property-based or behavior testing
5. **Manual creation difficulty**: Hard to manually construct realistic test scenarios

### Goals

1. **Comprehensive recording**: Capture everything about an agent execution
2. **Flexible replay**: Support strict, mocked-tools, and property-based testing modes
3. **Human-friendly format**: YAML format that's readable and hand-editable
4. **LLM-assisted generation**: Use LLMs to generate test scenarios from descriptions
5. **Efficient storage**: Deduplicate messages and use references to avoid bloat
6. **Integration with good-agent**: Leverage events, components, and message store

## Architecture

### Three-Layer Capture Model

The transcript system captures three distinct layers of agent execution:

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Agent State                            │
│ - Context variables                             │
│ - Configuration                                 │
│ - Hidden/external state                         │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Layer 2: Message Flow                           │
│ - Full message store (all messages)             │
│ - Message visibility (what's shown)             │
│ - Message transformations                       │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│ Layer 3: LLM Interactions                       │
│ - Actual messages sent to LLM                   │
│ - Raw LLM responses                             │
│ - Tool executions                               │
└─────────────────────────────────────────────────┘
```

### Component Architecture

```
good_agent.transcripts/
├── TranscriptRecorder     # Records execution → transcript file
├── TranscriptReplayer     # Replays transcript → deterministic execution
├── TranscriptBuilder      # Manual/programmatic transcript creation
└── TranscriptGenerator    # LLM-based transcript generation
```

## File Structure

```
src/good_agent/
├── transcripts/
│   ├── __init__.py           # Public API exports
│   ├── recording.py          # TranscriptRecorder component
│   ├── replay.py             # TranscriptReplayer and replay modes
│   ├── builder.py            # TranscriptBuilder fluent API
│   ├── generators.py         # LLM-based generation
│   ├── storage.py            # Serialization/deserialization
│   └── parsers.py            # Human-friendly format parsers
└── mock.py                   # DEPRECATED - replaced by transcripts

tests/
└── transcripts/
    ├── examples/             # Example transcripts for reference
    │   ├── simple_chat.yaml
    │   ├── multi_agent.yaml
    │   ├── tool_calling.yaml
    │   └── context_management.yaml
    └── test_transcript_system.py
```

## Transcript Format Specification

### Version 1.0 YAML Format

```yaml
# File: transcripts/example.transcript.yaml
version: "1.0"

# Metadata about this transcript
metadata:
  name: "weather_query_with_tools"
  description: "User asks about weather, agent calls tool, responds"
  created: "2025-01-13T10:30:00Z"
  author: "developer"  # or "llm-generated"
  tags: ["weather", "tool-calling", "single-turn"]

# Agent configuration at start of execution
agent_config:
  model: "gpt-4"
  temperature: 0.7
  max_tokens: 1000
  tools: ["weather", "search"]

  # Agent-specific config
  context:
    user_name: "Alice"
    location: "NYC"
    session_id: "abc123"

# State before execution begins
initial_state:
  # Context variables
  context:
    custom_var: "value"
    conversation_count: 0

  # Messages in the message store
  message_store:
    - id: msg_001
      ulid: "01HQXXX..."  # Full ULID for reference
      role: "system"
      content: "You are a helpful assistant"
      visible: true
      metadata: {}

    - id: msg_002
      ulid: "01HQYYY..."
      role: "user"
      content: "What's the weather in NYC?"
      visible: true

# Execution trace - sequential turns
execution:
  # Turn 1: LLM processes initial messages
  - turn: 1
    type: "llm_call"
    timestamp: "2025-01-13T10:30:01Z"

    # What messages were sent to the LLM
    # (after any filtering/transformation by good-agent)
    messages_sent_to_llm:
      - ref: msg_001
      - ref: msg_002

    # Configuration used for this call
    llm_config:
      model: "gpt-4"
      temperature: 0.7

    # Raw LLM response (as returned by litellm)
    llm_response:
      role: "assistant"
      content: "I'll check the weather for you in NYC."
      tool_calls:
        - id: call_abc123
          function:
            name: "weather"
            arguments: '{"location": "NYC"}'

      # Optional metadata
      usage:
        prompt_tokens: 45
        completion_tokens: 12
        total_tokens: 57

      refusal: null
      reasoning: null

    # Message created in store from this response
    message_created:
      id: msg_003
      ulid: "01HQZZZ..."
      role: "assistant"
      content: "I'll check the weather for you in NYC."
      tool_calls:
        - id: call_abc123
          function:
            name: "weather"
            arguments: {"location": "NYC"}
      visible: true

    # State changes during this turn
    state_changes:
      context:
        conversation_count: 1
        last_action: "weather_requested"

  # Turn 2: Tool execution
  - turn: 2
    type: "tool_call"
    timestamp: "2025-01-13T10:30:02Z"

    tool_call:
      id: call_abc123
      tool_name: "weather"
      parameters:
        location: "NYC"

      # Tool execution result
      result:
        temperature: 72
        condition: "sunny"
        humidity: 65

      # Whether tool succeeded
      success: true
      error: null

    # Message created from tool result
    message_created:
      id: msg_004
      ulid: "01HQ000..."
      role: "tool"
      tool_call_id: call_abc123
      tool_name: "weather"
      content: '{"temperature": 72, "condition": "sunny", "humidity": 65}'
      tool_response:
        tool_name: "weather"
        tool_call_id: call_abc123
        response: {temperature: 72, condition: "sunny", humidity: 65}
        parameters: {location: "NYC"}
        success: true
      visible: true

  # Turn 3: LLM processes tool result
  - turn: 3
    type: "llm_call"
    timestamp: "2025-01-13T10:30:03Z"

    messages_sent_to_llm:
      - ref: msg_001
      - ref: msg_002
      - ref: msg_003
      - ref: msg_004

    llm_response:
      role: "assistant"
      content: "It's currently 72°F and sunny in NYC, with 65% humidity. Perfect weather!"
      tool_calls: null

    message_created:
      id: msg_005
      ulid: "01HQ111..."
      role: "assistant"
      content: "It's currently 72°F and sunny in NYC, with 65% humidity. Perfect weather!"
      visible: true

    state_changes:
      context:
        last_action: "weather_reported"
        conversation_count: 2

# Final state after execution
final_state:
  context:
    custom_var: "value"
    conversation_count: 2
    last_action: "weather_reported"

  # All messages in store
  message_store:
    - ref: msg_001
    - ref: msg_002
    - ref: msg_003
    - ref: msg_004
    - ref: msg_005

  # Which messages are visible
  visible_messages: [msg_001, msg_002, msg_003, msg_004, msg_005]

  # Final assertions/expectations
  assertions:
    - type: "contains"
      message: msg_005
      pattern: "72°F"
    - type: "tool_called"
      tool: "weather"
      parameters: {location: "NYC"}
    - type: "context_value"
      key: "conversation_count"
      value: 2
```

### Compact Human-Friendly Format

For manual creation, support a more compact format:

```yaml
# transcripts/simple.yaml
name: simple_greeting

# Shorthand for messages
messages:
  - "system: You are helpful"
  - "user: Hello!"
  - "assistant: Hi there! How can I help?"

# That's it! System expands this automatically
```

With tool calls:

```yaml
name: weather_query

messages:
  - "system: You are helpful"
  - "user: What's the weather?"
  - "assistant:call weather(location='NYC')"  # Tool call shorthand
  - "tool:weather: {temp: 72, condition: 'sunny'}"  # Tool result
  - "assistant: It's 72°F and sunny!"
```

## Implementation Details

### 1. TranscriptRecorder Component

```python
# src/good_agent/transcripts/recording.py
from pathlib import Path
from typing import Any
import yaml
from ulid import ULID

from good_agent.components import AgentComponent
from good_agent.events import AgentEvents

class TranscriptRecorder(AgentComponent):
    """Records agent execution to a transcript file.

    Hooks into agent events to capture:
    - Initial state (context, config, messages)
    - LLM calls (input/output)
    - Tool executions
    - State changes
    - Final state

    Usage:
        recorder = TranscriptRecorder("transcripts/my_test.yaml")
        agent.extensions.add(recorder)
        await agent.call("Hello!")
        # Transcript automatically saved
    """

    def __init__(
        self,
        output_path: Path | str,
        *,
        include_ulids: bool = True,
        compact: bool = False
    ):
        """Initialize recorder.

        Args:
            output_path: Where to save transcript
            include_ulids: Include full ULIDs in output (for debugging)
            compact: Use compact format (omit optional fields)
        """
        self.output_path = Path(output_path)
        self.include_ulids = include_ulids
        self.compact = compact

        self.transcript: dict[str, Any] = {
            "version": "1.0",
            "metadata": {},
            "agent_config": {},
            "initial_state": {},
            "execution": [],
            "final_state": {}
        }

        self.turn_counter = 0
        self.message_refs: dict[str, str] = {}  # ULID -> short_id
        self.current_turn: dict[str, Any] | None = None

    def on_agent_initialize(self, event_data):
        """Capture agent configuration when initialized."""
        agent = event_data["agent"]

        self.transcript["metadata"] = {
            "name": self.output_path.stem,
            "created": datetime.utcnow().isoformat() + "Z",
            "author": "recorder"
        }

        self.transcript["agent_config"] = {
            "model": agent.config.get("model"),
            "temperature": agent.config.get("temperature"),
            "max_tokens": agent.config.get("max_tokens"),
            "tools": [tool.name for tool in agent.tools.all()],
            "context": agent.context.as_dict()
        }

    def on_agent_ready(self, event_data):
        """Capture initial state when agent is ready."""
        agent = event_data["agent"]

        self.transcript["initial_state"] = {
            "context": agent.context.as_dict(),
            "message_store": [
                self._serialize_message(msg)
                for msg in agent.messages.all()
            ]
        }

    def on_llm_complete_before(self, event_data):
        """Record LLM call before execution."""
        self.turn_counter += 1

        messages = event_data["messages"]
        config = event_data["config"]

        self.current_turn = {
            "turn": self.turn_counter,
            "type": "llm_call",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "messages_sent_to_llm": [
                {"ref": self._get_message_ref(msg)}
                for msg in messages
            ],
            "llm_config": {
                "model": config.get("model"),
                "temperature": config.get("temperature")
            }
        }

    def on_llm_complete_after(self, event_data):
        """Record LLM response after execution."""
        response = event_data["response"]

        choice = response.choices[0]

        llm_response = {
            "role": "assistant",
            "content": choice.message.content,
            "tool_calls": None
        }

        # Add tool calls if present
        if choice.message.tool_calls:
            llm_response["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in choice.message.tool_calls
            ]

        # Add usage if not compact
        if not self.compact and hasattr(response, "usage"):
            llm_response["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }

        self.current_turn["llm_response"] = llm_response
        self.transcript["execution"].append(self.current_turn)
        self.current_turn = None

    def on_message_created(self, event_data):
        """Record when a message is created."""
        message = event_data["message"]

        # Add message_created to current turn
        if self.current_turn:
            self.current_turn["message_created"] = self._serialize_message(message)

    def on_tool_call_before(self, event_data):
        """Record tool call before execution."""
        self.turn_counter += 1

        tool_call = event_data["tool_call"]

        self.current_turn = {
            "turn": self.turn_counter,
            "type": "tool_call",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_call": {
                "id": tool_call.id,
                "tool_name": tool_call.function.name,
                "parameters": json.loads(tool_call.function.arguments)
            }
        }

    def on_tool_call_after(self, event_data):
        """Record tool result after execution."""
        tool_response = event_data["tool_response"]

        self.current_turn["tool_call"]["result"] = tool_response.response
        self.current_turn["tool_call"]["success"] = tool_response.success
        self.current_turn["tool_call"]["error"] = tool_response.error

        self.transcript["execution"].append(self.current_turn)
        self.current_turn = None

    def on_context_changed(self, event_data):
        """Record context changes."""
        if self.current_turn:
            if "state_changes" not in self.current_turn:
                self.current_turn["state_changes"] = {}

            self.current_turn["state_changes"]["context"] = event_data["context"]

    def on_agent_complete(self, event_data):
        """Capture final state and write transcript."""
        agent = event_data["agent"]

        self.transcript["final_state"] = {
            "context": agent.context.as_dict(),
            "message_store": [
                {"ref": self._get_message_ref_by_id(msg.id)}
                for msg in agent.messages.all()
            ],
            "visible_messages": [
                {"ref": self._get_message_ref_by_id(msg.id)}
                for msg in agent.messages.visible()
            ]
        }

        # Write to file
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w') as f:
            yaml.dump(
                self.transcript,
                f,
                default_flow_style=False,
                sort_keys=False
            )

    def _serialize_message(self, message) -> dict[str, Any]:
        """Serialize a message for the transcript."""
        msg_id = str(message.id)

        # Create short reference if not exists
        if msg_id not in self.message_refs:
            self.message_refs[msg_id] = f"msg_{len(self.message_refs)+1:03d}"

        serialized = {
            "id": self.message_refs[msg_id],
            "role": message.role,
            "content": message.render(mode="llm"),
            "visible": True  # TODO: Track actual visibility
        }

        if self.include_ulids:
            serialized["ulid"] = msg_id

        # Add tool calls if present
        if hasattr(message, "tool_calls") and message.tool_calls:
            serialized["tool_calls"] = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments)
                    }
                }
                for tc in message.tool_calls
            ]

        # Add tool response if present
        if hasattr(message, "tool_response") and message.tool_response:
            tr = message.tool_response
            serialized["tool_response"] = {
                "tool_name": tr.tool_name,
                "tool_call_id": tr.tool_call_id,
                "response": tr.response,
                "parameters": tr.parameters,
                "success": tr.success
            }

        return serialized

    def _get_message_ref(self, message_dict: dict) -> str:
        """Get short reference for a message dict."""
        # Extract ID from message dict
        # This is tricky because messages_sent_to_llm are dicts
        # We need to track which message dict corresponds to which stored message
        # For now, use a simple approach
        return "msg_xxx"  # TODO: Implement properly

    def _get_message_ref_by_id(self, ulid: ULID) -> str:
        """Get short reference for a message by ULID."""
        msg_id = str(ulid)
        return self.message_refs.get(msg_id, msg_id)
```

### 2. TranscriptReplayer

```python
# src/good_agent/transcripts/replay.py
from pathlib import Path
from typing import Any
import yaml

from good_agent.mock import MockResponse, mock_message, mock_tool_call

class TranscriptReplayer:
    """Replays a transcript for deterministic testing.

    Supports multiple replay modes:
    - strict: Agent must follow exact same path
    - mocked_tools: Real LLM but mocked tool responses
    - property_based: Only check high-level behaviors

    Usage:
        replayer = TranscriptReplayer("transcripts/my_test.yaml")

        # Strict replay
        with replayer.mock_agent(agent):
            result = await agent.call("Hello!")

        # Property-based testing
        with replayer.assert_properties() as checker:
            result = await agent.call("Hello!")
            checker.assert_tool_called("weather")
    """

    def __init__(self, transcript_path: Path | str):
        self.transcript_path = Path(transcript_path)

        with open(self.transcript_path) as f:
            self.transcript = yaml.safe_load(f)

        self.llm_responses: list[MockResponse] = []
        self.tool_responses: dict[str, Any] = {}

        self._prepare_responses()

    def _prepare_responses(self):
        """Extract LLM and tool responses from transcript."""
        for turn in self.transcript["execution"]:
            if turn["type"] == "llm_call":
                llm_resp = turn["llm_response"]

                # Convert to MockResponse
                tool_calls = None
                if llm_resp.get("tool_calls"):
                    tool_calls = [
                        (tc["function"]["name"],
                         json.loads(tc["function"]["arguments"])
                         if isinstance(tc["function"]["arguments"], str)
                         else tc["function"]["arguments"])
                        for tc in llm_resp["tool_calls"]
                    ]

                mock_resp = mock_message(
                    content=llm_resp.get("content", ""),
                    role="assistant",
                    tool_calls=tool_calls
                )

                self.llm_responses.append(mock_resp)

            elif turn["type"] == "tool_call":
                tool_call = turn["tool_call"]
                self.tool_responses[tool_call["id"]] = tool_call["result"]

    def mock_agent(self, agent):
        """Create a mock agent that replays the transcript.

        Returns a context manager that replaces the agent's LLM
        with queued responses from the transcript.
        """
        return agent.mock(*self.llm_responses)

    def assert_properties(self):
        """Create a property checker for high-level behavior testing."""
        return PropertyChecker(self.transcript)

    def get_expected_config(self) -> dict:
        """Get the agent config from the transcript."""
        return self.transcript["agent_config"]

    def get_initial_context(self) -> dict:
        """Get the initial context from the transcript."""
        return self.transcript["initial_state"]["context"]

    def get_expected_tool_calls(self) -> list[dict]:
        """Get all tool calls from the transcript."""
        return [
            turn["tool_call"]
            for turn in self.transcript["execution"]
            if turn["type"] == "tool_call"
        ]


class PropertyChecker:
    """Checks high-level properties of agent execution."""

    def __init__(self, transcript: dict):
        self.transcript = transcript
        self.actual_tool_calls: list[dict] = []
        self.actual_messages: list[Any] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def assert_tool_called(self, tool_name: str):
        """Assert that a tool was called."""
        expected_calls = [
            turn for turn in self.transcript["execution"]
            if turn["type"] == "tool_call"
            and turn["tool_call"]["tool_name"] == tool_name
        ]
        assert len(expected_calls) > 0, f"Tool {tool_name} was not called"

    def assert_tool_params_include(self, **params):
        """Assert that tool was called with specific parameters."""
        # Implementation would check actual tool calls
        pass

    def assert_final_response_contains(self, pattern: str):
        """Assert that final response contains a pattern."""
        final_turn = self.transcript["execution"][-1]
        if final_turn["type"] == "llm_call":
            content = final_turn["llm_response"]["content"]
            assert pattern in content, f"Pattern '{pattern}' not found in response"
```

### 3. TranscriptBuilder (Fluent API)

```python
# src/good_agent/transcripts/builder.py
from pathlib import Path
from typing import Any
import yaml
from datetime import datetime

class TranscriptBuilder:
    """Fluent API for building transcripts programmatically.

    Usage:
        transcript = (
            TranscriptBuilder("my_test")
            .with_config(model="gpt-4", temperature=0.7)
            .with_context(user_name="Alice")
            .with_system_message("You are helpful")
            .with_user_message("Hello!")
            .then_llm_responds("Hi there!")
            .save("transcripts/my_test.yaml")
        )
    """

    def __init__(self, name: str):
        self.transcript = {
            "version": "1.0",
            "metadata": {
                "name": name,
                "created": datetime.utcnow().isoformat() + "Z",
                "author": "builder"
            },
            "agent_config": {
                "tools": []
            },
            "initial_state": {
                "context": {},
                "message_store": []
            },
            "execution": [],
            "final_state": {
                "context": {},
                "message_store": [],
                "visible_messages": []
            }
        }

        self.message_counter = 0
        self.turn_counter = 0
        self.message_ids: list[str] = []

    def with_config(self, **config) -> "TranscriptBuilder":
        """Set agent configuration."""
        self.transcript["agent_config"].update(config)
        return self

    def with_context(self, **context) -> "TranscriptBuilder":
        """Set initial context variables."""
        self.transcript["initial_state"]["context"].update(context)
        return self

    def with_tools(self, *tools: str) -> "TranscriptBuilder":
        """Set available tools."""
        self.transcript["agent_config"]["tools"] = list(tools)
        return self

    def with_system_message(self, content: str) -> "TranscriptBuilder":
        """Add initial system message."""
        msg_id = self._create_message("system", content)
        return self

    def with_user_message(self, content: str) -> "TranscriptBuilder":
        """Add initial user message."""
        msg_id = self._create_message("user", content)
        return self

    def then_llm_responds(
        self,
        content: str,
        *,
        tool_calls: list[dict] | None = None
    ) -> "TranscriptBuilder":
        """Add an LLM response turn."""
        self.turn_counter += 1
        msg_id = self._next_message_id()

        turn = {
            "turn": self.turn_counter,
            "type": "llm_call",
            "messages_sent_to_llm": [
                {"ref": mid} for mid in self.message_ids
            ],
            "llm_response": {
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls
            },
            "message_created": {
                "id": msg_id,
                "role": "assistant",
                "content": content,
                "visible": True
            }
        }

        if tool_calls:
            turn["message_created"]["tool_calls"] = tool_calls

        self.transcript["execution"].append(turn)
        self.message_ids.append(msg_id)
        self.message_counter += 1

        return self

    def then_tool_executes(
        self,
        tool: str,
        parameters: dict,
        result: Any,
        *,
        success: bool = True
    ) -> "TranscriptBuilder":
        """Add a tool execution turn."""
        self.turn_counter += 1
        msg_id = self._next_message_id()
        call_id = f"call_{self.turn_counter:03d}"

        turn = {
            "turn": self.turn_counter,
            "type": "tool_call",
            "tool_call": {
                "id": call_id,
                "tool_name": tool,
                "parameters": parameters,
                "result": result,
                "success": success
            },
            "message_created": {
                "id": msg_id,
                "role": "tool",
                "tool_call_id": call_id,
                "tool_name": tool,
                "content": str(result),
                "visible": True
            }
        }

        self.transcript["execution"].append(turn)
        self.message_ids.append(msg_id)
        self.message_counter += 1

        return self

    def with_assertion(
        self,
        assertion_type: str,
        **kwargs
    ) -> "TranscriptBuilder":
        """Add an assertion to final state."""
        if "assertions" not in self.transcript["final_state"]:
            self.transcript["final_state"]["assertions"] = []

        self.transcript["final_state"]["assertions"].append({
            "type": assertion_type,
            **kwargs
        })

        return self

    def save(self, path: Path | str) -> Path:
        """Save transcript to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # Finalize message store and visible messages
        self.transcript["final_state"]["message_store"] = [
            {"ref": mid} for mid in self.message_ids
        ]
        self.transcript["final_state"]["visible_messages"] = [
            {"ref": mid} for mid in self.message_ids
        ]

        with open(path, 'w') as f:
            yaml.dump(
                self.transcript,
                f,
                default_flow_style=False,
                sort_keys=False
            )

        return path

    def build(self) -> dict:
        """Build and return the transcript dict without saving."""
        # Finalize message store
        self.transcript["final_state"]["message_store"] = [
            {"ref": mid} for mid in self.message_ids
        ]
        self.transcript["final_state"]["visible_messages"] = [
            {"ref": mid} for mid in self.message_ids
        ]

        return self.transcript

    def _create_message(self, role: str, content: str) -> str:
        """Create a message in initial state."""
        self.message_counter += 1
        msg_id = f"msg_{self.message_counter:03d}"

        self.transcript["initial_state"]["message_store"].append({
            "id": msg_id,
            "role": role,
            "content": content,
            "visible": True
        })

        self.message_ids.append(msg_id)
        return msg_id

    def _next_message_id(self) -> str:
        """Get the next message ID."""
        return f"msg_{self.message_counter + 1:03d}"


# Convenience alias for compact usage
T = TranscriptBuilder
```

### 4. LLM-Based Transcript Generator

```python
# src/good_agent/transcripts/generators.py
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from good_agent import Agent

class GeneratedTranscript(BaseModel):
    """Structured output model for LLM-generated transcripts."""

    metadata: dict[str, Any] = Field(
        description="Metadata including name, description, tags"
    )
    agent_config: dict[str, Any] = Field(
        description="Agent configuration"
    )
    initial_state: dict[str, Any] = Field(
        description="Initial context and messages"
    )
    execution: list[dict[str, Any]] = Field(
        description="Sequential turns of execution"
    )
    final_state: dict[str, Any] = Field(
        description="Final state and assertions"
    )


async def generate_transcript_with_llm(
    scenario_description: str,
    output_path: Path | str,
    *,
    generator_agent: Agent | None = None,
    model: str = "gpt-4",
    temperature: float = 0.7
) -> Path:
    """Generate a test transcript from a natural language description.

    Uses an LLM to create realistic test scenarios based on descriptions.

    Args:
        scenario_description: Natural language description of the scenario
        output_path: Where to save the generated transcript
        generator_agent: Optional custom generator agent
        model: Model to use for generation
        temperature: Temperature for generation

    Returns:
        Path to the saved transcript

    Example:
        await generate_transcript_with_llm(
            \"\"\"
            Test a weather query where:
            1. User asks about weather in NYC
            2. Agent calls weather tool
            3. Tool returns sunny, 72°F
            4. Agent responds with formatted weather info
            \"\"\",
            "transcripts/weather_test.yaml"
        )
    """

    if generator_agent is None:
        generator_agent = Agent(
            \"\"\"You are a test scenario generator for an AI agent library.

            Generate realistic, comprehensive test transcripts that:
            - Follow proper conversation flow
            - Include realistic tool calls and responses
            - Test edge cases and error conditions
            - Include proper state management
            - Have clear assertions

            Make the transcripts detailed and production-ready.
            \"\"\"
        ).config(model=model, temperature=temperature)

    prompt = f\"\"\"
    Generate a test transcript for the following scenario:

    {scenario_description}

    Create a complete YAML transcript with:
    - Appropriate agent configuration
    - Initial context and messages
    - A realistic sequence of LLM responses and tool calls
    - State changes throughout execution
    - Final state with assertions

    Make it realistic and include edge cases.
    \"\"\"

    # Use structured output
    transcript_obj = await generator_agent.extract(
        prompt,
        response_model=GeneratedTranscript
    )

    # Add version
    transcript_dict = transcript_obj.model_dump()
    transcript_dict["version"] = "1.0"

    # Save to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        yaml.dump(
            transcript_dict,
            f,
            default_flow_style=False,
            sort_keys=False
        )

    return output_path
```

## Usage Examples

### Example 1: Recording a Transcript

```python
from good_agent import Agent
from good_agent.transcripts import TranscriptRecorder

# Create agent
agent = Agent("You are a helpful assistant")
agent.tools.add(weather_tool)

# Attach recorder
recorder = TranscriptRecorder("transcripts/session_001.yaml")
agent.extensions.add(recorder)

# Use agent normally
await agent.call("What's the weather in NYC?")

# Transcript automatically saved to file
```

### Example 2: Building a Transcript Manually

```python
from good_agent.transcripts import TranscriptBuilder, T

# Fluent API
transcript = (
    T("weather_query")
    .with_config(model="gpt-4", temperature=0.7)
    .with_tools("weather", "search")
    .with_context(user_name="Alice", location="NYC")
    .with_system_message("You are a helpful weather assistant")
    .with_user_message("What's the weather?")
    .then_llm_responds(
        "I'll check the weather for you",
        tool_calls=[{
            "id": "call_001",
            "function": {
                "name": "weather",
                "arguments": '{"location": "NYC"}'
            }
        }]
    )
    .then_tool_executes(
        tool="weather",
        parameters={"location": "NYC"},
        result={"temp": 72, "condition": "sunny"}
    )
    .then_llm_responds("It's 72°F and sunny in NYC!")
    .with_assertion("contains", message="msg_005", pattern="72°F")
    .with_assertion("tool_called", tool="weather")
    .save("transcripts/weather_query.yaml")
)
```

### Example 3: Replaying in Tests

```python
import pytest
from good_agent import Agent
from good_agent.transcripts import TranscriptReplayer

@pytest.mark.asyncio
async def test_weather_query_flow():
    """Test that weather query follows expected pattern."""

    # Create agent
    agent = Agent("You are a helpful assistant")
    agent.tools.add(weather_tool)

    # Load and replay transcript
    replayer = TranscriptReplayer("transcripts/weather_query.yaml")

    # Strict mode: agent must follow exact path
    with replayer.mock_agent(agent):
        result = await agent.call("What's the weather?")

        # Assertions
        assert "72°F" in result.content
        assert "sunny" in result.content
```

### Example 4: Property-Based Testing

```python
@pytest.mark.asyncio
async def test_agent_calls_tools_correctly():
    """Test high-level behavior without strict replay."""

    replayer = TranscriptReplayer("transcripts/weather_query.yaml")

    agent = Agent("You are a helpful assistant")
    agent.tools.add(weather_tool)

    # Property-based checking
    with replayer.assert_properties() as checker:
        await agent.call("What's the weather?")

        # Check behaviors
        checker.assert_tool_called("weather")
        checker.assert_tool_params_include(location="NYC")
        checker.assert_final_response_contains("72")
```

### Example 5: Generating with LLM

```python
from good_agent.transcripts import generate_transcript_with_llm

# Generate from description
await generate_transcript_with_llm(
    scenario_description="""
    Test a multi-turn conversation about weather in multiple cities:

    1. User asks about weather in NYC and LA
    2. Agent calls weather tool for NYC
    3. Tool returns: sunny, 72°F
    4. Agent calls weather tool for LA
    5. Tool returns: cloudy, 65°F
    6. Agent compares and recommends NYC for outdoor activities

    Edge cases to include:
    - What if one tool call fails?
    - What if user interrupts during tool calls?
    """,
    output_path="transcripts/multi_city_weather.yaml"
)
```

### Example 6: Hand-Editing Transcript

```yaml
# transcripts/simple_greeting.yaml
# Human-friendly compact format

name: simple_greeting
description: Basic greeting exchange

# Just write the messages!
messages:
  - "system: You are a friendly assistant"
  - "user: Hello!"
  - "assistant: Hi there! How can I help you today?"
  - "user: What's 2+2?"
  - "assistant: 2+2 equals 4."

# System expands this automatically when loaded
```

### Example 7: Multi-Agent Transcript

```yaml
name: nested_agent_call
description: Test agent calling another agent as a tool

execution:
  - turn: 1
    type: "llm_call"
    llm_response:
      content: "I'll ask the specialist agent"
      tool_calls:
        - id: call_001
          function:
            name: "ask_specialist"
            arguments: '{"query": "What is the weather?"}'

  - turn: 2
    type: "tool_call"
    tool_call:
      id: call_001
      tool_name: "ask_specialist"
      parameters: {query: "What is the weather?"}

      # Nested agent execution
      result:
        type: "nested_agent_result"
        agent_id: "specialist_001"
        response: "The weather is sunny"

        # Optional: full nested transcript
        nested_transcript:
          execution:
            - turn: 1
              type: "llm_call"
              llm_response:
                content: "I'll check the weather"
            - turn: 2
              type: "tool_call"
              tool_call:
                tool_name: "weather"
                result: {temp: 72, condition: "sunny"}
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/transcripts/test_recording.py
def test_recorder_captures_llm_calls():
    """Test that recorder captures LLM interactions."""
    # ...

def test_recorder_captures_tool_calls():
    """Test that recorder captures tool executions."""
    # ...

def test_recorder_captures_state_changes():
    """Test that recorder captures context changes."""
    # ...
```

### Integration Tests

```python
# tests/integration/transcripts/test_replay.py
@pytest.mark.asyncio
async def test_replayer_strict_mode():
    """Test strict replay matches original execution."""
    # ...

@pytest.mark.asyncio
async def test_replayer_mocked_tools():
    """Test replay with mocked tools but real LLM."""
    # ...
```

### Example Transcripts

Provide reference transcripts in `tests/transcripts/examples/`:

- `simple_chat.yaml` - Basic conversation
- `tool_calling.yaml` - Tool execution
- `multi_agent.yaml` - Nested agents
- `context_management.yaml` - Dynamic context
- `error_handling.yaml` - Error cases
- `structured_output.yaml` - Structured responses

## Migration Plan

### Phase 1: Core Implementation (Week 1-2)

1. Implement `TranscriptRecorder` component
2. Implement `TranscriptReplayer`
3. Implement `TranscriptBuilder` fluent API
4. Add YAML serialization/deserialization
5. Write comprehensive tests

### Phase 2: Integration (Week 2-3)

1. Integrate with agent event system
2. Hook into message store
3. Support context tracking
4. Add tool call recording/replay

### Phase 3: Advanced Features (Week 3-4)

1. Implement `generate_transcript_with_llm()`
2. Add compact human-friendly format parser
3. Add property-based testing mode
4. Add assertion framework

### Phase 4: Migration & Deprecation (Week 4-5)

1. Update all tests to use transcripts
2. Add deprecation warnings to old mock system
3. Write migration guide
4. Update documentation

### Phase 5: Cleanup (Week 5-6)

1. Remove old mock system
2. Finalize API
3. Add example gallery
4. Write blog post

### Breaking Changes

This is a **major breaking change** that replaces the mock system:

**Before:**
```python
with agent.mock(
    agent.mock.create("Response 1"),
    agent.mock.tool_call("weather", result="sunny")
):
    await agent.call("Hello!")
```

**After:**
```python
# Option 1: Use pre-recorded transcript
replayer = TranscriptReplayer("transcripts/my_test.yaml")
with replayer.mock_agent(agent):
    await agent.call("Hello!")

# Option 2: Build inline
transcript = (
    T("inline_test")
    .with_user_message("Hello!")
    .then_llm_responds("Response 1")
    .then_tool_executes("weather", {}, "sunny")
    .build()
)
```

Since backwards compatibility is not required, we can:
1. Remove `src/good_agent/mock.py` entirely
2. Update all existing tests
3. Provide migration tooling if needed

## Open Questions

1. **Message deduplication strategy**: How to efficiently reference messages that appear in multiple contexts?
   - Current approach: Short IDs (`msg_001`) with optional full ULIDs
   - Alternative: Content-based hashing

2. **Context change tracking**: How granular should context change recording be?
   - Current: Record context diff per turn
   - Alternative: Full snapshots per turn
   - Alternative: Event-based recording of each change

3. **Tool result serialization**: How to handle complex tool results?
   - Current: JSON serialization
   - Problem: Binary data, file handles, etc.
   - Solution: Pluggable serializers per tool?

4. **Nested agent transcripts**: Should we inline or reference nested executions?
   - Current: Inline full nested transcript
   - Alternative: Reference separate transcript files
   - Alternative: Configurable (inline for small, reference for large)

5. **Version compatibility**: How to handle transcript format evolution?
   - Version field in YAML
   - Migration tools for old formats
   - Deprecation policy

6. **Performance**: For very long conversations, transcripts could be large
   - Compression?
   - Incremental recording?
   - Pagination?

7. **Human-friendly format**: How expressive should the compact format be?
   - Current: Simple message list
   - Add: Context changes, assertions, conditionals?

8. **Diff/comparison**: Should we provide transcript diff tools?
   - Compare two transcripts
   - Show differences in execution flow
   - Identify regressions

## Success Criteria

1. **Functionality**
   - [ ] Can record full agent execution to transcript
   - [ ] Can replay transcripts deterministically
   - [ ] Can build transcripts programmatically
   - [ ] Can generate transcripts with LLM
   - [ ] Supports all good-agent features (context, tools, multi-agent)

2. **Usability**
   - [ ] Human-readable YAML format
   - [ ] Fluent builder API is intuitive
   - [ ] Hand-editing transcripts is straightforward
   - [ ] Error messages are helpful

3. **Testing**
   - [ ] 90%+ test coverage
   - [ ] All existing mock tests migrated
   - [ ] Property-based testing works
   - [ ] Performance acceptable (<10ms overhead)

4. **Documentation**
   - [ ] API documentation complete
   - [ ] Usage examples comprehensive
   - [ ] Migration guide available
   - [ ] Example transcript gallery

## References

- **VCR.py**: HTTP interaction recording - https://vcrpy.readthedocs.io/
- **AgentRR**: LLM agent record/replay (arXiv 2505.17716v1)
- **Playwright Traces**: Browser automation recording - https://playwright.dev/docs/trace-viewer
- **Redux DevTools**: Time-travel debugging - https://github.com/reduxjs/redux-devtools
- **LangSmith**: LLM tracing (but not replay) - https://docs.smith.langchain.com/
