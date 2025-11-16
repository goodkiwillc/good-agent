# Agent Routing and Orchestration

## Overview

This spec explores a routing and orchestration layer for agents that enables:
- Complex agent behaviors beyond simple call-and-response
- Reusable agent logic that can be encapsulated
- Deterministic and AI-powered routing between different agent modes
- User-facing commands that map to internal routes
- Dynamic context management and transformation before LLM calls
- Integration with existing features (invoke, stateful objects, agent-as-tool, event router)

## Motivation

Currently, the agent library is focused on agents that are defined and used in the same place:

```python
async with Agent("You are a helpful assistant.") as agent:
    response = await agent.call("What is 2 + 2?")
    print(response)
```

This works well for simple cases, but breaks down when we need to:
1. **Encapsulate complex agent behavior** - More than just system prompt + tools
2. **Reuse agent logic** - Same behavior across multiple places
3. **Define stateful modes** - Agent enters different operational states based on context
4. **Control context sent to LLM** - Filter/transform/truncate messages independently of agent history
5. **Handle user commands** - Expose agent capabilities as slash commands in chat interfaces
6. **Orchestrate multi-step workflows** - Define deterministic flows with conditional branching

Current workaround is function wrappers, which gets unwieldy:

```python
async def some_function(query: str):
    async with Agent("You are a helpful assistant.") as agent:
        # Complex logic here
        response = await agent.call(query)
        return response
```

## Pattern Inspiration

### Web Frameworks (Flask/FastAPI)
```python
@app.route('/users/<user_id>')
async def get_user(user_id: str):
    return user_service.get(user_id)
```
- Named routes with parameters
- Clear mapping of paths to handlers
- Middleware chains

### State Machines (XState, Spring State Machine)
```javascript
const machine = createMachine({
  initial: 'idle',
  states: {
    idle: { on: { START: 'running' } },
    running: { on: { FINISH: 'complete', ERROR: 'failed' } }
  }
})
```
- Explicit states and transitions
- Guards (conditions for transitions)
- Entry/exit actions

### Workflow Engines (Temporal, Prefect)
```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self, data):
        result1 = await workflow.execute_activity(step1, data)
        if result1.needs_approval:
            result2 = await workflow.execute_activity(step2, result1)
        return result2
```
- DAG-based execution
- Compensation/error handling
- Conditional branching

### API Gateways (Envoy Sidecar Pattern)
- Separate routing logic from business logic
- Can inspect/modify requests before they reach the service

### Redux Middleware
```javascript
const logger = store => next => action => {
  console.log('dispatching', action)
  let result = next(action)
  console.log('next state', store.getState())
  return result
}
```
- Composable interceptors
- Can modify or block actions

## Core Concepts

### 1. Routes
**Named behaviors or modes** that an agent can be in. Routes define what happens when the agent is in a particular state.

```python
@agent.route('ready')
async def ready_state(ctx: AgentContext):
    """Main conversation mode"""
    response = await ctx.llm_call()
    return response
```

### 2. Router
**Decision-making system** that determines which route to take next. Can be:
- **Deterministic**: Rule-based conditions
- **AI-powered**: Let an LLM make routing decisions
- **Hybrid**: Rules first, AI fallback
- **Custom**: User-defined logic

```python
# Deterministic
router = Router(
    rules=[
        Rule(condition=lambda ctx: ctx.message_count > 20, to_route='compact')
    ]
)

# AI-powered
ai_router = AIRouter(
    routing_agent=Agent("You are a routing assistant...")
)
```

### 3. Context Pipeline
**Transformation functions** that modify agent state before LLM calls. This is key for controlling what context gets sent to the LLM independently of conversation history.

```python
async def inject_rag_context(ctx: AgentContext) -> AgentContext:
    """Add relevant context from vector store"""
    last_message = ctx.agent[-1]
    relevant_docs = await vector_store.search(last_message.content)
    ctx.add_context_message(f"# Relevant Context\n{relevant_docs}")
    return ctx

@agent.route('ready')
async def ready_state(ctx: AgentContext):
    # Apply transformations before LLM call
    ctx.pipeline(
        inject_rag_context,
        truncate_old_messages,
        add_system_context
    )
    response = await ctx.llm_call()
    return response
```

### 4. Transitions
**Explicit flow control** between routes. Routes return transitions to indicate where to go next.

```python
@agent.route('research_mode')
async def research_mode(ctx: AgentContext):
    # Do research...
    return ctx.next('ready')  # Transition back to ready state
```

