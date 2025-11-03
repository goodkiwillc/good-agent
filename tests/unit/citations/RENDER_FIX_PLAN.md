# Citation Rendering Fix Plan

## Problem
Citations are stored in `[!CITE_X!]` format but not being transformed for DISPLAY mode rendering.

## Current Behavior
```python
# After message creation:
message.content_parts[0].text = "Research shows [!CITE_1!] that citations work."
message.citations = ["https://example.com/study.pdf"]

# When rendering for DISPLAY:
message.render(RenderMode.DISPLAY) # Returns: "Research shows [!CITE_1!] that citations work."
# ❌ Should return: "Research shows [example.com](https://example.com/study.pdf) that citations work."
```

## Root Cause
1. MESSAGE_RENDER_BEFORE only fires for LLM rendering (in `format_message_list_for_llm`)
2. Direct `message.render()` calls don't trigger events
3. Previous attempt to hook MESSAGE_RENDER_BEFORE caused recursion

## Solution Options

### Option 1: Transform at Render Time (Current Attempt - Has Recursion Issues)
Hook MESSAGE_RENDER_BEFORE to transform content_parts based on mode.
**Problem:** Causes recursion when event handler tries to render content.

### Option 2: Custom ContentPart Type
Create `CitationContentPart` that knows how to render itself differently for each mode.
**Pros:** Clean separation, no recursion
**Cons:** More complex, requires changing content part creation

### Option 3: Post-Process Rendered String
Let message render normally, then post-process the string to replace `[!CITE_X!]` with links.
**Pros:** Simple, no recursion
**Cons:** String manipulation, less structured

### Option 4: Store Multiple Representations
Store both LLM format (`[!CITE_X!]`) and DISPLAY format in content parts.
**Pros:** Fast rendering
**Cons:** More memory, duplication

### Option 5: Transform Content Parts Directly (No Events)
Instead of using MESSAGE_RENDER_BEFORE (which is async and can cause recursion),
directly transform the content_parts array before Message.render() processes them.
**Pros:** No events, no recursion, direct control
**Cons:** Requires modifying Message class or creating a wrapper

## Recommended Approach: Option 3 (Post-Process)

Implement transformation AFTER rendering, not during:

1. Let Message.render() complete normally → Returns string with `[!CITE_X!]`
2. If mode == DISPLAY, post-process the string:
   - Replace `[!CITE_(\d+)!]` with markdown links using message.citations
   - Replace `idx="(\d+)"` with `url="..."` in XML

This avoids recursion because we're not triggering any events or calling render() again.

### Implementation

```python
@on(AgentEvents.MESSAGE_RENDER_AFTER, priority=150)
def _on_message_render_after(self, ctx: EventContext) -> None:
    """Transform rendered output based on mode."""
    mode = ctx.parameters.get("mode")
    message = ctx.parameters.get("message")
    output = ctx.output  # Already rendered string or list

    if not message or not mode or not hasattr(message, "citations"):
        return

    if mode == RenderMode.DISPLAY and message.citations:
        # Post-process the rendered output
        transformed = self._transform_for_display(output, message.citations)
        ctx.output = transformed
```

Wait - but MESSAGE_RENDER_AFTER also only fires for LLM rendering!

## Alternative: Monkey-patch or Wrapper

Since `Message.render()` doesn't fire events for DISPLAY mode, we need to either:

1. **Modify Message class** to fire events (risky)
2. **Wrap render method** when CitationManager is installed
3. **Use a different hook point** - maybe MESSAGE_APPEND_AFTER?

Actually, the simplest solution is to **transform content at creation time based on target mode**.

## SIMPLEST SOLUTION: Store Raw, Transform on Access

Store content in a neutral format and transform when content_parts are accessed for rendering:

1. **At creation:** Store in LLM format `[!CITE_X!]`
2. **When content_parts accessed:** Return transformed parts based on context

But this requires modifying how content_parts work.

## PRACTICAL SOLUTION: Transform During Part Rendering

Override `_render_part()` or use a custom TextContentPart that knows about citations.

Actually - let me check if we can use MESSAGE_PART_RENDER event...
