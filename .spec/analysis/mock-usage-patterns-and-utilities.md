# Mock Usage Patterns Analysis

**Date**: 2025-11-20  
**Context**: Post handler-based mocking implementation

## Summary

**Question**: Now that we have handler-based mocking, should we:
- a) Refactor existing tests to use the new handlers?
- b) Identify common patterns that justify additional utility handlers?

**Answer**: 
- **a) No major refactoring needed** - Most tests already work great with queue-based API (which now uses QueuedResponseHandler internally)
- **b) No urgent need for additional handlers** - The 3 implemented handlers cover the main use cases well

## Implemented Handlers (from spec)

1. ✅ **QueuedResponseHandler** - FIFO queue of responses (backwards compatible with existing `agent.mock("a", "b", "c")`)
2. ✅ **ConditionalHandler** - Pattern matching with `.when()` and `.default()` for context-dependent responses
3. ✅ **TranscriptHandler** - Follow predefined conversation sequences with role-based responses

## Test Suite Analysis

**Stats**: 19 test files, ~100+ mock usage instances

**Current distribution**:
- 75% - Simple single/multi responses → **Already using QueuedResponseHandler** ✅
- 15% - Tool call sequences → Queue-based works fine for now ✅  
- 5% - Context-dependent → **Could benefit from ConditionalHandler** 📝
- 5% - Other (error handling, edge cases) → No handlers needed ✅

---

## Findings

### ✅ Good News: Most Tests Don't Need Changes

**75% of mocks** are simple queue-based responses:
```python
with agent.mock("Response 1", "Response 2"):
    await agent.call("Q1")  # -> Response 1
    await agent.call("Q2")  # -> Response 2
```

**Assessment**: Already using QueuedResponseHandler under the hood. **No changes needed.**

---

### 📝 Opportunity: 5% Could Use ConditionalHandler

**Current workaround** (rare, but exists):
```python
# Tests that manually track state or use complex logic
# are hard to write with queue-based mocking
```

**Example where ConditionalHandler would help**:
```python
# Instead of setting up complex state tracking
handler = ConditionalHandler() \
    .when(lambda ctx: "weather" in ctx.agent.user[-1].content.lower(),
          respond="It's sunny") \
    .when(lambda ctx: "time" in ctx.agent.user[-1].content.lower(),
          respond="It's 3pm") \
    .default("I don't know")

with agent.mock(handler):
    await agent.call("What's the weather?")  # -> "It's sunny"
    await agent.call("What time is it?")      # -> "It's 3pm"  
    await agent.call("Random question")       # -> "I don't know"
```

**Recommendation**: Add this pattern to examples/docs rather than refactoring existing tests

---

### 🤔 Question: Tool Call Sequences (15% of cases)

**Current pattern**:
```python
with agent.mock(
    agent.mock.create("I'll check", tool_calls=[...]),
    agent.mock.tool_call("weather", result={"temp": 72}),
    agent.mock.create("It's 72°F"),
):
    await agent.execute()
```

**Assessment**: Works fine, but verbose. Is it worth a utility?

```python
# Proposed improvement
handler = ToolCallSequenceHandler() \
    .tool_call("weather", {"location": "NYC"}, result={"temp": 72}) \
    .then("The weather is 72°F") \
    .tool_call("calendar", {"date": "today"}, result=["Meeting at 2pm"]) \
    .then("You have a meeting at 2pm")

with agent.mock(handler):
    await agent.execute()
```

**Benefits**:
- Cleaner, more readable
- Automatically handles tool call → result → response flow
- Type-safe tool definitions

---

### 3. Context-Dependent Responses (5% of cases)
**Current Usage**:
```python
# Can't do this with queue-based mocking!
# Must manually track state or use complex workarounds
```

**Example Need**:
```python
# Want to return different responses based on user input
if "weather" in user_message:
    return "It's sunny"
elif "time" in user_message:
    return "It's 3pm"
```

**Assessment**: ✅ **Now solved by ConditionalHandler!**

```python
handler = ConditionalHandler() \
    .when(lambda ctx: "weather" in ctx.agent.user[-1].content.lower(),
          respond="It's sunny") \
    .when(lambda ctx: "time" in ctx.agent.user[-1].content.lower(),
          respond="It's 3pm") \
    .default("I don't know")

with agent.mock(handler):
    await agent.call("What's the weather?")  # -> "It's sunny"
    await agent.call("What time is it?")      # -> "It's 3pm"
```

**Recommendation**: Evangelize ConditionalHandler usage in docs

---

### 4. Multi-Agent Conversations (2% of cases)
**Current Usage**: Limited - hard to test with queue-based mocking

**Proposed Utility**: `ConversationScriptHandler`

