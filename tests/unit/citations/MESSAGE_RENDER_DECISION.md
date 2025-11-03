# Should Message.render() Exist?

## Current Usage

### 1. Internal Message Protocol Methods
```python
# messages.py:426-442
def __llm__(self) -> str:
    return self.render(RenderMode.LLM)

def __display__(self) -> str:
    return self.render(RenderMode.DISPLAY)

def __str__(self) -> str:
    return self.render(RenderMode.DISPLAY)

@property
def content(self) -> str:
    return self.render(RenderMode.DISPLAY)
```

**Purpose:** Provide standard Python protocols (`__str__`, `__repr__`) for displaying messages

### 2. Specialized Display Logic
```python
# ToolMessage.__display__() - messages.py:825
def __display__(self) -> str:
    content = self.render(RenderMode.DISPLAY)
    # Wraps XML content in code blocks
    if content.startswith("<"):
        return f"```xml\n{content}\n```"
    return content
```

**Purpose:** Post-process rendered content for specific message types

### 3. External Utility Usage
```python
# utilities.py:327
def print_message(message, render_mode=None, ...):
    if render_mode:
        content = message.render(render_mode)
```

**Purpose:** Allow external code to render messages

### 4. LLM Formatting (Indirect)
`LanguageModel._format_message_content()` doesn't call `message.render()` directly - it processes content_parts and fires events separately.

## The Confusion Factor

**Having `Message.render()` creates ambiguity:**

```python
# Which should I use?
message.render(RenderMode.DISPLAY)  # Direct rendering
agent.render_message(message, RenderMode.DISPLAY)  # Event-driven rendering

# Do they produce the same output?
# When should I use which?
```

This is especially confusing because:
- `Message.render()` fires events (as of current code) but not consistently
- For LLM rendering, you must use `format_message_list_for_llm()`, not `message.render()`
- Different rendering paths fire events differently

## Option 1: Keep Message.render() (Status Quo + Fix)

**Make it fire events consistently:**
```python
def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
    """
    Render message content with agent component transformations.

    If attached to an agent, fires MESSAGE_RENDER_BEFORE/AFTER events
    to allow components (like CitationManager) to transform content.
    """
    # Fire BEFORE event with content_parts
    if self.agent:
        ctx = self.agent.apply_sync(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            message=self,
            mode=mode,
            output=list(self.content_parts)  # Components can modify
        )
        parts = ctx.parameters.get("output", self.content_parts)
    else:
        parts = self.content_parts

    # Render parts
    result = "\n".join(self._render_part(p, mode) for p in parts)

    # Fire AFTER event
    if self.agent:
        ctx = self.agent.apply_sync(
            AgentEvents.MESSAGE_RENDER_AFTER,
            message=self,
            mode=mode,
            output=result
        )
        result = ctx.output or result

    return result
```

**PROS:**
- ✅ Works with existing code (`__str__`, `__display__`, utilities)
- ✅ No breaking changes
- ✅ Simple to fix - just adjust event parameters
- ✅ Components automatically work

**CONS:**
- ⚠️ Message calls agent (coupling)
- ⚠️ Two rendering paths still exist (this + format_message_list_for_llm)
- ⚠️ Potential confusion about when to use what
- ⚠️ Events in a data object method feels wrong architecturally

## Option 2: Remove Message.render(), Add Agent.render_message()

**Remove public render(), make it internal:**
```python
class Message:
    def _render_internal(self, mode: RenderMode) -> str:
        """Internal rendering without events. Use agent.render_message() instead."""
        parts = [self._render_part(p, mode) for p in self.content_parts]
        return "\n".join(parts)

    def __str__(self) -> str:
        """String representation. Uses agent rendering if available."""
        if self.agent:
            return self.agent.render_message(self, RenderMode.DISPLAY)
        return self._render_internal(RenderMode.DISPLAY)

    # Similar for __display__, __llm__, etc.
```

**Add agent-level rendering:**
```python
class Agent:
    def render_message(self, message: Message, mode: RenderMode = RenderMode.DISPLAY) -> str:
        """
        Render a message with full component transformation pipeline.

        This is the official way to render messages - it fires events
        allowing components like CitationManager to transform content.
        """
        # Fire BEFORE event
        ctx = self.apply_sync(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            message=message,
            mode=mode,
            output=list(message.content_parts)
        )

        # Render modified parts
        parts = ctx.parameters.get("output", message.content_parts)
        result = "\n".join(message._render_part(p, mode) for p in parts)

        # Fire AFTER event
        ctx = self.apply_sync(
            AgentEvents.MESSAGE_RENDER_AFTER,
            message=message,
            mode=mode,
            output=result
        )

        return ctx.output or result
```

