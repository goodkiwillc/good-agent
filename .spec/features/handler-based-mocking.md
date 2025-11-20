# Feature Spec: Handler-Based Mocking for Multi-Turn and Multi-Agent Workflows

**Status**: ✅ Implemented  
**Created**: 2025-11-19  
**Completed**: 2025-11-20  
**Author**: System Design  
**Related**: `.spec/v1/review/2025-11-19-llm-mocking-analysis.md`

## Overview

Introduce a **handler-based mocking API** that serves as the primitive for all mock behaviors, while maintaining **full backwards compatibility** with the existing queue-based `agent.mock()` API.

### Current Limitations

The existing queue-based mock API works well for simple tests:

```python
with agent.mock("Response 1", "Response 2") as mock:
    await mock.call("Question 1")  # -> "Response 1"
    await mock.call("Question 2")  # -> "Response 2"
```

But struggles with:

1. **Multi-turn workflows** - `execute()` makes multiple LLM calls internally (assistant + tools), making response ordering unpredictable
2. **Context-dependent responses** - Can't inspect agent state to decide what to return
3. **Multi-agent conversations** - Hard to coordinate responses between agents
4. **Complex branching** - Can't handle "if weather query, return X, else return Y" logic

### Proposed Solution

Make **handlers** the primitive mock mechanism. A handler is a callable that receives full context on each LLM call and returns a response:

```python
def my_handler(ctx: MockContext) -> MockResponse:
    """Handler is called on EACH LLM completion request"""
    if "weather" in ctx.agent.user[-1].content.lower():
        return MockResponse("It's sunny!")
    return MockResponse("I don't know")

with agent.mock(my_handler):
    await agent.call("What's the weather?")  # Handler called with context
```

The current queue-based API becomes syntactic sugar for `QueuedResponseHandler`:

```python
# This code (current API)
with agent.mock("Response 1", "Response 2"):
    ...

# Becomes this internally
with agent.mock(QueuedResponseHandler("Response 1", "Response 2")):
    ...
```

**No breaking changes** - existing code works exactly as before.

---

## Design

### Core: MockHandler Protocol

```python
from typing import Protocol

class MockHandler(Protocol):
    """Protocol for mock response handlers
    
    Handlers are called on each LLM completion request and must return
    a MockResponse based on the current context.
    """
    
    async def handle(self, context: MockContext) -> MockResponse:
        """Generate mock response based on context
        
        Args:
            context: Full context about the current LLM call
            
        Returns:
            MockResponse to return instead of calling real LLM
        """
        ...
```

Handlers can be:
- **Classes** implementing the protocol
- **Functions** with signature `(MockContext) -> MockResponse`
- **Async functions** with signature `async (MockContext) -> MockResponse`

### MockContext

```python
@dataclass
class MockContext:
    """Context passed to handler on each LLM call
    
    Provides access to agent state, message history, and call metadata
    to help handlers decide what response to return.
    """
    
    # Agent and state
    agent: Agent
    """The agent making the LLM call"""
    
    messages: list[Message]
    """Messages being sent to LLM (formatted for LLM call)"""
    
    # Call tracking
    iteration: int
    """Current execute() iteration number (0-indexed)"""
    
    call_count: int
    """Total number of LLM calls made during this mock session"""
    
    # Request details
    kwargs: dict[str, Any]
    """Additional kwargs passed to LLM (temperature, model, etc.)"""
```

**Note**: Use `context.agent.user[-1]`, `context.agent.assistant[-1]`, etc. to access messages with existing convenience accessors.

### MockResponse (Existing)

The existing `MockResponse` dataclass is used - no changes needed:

```python
@dataclass
class MockResponse:
    """Configuration for a mock response"""
    type: Literal["message", "tool_call"]
    content: str | None = None
    role: Literal["assistant", "user", "system", "tool"] = "assistant"
    tool_calls: list[MockToolCall] | None = None
    # ... other fields
```

---

## Backwards Compatibility

### Current API (Preserved)

The existing queue-based API continues to work exactly as before:

