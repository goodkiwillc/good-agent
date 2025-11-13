# API Design Issues

## Overview

The API surface is large and sometimes inconsistent, with multiple ways to accomplish the same tasks and unclear boundaries between public and internal APIs.

---

## 1. Multiple Ways to Add Messages

### Problem: Too Many Message Creation Patterns

```python
# Method 1: Direct append
agent.append("Hello", role="user")

# Method 2: Create then add
msg = agent.model.create_message("Hello", role="user")
agent.append(msg)

# Method 3: Direct assignment (Messages)
agent.messages.append(msg)

# Method 4: Internal method (used by call/execute)
agent._append_message(msg)

# Method 5: add_tool_response (special case)
agent.add_tool_response("result", tool_call_id="123")
```

**Issues:**
- 5 different ways to add messages
- Unclear which is preferred
- Different validation/event behavior
- Internal `_append_message` vs public `append`

**Recommendation:**

Simplify to 2 patterns:

```python
# Pattern 1: Convenience method (most common)
agent.append("Hello")  # User message by default
agent.append("Response", role="assistant")

# Pattern 2: Full control
msg = Message(content="Hello", role="user")
agent.messages.append(msg)  # Direct list access

# Remove:
# - add_tool_response (use append with role="tool")
# - _append_message (make append the canonical method)
```

---

## 2. Call vs Execute Confusion

### Problem: Similar Methods with Different Behavior

```python
# Method 1: call() - Get single response
response = await agent.call("Question")

# Method 2: execute() - Iterator over messages
async for msg in agent.execute():
    print(msg)

# Method 3: call() can also accept no input if messages already added
agent.append("Question")
response = await agent.call()

# Method 4: execute() auto-executes tools by default
async for msg in agent.execute(auto_execute_tools=True):
    ...
```

**Issues:**
- Naming doesn't clearly indicate difference
- `call()` and `execute()` do similar things
- Both can work with/without input
- Auto-execution behavior confusing

**Better Names:**

```python
# Clear distinction:
await agent.respond(prompt)      # Single response
async for msg in agent.run():    # Full execution loop

# Or:
await agent.chat(prompt)         # Conversational
async for msg in agent.execute(): # Step-by-step execution
```

**Better Documentation:**

```python
async def call(self, prompt: str | None = None) -> AssistantMessage:
    """Get a single response from the LLM.
    
    Adds prompt as user message (if provided), calls LLM, executes
    any requested tools, and returns final assistant response.
    
    For step-by-step control, use execute() instead.
    """

async def execute(self) -> AsyncIterator[Message]:
    """Execute agent loop with full control over each step.
    
    Yields each message (assistant, tool) as it's created.
    Use for streaming or custom tool execution logic.
    """
```

---

## 3. Too Many Ways to Access Messages

### Problem: Overlapping Message Access Patterns

```python
# Access pattern 1: Index
agent[0]           # First message
agent[-1]          # Last message

# Access pattern 2: messages property
agent.messages[0]  # Same as agent[0]

# Access pattern 3: Filtered properties
agent.user         # FilteredMessageList[UserMessage]
agent.assistant    # FilteredMessageList[AssistantMessage]
agent.tool         # FilteredMessageList[ToolMessage]

# Access pattern 4: filter method
agent.messages.filter(role="user")  # Same as agent.user

# Access pattern 5: role-specific lists
agent.user[0]      # First user message
agent.user[-1]     # Last user message
```

**Issues:**
- 5 different ways to get messages
- `agent[0]` vs `agent.messages[0]` - which is preferred?
- `agent.user` vs `agent.messages.filter(role="user")` - redundant

**Recommendation:**

Choose a primary pattern:

```python
# Option A: Keep index access, filtered properties
agent[0]              # Direct index
agent[-1]             # Last message
agent.user            # User messages
agent.assistant       # Assistant messages

# Remove: agent.messages[...] direct access
# Keep: agent.messages for full list reference

# Option B: Explicit is better
agent.messages[0]     # Direct index
agent.messages[-1]    # Last message
agent.user_messages   # Explicit plural
agent.assistant_messages

# Remove: agent[...] magic indexing
```

**Recommended: Option A** - More concise for common operations.

---

## 4. State Management Confusion

### Problem: Multiple State Representations

