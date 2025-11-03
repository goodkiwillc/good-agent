# Message Rendering Architecture Analysis

## Current State

### Two Rendering Paths

**Path 1: LLM Consumption (via `format_message_list_for_llm`)**
```
Agent.call()
  → LanguageModel.format_message_list_for_llm()
    → Fires MESSAGE_RENDER_BEFORE event ✅
    → Processes content_parts
    → Fires MESSAGE_RENDER_AFTER event ✅
    → Returns formatted messages for API
```

**Path 2: Display/Printing (via `Message.render()`)**
```
agent.print() / utilities.print_message()
  → Message.render(mode)
    → Directly renders content_parts
    → NO events fired ❌
    → Returns string
```

### Current Event Usage
- **MESSAGE_RENDER_BEFORE/AFTER**: Only fired in `format_message_list_for_llm` (llm.py:855, 922)
- **MESSAGE_PART_RENDER**: Defined in enum but never fired
- Used by: CitationManager, LogfireTracking

## The Problem

CitationManager needs to transform content for DISPLAY mode, but `Message.render()` doesn't fire events.

```python
# This works (LLM path):
agent.call("question")  # MESSAGE_RENDER_BEFORE fires, citations transformed ✅

# This doesn't work (Display path):
message.render(RenderMode.DISPLAY)  # No events, citations not transformed ❌
```

## Architectural Options

### Option A: Message.render() Fires Events (Event-Driven)

**Implementation:**
```python
# In Message.render()
def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
    if self.agent:
        # Fire BEFORE event
        ctx = self.agent.apply_sync(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            message=self,
            mode=mode,
            output=self.content_parts
        )
        content_parts = ctx.parameters.get("output", self.content_parts)

    # Render parts
    result = "\n".join(self._render_part(part, mode) for part in content_parts)

    if self.agent:
        # Fire AFTER event
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
- ✅ Unified event model - both paths fire events
- ✅ Clean separation - CitationManager hooks events
- ✅ Other components can also transform (e.g., LogfireTracking)
- ✅ Consistent with existing LLM rendering path
- ✅ Message remains a data object (just fires events)

**CONS:**
- ⚠️ **RECURSION RISK**: If event handler calls `message.render()`, infinite loop
- ⚠️ **ASYNC COMPLEXITY**: `apply_sync` vs `apply` - Message.render() is sync
- ⚠️ Message now depends on Agent (already does via `self.agent`)
- ⚠️ Performance overhead for every render call
- ⚠️ Events in a render method feels conceptually odd

**Recursion Mitigation:**
```python
# Use render stack (already exists for templates)
render_key = f"{id(self)}:{mode.value}"
if render_key in _get_render_stack():
    return self._rendered_cache.get(mode, "[Recursion]")

_get_render_stack().add(render_key)
try:
    # Fire events and render
finally:
    _get_render_stack().remove(render_key)
```

**Verdict:** Recursion risk is manageable with existing stack tracking.

---

### Option B: Agent-Level Rendering Service (Separation Pattern)

**Implementation:**
```python
class Agent:
    def render_message(
        self,
        message: Message,
        mode: RenderMode = RenderMode.DISPLAY
    ) -> str:
        """Render a message with full event pipeline."""

        # Fire BEFORE event
        ctx = self.apply_sync(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            message=message,
            mode=mode,
            output=message.content_parts
        )

        # Let message do its rendering
        result = message._render_internal(mode, ctx.parameters.get("output"))

        # Fire AFTER event
        ctx = self.apply_sync(
            AgentEvents.MESSAGE_RENDER_AFTER,
            message=message,
            mode=mode,
            output=result
        )

        return ctx.output or result
```

**Message.render() becomes:**
```python
def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
    """Render message. Use agent.render_message() for event-driven rendering."""
    if self.agent:
        return self.agent.render_message(self, mode)
    else:
        return self._render_internal(mode)
```

**PROS:**
- ✅ Clear separation: Agent orchestrates, Message is pure data
- ✅ No recursion - Message.render() delegates to Agent
- ✅ Event logic lives in Agent, not Message
- ✅ Message can still render independently (no agent)
- ✅ Easy to test - mock Agent.render_message()

**CONS:**
- ⚠️ Breaking change if external code calls `message.render()` directly
- ⚠️ Two ways to render: `message.render()` vs `agent.render_message()`
- ⚠️ More complexity - delegation pattern
- ⚠️ Still need to update all `message.render()` call sites

**Verdict:** Better separation but more complexity and breaking changes.

---

### Option C: Component-Level Rendering Wrapper (Explicit Pattern)

**Implementation:**
```python
class CitationManager:
    def render_message(
        self,
        message: Message,
        mode: RenderMode = RenderMode.DISPLAY
    ) -> str:
        """Render message with citation transformations."""

        # Get base rendering
        content = message.render(mode)

        # Transform based on mode
        if message.citations:
            if mode == RenderMode.DISPLAY:
                content = self._transform_for_display(content, message.citations)
            elif mode == RenderMode.LLM:
                content = self._transform_for_llm(content, message.citations)

        return content