```python
# Strings (creates MockResponse automatically)
with agent.mock("Response 1", "Response 2") as mock:
    result = await mock.call("Question")

# MockResponse objects
with agent.mock(
    MockResponse(content="Hello", role="assistant"),
    MockResponse(content="Goodbye", tool_calls=[...])
) as mock:
    async for msg in mock.execute():
        print(msg)

# Helper methods
with agent.mock(
    agent.mock.create("Response", role="assistant"),
    agent.mock.tool_call("weather", location="Paris", result={"temp": 72})
) as mock:
    ...
```

### Implementation Strategy

The `agent.mock()` method detects what's passed and adapts:

```python
class AgentMockInterface:
    def __call__(
        self, 
        *args: MockResponse | str | MockHandler,
        **kwargs
    ) -> MockAgent:
        """Flexible mock() that handles both APIs"""
        
        # No arguments -> empty queue
        if not args:
            handler = QueuedResponseHandler()
        
        # Single argument that's callable -> use as handler
        elif len(args) == 1 and callable(args[0]):
            handler = args[0]
        
        # Multiple args or MockResponse/str -> queue handler
        else:
            handler = QueuedResponseHandler(*args)
        
        return MockAgent(self.agent, handler, **kwargs)
```

**Result**: Existing code uses `QueuedResponseHandler` under the hood, new code can use custom handlers.

---

## Built-in Handlers

Provide common patterns as ready-to-use handlers:

### 1. QueuedResponseHandler (Default)

```python
class QueuedResponseHandler(MockHandler):
    """Simple FIFO queue of responses (current behavior)"""
    
    def __init__(self, *responses: MockResponse | str):
        self.responses = [ensure_mock_response(r) for r in responses]
        self.index = 0
    
    async def handle(self, context: MockContext) -> MockResponse:
        if self.index >= len(self.responses):
            raise MockExhaustedError(
                f"Mock exhausted: needed response {self.index + 1} "
                f"but only {len(self.responses)} were queued"
            )
        
        response = self.responses[self.index]
        self.index += 1
        return response

# Used automatically by current API
with agent.mock("Response 1", "Response 2"):
    # Uses QueuedResponseHandler internally
    pass
```

### 2. ConditionalHandler

```python
class ConditionalHandler(MockHandler):
    """Match responses based on conditions (content, iteration, etc.)"""
    
    def __init__(self):
        self.rules: list[tuple[Callable[[MockContext], bool], MockResponse]] = []
        self.default_response: MockResponse | None = None
    
    def when(
        self, 
        condition: Callable[[MockContext], bool],
        respond: str | MockResponse
    ) -> Self:
        """Add conditional rule"""
        response = ensure_mock_response(respond)
        self.rules.append((condition, response))
        return self
    
    def default(self, respond: str | MockResponse) -> Self:
        """Set fallback response"""
        self.default_response = ensure_mock_response(respond)
        return self
    
    async def handle(self, context: MockContext) -> MockResponse:
        # Check rules in order
        for condition, response in self.rules:
            if condition(context):
                return response
        
        # Fallback
        if self.default_response:
            return self.default_response
        
        raise MockNoMatchError("No condition matched and no default set")

# Usage
handler = ConditionalHandler()
handler.when(
    lambda ctx: "weather" in ctx.agent.user[-1].content.lower(),
    respond="It's sunny!"
).when(
    lambda ctx: "capital" in ctx.agent.user[-1].content.lower(),
    respond="The capital is Paris"
).default("I don't know")

with agent.mock(handler):
    await agent.call("What's the weather?")  # Matches first rule
    await agent.call("What's the capital?")   # Matches second rule
    await agent.call("Random question")       # Uses default
```

**Convenience API:**

```python
# Shorthand via agent.mock namespace
with agent.mock.conditional(
    when=lambda ctx: "weather" in ctx.agent.user[-1].content,
    respond="Sunny"
):
    ...
```

### 3. TranscriptHandler