### 5. Commands
**User-facing entry points** that map to routes. When exposed in a chat interface, users can invoke routes directly.

```python
@agent.route('draft-report')
@expose.command(
    usage='/draft-report <topic>',
    description='Draft a comprehensive report'
)
async def draft_report(ctx: AgentContext):
    """Route that can be triggered by user command or internal logic"""
    topic = ctx.get_param('topic')
    response = await ctx.llm_call(f"Draft a report on: {topic}")
    return ctx.next('ready')
```

## Proposed Design

### Basic Route Definition

```python
from good_agent import Agent, AgentContext, Router, expose

# Create agent with routing
agent = Agent(
    "You are a helpful assistant.",
    tools=[...],
    router=Router()  # Default router
)

# Define routes
@agent.route('init')
async def initialize_conversation(ctx: AgentContext):
    """Runs when conversation starts"""
    ctx.agent.append("Conversation initialized at " + datetime.now())
    return ctx.next('ready')

@agent.route('ready')
async def ready_state(ctx: AgentContext):
    """Main conversation mode"""

    # Apply context transformations before LLM call
    ctx.pipeline(
        inject_rag_context,
        truncate_old_messages,
        add_system_context
    )

    # Make LLM call with transformed context
    response = await ctx.llm_call()

    # Conditional routing based on runtime state
    if ctx.agent.message_count > 20:
        return ctx.next('compact')
    elif 'need to search' in response.lower():
        return ctx.next('research_mode')

    return response

@agent.route('compact')
async def compact_history(ctx: AgentContext):
    """Compact conversation history when it gets too long"""

    # Get messages 5-15 (older messages)
    old_messages = ctx.agent.messages[5:15]

    # Summarize them using invoke (automatically updates history)
    summary = await ctx.agent.invoke(
        summarize_tool,
        messages=old_messages
    )

    # Replace old messages with summary
    ctx.agent.replace_messages(5, 15, summary)

    # Return to ready state
    return ctx.next('ready')

@agent.route('research_mode')
async def research_mode(ctx: AgentContext):
    """Specialized mode for research tasks"""

    # Temporarily modify tools and instructions using stateful object
    with ctx.agent.mode(
        tools=[web_search, arxiv_search],
        instructions="Focus on finding authoritative sources."
    ):
        response = await ctx.llm_call()

    return ctx.next('ready')
```

### Usage

```python
# Single turn
async with agent:
    response = await agent.call("Hello!")
    # Automatically goes through: init -> ready

# Multi-turn
async with agent:
    await agent.call("Tell me about quantum computing")
    # Goes through: init -> ready

    await agent.call("Can you elaborate on quantum entanglement?")
    # Stays in: ready

    # After many messages...
    await agent.call("And what about quantum supremacy?")
    # Automatically: ready -> compact -> ready

# Manual route specification
async with agent:
    response = await agent.call(
        "Write me a report on AI",
        route='draft_report'
    )
```

### Context Pipeline Functions

Pipeline functions transform the agent context before LLM calls:

```python
async def inject_rag_context(ctx: AgentContext) -> AgentContext:
    """Add relevant context from vector store"""
    last_message = ctx.agent[-1]
    relevant_docs = await vector_store.search(last_message.content)

    ctx.add_context_message(
        f"# Relevant Context\n{relevant_docs}",
        section="rag-context"  # Named section for easy removal later
    )
    return ctx

async def truncate_old_messages(ctx: AgentContext) -> AgentContext:
    """Keep only recent messages if context is large"""
    if ctx.estimated_tokens > 8000:
        # Keep system, first 2, and last 10 messages
        ctx.set_llm_messages([
            ctx.agent.system_message,
            *ctx.agent.messages[0:2],
            *ctx.agent.messages[-10:]
        ])
    return ctx

async def add_system_context(ctx: AgentContext) -> AgentContext:
    """Add current time, user info, etc."""
    ctx.add_system_message(f"Current time: {datetime.now()}")
    return ctx
```

### AgentContext API

The context object passed to route handlers:

```python
class AgentContext:
    """Context object passed to route handlers"""

    # Core attributes
    agent: Agent  # The agent instance
    current_route: str  # Current route name
    available_routes: list[str]  # All defined routes
    entry_point: str  # How we entered route: 'command', 'router', 'code'

    # Routing
    def next(self, route: str, **params) -> Transition:
        """Transition to another route with optional parameters"""

    def stay(self) -> Transition:
        """Stay in current route"""

    # LLM calls
    async def llm_call(self, **kwargs) -> Message:
        """Make LLM call with current context"""

    # Context pipeline
    def pipeline(self, *transforms):
        """Apply transformations to context before LLM call"""

    def set_llm_messages(self, messages: list[Message]):
        """Explicitly set what messages go to LLM (not persisted in history)"""

    def add_context_message(self, content: str, section: str = None):
        """Add ephemeral context (sent to LLM but not persisted in history)"""

    def add_system_message(self, content: str):
        """Add system message to context"""

    # Parameters (from command invocation or route transition)
    def get_param(self, name: str, default: Any = None) -> Any:
        """Get parameter value (works for all entry points)"""

    # State
    state: dict  # Route-specific state
    estimated_tokens: int  # Estimated token count
    message_count: int  # Number of messages in conversation
    is_command_entry: bool  # True if entered via user command
    should_exit: bool  # True if user wants to exit current mode
```

## Router Types

### 1. Deterministic Router (Rule-Based)

```python
router = Router(
    initial_route='init',
    rules=[
        Rule(
            from_route='ready',
            to_route='compact',
            condition=lambda ctx: ctx.agent.message_count > 20
        ),
        Rule(
            from_route='ready',
            to_route='research_mode',
            condition=lambda ctx: 'research' in ctx.agent[-1].content.lower()
        )
    ]
)

agent = Agent("You are a helpful assistant.", router=router)
```

### 2. AI-Powered Router

A sidecar agent that makes routing decisions:

```python
routing_agent = Agent(
    """You are a routing assistant. Based on the conversation state,
    decide which route the main agent should take next.

    Available routes:
    - ready: Normal conversation
    - research_mode: Deep research is needed
    - compact: History is getting long
    - draft_report: User asked for a report
    """
)

ai_router = AIRouter(
    routing_agent=routing_agent,
    available_routes=['init', 'ready', 'research_mode', 'compact', 'draft_report']
)

agent = Agent("You are a helpful assistant.", router=ai_router)

# Can also define custom routing logic
@agent.use_router(routing_agent)
async def ai_route_decision(ctx: AgentContext) -> str:
    """Let an AI decide the next route"""
    decision = await routing_agent.call(
        f"""
        Current state: {ctx.current_route}
        Message count: {ctx.agent.message_count}
        Last message: {ctx.agent[-1].content[:200]}
        Available routes: {ctx.available_routes}

        What route should we take next?
        """
    )
    return decision.route_name
```

### 3. Hybrid Router

Uses rules first, falls back to AI:

```python
hybrid_router = HybridRouter(
    rules=[
        Rule(condition=lambda ctx: ctx.message_count > 20, to_route='compact'),
    ],
    fallback=ai_router
)

agent = Agent("You are a helpful assistant.", router=hybrid_router)
```

### 4. Custom Router

```python
class MyCustomRouter(Router):
    async def route(self, ctx: AgentContext) -> str:
        """Custom routing logic"""
        if ctx.agent.message_count < 3:
            return 'init'
        elif self.should_research(ctx):
            return 'research_mode'
        else:
            return 'ready'

    def should_research(self, ctx: AgentContext) -> bool:
        # Custom logic
        return 'research' in ctx.agent[-1].content.lower()

agent = Agent("You are a helpful assistant.", router=MyCustomRouter())
```

## Commands and User-Facing Routes

### Unified Approach: Routes with Entry Points

Routes are the foundation. Commands are just one way to enter routes:

```python
@agent.route('draft-report')
@expose.command(
    usage='/draft-report <topic>',
    description='Draft a comprehensive report',
    params={
        'topic': 'The topic to research and write about',
        'format': 'Output format (markdown, html, pdf)',
    },
    examples=[
        '/draft-report quantum computing',
        '/draft-report "AI safety" --format=pdf'
    ]
)
async def draft_report(ctx: AgentContext):
    """Route that can be triggered multiple ways"""

    # Unified parameter access (works for all entry points)
    topic = ctx.get_param('topic')
    format = ctx.get_param('format', default='markdown')

    if not topic and ctx.is_command_entry:
        return "Please specify a topic: /draft-report <topic>"
    elif not topic:
        topic = await ctx.extract_topic_from_conversation()

    # Core logic
    response = await ctx.llm_call(
        f"Draft a {format} report on: {topic}"
    )

    return ctx.next('ready')

@agent.route('compact')  # No @expose decorator = internal only
async def compact_history(ctx: AgentContext):
    """Internal route - not exposed to users"""
    # Compact logic...
    return ctx.next('ready')

# Pure commands (no route logic needed)
@agent.command('clear')
async def clear_command(ctx: AgentContext):
    """Clear conversation history."""
    ctx.agent.clear_messages()
    return "Conversation cleared."

@agent.command('help')
async def help_command(ctx: AgentContext):
    """Show available commands"""
    commands = [cmd for cmd in ctx.agent.routes if cmd.exposed]

    help_text = "Available commands:\n\n"
    for cmd in commands:
        help_text += f"/{cmd.name} - {cmd.description}\n"
        help_text += f"  Usage: {cmd.usage}\n\n"

    return help_text
```