**Update utilities:**
```python
def print_message(message, render_mode=None, agent=None, ...):
    if render_mode:
        agent = agent or getattr(message, 'agent', None)
        if agent:
            content = agent.render_message(message, render_mode)
        else:
            content = message._render_internal(render_mode)
```

**PROS:**
- ✅ Clear separation: Agent orchestrates, Message is pure data
- ✅ Explicit API: `agent.render_message()` is the official way
- ✅ No confusion about when to use what
- ✅ Consistent with `format_message_list_for_llm()` pattern
- ✅ Message doesn't call agent (better architecture)

**CONS:**
- ⚠️ Breaking change for external code calling `message.render()`
- ⚠️ More methods: `_render_internal()` + `agent.render_message()`
- ⚠️ Protocol methods (`__str__`) need agent awareness
- ⚠️ More complex call chain

## Option 3: Hybrid - Keep render() but Deprecate Direct Use

**Message.render() delegates to agent:**
```python
def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
    """
    Render message content.

    Deprecated: Use agent.render_message() for event-driven rendering.
    This method is kept for backward compatibility and will delegate
    to agent.render_message() if an agent is attached.
    """
    if self.agent:
        return self.agent.render_message(self, mode)
    else:
        # Fallback for messages without agent
        return self._render_internal(mode)
```

**PROS:**
- ✅ No breaking changes
- ✅ Clear migration path
- ✅ Proper separation (render delegates to agent)
- ✅ Simple fix

**CONS:**
- ⚠️ Still have two methods (`render()` + `agent.render_message()`)
- ⚠️ Deprecation means eventual breaking change

## Recommendation: **Option 1 (Keep and Fix)**

### Why:

1. **Pragmatic**: Message.render() is already used throughout the codebase and by protocol methods (`__str__`, `__display__`)

2. **Minimal Changes**: Just fix event parameter passing to be consistent

3. **Works Now**: The architecture already exists (events are already fired), just needs consistency

4. **Not Really Broken**: A data object calling agent.apply_sync() for extensibility is not inherently wrong. It's similar to how Django models fire signals or how React components call hooks.

5. **Clean Enough**: The coupling is loose (via events), not tight (direct method calls)

### The Key Fix:

**Make Message.render() pass `output=content_parts` BEFORE rendering** (like LanguageModel does):

```python
# Current (WRONG):
rendered = [self._render_part(p, mode) for p in self.content_parts]
result = "\n".join(rendered)
ctx = self.agent.apply_sync(..., content=result)  # ← Too late!

# Fixed (RIGHT):
ctx = self.agent.apply_sync(..., output=list(self.content_parts))  # ← Before rendering
parts = ctx.parameters.get("output", self.content_parts)  # ← Components can modify
rendered = [self._render_part(p, mode) for p in parts]
result = "\n".join(rendered)
```

This way:
- CitationManager modifies TextContentPart.text from `[!CITE_1!]` → `[domain](url)`
- Message renders the modified parts
- Final result has transformed citations

### Why Not Option 2?

Option 2 is architecturally purer but requires:
- Breaking changes
- More code complexity
- Migration path for existing code
- Doesn't solve any problem that Option 1 doesn't solve

**The practical win:** Fix one line (event parameter) vs refactor entire rendering system.

## Conclusion

**Keep `Message.render()`** but fix event parameter consistency:

```python
# Before rendering parts, let components modify them:
if self.agent:
    ctx = self.agent.apply_sync(
        AgentEvents.MESSAGE_RENDER_BEFORE,
        message=self,
        mode=mode,
        output=list(self.content_parts)  # ← Pass parts, not rendered string
    )
    parts_to_render = ctx.parameters.get("output", self.content_parts)
else:
    parts_to_render = self.content_parts

# Now render the (possibly modified) parts
rendered_parts = [self._render_part(p, mode) for p in parts_to_render]
result = "\n".join(rendered_parts)

# Optional: Fire AFTER event for notification
if self.agent:
    self.agent.do(
        AgentEvents.MESSAGE_RENDER_AFTER,
        message=self,
        mode=mode,
        rendered_content=result
    )
```

This maintains the existing architecture while making it work correctly for CitationManager.