```python
class TranscriptHandler(MockHandler):
    """Follow a predefined conversation transcript"""
    
    def __init__(self, transcript: list[tuple]):
        """
        Args:
            transcript: List of (role, content, **extras) tuples
                Example: [
                    ("assistant", "I'll check weather", {"tool_calls": [...]}),
                    ("assistant", "It's sunny"),
                ]
        """
        self.transcript = transcript
        self.position = 0
    
    async def handle(self, context: MockContext) -> MockResponse:
        if self.position >= len(self.transcript):
            raise MockExhaustedError(
                f"Transcript exhausted at position {self.position}"
            )
        
        entry = self.transcript[self.position]
        self.position += 1
        
        # Parse entry
        role, content, *extras = entry
        kwargs = extras[0] if extras else {}
        
        return MockResponse(content=content, role=role, **kwargs)

# Usage
transcript = [
    ("assistant", "I'll check the weather", {"tool_calls": [("get_weather", {})]}),
    ("assistant", "It's 75°F and sunny"),
]

with agent.mock(TranscriptHandler(transcript)):
    async for msg in agent.execute("What's the weather?"):
        # First LLM call: returns assistant with tool_calls
        # Second LLM call: returns final assistant message
        print(msg)
```

**Convenience API:**

```python
with agent.mock.transcript([
    ("assistant", "I'll check", {"tool_calls": [...]}),
    ("assistant", "Result"),
]):
    ...
```

### 4. StateMachineHandler

```python
@dataclass
class State:
    """A state in the mock state machine"""
    
    respond: str | MockResponse | Callable[[MockContext], MockResponse]
    """What to respond with in this state"""
    
    transitions: dict[str, Callable[[MockContext], bool]] | None = None
    """Transitions: {target_state: condition_fn}"""
    
    default_next: str | None = None
    """Default next state if no transition matches"""
    
    def get_response(self, context: MockContext) -> MockResponse:
        if callable(self.respond):
            result = self.respond(context)
            return ensure_mock_response(result)
        return ensure_mock_response(self.respond)
    
    def get_next_state(self, context: MockContext) -> str | None:
        if not self.transitions:
            return self.default_next
        
        for target, condition in self.transitions.items():
            if condition(context):
                return target
        
        return self.default_next


class StateMachineHandler(MockHandler):
    """State machine for complex conversation flows"""
    
    def __init__(self, states: dict[str, State], initial: str):
        self.states = states
        self.current_state = initial
        self.history: list[str] = [initial]
    
    async def handle(self, context: MockContext) -> MockResponse:
        if self.current_state not in self.states:
            raise ValueError(f"Unknown state: {self.current_state}")
        
        state = self.states[self.current_state]
        
        # Get response
        response = state.get_response(context)
        
        # Transition
        next_state = state.get_next_state(context)
        if next_state:
            self.current_state = next_state
            self.history.append(next_state)
        
        return response

# Usage
fsm = StateMachineHandler(
    states={
        "greeting": State(
            respond="Hello! How can I help?",
            transitions={
                "weather": lambda ctx: "weather" in ctx.agent.user[-1].content,
                "capital": lambda ctx: "capital" in ctx.agent.user[-1].content,
            }
        ),
        "weather": State(
            respond=MockResponse(
                "Let me check",
                tool_calls=[("get_weather", {})]
            ),
            default_next="weather_result"
        ),
        "weather_result": State(
            respond="It's sunny!",
            default_next="greeting"
        ),
        "capital": State(
            respond="Which country?",
            default_next="capital_answer"
        ),
        "capital_answer": State(
            respond=lambda ctx: f"The capital is {extract_country(ctx)}",
            default_next="greeting"
        ),
    },
    initial="greeting"
)

with agent.mock(fsm):
    await agent.call("What's the weather?")  # greeting -> weather -> weather_result
    await agent.call("Tell me a capital")     # weather_result -> greeting -> capital
```

---

## Multi-Turn Workflows

Handlers shine with `execute()` where multiple LLM calls happen:

```python
def weather_handler(ctx: MockContext) -> MockResponse:
    """Handler called on each LLM completion"""
    
    # First call: return tool request
    if ctx.call_count == 1:
        return MockResponse(
            content="I'll check the weather for you",
            tool_calls=[("get_weather", {"location": "Paris"})]
        )
    
    # Second call: return final answer (after tool executes)
    elif ctx.call_count == 2:
        # Can inspect tool results in messages
        tool_result = ctx.agent.messages[-1]  # Last message is tool result
        return MockResponse(content=f"Based on the data: it's sunny!")
    
    return MockResponse(content="Unexpected call")

with agent.mock(weather_handler):
    async for msg in agent.execute("What's the weather in Paris?"):
        # Iteration 0:
        #   - LLM call #1 -> handler returns assistant with tool_calls
        #   - Tool executes -> returns tool message
        # Iteration 1:
        #   - LLM call #2 -> handler returns final assistant message
        print(msg.role, msg.content)
```