### How Entry Points Work

**User types `/draft-report quantum computing`:**
1. Parser extracts command name (`draft-report`) and params (`topic='quantum computing'`)
2. Finds route decorated with `@expose.command`
3. Creates `AgentContext` with `entry_point='command'` and parsed params
4. Route handler executes
5. Can transition to other routes

**Router triggers transition:**
```python
# Inside another route
return ctx.next('draft-report', topic='quantum computing', format='markdown')
```

**Natural language invocation:**
```python
async with agent:
    # User just talks naturally
    await agent.call("Can you write a report on quantum computing?")
    # Router/agent logic detects intent, transitions to 'draft-report' route
```

### Multi-Turn Command Modes

Commands can enter multi-turn modes:

```python
@agent.route('document-editor')
@expose.command(
    usage='/edit-doc <document_name>',
    description='Enter document editing mode'
)
async def document_editor(ctx: AgentContext):
    """Multi-turn document editing mode"""

    doc_name = ctx.get_param('document_name')
    doc = await load_document(doc_name)

    # Enter stateful mode (existing feature)
    editor = DocumentEditor(doc)

    with ctx.agent.use_object(editor):
        # Loop until user exits or saves
        while not editor.is_done:
            response = await ctx.llm_call()

            if ctx.should_exit:  # User typed /exit
                break

        if editor.has_changes:
            await editor.save()

    return ctx.next('ready')
```

## Integration with Existing Features

### With Event Router

The routing system builds on the existing event router:

```python
# Existing event system
@agent.on('message:created')
async def on_message_created(event):
    log_message(event.message)

# Routes can emit events
@agent.route('ready')
async def ready_state(ctx: AgentContext):
    # Emit events for observability
    ctx.emit('entering:ready', {'context': ctx})

    response = await ctx.llm_call()

    ctx.emit('llm:response', {'response': response})

    return response
```

### With Agent.invoke()

**Reminder:** `agent.invoke(tool, **params)` automatically:
1. Adds an assistant message with the tool call to history (as if agent decided to call it)
2. Executes the tool
3. Adds the tool response to history
4. Returns the result

**There's no need to manually append to history when using invoke.**

```python
@agent.route('research_mode')
async def research_mode(ctx: AgentContext):
    """Programmatically trigger a web search"""

    # This automatically updates history with tool call + response
    search_results = await ctx.agent.invoke(
        web_search,
        query="latest AI developments"
    )

    # search_results contains the tool response
    # History already has: assistant message (tool call) + tool response

    # Can use the results in next LLM call
    response = await ctx.llm_call()

    return ctx.next('ready')
```

### With Stateful Objects

```python
# Existing stateful object (e.g., document editor)
document_editor = StatefulObject(
    methods=['find', 'replace', 'save'],
    instructions="Edit the document carefully..."
)

@agent.route('edit_mode')
async def edit_mode(ctx: AgentContext):
    """Enter document editing mode"""

    # Stateful object replaces tools and modifies instructions
    with ctx.agent.use_object(document_editor):
        # Agent now only has find/replace/save tools
        response = await ctx.llm_call()

        # Wait for agent to call 'save' tool
        while not document_editor.saved:
            response = await ctx.llm_call()

    return ctx.next('ready')
```

### With Agent Components