```

**Usage:**
```python
# Application code needs to be aware of CitationManager
citation_manager = agent[CitationManager]
rendered = citation_manager.render_message(message, RenderMode.DISPLAY)
```

**PROS:**
- ✅ No events, no recursion
- ✅ Simple, explicit
- ✅ Message unchanged
- ✅ Easy to test

**CONS:**
- ❌ Not automatic - application must know to use CitationManager
- ❌ Breaks separation - application aware of component
- ❌ Doesn't work for agent.print() or other internal rendering
- ❌ Not scalable - what if multiple components need to transform?

**Verdict:** Too explicit, defeats purpose of AgentComponent architecture.

---

### Option D: Post-Process Hook (Transform After Render)

**Implementation:**
```python
# In Message class (or Agent)
def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
    # Render normally
    result = self._render_internal(mode)

    # Post-process hook (if agent exists)
    if self.agent:
        result = self.agent._post_process_render(result, self, mode)

    return result

# In Agent
def _post_process_render(self, content: str, message: Message, mode: RenderMode) -> str:
    """Allow components to post-process rendered content."""
    ctx = self.apply_sync(
        AgentEvents.MESSAGE_RENDER_AFTER,  # Reuse existing event
        message=message,
        mode=mode,
        output=content
    )
    return ctx.output or content
```

**PROS:**
- ✅ No recursion - rendering is done before events
- ✅ Simple hook point
- ✅ Components can transform via MESSAGE_RENDER_AFTER
- ✅ Minimal changes to Message class

**CONS:**
- ⚠️ Can't modify content_parts, only final string
- ⚠️ String manipulation less structured than part transformation
- ⚠️ Still fires event in Message.render()

**Verdict:** Simpler than Option A, but string manipulation is less elegant.

---

## Recommendation

**Choose Option A (Message.render() Fires Events) with recursion protection**

### Rationale:

1. **Architectural Consistency**: LLM rendering already fires MESSAGE_RENDER events. DISPLAY rendering should too.

2. **AgentComponent Pattern**: The whole point of AgentComponents is event-driven extensibility. Making render() fire events enables this.

3. **Recursion is Solvable**: Message.render() already has recursion detection for templates (line 322-332). Same pattern works for events.

4. **Message is Already Coupled**: Message already has `self.agent` and calls `agent.template.render_template()`. Event firing isn't increasing coupling.

5. **Multiple Components**: If LogfireTracking, CitationManager, and future components all need to transform rendering, events are the only scalable solution.

6. **Sync Events Work**: `apply_sync()` exists for exactly this purpose - synchronous event handling.

### Implementation Plan:

```python
def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
    """Render message content with event hooks for component transformations."""

    # Recursion detection
    render_key = f"{id(self)}:{mode.value}"
    render_stack = _get_render_stack()

    if render_key in render_stack:
        logger.warning(f"Recursion detected in Message.render()")
        return self._rendered_cache.get(mode, "[Error: Recursive rendering]")

    render_stack.add(render_key)

    try:
        # Check cache
        if mode in self._rendered_cache and not self._has_templates():
            return self._rendered_cache[mode]

        if not self.content_parts:
            return ""

        # Fire BEFORE event (if agent available)
        content_parts = self.content_parts
        if self.agent:
            ctx = self.agent.apply_sync(
                AgentEvents.MESSAGE_RENDER_BEFORE,
                message=self,
                mode=mode,
                output=list(content_parts)  # Copy to avoid mutation
            )
            content_parts = ctx.parameters.get("output", content_parts)

        # Render parts
        parts = [self._render_part(part, mode) for part in content_parts]
        result = "\n".join(parts)

        # Fire AFTER event (if agent available)
        if self.agent:
            ctx = self.agent.apply_sync(
                AgentEvents.MESSAGE_RENDER_AFTER,
                message=self,
                mode=mode,
                output=result
            )
            result = ctx.output or result

        # Cache result
        self._rendered_cache[mode] = result

        return result

    finally:
        render_stack.discard(render_key)
```

### Why This Is Safe:

1. **Recursion Protection**: Existing stack tracking prevents infinite loops
2. **Sync Events**: No async complexity - `apply_sync()` runs synchronously
3. **Graceful Degradation**: If no agent, renders normally
4. **Caching**: Results cached to avoid re-firing events
5. **Copy Content Parts**: Event handlers get a copy, can't break original

### Migration Path:

1. Implement in Message.render()
2. CitationManager's existing `_on_message_render_before` will start working
3. Uncomment transformation logic in manager.py
4. Tests pass

## Conclusion

**Option A is the right architectural choice** because:
- Maintains AgentComponent event-driven pattern
- Enables multiple components to transform rendering
- Recursion is already solved for templates
- Clean separation: Message fires events, Components handle them
- No breaking changes to external APIs

The key insight: **Message can remain a data object that fires events**. It doesn't need to know what those events do. Components like CitationManager handle the transformation logic.