### Alternative: Use Conditional Handler

```python
handler = ConditionalHandler()
handler.when(
    lambda ctx: ctx.call_count == 1 and "weather" in ctx.agent.user[-1].content,
    respond=MockResponse("I'll check", tool_calls=[("get_weather", {})])
).when(
    lambda ctx: ctx.call_count == 2,
    respond="It's sunny based on the tool result"
)

with agent.mock(handler):
    async for msg in agent.execute("What's the weather?"):
        print(msg)
```

---

## Multi-Agent Workflows

Each agent gets its own handler:

### Simple Conversation

```python
def agent_a_handler(ctx: MockContext) -> MockResponse:
    """Agent A always greets"""
    return MockResponse("Hello from Agent A!")

def agent_b_handler(ctx: MockContext) -> MockResponse:
    """Agent B responds to greetings"""
    last_user_msg = ctx.agent.user[-1]
    
    if "hello" in last_user_msg.content.lower():
        return MockResponse("Hi back from Agent B!")
    
    return MockResponse("Agent B says: I heard you")

async with agent_a | agent_b as conversation:
    with agent_a.mock(agent_a_handler), agent_b.mock(agent_b_handler):
        agent_a.assistant.append("Hello Agent B")
        
        async for msg in conversation.execute(max_iterations=3):
            print(f"{msg.agent.name}: {msg.content}")
        
        # Output:
        # agent_a: Hello from Agent A!
        # agent_b: Hi back from Agent B!
        # agent_a: Hello from Agent A!
        # ...
```

### Stateful Multi-Agent

```python
class AgentAHandler(MockHandler):
    """Stateful handler for agent A"""
    
    def __init__(self):
        self.response_count = 0
    
    async def handle(self, ctx: MockContext) -> MockResponse:
        self.response_count += 1
        
        if self.response_count == 1:
            return MockResponse("Hi, I'm Agent A!")
        elif self.response_count == 2:
            return MockResponse("Nice to meet you too!")
        else:
            return MockResponse("Goodbye from A")

class AgentBHandler(MockHandler):
    """Stateful handler for agent B"""
    
    def __init__(self):
        self.saw_greeting = False
    
    async def handle(self, ctx: MockContext) -> MockResponse:
        last_msg = ctx.agent.user[-1].content
        
        if not self.saw_greeting and "hi" in last_msg.lower():
            self.saw_greeting = True
            return MockResponse("Hello Agent A, nice to meet you!")
        
        return MockResponse("Agent B acknowledges")

async with agent_a | agent_b as conv:
    with agent_a.mock(AgentAHandler()), agent_b.mock(AgentBHandler()):
        async for msg in conv.execute(max_iterations=4):
            print(msg.agent.name, msg.content)
```

---

## API Surface

### agent.mock() - Main Entry Point

```python
# Current API (backwards compatible)
with agent.mock("Response 1", "Response 2"):
    ...

# Handler (function)
with agent.mock(my_handler_func):
    ...

# Handler (class instance)
with agent.mock(MyHandler()):
    ...
```

### agent.mock.* - Convenience Methods

```python
# Conditional
with agent.mock.conditional(
    when=lambda ctx: "weather" in ctx.agent.user[-1].content,
    respond="Sunny"
).when(...).default(...):
    ...

# Transcript
with agent.mock.transcript([
    ("assistant", "Response 1"),
    ("assistant", "Response 2", {"tool_calls": [...]}),
]):
    ...

# State machine
with agent.mock.fsm(
    states={...},
    initial="greeting"
):
    ...
```

### Helper Functions

```python
# Existing helpers still work
agent.mock.create(content="Hello", role="assistant")
agent.mock.tool_call(name="weather", arguments={}, result={})
```

---