```python
# Agent component with external state
class ResearchComponent:
    def __init__(self):
        self.research_cache = {}
        self.sources = []

    async def search(self, query: str) -> str:
        if query in self.research_cache:
            return self.research_cache[query]

        results = await web_search(query)
        self.research_cache[query] = results
        self.sources.append(results.sources)
        return results

research_component = ResearchComponent()

agent = Agent(
    "You are a research assistant.",
    tools=[research_component.search],
    components={'research': research_component}
)

@agent.route('research_mode')
async def research_mode(ctx: AgentContext):
    """Access component state"""
    research = ctx.agent.components['research']

    # Can check state before making decisions
    if len(research.sources) > 10:
        return ctx.next('compile_sources')

    response = await ctx.llm_call()
    return ctx.next('ready')
```

### Agent as Tool (Single-Shot)

```python
# Research agent can be used as tool
research_agent = Agent(
    "You are a research assistant.",
    tools=[web_search, arxiv_search]
)

@research_agent.route('init')
async def research_init(ctx: AgentContext):
    # Single-shot: do research and return
    results = await ctx.llm_call()
    return results  # No transition, just return result

# Main agent uses research agent as tool
main_agent = Agent(
    "You are a helpful assistant.",
    tools=[research_agent]  # Agent as tool
)

async with main_agent:
    response = await main_agent.call("Research quantum computing for me")
    # main_agent calls research_agent as a tool
    # research_agent executes init route and returns result
```

### Agent as Tool (Multi-Turn)

```python
# Research agent with multi-turn interface
research_agent = Agent(
    "You are a research assistant.",
    tools=[web_search, arxiv_search],
    multi_turn=True  # Expose multi-turn interface
)

@research_agent.route('ready')
async def research_ready(ctx: AgentContext):
    """Can have multi-turn conversation"""
    response = await ctx.llm_call()
    return response

# Main agent can have multi-turn conversation with research agent
main_agent = Agent(
    "You are a helpful assistant.",
    tools=[research_agent.as_multi_turn_tool()]
)

# When main agent calls research_agent tool with multi-turn:
# research_agent.call(
#     message="Tell me about quantum computing",
#     conversation_id="conv-123"  # Maintains separate conversation
# )
```

### Agent as Tool with Explicit Routes

```python
# Research agent with multiple routes
research_agent = Agent("You are a research assistant.", tools=[web_search])

@research_agent.route('quick-search')
async def quick_search(ctx: AgentContext):
    """Quick web search"""
    query = ctx.get_param('query')
    results = await ctx.agent.invoke(web_search, query=query)
    return f"Quick results: {results}"

@research_agent.route('deep-research')
async def deep_research(ctx: AgentContext):
    """Comprehensive multi-source research"""
    query = ctx.get_param('query')

    # Multiple searches
    web_results = await ctx.agent.invoke(web_search, query=query)
    academic_results = await ctx.agent.invoke(arxiv_search, query=query)

    # Synthesize
    synthesis = await ctx.llm_call(
        f"Synthesize these results:\n{web_results}\n{academic_results}"
    )

    return synthesis

# Main agent can invoke specific routes
main_agent = Agent(
    "You are a helpful assistant.",
    tools=[research_agent]
)

async with main_agent:
    # Can specify which route to invoke when using as tool
    # The tool interface would expose both routes as parameters
    response = await main_agent.call(
        "Do a deep research on quantum computing"
    )
    # main_agent decides to call research_agent.deep_research
```

## Advanced Use Cases

### 1. RAG with Context Injection

```python
@agent.route('ready')
async def ready_with_rag(ctx: AgentContext):
    """Main mode with RAG"""

    async def inject_rag(ctx: AgentContext) -> AgentContext:
        last_message = ctx.agent[-1]
        docs = await vector_store.search(last_message.content)
        ctx.add_context_message(f"# Relevant Context\n{docs}", section="rag")
        return ctx

    ctx.pipeline(inject_rag)
    response = await ctx.llm_call()

    return response
```

### 2. Response Validation with Retry

```python
@agent.route('ready')
async def ready_with_validation(ctx: AgentContext):
    """Validate responses and retry if needed"""

    max_retries = 3
    for attempt in range(max_retries):
        response = await ctx.llm_call()

        if is_valid_json(response):
            return response
        else:
            # Add feedback for retry
            ctx.agent.append_user(
                "That wasn't valid JSON. Please try again with proper formatting."
            )

    return "Failed to generate valid response after retries."
```

### 3. Dynamic Tool Selection

```python
@agent.route('ready')
async def ready_with_dynamic_tools(ctx: AgentContext):
    """Add/remove tools based on query"""

    last_message = ctx.agent[-1].content

    # Determine which tools are relevant
    if 'search' in last_message.lower():
        ctx.add_tools([web_search, arxiv_search])
    elif 'calculate' in last_message.lower():
        ctx.add_tools([calculator])

    response = await ctx.llm_call()

    return response
```

