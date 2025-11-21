# Built-in Components

Good Agent includes several built-in components for common functionality:

## TaskManager Component

Provides todo list management with agent tool integration:

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

Manages citations and references in agent responses:

```python
from good_agent.extensions.citations import CitationManager

async with Agent(
    "Research assistant",
    extensions=[CitationManager()]
) as agent:
    
    # Component automatically manages citations in responses
    response = await agent.call("Tell me about Python async programming")
    
    # Access citation data
    citation_manager = agent[CitationManager]
    citations = citation_manager.get_all_citations()
```

## AgentSearch Component

Provides semantic search capabilities within agent conversations:

```python
from good_agent.extensions.search import AgentSearch

async with Agent(
    "Knowledge assistant",
    extensions=[AgentSearch()]
) as agent:
    
    # Component enables semantic search across message history
    await agent.call("What did we discuss about databases earlier?")
```