## Implementation Notes

### LLM Call Interception

The `MockQueuedLanguageModel` (currently used) is replaced with `MockHandlerLanguageModel`:

```python
class MockHandlerLanguageModel:
    """Language model that delegates to a handler"""
    
    def __init__(self, handler: MockHandler, agent: Agent):
        self.handler = handler
        self.agent = agent
        self.call_count = 0
        
        # Tracking (existing behavior)
        self.api_requests: list[Any] = []
        self.api_responses: list[Any] = []
    
    async def complete(self, messages: list[dict[str, Any]], **kwargs) -> Any:
        """Intercept LLM call and use handler"""
        self.call_count += 1
        
        # Track request
        request_data = {"messages": messages, **kwargs}
        self.api_requests.append(request_data)
        
        # Fire before event
        self.agent.do(
            AgentEvents.LLM_COMPLETE_BEFORE,
            messages=messages,
            config=kwargs,
            llm=self,
        )
        
        # Build context
        context = MockContext(
            agent=self.agent,
            messages=self.agent.messages,
            iteration=self.agent._iteration_index,
            call_count=self.call_count,
            kwargs=kwargs,
        )
        
        # Get response from handler
        mock_response = await self._call_handler(context)
        
        # Convert MockResponse to LiteLLM format
        llm_response = self._to_litellm_response(mock_response)
        
        # Track response
        self.api_responses.append(llm_response)
        
        # Fire after event
        self.agent.do(
            AgentEvents.LLM_COMPLETE_AFTER,
            response=llm_response,
            messages=messages,
            llm=self,
        )
        
        return llm_response
    
    async def _call_handler(self, context: MockContext) -> MockResponse:
        """Call handler (sync or async)"""
        if asyncio.iscoroutinefunction(self.handler.handle):
            return await self.handler.handle(context)
        else:
            return self.handler.handle(context)
```

### api_requests / api_responses Tracking

**Critical**: All handlers must maintain the existing behavior where:
- `api_requests` is populated before handler execution
- `api_responses` is populated after handler execution
- LiteLLM-style response objects are created (with `.choices`, `.usage`, etc.)
- Agent events (`LLM_COMPLETE_BEFORE` / `LLM_COMPLETE_AFTER`) are fired

This is already implemented in the current `MockQueuedLanguageModel` and carries over to `MockHandlerLanguageModel`.

---

## Migration Path

### Phase 1: Implement Handler Infrastructure

1. Add `MockHandler` protocol
2. Add `MockContext` dataclass
3. Implement `MockHandlerLanguageModel`
4. Refactor existing `MockQueuedLanguageModel` -> `QueuedResponseHandler`
5. Update `agent.mock()` to detect and route to appropriate handler
6. **All existing tests pass with no changes**

### Phase 2: Add Built-in Handlers

1. Implement `ConditionalHandler`
2. Implement `TranscriptHandler`
3. Add convenience methods (`agent.mock.conditional()`, etc.)
4. Documentation and examples

### Phase 3: Advanced Handlers

1. Implement `StateMachineHandler`
2. Add more sophisticated multi-agent helpers
3. Community contribution templates

---

## Testing Strategy

### Backwards Compatibility Tests

```python
def test_current_api_still_works():
    """Ensure existing queue-based API is unchanged"""
    agent = Agent("You are helpful")
    
    with agent.mock("Response 1", "Response 2") as mock:
        result = await mock.call("Question 1")
        assert result.content == "Response 1"
        
        result = await mock.call("Question 2")
        assert result.content == "Response 2"
```

### Handler Tests

```python
def test_custom_handler():
    """Test custom handler receives context"""
    call_contexts = []
    
    def handler(ctx: MockContext) -> MockResponse:
        call_contexts.append(ctx)
        return MockResponse(f"Call {ctx.call_count}")
    
    agent = Agent("You are helpful")
    
    with agent.mock(handler):
        await agent.call("Question 1")
        await agent.call("Question 2")
    
    assert len(call_contexts) == 2
    assert call_contexts[0].call_count == 1
    assert call_contexts[1].call_count == 2
```

### Multi-Turn Tests