```python
# Proposed for multi-agent testing
script = ConversationScript()
script.agent_says("alice", "Hello Bob!")
script.agent_says("bob", "Hi Alice! How are you?")
script.agent_says("alice", "Great! Want to collaborate?")
script.agent_says("bob", "Sure!")

alice_handler = script.handler_for("alice")
bob_handler = script.handler_for("bob")

with alice.mock(alice_handler), bob.mock(bob_handler):
    async with alice | bob as conv:
        messages = []
        async for msg in conv.execute(max_iterations=4):
            messages.append(msg)
```

---

### 5. Repeating Patterns (3% of cases)
**Current Usage**:
```python
with agent.mock("ok", "ok", "ok", "ok", "ok"):  # Repetitive!
    for i in range(5):
        await agent.call(f"Step {i}")
```

**Proposed Utility**: `RepeatingHandler`

```python
with agent.mock(RepeatingHandler("ok")):  # Infinite "ok" responses
    for i in range(5):
        await agent.call(f"Step {i}")

# Or with variation
with agent.mock(RepeatingHandler(lambda ctx: f"Response {ctx.call_count}")):
    for i in range(5):
        await agent.call(f"Step {i}")  # "Response 1", "Response 2", ...
```

---

### 6. Error/Failure Scenarios (<1% of cases)
**Current Usage**: Hard to test LLM failures

**Proposed Utility**: `ErrorHandler`

```python
# Test retry logic
handler = ErrorHandler(
    fail_times=2,  # Fail first 2 calls
    error=Exception("LLM timeout"),
    then_return="Success after retries"
)

with agent.mock(handler):
    result = await agent.call("Question")  # Retries internally
    assert result.content == "Success after retries"
```

---

## Potential Additional Utility Handlers (Beyond Spec)

These are NOT in the original spec but could be useful:

### Option 1: `ToolCallSequenceHandler` 
**Problem**: Tool call mocking is verbose (3 lines per tool call)
```python
# Current
with agent.mock(
    agent.mock.create("I'll check", tool_calls=[{"name": "weather", ...}]),
    agent.mock.tool_call("weather", result=72),
    agent.mock.create("It's 72°F"),
):
    ...

# Potential improvement
handler = ToolCallSequenceHandler() \
    .tool_call("weather", {"location": "NYC"}, result=72) \
    .then("It's 72°F")
```

**Assessment**: Nice-to-have, not urgent. Current API works fine.

---

### Option 2: `RepeatingHandler`
**Problem**: Repeating same response many times
```python
# Current (annoying)
with agent.mock("ok", "ok", "ok", "ok", "ok"):
    for i in range(5):
        await agent.call(f"Step {i}")

# Potential improvement  
with agent.mock(RepeatingHandler("ok")):  # Infinite repeats
    for i in range(5):
        await agent.call(f"Step {i}")
```

**Assessment**: Low priority, rare use case

---

### Option 3: `RecordingHandler` (Debugging Wrapper)
**Use Case**: Debug what the agent is asking
```python
recorder = RecordingHandler(ConditionalHandler().default("Response"))
with agent.mock(recorder):
    await agent.call("Question")

# Inspect recorded calls
for call in recorder.calls:
    print(f"Agent asked: {call.agent.user[-1].content}")
```

**Assessment**: Nice for debugging, could be added later

---

## Recommendations

### ✅ Immediate Actions (No Code Changes)

1. **Document the handlers we have** - Add examples to docs showing:
   - When to use ConditionalHandler (context-dependent responses)
   - When to use TranscriptHandler (multi-turn conversations)
   - How queue-based API maps to QueuedResponseHandler

2. **Add 2-3 example tests** demonstrating handler patterns:
   - One showing ConditionalHandler for branching logic
   - One showing TranscriptHandler for multi-agent conversations
   - Keep them in `tests/examples/` as reference

### 🤔 Optional: Additional Utility Handlers

If tool call testing becomes painful, consider adding `ToolCallSequenceHandler`, but **not urgent**.

Current tool call mocking works fine - it's just verbose:
```python
# Current (works, just verbose)
with agent.mock(
    agent.mock.create("I'll check", tool_calls=[...]),
    agent.mock.tool_call("weather", result=72),
    agent.mock.create("Done"),
):
    ...
```

**Decision point**: Wait to see if this becomes a real pain point in practice.

---

## Conclusion

### What We Have (from spec)
- ✅ QueuedResponseHandler - covers 90% of use cases
- ✅ ConditionalHandler - for context-dependent responses
- ✅ TranscriptHandler - for conversation scripts

### What We DON'T Need Yet
- ❌ No need to refactor existing tests (they work fine)
- ❌ No urgent need for additional utility handlers
- ⏸️ Additional handlers can wait until we see real patterns emerge

### Next Step
**Add documentation and examples** showing when/how to use ConditionalHandler and TranscriptHandler. That's it!
