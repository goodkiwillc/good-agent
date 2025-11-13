# Naming Convention Issues

## Overview

While the codebase generally follows Python conventions, there are inconsistencies in naming patterns, unclear naming choices, and confusion between similar concepts.

---

## 1. utilities vs core Naming Confusion

The biggest naming issue is the unclear distinction between `utilities/` and `core/`:

**Questions:**
- What makes something a "utility" vs "core"?
- Why do utilities re-export core modules?
- When should I import from which?

**Current State:**
```python
# Both exist and are used interchangeably:
from good_agent.utilities.event_router import EventRouter
from good_agent.core.event_router import EventRouter

from good_agent.utilities.ulid_monotonic import create_monotonic_ulid
from good_agent.core.ulid_monotonic import create_monotonic_ulid
```

**Recommendation:**
- Choose one: Either `core/` for foundational modules, `utils/` for helpers
- If keeping both, establish clear semantic distinction:
  - `core/`: Internal implementation details, complex logic
  - `utilities/`: Public helper functions, convenience wrappers
- Document the distinction in CONTRIBUTING.md

---

## 2. Context vs AgentContext

Two similar names for different concepts:

```python
from .context import Context as AgentContext  # Template variable context
from .utilities.event_router import EventContext  # Event handling context
```

**Issues:**
- Confusing: Both are "contexts" but serve different purposes
- Import aliasing indicates awareness of the problem
- EventContext is more specific, AgentContext is vague

**Better Names:**
```python
# Current
Context  # What kind of context?
AgentContext  # Still vague
EventContext  # Clear!

# Suggested
TemplateContext  # or VariableContext
AgentContext → AgentTemplateContext
EventContext  # Keep as is (good name)
```

---

## 3. Message Type Naming

Message types follow good naming pattern:

```python
SystemMessage    ✅ Clear
UserMessage      ✅ Clear
AssistantMessage ✅ Clear
ToolMessage      ✅ Clear
```

But there are inconsistencies in related types:

```python
# Message content related:
MessageContent      # Union type - good
MessageRole         # Literal type - good
MessageList         # Container - good

# But then:
FilteredMessageList  # Good, descriptive
T_Message           # Type variable - inconsistent prefix
P_Message           # Type variable - inconsistent prefix (P usually for ParamSpec)
```

**Recommendation:**
```python
# Standardize type variable naming:
MessageT  # Type variable for messages
ContentT  # Type variable for content
RoleT     # Etc.
```

---

## 4. Component vs Extension

Inconsistent terminology for the same concept:

```python
class AgentComponent(EventRouter):  # Called "Component" in class name
    """Base class for agent extensions..."""  # Called "Extension" in docs
    
# In Agent class:
self._extensions: dict[type[AgentComponent], AgentComponent]  # "extensions"
self._extension_names: dict[str, AgentComponent]

# In config:
extensions: list[AgentComponent] | None = None  # parameter name

# In events:
AgentEvents.EXTENSION_INSTALL  # event name
AgentEvents.EXTENSION_ERROR
```

**The codebase uses both terms interchangeably:**
- Class: `AgentComponent`
- Docs: "extensions"
- Variables: `_extensions`
- Events: `EXTENSION_*`

**Recommendation:**

Pick one term and use consistently:

**Option A: "Component"** (matches class name)
```python
class AgentComponent: pass
self._components: dict[...]
components: list[AgentComponent]
AgentEvents.COMPONENT_INSTALL
```

**Option B: "Extension"** (more intuitive, matches usage)
```python
class AgentExtension: pass  # Rename class
self._extensions: dict[...]
extensions: list[AgentExtension]
AgentEvents.EXTENSION_INSTALL
```

**Recommended: Option B** - "Extension" is more intuitive for plugins.

---

## 5. Manager Naming Pattern

Good use of "Manager" suffix for coordinator classes:

```python
ToolManager          ✅ Manages tools
TemplateManager      ✅ Manages templates
ConfigManager        ✅ Manages config
ModelManager         ✅ Manages models
```

But inconsistent application:

```python
# These coordinate/manage but don't use "Manager":
MessageList          # Could be MessageManager?
ComponentRegistry    # Could be ComponentManager?
VersionManager       ✅ Good
MessageRegistry      # Different from VersionManager how?
```

**Questions:**
- When to use "Manager" vs "Registry" vs class name only?
- What's the semantic difference?

**Current patterns:**
- `*Manager`: Active coordinator with logic
- `*Registry`: Passive storage/lookup
- `*List`: Collection with operations

**Recommendation:**