```python
# State representation 1: state property
agent.state  # Returns AgentState enum

# State representation 2: ready() method
await agent.ready()  # Waits until READY

# State representation 3: _ready_event
agent._ready_event  # Internal asyncio.Event

# State representation 4: Boolean checks
if agent.state >= AgentState.READY:
    ...

# State representation 5: State transitions
agent.update_state(AgentState.READY)  # Public method
```

**Issues:**
- Users need to understand AgentState enum
- Unclear when to use `state` vs `ready()`
- Public `update_state()` seems dangerous
- State machine implementation leaks into public API

**Recommendation:**

Simplify state API:

```python
# Public API: Simple boolean checks
agent.is_ready  # Property, not method
agent.is_processing
agent.is_waiting_for_tools

# Internal: State machine
agent._state  # Internal enum
agent._update_state()  # Internal method

# Initialization:
await agent.ready()  # Only public async method

# Users rarely need to check state directly
# Most operations should handle state automatically
```

---

## 5. Tool Registration Patterns

### Problem: Inconsistent Tool Registration

```python
# Pattern 1: Constructor
agent = Agent(tools=[search_tool, calculator])

# Pattern 2: Direct assignment
agent.tools["search"] = search_tool

# Pattern 3: register_tool method
await agent.tools.register_tool(search_tool)

# Pattern 4: String patterns
agent = Agent(tools=["namespace:*", "specific_tool"])

# Pattern 5: Component @tool decorator
class MyComponent(AgentComponent):
    @tool
    async def my_tool(self, ...): ...

# Pattern 6: invoke() for manual execution
await agent.invoke("search", query="test")
```

**Issues:**
- 6 different ways to register/use tools
- Unclear which is preferred
- String patterns undocumented
- `invoke()` vs `call()` vs `execute()` confusion

**Recommendation:**

Simplify to 3 clear patterns:

```python
# Pattern 1: Constructor (declarative)
agent = Agent(tools=[search_tool, calculator])

# Pattern 2: Component system (for complex tools)
class SearchExtension(AgentExtension):
    @tool
    async def search(self, query: str) -> str:
        ...

agent = Agent(extensions=[SearchExtension()])

# Pattern 3: Runtime addition (dynamic)
await agent.tools.add(search_tool)

# Remove:
# - Direct dictionary assignment (agent.tools["name"] = ...)
# - String patterns (magic, undocumented)
# - invoke() for manual execution (use tools directly if needed)
```

---

## 6. Configuration API

### Problem: Multiple Configuration Sources

```python
# Config source 1: Constructor kwargs
agent = Agent(model="gpt-4", temperature=0.7)

# Config source 2: AgentConfigParameters TypedDict
config: AgentConfigParameters = {
    "model": "gpt-4",
    "temperature": 0.7
}
agent = Agent(**config)

# Config source 3: AgentConfigManager
config_manager = AgentConfigManager(model="gpt-4")
agent = Agent(config_manager=config_manager)

# Config source 4: agent.config property (runtime)
agent.config.temperature = 0.8

# Config source 5: Model-specific overrides
agent.model.config.temperature = 0.8
```

**Issues:**
- 5 different ways to set configuration
- Unclear which takes precedence
- Runtime changes may not work as expected
- Split between agent config and model config

**Recommendation:**

Simplify configuration:

```python
# Pattern 1: Constructor (most common)
agent = Agent(model="gpt-4", temperature=0.7)

# Pattern 2: Config dict (for complex setups)
config = AgentConfig(
    model="gpt-4",
    temperature=0.7,
    tools=["search"],
)
agent = Agent(config=config)

# Pattern 3: Runtime changes (limited)
agent.config.update(temperature=0.8)  # Only safe parameters

# Remove:
# - Direct property assignment (agent.config.temperature = ...)
# - Model-specific config access (consolidate into agent.config)
# - ConfigManager as separate concept (merge into Config)
```

---

## 7. Context and Forking

### Problem: Overlapping Context Operations

```python
# Pattern 1: fork()
forked = agent.fork()

# Pattern 2: fork_context() (context manager)
async with agent.fork_context() as forked:
    ...

# Pattern 3: thread_context()
async with agent.thread_context() as ctx_agent:
    ...

# Pattern 4: copy()
copied = agent.copy()
```

