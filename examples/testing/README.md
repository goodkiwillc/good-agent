# Testing Examples

This directory contains examples demonstrating how to test agents using the handler-based mocking system.

## Files

### `handler_based_mocking.py`

Comprehensive examples of handler-based mocking for testing agents. Includes:

1. **Simple Function Handler** - Basic handler that returns mock responses
2. **ConditionalHandler** - Pattern matching for context-dependent responses
3. **ConditionalHandler with State** - Accessing agent state in conditions
4. **TranscriptHandler** - Following predefined conversation scripts
5. **TranscriptHandler with Tools** - Mocking tool calls in conversations
6. **Multi-Agent with Handlers** - Each agent has its own mock behavior
7. **Multi-Agent Conversation (agent | agent)** - Testing agent-to-agent communication
8. **Custom Handler Class** - Building reusable stateful handlers
9. **Context Inspection** - Debugging with handler context
10. **Backwards Compatibility** - Queue-based API still works

## Running the Examples

```bash
# Run all examples
uv run python examples/testing/handler_based_mocking.py

# Or with plain python
python examples/testing/handler_based_mocking.py
```

## Key Concepts

### Handlers

Handlers are callables that receive `MockContext` and return `MockResponse`:

```python
def my_handler(ctx: MockContext) -> MockResponse:
    return MockResponse(content="Hello!")

with agent.mock(my_handler):
    await agent.call("Question")  # Returns "Hello!"
```

### MockContext

The context provides full access to agent state:

- `ctx.agent` - The agent instance
- `ctx.agent.user` - All user messages
- `ctx.agent.assistant` - All assistant messages
- `ctx.messages` - Full message list
- `ctx.call_count` - Number of LLM calls made
- `ctx.iteration` - Current execute() iteration
- `ctx.kwargs` - LLM call parameters

### Built-in Handlers

1. **QueuedResponseHandler** (default for string responses)
2. **ConditionalHandler** - `.when()` and `.default()` pattern matching
3. **TranscriptHandler** - Predefined conversation sequences

## Multi-Agent Testing

The handler system excels at testing multi-agent conversations:

```python
alice = Agent("Alice")
bob = Agent("Bob")

with alice.mock(TranscriptHandler([...])), bob.mock(TranscriptHandler([...])):
    async with alice | bob as conversation:
        async for msg in conversation.execute():
            print(f"{msg.agent.system[0].content}: {msg.content}")
```

See Example 7 in `handler_based_mocking.py` for a complete example.

## More Information

- Feature spec: `.spec/features/handler-based-mocking.md`
- Test suite: `tests/unit/agent/test_handler_based_mocking.py`
- Analysis: `.spec/analysis/mock-usage-patterns-and-utilities.md`