Be consistent:
```python
# Managing/coordinating:
ToolManager
TemplateManager
ModelManager
MessageManager  # Consider renaming MessageList?
ComponentManager  # Consider renaming ComponentRegistry?

# Pure storage/lookup:
MessageRegistry  # Lookup by ID
ToolRegistry  # Lookup by name
ComponentRegistry  # Lookup by type

# Collections:
MessageList  # Ordered collection with operations
FilteredMessageList
```

---

## 6. Private Attribute Naming

Inconsistent use of single vs double underscore:

```python
# In Agent class:
_agent: Agent | None           # Single underscore
_extensions: dict[...]         # Single underscore
_version_id: ULID              # Single underscore
__registry__: ClassVar[...]    # Double underscore (class-level)

# In components:
_agent: Agent | None           # Single underscore
_enabled: bool                 # Single underscore
__depends__: list[str]         # Double underscore (class-level config)
```

**Observation:**
- Instance attributes: Single underscore (good)
- Class-level config: Double underscore (acceptable)
- But `__registry__` could be `_registry` (class variable, not special)

**Recommendation:**

Follow PEP 8 strictly:
- Single underscore: Internal/private (normal use)
- Double underscore: Name mangling (rarely needed)
- Double underscore both sides: Special/magic (Python internals only)

```python
# Good:
_agent: Agent | None
_extensions: dict[...]

# Questionable (unless name mangling needed):
__depends__: list[str]  # Could be _depends

# Special (keep):
__init__, __call__, __getitem__  # Python magic methods
```

---

## 7. Event Naming

Good consistent pattern for events:

```python
# Pattern: NOUN_VERB or NOUN_VERB_TIMING
AGENT_INIT_AFTER
AGENT_STATE_CHANGE
MESSAGE_APPEND_AFTER
MESSAGE_REPLACE_BEFORE
TOOL_CALL_BEFORE
TOOL_CALL_AFTER
LLM_COMPLETE_BEFORE
LLM_COMPLETE_AFTER
EXTENSION_INSTALL
EXTENSION_ERROR
```

**Observation:** Events use consistent naming convention ✅

Minor inconsistencies:
```python
AGENT_INIT_AFTER    # No "BEFORE" equivalent
EXTENSION_INSTALL   # No "_AFTER" suffix (but EXTENSION_INSTALL_AFTER exists)
```

**Recommendation:**

Ensure every lifecycle event has BEFORE/AFTER pair:
```python
# If you have:
AGENT_INIT_AFTER  

# Consider adding:
AGENT_INIT_BEFORE  # Or remove the suffix if no BEFORE needed
```

---

## 8. Boolean Flag Naming

Inconsistent naming for boolean flags:

```python
# Good (positive framing):
enabled: bool = True
use_sandbox: bool = True
auto_execute_tools: bool = True

# Inconsistent:
_event_trace: bool | None = None  # Should be enable_event_trace?
_instructor_patched: bool = False  # Past tense (is_instructor_patched?)
_components_installed: bool = False  # Past tense (are_components_installed?)
```

**Recommendation:**

Use consistent boolean naming:
- Prefix with `is_`, `has_`, `can_`, `should_`, `enable_`
- Use present tense
- Prefer positive framing

```python
# Good:
is_enabled: bool
has_sandbox: bool
should_auto_execute: bool
enable_event_trace: bool

# Avoid:
enabled  # Unclear if bool or str
_event_trace  # Not obviously boolean
_components_installed  # Past tense
```

---

## 9. Type Alias Naming

Good use of `type` statement (Python 3.12+):

```python
type FilterPattern = str
type ModelName = str
```

But inconsistent with TypeVar naming:

```python
T = TypeVar("T")                        # Generic T
P = ParamSpec("P")                      # Generic P
T_Message = TypeVar("T_Message")        # Underscore separator
P_Message = TypeVar("P_Message")        # Confusing (P usually for ParamSpec)
T_Output = TypeVar("T_Output")          # Underscore separator
MessageT = TypeVar("MessageT")          # Suffix pattern
```

**Recommendation:**

Standardize type variable naming:

```python
# Option A: Suffix pattern (more Pythonic)
T = TypeVar("T")                    # Generic
MessageT = TypeVar("MessageT")      # Specific type
OutputT = TypeVar("OutputT")        # Specific type
ParamsP = ParamSpec("ParamsP")      # ParamSpec uses P suffix

# Option B: Prefix pattern (clear but verbose)
T_Message = TypeVar("T_Message")
T_Output = TypeVar("T_Output")
P_Params = ParamSpec("P_Params")
```

**Recommended: Option A (suffix pattern)** - More concise and Pythonic.

---

## 10. Method Naming Inconsistencies

### A. get_ vs fetch_ vs retrieve_

```python
# In various places:
get_tool_registry()      # "get"
fetch_url()              # "fetch"
retrieve_agent()         # Different term
```

**Recommendation:** Standardize on `get_` for all retrieval operations.

### B. _internal vs public