**Issues:**
- 4 different ways to create agent variants
- `fork()` vs `fork_context()` vs `thread_context()` vs `copy()` unclear
- When to use which?
- What's the difference?

**Current Semantics (from code):**
- `fork()`: Creates independent copy with shared message history
- `fork_context()`: Temporary fork, discarded after context
- `thread_context()`: Temporary fork, changes merged back
- `copy()`: Full independent copy

**Recommendation:**

Clarify naming and reduce options:

```python
# Option 1: Explicit names
agent.clone()                    # Full independent copy
agent.snapshot()                 # Fork with shared history
async with agent.temporary():    # Temporary context (discarded)
async with agent.branch():       # Branch context (merged)

# Option 2: Single context manager with modes
async with agent.context(mode="temporary"):
    ...
async with agent.context(mode="branch"):
    ...

# Remove:
# - fork() / copy() confusion
# - fork_context() naming
```

**Recommended: Option 1** - More explicit and Pythonic.

---

## 8. Event Subscription API

### Problem: Multiple Event Subscription Patterns

```python
# Pattern 1: @agent.on() decorator
@agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
async def handler(ctx):
    ...

# Pattern 2: Component.on() decorator
class MyComponent(AgentComponent):
    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    async def handler(self, ctx):
        ...

# Pattern 3: Explicit registration (?)
agent.register_handler(AgentEvents.MESSAGE_APPEND_AFTER, handler)

# Pattern 4: Priority specification
@agent.on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
async def handler(ctx):
    ...
```

**Issues:**
- Multiple subscription methods
- Priority system adds complexity
- Unclear how component handlers work vs agent handlers
- No unsubscribe mechanism obvious

**Recommendation:**

Simplify event API:

```python
# Pattern 1: Agent-level events (for user code)
@agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
async def handler(event):
    ...

# Pattern 2: Component events (for extensions)
class MyExtension(AgentExtension):
    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    async def handler(self, event):
        ...

# Remove:
# - Priority system (over-engineered)
# - Multiple subscription methods
# - Complex event context (simplify to event object)
```

---

## 9. Type Annotations Inconsistency

### Problem: Inconsistent Type Annotations

```python
# Some methods: Full typing
async def call(
    self,
    *content_parts: MessageContent,
    role: Literal["user", "assistant", "system", "tool"] = "user",
    response_model: type[T_Output] | None = None,
    **kwargs: Any,
) -> AssistantMessage | AssistantMessageStructuredOutput[T_Output]:
    ...

# Other methods: Minimal typing
def append(
    self,
    *content_parts: MessageContent,
    role: MessageRole = "user",
    **kwargs: Any,
) -> None:
    ...

# Some methods: Overloads
@overload
async def call(..., response_model: None = None) -> AssistantMessage: ...

@overload
async def call(..., response_model: type[T_Output]) -> AssistantMessageStructuredOutput[T_Output]: ...
```

**Issues:**
- Inconsistent use of overloads
- Mix of `Literal` and type aliases
- Some `Any` types where more specific possible
- Complex generic types hard to use

**Recommendation:**

Standardize type annotations:

```python
# Use overloads for major API methods
@overload
async def call(self, prompt: str) -> AssistantMessage: ...

@overload
async def call(
    self, 
    prompt: str, 
    response_model: type[T]
) -> AssistantMessageStructuredOutput[T]: ...

# Use type aliases for clarity
MessageRole = Literal["user", "assistant", "system", "tool"]
ContentPart = str | dict[str, Any] | BaseModel

# Avoid Any when possible
def append(
    self,
    *content: ContentPart,
    role: MessageRole = "user",
    **kwargs: Unpack[MessageOptions],  # Instead of Any
) -> None:
    ...
```

---

## 10. Property vs Method Confusion

### Problem: Inconsistent Use of Properties vs Methods

```python
# Properties (no parens):
agent.messages      # Property
agent.user          # Property
agent.state         # Property
agent.config        # Property

# Methods (with parens):
await agent.ready()       # Method (async!)
agent.print()             # Method
agent.validate_message_sequence()  # Method

# Inconsistent:
agent.extensions         # Property (dict)
agent.current_version    # Property (computed)
agent.get_task_count()   # Method (simple getter)
```