### 4. Context Window Management

```python
@agent.route('ready')
async def ready_with_auto_compact(ctx: AgentContext):
    """Automatically manage context window"""

    if ctx.estimated_tokens > ctx.agent.max_tokens * 0.8:
        # Auto-transition to compact mode
        return ctx.next('compact')

    response = await ctx.llm_call()
    return response

@agent.route('compact')
async def compact(ctx: AgentContext):
    """Compact conversation history"""

    # Summarize older messages
    old_messages = ctx.agent.messages[5:15]
    summary = await ctx.agent.invoke(summarize_tool, messages=old_messages)

    # Replace with summary
    ctx.agent.replace_messages(5, 15, summary)

    return ctx.next('ready')
```

### 5. A/B Testing Routes

```python
import random

@agent.route('ready')
async def ready_ab_test(ctx: AgentContext):
    """A/B test different prompting strategies"""

    variant = random.choice(['control', 'treatment'])

    if variant == 'treatment':
        ctx.add_system_message(
            "Use chain-of-thought reasoning before answering."
        )

    response = await ctx.llm_call()

    # Log variant for analysis
    ctx.log_metric('variant', variant)

    return response
```

### 6. Multi-Step Reasoning Pipeline

```python
@agent.route('reasoning-mode')
async def reasoning_mode(ctx: AgentContext):
    """Force agent through specific reasoning steps"""

    # Step 1: Understand the question
    ctx.agent.append_system("First, restate the question in your own words.")
    understanding = await ctx.llm_call()

    # Step 2: Break down the problem
    ctx.agent.append_system("Now, break down the problem into sub-problems.")
    breakdown = await ctx.llm_call()

    # Step 3: Solve each sub-problem
    ctx.agent.append_system("Solve each sub-problem one by one.")
    solution = await ctx.llm_call()

    # Step 4: Synthesize final answer
    ctx.agent.append_system("Finally, synthesize a final answer.")
    final_answer = await ctx.llm_call()

    return ctx.next('ready')
```

### 7. Rate Limiting

```python
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_calls: int, window: timedelta):
        self.max_calls = max_calls
        self.window = window
        self.calls = []

    def can_call(self) -> bool:
        now = datetime.now()
        self.calls = [t for t in self.calls if now - t < self.window]
        return len(self.calls) < self.max_calls

    def record_call(self):
        self.calls.append(datetime.now())

rate_limiter = RateLimiter(max_calls=10, window=timedelta(minutes=1))

@agent.route('ready')
async def ready_with_rate_limit(ctx: AgentContext):
    """Rate limit LLM calls"""

    if not rate_limiter.can_call():
        return "Rate limit exceeded. Please wait before trying again."

    rate_limiter.record_call()
    response = await ctx.llm_call()

    return response
```

### 8. Caching

```python
import hashlib
import json

cache = {}

def cache_key(messages: list[Message]) -> str:
    """Generate cache key from messages"""
    content = json.dumps([m.content for m in messages])
    return hashlib.sha256(content.encode()).hexdigest()

@agent.route('ready')
async def ready_with_cache(ctx: AgentContext):
    """Cache responses for identical queries"""

    key = cache_key(ctx.agent.messages)

    if key in cache:
        ctx.log_metric('cache_hit', True)
        return cache[key]

    response = await ctx.llm_call()
    cache[key] = response

    return response
```

## Lifecycle and Scope

### Single-Turn vs Multi-Turn Agents

Agents need to support both patterns:

```python
# Single-turn: agent initializes and handles one request
async with Agent("You are a helper.", router=Router(initial_route='init')) as agent:
    response = await agent.call("What is 2+2?")
    # Goes through: init -> ready -> (returns response)

# Multi-turn: agent maintains state across multiple calls
async with Agent("You are a helper.", router=Router(initial_route='init')) as agent:
    response1 = await agent.call("What is 2+2?")
    # Goes through: init -> ready

    response2 = await agent.call("What about 3+3?")
    # Stays in: ready (no re-initialization)

    response3 = await agent.call("Tell me more")
    # Still in: ready
```

### Route Lifecycle

Routes should have clear lifecycle:

```python
@agent.route('research_mode')
@agent.on_enter('research_mode')
async def enter_research_mode(ctx: AgentContext):
    """Called when entering route"""
    ctx.state['research_start'] = datetime.now()
    ctx.agent.append_system("Entering research mode...")

@agent.on_exit('research_mode')
async def exit_research_mode(ctx: AgentContext):
    """Called when exiting route"""
    duration = datetime.now() - ctx.state['research_start']
    ctx.log_metric('research_duration', duration.total_seconds())

async def research_mode(ctx: AgentContext):
    """Main route logic"""
    response = await ctx.llm_call()
    return ctx.next('ready')
```

### Agent-as-Tool Lifecycle

When agents are used as tools, they should have separate conversation state:

```python
# Each invocation gets its own conversation_id
main_agent = Agent("You are a helper.", tools=[research_agent.as_multi_turn_tool()])

async with main_agent:
    # First invocation
    await main_agent.call("Research topic A")
    # research_agent gets conversation_id="conv-1"

    # Second invocation
    await main_agent.call("Research topic B")
    # research_agent gets conversation_id="conv-2"

    # Continue first conversation
    await main_agent.call("Tell me more about topic A")
    # research_agent uses conversation_id="conv-1" (continued)
```

## Open Questions

### 1. Route Discovery
Should routes be auto-discovered from decorators, or explicitly registered?

```python
# Option A: Auto-discovery (decorator-based)
@agent.route('ready')
async def ready(ctx): ...

# Option B: Explicit registration
agent.add_route('ready', ready_handler)

# Option C: Both
@agent.route('ready')
async def ready(ctx): ...
# OR
agent.add_route('other', other_handler)
```

### 2. Route Parameters
Do we need parameterized routes like `/draft_report/{report_type}`?

```python
@agent.route('draft-report/{report_type}')
async def draft_report(ctx: AgentContext):
    report_type = ctx.route_params['report_type']
    # ...
```

### 3. Nested Routing
Can routes have sub-routes?

```python
@agent.route('research_mode')
async def research_mode(ctx): ...

@agent.route('research_mode/web')
async def research_web(ctx): ...

@agent.route('research_mode/academic')
async def research_academic(ctx): ...
```

### 4. Default Behavior
If no routes are defined, does the agent just work normally?

```python
# No routes defined - should still work
agent = Agent("You are a helper.")

async with agent:
    response = await agent.call("Hello")
    # Should just work like current implementation
```

### 5. Middleware vs Pipeline
Should context transformations be:
- Applied globally (middleware)
- Applied per-route (pipeline)
- Both?

```python
# Global middleware
agent = Agent(
    "Helper",
    middleware=[logging_middleware, caching_middleware]
)

# Per-route pipeline
@agent.route('ready')
async def ready(ctx):
    ctx.pipeline(inject_rag, truncate_messages)
    response = await ctx.llm_call()
    return response
```

### 6. Error Handling
What happens if:
- A route handler fails?
- Router can't decide which route?
- Agent tries to transition to non-existent route?

```python
@agent.on_error
async def handle_route_error(ctx: AgentContext, error: Exception):
    """Global error handler for routes"""
    ctx.log_error(error)

    # Can transition to error recovery route
    return ctx.next('error_recovery')

@agent.route('error_recovery')
async def error_recovery(ctx: AgentContext):
    """Handle errors gracefully"""
    ctx.agent.append_system("An error occurred. Recovering...")
    return ctx.next('ready')
```

### 7. Testing
How do we make routes testable in isolation?

```python
# Test a route without full agent context
async def test_research_mode():
    ctx = MockAgentContext(
        agent=mock_agent,
        current_route='research_mode'
    )

    result = await research_mode(ctx)

    assert result.next_route == 'ready'
    assert mock_agent.invoke.called_with(web_search)
```

### 8. Route Lifecycle Hooks
Do we need `on_enter`, `on_exit` for routes?

```python
@agent.on_enter('research_mode')
async def setup_research(ctx):
    """Called when entering route"""
    ctx.state['start_time'] = datetime.now()

@agent.on_exit('research_mode')
async def teardown_research(ctx):
    """Called when exiting route"""
    duration = datetime.now() - ctx.state['start_time']
    ctx.log_metric('duration', duration)
```

### 9. Concurrent Routes
Can an agent be in multiple routes simultaneously? (Probably not, but worth asking)

### 10. Route Composition
Can routes be reusable across agents?

