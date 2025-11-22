# Built-in Components

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent includes several built-in components for common functionality:

## TaskManager Component

Provides todo list management with agent tool integration:
<!-- @TODO: need more documentation on this - show how we augment the system message on each invocation and expose tools for checking off items. -->

```python
from good_agent.extensions.task_manager import TaskManager

async with Agent(
    "Task coordinator",
    extensions=[TaskManager()]
) as agent:

    # Agent can now create and manage todo lists
    await agent.call("Create a project list with 3 development tasks")

    # Access component directly
    task_manager = agent[TaskManager]
    print(f"Created {len(task_manager.lists)} lists")
```

## MessageInjectorComponent

Base class for components that inject content into messages:

```python
--8<-- "src/good_agent/core/components/injection.py:16:42"
```

```python
from good_agent import MessageInjectorComponent
from good_agent.content import TextContentPart

class ContextComponent(MessageInjectorComponent):

    def get_system_prompt_prefix(self, agent: Agent) -> list[ContentPartType]:
        """Add context to the beginning of system prompts."""
        return [TextContentPart(text="Current environment: production")]

    def get_user_message_suffix(self, agent: Agent, message: UserMessage) -> list[ContentPartType]:
        """Add timestamp to user messages."""
        timestamp = datetime.now().isoformat()
        return [TextContentPart(text=f"\n\n[Timestamp: {timestamp}]")]
```

## CitationManager Component

The `CitationManager` is a foundational component for research, browsing, and data-gathering agents. It solves the "URL context" problem by maintaining a consistent, deduplicated global index of all URLs encountered during a conversation (from user inputs, tool outputs, or system context).

### Key Features

*   **Global Indexing**: Maintains a session-wide registry of URLs. If a user provides a link in message 1, and a search tool finds the same link in message 10, they both map to the same Citation ID (e.g., `[!CITE_1!]`).
*   **Token Optimization**: Replaces long, token-heavy URLs with compact references (`[!CITE_n!]` or `idx="n"`) when sending context to the LLM. This significantly reduces prompt size and costs.
*   **Hallucination Prevention**: By forcing the LLM to reference sources by integer ID rather than generating URL strings, it eliminates the generation of "fake" or broken links.
*   **Smart Rendering**:
    *   **LLM View**: Sees standardized tokens: `Based on [!CITE_1!]...`
    *   **User View**: Sees user-friendly elements: `Based on [example.com](https://example.com)...`

### How It Works

The component intercepts message processing at two key stages:

1.  **Input / Creation**: When a message is added (User message or Tool output), `CitationManager` scans for URLs, Markdown links (`[text](url)`), and XML attributes (`url="..."`). These are extracted to the global index, and the message content is normalized to use internal IDs.
2.  **Rendering**:
    *   When sending to the **LLM**, it ensures all references use the `[!CITE_n!]` format or `idx="n"` XML attributes.
    *   When displaying to the **User**, it resolves these IDs back to the original URLs and formats them as clickable Markdown links.

### Examples

**1. Basic Usage**

```python
from good_agent.extensions.citations import CitationManager

async with Agent(
    "Research Assistant",
    extensions=[CitationManager()]
) as agent:
    # The manager automatically indexes the URL in this message
    # Internal state: {1: "https://www.python.org"}
    await agent.call("What is the latest version mentioned on https://www.python.org?")

    # The LLM sees: "What is the latest version mentioned on [!CITE_1!]?"
    # The LLM responds: "According to [!CITE_1!], the latest version is..."
    
    # The User sees: "According to [python.org](https://www.python.org), the latest version is..."

    # Access the index programmatically
    manager = agent[CitationManager]
    url = manager.index.get_url(1)
```

**2. Integration with Search Tools**

One of the most powerful patterns is combining `CitationManager` with search tools that return XML.

```python
# 1. Search Tool returns raw XML
# <results>
#   <item url="https://docs.python.org/3/">Python 3 Docs</item>
#   <item url="https://github.com/python">GitHub</item>
# </results>

# 2. CitationManager intercepts and transforms for LLM
# <results>
#   <item idx="2">Python 3 Docs</item>
#   <item idx="3">GitHub</item>
# </results>

# 3. LLM references specific items by ID
# "I found the documentation at [!CITE_2!] and the repository at [!CITE_3!]."
```

This pattern allows the LLM to "point" to search results accurately without hallucinating URLs or wasting tokens repeating them.

## AgentSearch Component

coming soon...