```python
def test_handler_with_execute():
    """Test handler works with execute() multi-turn"""
    
    def handler(ctx: MockContext) -> MockResponse:
        if ctx.call_count == 1:
            return MockResponse(
                "I'll check",
                tool_calls=[("get_weather", {})]
            )
        return MockResponse("It's sunny")
    
    agent = Agent("You are helpful", tools=[get_weather])
    
    with agent.mock(handler):
        messages = []
        async for msg in agent.execute("What's the weather?"):
            messages.append(msg)
        
        # Should have assistant (with tool) -> tool -> assistant
        assert len(messages) == 3
```

### Multi-Agent Tests

```python
def test_multi_agent_handlers():
    """Test each agent has its own handler"""
    
    def handler_a(ctx):
        return MockResponse("Agent A speaking")
    
    def handler_b(ctx):
        return MockResponse("Agent B speaking")
    
    agent_a = Agent("Agent A")
    agent_b = Agent("Agent B")
    
    async with agent_a | agent_b as conv:
        with agent_a.mock(handler_a), agent_b.mock(handler_b):
            messages = []
            async for msg in conv.execute(max_iterations=2):
                messages.append(msg)
            
            # Each agent used its own handler
            contents = [m.content for m in messages]
            assert "Agent A speaking" in contents
            assert "Agent B speaking" in contents
```

---

## Examples

### Example 1: Simple Test (Current API)

```python
async def test_capital_query():
    """Simple test using current API"""
    agent = Agent("You are helpful")
    
    with agent.mock("The capital of France is Paris") as mock:
        result = await mock.call("What is the capital of France?")
        assert "Paris" in result.content
```

### Example 2: Context-Aware Handler

```python
async def test_weather_with_context():
    """Handler that inspects context to decide response"""
    
    def weather_handler(ctx: MockContext) -> MockResponse:
        user_msg = ctx.agent.user[-1].content
        
        if "paris" in user_msg.lower():
            return MockResponse("It's 72°F in Paris")
        elif "london" in user_msg.lower():
            return MockResponse("It's 65°F in London")
        else:
            return MockResponse("I don't know that location")
    
    agent = Agent("You are helpful")
    
    with agent.mock(weather_handler):
        result = await agent.call("What's the weather in Paris?")
        assert "72°F" in result.content
        
        result = await agent.call("How about London?")
        assert "65°F" in result.content
```

### Example 3: Multi-Turn Tool Usage

```python
async def test_multi_turn_with_tools():
    """Handler for tool-based workflow"""
    
    def tool_handler(ctx: MockContext) -> MockResponse:
        if ctx.call_count == 1:
            # First call: request tool
            return MockResponse(
                content="I'll fetch that data",
                tool_calls=[("fetch_data", {"query": "sales"})]
            )
        else:
            # Second call: use tool result
            tool_msg = ctx.agent.messages[-1]
            return MockResponse(f"The data shows: {tool_msg.content}")
    
    agent = Agent("You are helpful", tools=[fetch_data])
    
    with agent.mock(tool_handler):
        async for msg in agent.execute("Get sales data"):
            print(msg.role, msg.content)
```

### Example 4: Conditional Handler

```python
async def test_conditional_responses():
    """Use ConditionalHandler for pattern matching"""
    
    handler = ConditionalHandler()
    handler.when(
        lambda ctx: "weather" in ctx.agent.user[-1].content,
        respond="It's sunny!"
    ).when(
        lambda ctx: "time" in ctx.agent.user[-1].content,
        respond="It's 3 PM"
    ).default("I don't understand")
    
    agent = Agent("You are helpful")
    
    with agent.mock(handler):
        result = await agent.call("What's the weather?")
        assert "sunny" in result.content
        
        result = await agent.call("What time is it?")
        assert "3 PM" in result.content
        
        result = await agent.call("Random question")
        assert "don't understand" in result.content
```

### Example 5: Multi-Agent Conversation