```python
# Define reusable routes
rag_route = Route('rag-mode', handler=rag_handler)
research_route = Route('research', handler=research_handler)

# Use in multiple agents
agent1 = Agent("Helper 1", routes=[rag_route, research_route])
agent2 = Agent("Helper 2", routes=[rag_route])
```

### 11. Command Parsing
Should the agent framework include a command parser, or rely on external parsing (like Discord/Slack bots do)?

### 12. Command Permissions
Do we need role-based access for commands? E.g., only admin users can run `/clear`?

```python
@agent.command('clear', roles=['admin'])
async def clear(ctx: AgentContext):
    if not ctx.user.has_role('admin'):
        return "Permission denied"
    ctx.agent.clear_messages()
    return "Cleared"
```

### 13. Command Middleware
Should commands have their own middleware/hooks? E.g., logging all command invocations?

```python
@agent.before_command
async def log_command(ctx: AgentContext):
    log.info(f"User {ctx.user.id} invoked /{ctx.command_name}")
```

### 14. Discovery
How do users discover available commands? Auto-generated help? Documentation?

### 15. Command Aliases
Should routes support multiple command names? E.g., `/help` and `/?`

```python
@agent.command('help', aliases=['?', 'h'])
async def help(ctx): ...
```

### 16. Error Handling for Commands
What happens if user types `/unknown-command`? Show help? Let agent respond naturally?

### 17. Streaming
How do commands work with streaming responses? Can commands return generators?

```python
@agent.command('stream-search')
async def stream_search(ctx: AgentContext):
    """Stream search results as they come in"""
    async for result in search_stream(ctx.get_param('query')):
        yield result
```

## Todo List

- [ ] Design and implement `AgentContext` class
- [ ] Design and implement `Router` base class
- [ ] Implement `DeterministicRouter` with rule-based routing
- [ ] Implement `AIRouter` with sidecar agent routing
- [ ] Implement `HybridRouter` combining rules and AI
- [ ] Design route decorator and registration system
- [ ] Implement context pipeline transformation system
- [ ] Design command exposure system (`@expose.command`)
- [ ] Implement command parsing and parameter extraction
- [ ] Design transition API (`ctx.next()`, `ctx.stay()`)
- [ ] Implement route lifecycle hooks (`on_enter`, `on_exit`)
- [ ] Add support for route parameters
- [ ] Implement error handling for routes
- [ ] Design testing utilities for routes
- [ ] Write comprehensive tests for routing system
- [ ] Document integration with existing features
- [ ] Create examples and tutorials
- [ ] Add observability/logging for routes
- [ ] Implement route composition and reusability
- [ ] Design permission system for commands
- [ ] Add streaming support for routes

## Testing Strategy

Routes should be testable in isolation:

```python
import pytest
from good_agent import Agent, AgentContext, MockAgent

@pytest.mark.asyncio
async def test_research_mode_route():
    """Test research mode route in isolation"""

    # Create mock agent with necessary state
    mock_agent = MockAgent(
        messages=[
            Message(role='user', content='Research quantum computing')
        ]
    )

    # Create context
    ctx = AgentContext(
        agent=mock_agent,
        current_route='research_mode'
    )

    # Execute route
    result = await research_mode(ctx)

    # Assert behavior
    assert result.next_route == 'ready'
    assert mock_agent.invoke.called_once()
    assert mock_agent.invoke.call_args[0][0] == web_search

@pytest.mark.asyncio
async def test_route_transitions():
    """Test route transitions in full agent"""

    agent = Agent("Helper", router=Router(initial_route='init'))

    # Add routes
    @agent.route('init')
    async def init(ctx):
        return ctx.next('ready')

    @agent.route('ready')
    async def ready(ctx):
        if ctx.message_count > 5:
            return ctx.next('compact')
        return await ctx.llm_call()

    async with agent:
        # Should start in init, transition to ready
        response = await agent.call("Hello")
        assert agent.current_route == 'ready'

        # After many messages, should transition to compact
        for i in range(10):
            await agent.call(f"Message {i}")

        assert agent.current_route == 'compact'

@pytest.mark.asyncio
async def test_command_invocation():
    """Test user command invocation"""

    agent = Agent("Helper")

    @agent.route('draft-report')
    @expose.command(usage='/draft-report <topic>')
    async def draft_report(ctx):
        topic = ctx.get_param('topic')
        return f"Drafting report on {topic}"

    async with agent:
        # Invoke via command
        response = await agent.call("/draft-report quantum computing")
        assert "quantum computing" in response
        assert ctx.entry_point == 'command'
```