Good separation generally, but some confusion:

```python
# Public:
def call(self, ...): ...
def execute(self, ...): ...
def append(self, ...): ...

# Internal:
def _llm_call(self, ...): ...
def _append_message(self, ...): ...
def _register_extension(self, ...): ...

# Inconsistent:
def _get_tool_definitions(self): ...  # Internal but generic name
def _clone_extensions_for_config(self): ...  # Very specific, could be public?
```

**Recommendation:**

Be intentional about public API:
- No underscore: Public, stable API
- Single underscore: Internal, may change
- Keep internal methods specific to avoid naming conflicts

---

## 11. Abbreviations

Inconsistent use of abbreviations:

```python
# Abbreviations used:
llm          # LanguageModel
msg          # Message
ctx          # Context
ext          # Extension
resp         # Response
arg/kwarg    # Standard Python
config       # Configuration

# But spelled out:
message      # Sometimes abbreviated, sometimes not
response     # Sometimes abbreviated
context      # Sometimes abbreviated
```

**Recommendation:**

Establish abbreviation policy:
```python
# In variable names (local scope):
msg = Message()           # OK
resp = await call()       # OK
ctx = EventContext()      # OK

# In function/class names (public API):
create_message()          # Full word
get_response()            # Full word
get_context()             # Full word

# Exceptions (well-known):
llm, config, id
```

---

## 12. Pluralization

Mostly consistent, with some confusion:

```python
# Singular
self.message           # ❌ Confusing (is it a Message or index?)
self.tool              # ❌ Confusing

# Plural
self.messages          # ✅ Clear (it's a collection)
self.tools             # ✅ Clear

# But then:
self.user              # Returns FilteredMessageList (singular name, plural content)
self.assistant         # Same issue
```

**Recommendation:**

Be clear about singular vs plural:
```python
# Collections should be plural:
self.messages: MessageList
self.tools: ToolManager
self.extensions: dict[...]

# Filtered views (return collections):
self.user_messages -> FilteredMessageList  # Make plural
self.assistant_messages -> FilteredMessageList
self.tool_messages -> FilteredMessageList

# Or keep singular if it's clear it's a filter:
self.user -> FilteredMessageList[UserMessage]  # Type hint makes it clear
```

---

## 13. File Naming

Generally good, with minor issues:

```python
# Good:
agent.py              # Main Agent class
messages.py           # Message classes
tools.py              # Tool system
events.py             # Event definitions

# Questionable:
base.py              # Too generic (base of what?)
interfaces.py        # Only 4 protocols, could be protocols.py
spec.py              # Unclear (specification? special?)
config_types.py      # vs config.py - unclear split
```

**Recommendation:**

Be specific:
```python
# More specific names:
base.py → agent_base.py (or merge into agent.py)
interfaces.py → protocols.py (standard Python term)
spec.py → specification.py (or rename based on purpose)
config_types.py → config_schemas.py (clearer intent)
```

---

## 14. Summary of Issues

| Issue | Severity | Examples | Recommendation |
|-------|----------|----------|----------------|
| utilities vs core confusion | HIGH | Dual imports | Consolidate |
| Context naming overlap | MEDIUM | Context vs EventContext | Rename to TemplateContext |
| Component vs Extension | MEDIUM | AgentComponent vs extensions | Pick one term |
| Type variable naming | LOW | T_Message vs MessageT | Standardize |
| Boolean naming | LOW | _event_trace | Use is_/has_/enable_ prefix |
| Abbreviation consistency | LOW | msg vs message | Establish policy |
| Pluralization | LOW | self.user | Be explicit |
| Manager vs Registry | LOW | Multiple patterns | Document distinction |

---

## 15. Naming Conventions Guide (Recommended)

Create `CONTRIBUTING.md` with naming guidelines:

```markdown
## Naming Conventions

### Modules
- Lowercase with underscores: `message_list.py`
- Specific, not generic: `agent_base.py` not `base.py`

### Classes
- PascalCase: `AgentComponent`, `MessageList`
- Suffix pattern: `*Manager` for coordinators, `*Registry` for lookup

### Functions/Methods
- lowercase_with_underscores
- Verb phrases: `get_message()`, `create_tool()`, `validate_sequence()`

### Variables
- lowercase_with_underscores
- Descriptive: `message_count` not `count`
- Boolean: `is_enabled`, `has_sandbox`, `should_validate`

### Constants
- UPPERCASE_WITH_UNDERSCORES
- Grouped by prefix: `AGENT_*`, `MESSAGE_*`

### Type Variables
- Suffix with T: `MessageT`, `OutputT`
- ParamSpec suffix with P: `ParamsP`

### Private/Internal
- Single underscore: `_internal_method()`
- Avoid double underscore unless name mangling needed