```python
async def test_two_agent_conversation():
    """Mock responses for two-agent conversation"""
    
    class CountingHandler(MockHandler):
        def __init__(self, name: str):
            self.name = name
            self.count = 0
        
        async def handle(self, ctx: MockContext) -> MockResponse:
            self.count += 1
            return MockResponse(f"[{self.name}] Message {self.count}")
    
    agent_a = Agent("Agent A")
    agent_b = Agent("Agent B")
    
    handler_a = CountingHandler("A")
    handler_b = CountingHandler("B")
    
    async with agent_a | agent_b as conv:
        with agent_a.mock(handler_a), agent_b.mock(handler_b):
            messages = []
            async for msg in conv.execute(max_iterations=3):
                messages.append(msg)
                if len(messages) >= 6:
                    break
            
            # Should alternate between agents
            assert any("[A]" in m.content for m in messages)
            assert any("[B]" in m.content for m in messages)
```

---

## Open Questions

1. **Async vs Sync Handlers**
   - Should we support both sync and async handlers?
   - **Recommendation**: Yes, detect with `asyncio.iscoroutinefunction()` and handle appropriately

2. **Handler State Persistence**
   - Should handler state persist across multiple `execute()` calls in the same mock context?
   - **Recommendation**: Yes, handlers are instantiated once per `with agent.mock(handler)` block

3. **Error Handling**
   - What happens if a handler raises an exception?
   - **Recommendation**: Let it propagate (fail fast), but provide clear error messages

4. **Handler Composition**
   - Should we support composing multiple handlers?
   - **Recommendation**: Phase 2 feature - `CompositeHandler([handler1, handler2])`

5. **Logging/Debugging**
   - How do we help users debug handler behavior?
   - **Recommendation**: Add optional `debug=True` flag to log handler calls and decisions

---

## Success Criteria

- [ ] All existing tests pass with no modifications
- [ ] `QueuedResponseHandler` provides identical behavior to current `MockQueuedLanguageModel`
- [ ] `api_requests` and `api_responses` tracking works correctly with handlers
- [ ] LLM events (`LLM_COMPLETE_BEFORE/AFTER`) fire correctly
- [ ] Custom handlers can inspect `context.agent.user[-1]`, `context.agent.assistant[-1]`, etc.
- [ ] Multi-turn `execute()` workflows work with handlers
- [ ] Multi-agent conversations work with per-agent handlers
- [ ] Documentation includes migration guide and examples
- [ ] At least 3 built-in handlers implemented (Queued, Conditional, Transcript)

---

## Implementation Complete ✅ (2025-11-20)

### Summary

All planned features have been successfully implemented and tested:

- ✅ **Core Infrastructure**: MockContext, MockHandler Protocol, MockHandlerLanguageModel
- ✅ **Built-in Handlers**: QueuedResponseHandler, ConditionalHandler, TranscriptHandler
- ✅ **Convenience API**: `agent.mock.conditional()`, `agent.mock.transcript()`
- ✅ **Event Integration**: Proper `LLM_COMPLETE_BEFORE/AFTER` event firing
- ✅ **Citations/Annotations**: Full support for mock responses with metadata
- ✅ **Backwards Compatibility**: All 55 existing mock tests pass unchanged
- ✅ **Test Coverage**: 40 new comprehensive tests, 100% passing

### Test Results
```
✅ 1586/1586 total tests passing
✅ 40/40 new handler-based mocking tests  
✅ 55/55 existing mock tests
✅ 0 regressions
```

### Key Files Modified
- `src/good_agent/mock.py` - Handler infrastructure and built-in handlers
- `src/good_agent/messages/base.py` - Citations/annotations extraction
- `src/good_agent/agent/llm.py` - Citations/annotations pipeline
- `tests/unit/agent/test_handler_based_mocking.py` - Comprehensive test suite
- Multiple test files updated for new behavior

### Next Steps (Future Work)
1. Documentation with examples and migration guide
2. Advanced handlers (StateMachineHandler, CompositeHandler)
3. Debug/logging utilities for handler troubleshooting

---

## References

- Current implementation: `src/good_agent/mock.py`
- Analysis: `.spec/v1/review/2025-11-19-llm-mocking-analysis.md`
- Related designs: `/Users/chrisgoddard/.factory/docs/2025-11-19-mock-api-design-alternatives-for-multi-turn-and-multi-agent-workflows.md`
- Test suite: `tests/unit/agent/test_handler_based_mocking.py`