**Python Conventions:**
- Property: Cheap computation, no side effects, feels like attribute
- Method: Expensive, has side effects, action-oriented

**Issues:**
- `ready()` is async but has no verb (could be `is_ready` property?)
- `get_task_count()` could be `task_count` property
- Some computed properties are expensive

**Recommendation:**

Follow conventions strictly:

```python
# Properties: Cheap, no side effects
agent.messages          # ✅ List reference
agent.user              # ✅ Filter (cached?)
agent.state             # ✅ Enum value
agent.task_count        # ✅ Simple counter (was get_task_count())
agent.is_ready          # ✅ Boolean (was ready() method)

# Methods: Async, side effects, expensive
await agent.initialize()    # ✅ Async setup (was ready())
agent.print_message(msg)    # ✅ Side effect
agent.validate_sequence()   # ✅ Expensive operation
await agent.wait_for_ready()  # ✅ Blocking operation
```

---

## 11. Public API Surface Size

### Problem: Very Large Public API

Counting public methods/properties on `Agent` class:

```
Core operations: ~10
  - call, execute, append, etc.

Message access: ~15
  - messages, user, assistant, tool, system, etc.

State/lifecycle: ~8
  - state, ready, update_state, etc.

Configuration: ~5
  - config, context, etc.

Tool operations: ~5
  - tools, invoke, etc.

Component system: ~8
  - extensions, register, etc.

Versioning: ~6
  - current_version, revert_to_version, etc.

Context operations: ~4
  - fork, fork_context, thread_context, copy

Task management: ~5
  - create_task, get_task_count, etc.

Utilities: ~8
  - print, validate, etc.

Total: ~74 public methods/properties
```

**Issues:**
- Very large API surface
- High cognitive load
- Hard to document
- Many rarely-used methods

**Recommendation:**

Reduce public API:

```python
# Core (10-15 methods)
class Agent:
    # Essential operations
    async def chat(self, prompt) -> Message
    async def run(self) -> AsyncIterator[Message]
    def append(self, content, **opts) -> None
    
    # Essential properties
    messages: MessageList
    config: AgentConfig
    tools: ToolManager
    
# Move advanced features to managers/registries:
agent.versioning.revert_to(index)      # Not agent.revert_to_version()
agent.tasks.create(coro)                # Not agent.create_task()
agent.components.register(ext)          # Not agent.register_extension()
```

---

## 12. Summary of API Issues

| Issue | Severity | Impact | Recommendation |
|-------|----------|--------|----------------|
| Multiple message creation methods | HIGH | Confusion | Consolidate to 2 patterns |
| call() vs execute() naming | HIGH | Unclear intent | Rename or better docs |
| Too many message access patterns | MEDIUM | Inconsistent usage | Choose primary pattern |
| State management confusion | MEDIUM | Implementation leak | Simplify to boolean checks |
| Tool registration inconsistency | HIGH | Hard to learn | Reduce to 3 patterns |
| Configuration complexity | MEDIUM | Hard to understand | Simplify to 2-3 patterns |
| Context/fork confusion | MEDIUM | Unclear semantics | Better naming |
| Event subscription complexity | LOW | Over-engineered | Simplify, remove priority |
| Large public API | HIGH | High cognitive load | Reduce to core operations |

---

## 13. API Refactoring Priority

### Phase 1: Core API (2 weeks)
- Consolidate message operations
- Clarify call() vs execute()
- Reduce Agent public methods

### Phase 2: Configuration (1 week)
- Simplify configuration API
- Consolidate config sources
- Better type annotations

### Phase 3: Advanced Features (1 week)
- Better naming for fork/context operations
- Simplify event system
- Refactor state management

### Phase 4: Documentation (1 week)
- API reference
- Migration guide
- Best practices

---

## 14. Example of Improved API

### Before (Current):

```python
agent = Agent(model="gpt-4", tools=[search])
await agent.ready()
agent.append("Question", role="user")
response = await agent.call()
print(agent[-1].content)
```

### After (Proposed):

```python
agent = Agent("gpt-4", tools=[search])  # Auto-initializes
response = await agent.chat("Question")  # Simpler
print(response.content)  # Direct access
```

Or with context manager:

```python
async with Agent("gpt-4", tools=[search]) as agent:
    response = await agent.chat("Question")
    print(response.content)
```
