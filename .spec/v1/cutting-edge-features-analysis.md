# Cutting-Edge Agent Framework Features: Analysis & Proposals for good-agent

This document analyzes features and design patterns from leading Python agent frameworks in 2025, including LangGraph, CrewAI, AutoGen, LlamaIndex, and Haystack. For each feature, we propose how it could be implemented in the good-agent library while maintaining consistency with our existing API style.

**Date**: November 2025
**Frameworks Analyzed**: LangGraph, CrewAI, AutoGen, LlamaIndex Workflows, Haystack

---

## Executive Summary

The agent framework landscape in 2025 is characterized by:
- **Graph-based orchestration** (LangGraph, LlamaIndex) for complex, stateful workflows
- **Role-based collaboration** (CrewAI) for multi-agent teamwork
- **Event-driven architectures** (AutoGen v0.4, LlamaIndex Workflows) for async, long-running agents
- **Checkpointing and state persistence** (LangGraph) for resumable workflows
- **Hierarchical and swarm patterns** (LangGraph Supervisor/Swarm) for agent coordination

Key insights for good-agent:
1. Simplicity is a differentiator - most frameworks have steep learning curves
2. Async context managers remain a clean pattern for lifecycle management
3. Decorator-based APIs are intuitive but need to support both imperative and declarative styles
4. State management is critical but often over-engineered

---

## 1. Graph-Based Orchestration

### What It Is

Workflows defined as directed graphs where:
- **Nodes** represent operations (LLM calls, tool invocations, computations)
- **Edges** represent transitions between nodes (can be conditional)
- **State** flows through the graph and can be modified at each node

### Current State of the Art

**LangGraph** (Most mature):
```python
from langgraph.graph import StateGraph

workflow = StateGraph(state_schema=AgentState)
workflow.add_node("research", research_node)
workflow.add_node("analyze", analyze_node)
workflow.add_node("synthesize", synthesize_node)

# Conditional edges
workflow.add_conditional_edges(
    "research",
    should_continue,
    {"continue": "analyze", "end": END}
)

graph = workflow.compile()
result = await graph.ainvoke({"query": "..."})
```

**LlamaIndex Workflows**:
```python
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step

class MyWorkflow(Workflow):
    @step
    async def research(self, ctx: Context, ev: StartEvent) -> AnalyzeEvent:
        # Research logic
        return AnalyzeEvent(data=results)

    @step
    async def analyze(self, ctx: Context, ev: AnalyzeEvent) -> StopEvent:
        # Analyze logic
        return StopEvent(result=analysis)

workflow = MyWorkflow()
result = await workflow.run(query="...")
```

### Why It's Useful

- **Parallel execution**: Multiple nodes can run concurrently when there are no dependencies
- **Complex branching**: Easy to express conditional logic and loops
- **Visual debugging**: Workflows can be visualized as graphs
- **Resumability**: Can pause at any node and resume later
- **Modularity**: Nodes are self-contained and reusable

### Proposed Implementation for good-agent

**Design Philosophy**: Keep it simple. Most agents don't need full graph orchestration, but when they do, the API should feel natural.

```python
from good_agent import Agent, Workflow, Node

agent = Agent("You are a research assistant.")

# Option 1: Declarative graph definition
workflow = Workflow()

@workflow.node('research')
async def research_node(ctx):
    """Research step"""
    query = ctx.state.get('query')
    results = await ctx.agent.invoke(web_search, query=query)
    ctx.state['research_results'] = results
    return 'analyze'  # Next node name

@workflow.node('analyze')
async def analyze_node(ctx):
    """Analyze step"""
    results = ctx.state['research_results']
    analysis = await ctx.agent.call(f"Analyze these results: {results}")
    ctx.state['analysis'] = analysis

    # Conditional transition
    if ctx.state.get('needs_more_research'):
        return 'research'  # Loop back
    else:
        return 'synthesize'

@workflow.node('synthesize')
async def synthesize_node(ctx):
    """Synthesize final answer"""
    analysis = ctx.state['analysis']
    response = await ctx.agent.call(f"Synthesize: {analysis}")
    return response  # Return value ends workflow

# Attach workflow to agent
agent.workflow = workflow

# Execute
async with agent:
    result = await agent.call("Research quantum computing", route='research')
    # Automatically executes: research -> analyze -> synthesize

# Option 2: Functional API for simple cases
from good_agent import pipeline

@pipeline(agent)
async def research_pipeline(ctx):
    """Linear pipeline - syntactic sugar over workflow"""

    # Step 1
    results = await ctx.agent.invoke(web_search, query=ctx.state['query'])

    # Step 2
    analysis = await ctx.agent.call(f"Analyze: {results}")

    # Step 3
    if ctx.needs_more_depth:
        results = await ctx.agent.invoke(arxiv_search, query=ctx.state['query'])
        analysis = await ctx.agent.call(f"Deeper analysis: {results}")

    # Step 4
    return await ctx.agent.call(f"Synthesize: {analysis}")

# Execute pipeline
async with agent:
    result = await research_pipeline.execute(query="quantum computing")

# Option 3: Visual workflow builder (future consideration)
workflow = (Workflow()
    .add_node('research', research_node)
    .add_node('analyze', analyze_node)
    .add_node('synthesize', synthesize_node)
    .add_edge('research', 'analyze')
    .add_conditional_edge(
        'analyze',
        condition=lambda ctx: ctx.needs_more_research,
        if_true='research',
        if_false='synthesize'
    )
)
```

**Key Decisions**:
1. **Return value determines transition**: Returning a string transitions to that node, returning a value ends workflow
2. **State is a dict**: Simple and Pythonic, can be accessed via `ctx.state`
3. **No explicit graph classes**: Decorator approach feels more natural
4. **Conditional edges as return values**: Simpler than explicit condition functions
5. **Integrate with existing routes**: Workflows can be routes themselves

**Implementation Notes**:
- Workflows should support both sync and async nodes
- Add visualization via `workflow.visualize()` using graphviz
- Support parallel execution with `workflow.parallel(['node1', 'node2'])`
- Integrate with existing event system for observability

---

## 2. Checkpointing and State Persistence

### What It Is

The ability to save agent state at any point and resume execution later. Critical for:
- Long-running agents that may be interrupted
- Human-in-the-loop workflows that wait for user input
- Error recovery and retry logic
- Debugging and replay

### Current State of the Art

**LangGraph** (Industry leader):
```python
from langgraph.checkpoint.sqlite import SqliteSaver

# Persistent checkpointing
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = workflow.compile(checkpointer=checkpointer)

# Execute with thread ID for persistence
config = {"configurable": {"thread_id": "conversation-123"}}
result = await graph.ainvoke({"query": "..."}, config)

# Resume later
more_results = await graph.ainvoke({"query": "follow up"}, config)
# Automatically resumes from checkpoint

# Manual checkpoint management
checkpoints = checkpointer.list(config)
state = checkpointer.get(config, checkpoint_id)
```

**AutoGen v0.4**:
```python
# Event-driven checkpointing
runtime = SingleThreadedAgentRuntime()
await runtime.register("agent_id", agent)

# State automatically persisted in runtime
# Can resume from failures
```

### Why It's Useful

- **Resumability**: Pause and resume conversations across sessions
- **Human-in-the-loop**: Wait for user input without holding connections
- **Error recovery**: Rollback to previous state on errors
- **Debugging**: Replay conversations from checkpoints
- **Experimentation**: Branch from checkpoints to explore alternatives

### Proposed Implementation for good-agent

**Design Philosophy**: Make checkpointing opt-in but trivial to enable. Use familiar patterns (context managers, decorators).

```python
from good_agent import Agent, Checkpointer

# Option 1: Automatic checkpointing
agent = Agent(
    "You are a helpful assistant.",
    checkpointer=Checkpointer.from_file("checkpoints.json")
    # or Checkpointer.from_sqlite("checkpoints.db")
    # or Checkpointer.from_redis(redis_client)
)

# Checkpoints saved automatically at key points
async with agent:
    response = await agent.call("Hello", conversation_id="conv-123")
    # Checkpoint saved

    response = await agent.call("Tell me more", conversation_id="conv-123")
    # Checkpoint updated

# Resume from checkpoint (automatic)
async with agent:
    # Using same conversation_id loads checkpoint
    response = await agent.call("Continue", conversation_id="conv-123")
    # Conversation history automatically restored

# Option 2: Manual checkpoint control
async with agent:
    response1 = await agent.call("What is quantum computing?")

    # Create named checkpoint
    checkpoint = agent.checkpoint("before_deep_dive")

    response2 = await agent.call("Explain entanglement in detail")
    response3 = await agent.call("Now explain superposition")

    # Rollback to checkpoint
    agent.restore(checkpoint)
    # or agent.restore("before_deep_dive")

    # Take a different path
    response4 = await agent.call("Tell me about practical applications")

# Option 3: Checkpoint decorators for routes
@agent.route('research')
@agent.checkpoint_before()  # Auto-checkpoint before entering route
async def research(ctx):
    """Research with automatic checkpointing"""

    try:
        results = await extensive_research(ctx)
        return results
    except Exception as e:
        # Automatic rollback on error
        ctx.restore_checkpoint()
        return ctx.next('error_handler')

# Option 4: Checkpoint branching for exploration
async with agent:
    response1 = await agent.call("Tell me about space")

    checkpoint = agent.checkpoint("main")

    # Branch A: Mars focus
    with agent.branch("mars_branch", from_checkpoint=checkpoint):
        mars_response = await agent.call("Focus on Mars")

    # Branch B: Moon focus
    with agent.branch("moon_branch", from_checkpoint=checkpoint):
        moon_response = await agent.call("Focus on Moon")

    # Compare branches and merge best one
    if mars_response.quality > moon_response.quality:
        agent.merge_branch("mars_branch")

# Option 5: Checkpoint inspection and management
# List checkpoints
checkpoints = agent.list_checkpoints(conversation_id="conv-123")
for cp in checkpoints:
    print(f"{cp.name} at {cp.timestamp}: {cp.message_count} messages")

# Diff checkpoints
diff = agent.diff_checkpoints(checkpoint1, checkpoint2)
print(f"Messages added: {len(diff.added_messages)}")

# Export/import checkpoints
agent.export_checkpoint("checkpoint.json")
agent.import_checkpoint("checkpoint.json")
```

**Key Decisions**:
1. **Conversation ID for automatic persistence**: Use `conversation_id` parameter to enable persistence
2. **Multiple storage backends**: File, SQLite, Redis, etc.
3. **Automatic vs manual**: Auto-checkpoint at key points (after each call), manual for fine control
4. **Checkpoint branching**: Support exploring different conversation paths
5. **Serializable state**: Agent state must be JSON-serializable by default

**Implementation Notes**:
- Checkpointer interface: `save(conversation_id, state)`, `load(conversation_id)`, `list(conversation_id)`
- State includes: messages, context, component state, current route
- Add `@serializable` decorator for custom state objects
- Integrate with existing `agent.messages` and `agent.state` APIs
- Support checkpoint metadata (tags, description, quality scores)

---

## 3. Multi-Agent Collaboration Patterns

### What It Is

Multiple agents working together to solve problems. Different patterns:
- **Hierarchical**: Leader delegates to workers (LangGraph Supervisor)
- **Swarm**: Many simple agents collaborate (LangGraph Swarm, OpenAI Swarm)
- **Peer-to-peer**: Agents collaborate as equals (AutoGen)
- **Sequential handoff**: Agents pass tasks in sequence (CrewAI)
- **Debate/Ensemble**: Multiple agents solve same problem, best answer chosen

### Current State of the Art

**LangGraph Supervisor** (2025):
```python
from langgraph_supervisor import Supervisor

supervisor = Supervisor(
    workers=[research_agent, writing_agent, coding_agent],
    llm=ChatAnthropic()
)

result = await supervisor.run("Build a web app")
# Supervisor delegates subtasks to appropriate workers
```

**LangGraph Swarm** (May 2025):
```python
from langgraph_swarm import Swarm, Agent as SwarmAgent

agent1 = SwarmAgent(name="researcher", instructions="...")
agent2 = SwarmAgent(name="writer", instructions="...")

swarm = Swarm(agents=[agent1, agent2])
result = await swarm.run("Create a report")
# Agents dynamically hand off control
```

**CrewAI**:
```python
from crewai import Crew, Agent, Task

researcher = Agent(role="Researcher", goal="Research topic", tools=[...])
writer = Agent(role="Writer", goal="Write report", tools=[...])

task1 = Task(description="Research AI", agent=researcher)
task2 = Task(description="Write report", agent=writer, context=[task1])

crew = Crew(agents=[researcher, writer], tasks=[task1, task2])
result = crew.kickoff()
```

**AutoGen v0.4**:
```python
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat

agent1 = AssistantAgent("agent1", model_client=..., tools=[...])
agent2 = AssistantAgent("agent2", model_client=..., tools=[...])

team = RoundRobinGroupChat([agent1, agent2])
result = await team.run("Solve this problem")
```

### Why It's Useful

- **Specialization**: Each agent focuses on what it does best
- **Parallelization**: Multiple agents work simultaneously
- **Quality improvement**: Debate/ensemble reduces errors
- **Complex workflows**: Break down complex tasks
- **Human-like collaboration**: Mirrors how human teams work

### Proposed Implementation for good-agent

**Design Philosophy**: Agents can already be used as tools. Build collaboration patterns as lightweight wrappers, not a separate system.

```python
from good_agent import Agent, Collaboration

# Agents are just regular agents
research_agent = Agent(
    "You are a research specialist.",
    tools=[web_search, arxiv_search]
)

writing_agent = Agent(
    "You are a writing specialist.",
    tools=[grammar_check, style_guide]
)

coding_agent = Agent(
    "You are a coding specialist.",
    tools=[code_generator, linter]
)

# Option 1: Leader-follower (supervisor pattern)
supervisor = Agent(
    "You are a project manager. Delegate tasks to specialists.",
    tools=[research_agent, writing_agent, coding_agent]
)

async with supervisor:
    result = await supervisor.call("Build a web app for tracking expenses")
    # Supervisor decides which agents to call and in what order

# Option 2: Explicit collaboration pattern
from good_agent.patterns import Supervisor

collaboration = Supervisor(
    leader=supervisor,
    workers={
        'research': research_agent,
        'writing': writing_agent,
        'coding': coding_agent
    }
)

async with collaboration:
    result = await collaboration.execute("Build a web app")
    # Explicit delegation with visibility into subtasks

# Option 3: Sequential handoff
from good_agent.patterns import Sequential

pipeline = Sequential([
    research_agent,  # First does research
    writing_agent,   # Then writes based on research
])

async with pipeline:
    result = await pipeline.execute("Write a report on AI safety")

# Option 4: Parallel execution
from good_agent.patterns import Parallel

parallel = Parallel([
    research_agent,
    writing_agent,
    coding_agent
])

async with parallel:
    # All agents work on same task simultaneously
    results = await parallel.execute("Analyze this problem")
    # Returns list of results from each agent

# Option 5: Debate pattern
from good_agent.patterns import Debate

agent_pro = Agent("You argue for approach A")
agent_con = Agent("You argue for approach B")
moderator = Agent("You are an impartial moderator")

debate = Debate(
    participants=[agent_pro, agent_con],
    moderator=moderator,
    rounds=3
)

async with debate:
    result = await debate.run("Should we use SQL or NoSQL?")
    # Agents debate, moderator synthesizes best solution

# Option 6: Ensemble pattern
from good_agent.patterns import Ensemble

ensemble = Ensemble(
    agents=[
        Agent("Solver 1", model='gpt-4'),
        Agent("Solver 2", model='claude-3'),
        Agent("Solver 3", model='gemini'),
    ],
    selector=Agent("You evaluate solutions and pick the best")
)

async with ensemble:
    result = await ensemble.solve("What is the capital of France?")
    # All agents solve, selector picks best answer

# Option 7: Swarm pattern
from good_agent.patterns import Swarm

swarm = Swarm(
    num_agents=10,
    agent_template=Agent("You are a search agent."),
    aggregator=lambda results: list(set(results))  # Deduplicate
)

async with swarm:
    results = await swarm.search("Latest AI research papers")
    # 10 agents search in parallel, results aggregated

# Option 8: Custom collaboration with explicit handoffs
@agent.route('collaborative_research')
async def collaborative_research(ctx):
    """Custom collaboration logic"""

    # Step 1: Research agent gathers data
    research = await ctx.invoke_agent(
        research_agent,
        "Find recent papers on quantum computing"
    )

    # Step 2: Writing agent summarizes
    summary = await ctx.invoke_agent(
        writing_agent,
        f"Summarize these findings: {research}"
    )

    # Step 3: If technical, get coding agent's input
    if 'implementation' in summary.lower():
        code = await ctx.invoke_agent(
            coding_agent,
            f"Provide code examples for: {summary}"
        )
        summary += f"\n\n{code}"

    return summary

# Helper for invoking agents
async def invoke_agent(self, agent: Agent, message: str):
    """Invoke another agent and add to history"""
    # Creates mini-conversation with agent
    async with agent:
        result = await agent.call(message)

    # Add to current agent's history
    self.append_assistant(f"[{agent.name}]: {result}")

    return result
```

**Key Decisions**:
1. **Agents as tools is the foundation**: Use existing agent-as-tool pattern
2. **Collaboration patterns are helpers**: Lightweight wrappers, not a new system
3. **Explicit vs implicit**: Support both explicit orchestration and implicit collaboration
4. **Visibility**: Make agent interactions visible in history
5. **Composability**: Patterns can be nested and combined

**Implementation Notes**:
- Add `agent.invoke_agent(other_agent, message)` helper
- Collaboration patterns in `good_agent.patterns` module
- Support both multi-turn and single-shot agent invocations
- Add observability for multi-agent interactions
- Consider adding `@collaboration` decorator for custom patterns

---

## 4. Event-Driven Architecture

### What It Is

Agents that respond to events in real-time rather than just request-response. Key features:
- **Async by default**: Non-blocking operations
- **Event emission**: Agents emit events during execution
- **Event subscription**: Agents/systems subscribe to events
- **Stream processing**: Handle streaming data and responses
- **Long-running**: Agents can run indefinitely

### Current State of the Art

**AutoGen v0.4** (Major architectural shift):
```python
from autogen_core import SingleThreadedAgentRuntime, MessageContext
from autogen_core.components import event

class MyAgent:
    async def on_message(self, message: str, ctx: MessageContext):
        # Process message
        await ctx.publish_event("response_ready", {"response": "..."})

runtime = SingleThreadedAgentRuntime()
await runtime.register("my_agent", MyAgent)

# Event-driven execution
await runtime.publish_event("user_message", {"text": "hello"})
```

**LlamaIndex Workflows**:
```python
from llama_index.core.workflow import Event

class CustomEvent(Event):
    data: str

class MyWorkflow(Workflow):
    @step
    async def step1(self, ev: StartEvent) -> CustomEvent:
        # Emit custom event
        return CustomEvent(data="result")

    @step
    async def step2(self, ev: CustomEvent) -> StopEvent:
        # React to custom event
        return StopEvent(result=ev.data)
```

### Why It's Useful

- **Real-time responsiveness**: React to events as they happen
- **Loose coupling**: Components don't need to know about each other
- **Scalability**: Event-driven systems scale better
- **Observability**: Events provide natural audit trail
- **Long-running agents**: Can run indefinitely, reacting to events

### Proposed Implementation for good-agent

**Design Philosophy**: Build on existing event router. Add streaming and async patterns.

```python
from good_agent import Agent, Event

agent = Agent("You are a helpful assistant.")

# Option 1: Event emission during execution
@agent.route('processing')
async def processing_route(ctx):
    """Route that emits events"""

    # Emit progress events
    ctx.emit('processing:started', {'query': ctx.agent[-1].content})

    results = await long_running_task()

    ctx.emit('processing:halfway', {'partial_results': results[:10]})

    final_results = await process_results(results)

    ctx.emit('processing:complete', {'results': final_results})

    return ctx.next('ready')

# Subscribe to events
@agent.on('processing:halfway')
async def on_halfway(event):
    """React to halfway event"""
    print(f"Halfway done: {event.data['partial_results']}")

# Option 2: Streaming responses
@agent.route('streaming')
async def streaming_route(ctx):
    """Stream response chunks"""

    async for chunk in ctx.llm_call_stream():
        # Emit each chunk
        ctx.emit('response:chunk', {'chunk': chunk})

        # Can process or interrupt
        if 'ERROR' in chunk:
            ctx.interrupt()
            return ctx.next('error_handler')

    return ctx.next('ready')

# Subscribe to streaming chunks
@agent.on('response:chunk')
async def on_chunk(event):
    print(event.data['chunk'], end='', flush=True)

# Option 3: External event handling
from good_agent import EventBus

event_bus = EventBus()

@agent.on_external('user:message')
async def on_user_message(event, ctx):
    """React to external user messages"""
    response = await ctx.agent.call(event.data['message'])
    event_bus.emit('agent:response', {'response': response})

# Emit external events
event_bus.emit('user:message', {'message': 'Hello'})

# Option 4: Long-running reactive agent
async def start_monitoring_agent():
    """Long-running agent that reacts to system events"""

    async with agent:
        # Listen for events indefinitely
        async for event in event_bus.subscribe('system:*'):
            if event.type == 'system:error':
                response = await agent.call(
                    f"Analyze this error: {event.data}"
                )
                event_bus.emit('alert:admin', {'analysis': response})

# Start in background
asyncio.create_task(start_monitoring_agent())

# Option 5: Event-driven workflows
@agent.workflow_event('research_complete')
async def on_research_complete(ctx, event):
    """Triggered when research completes"""
    research_data = event.data['research']

    # Automatically transition to analysis
    ctx.state['research_data'] = research_data
    return ctx.next('analyze')

# Option 6: Reactive context updates
@agent.on('context:needed')
async def inject_context(event, ctx):
    """Dynamically inject context based on events"""

    if event.data['type'] == 'rag':
        docs = await vector_store.search(event.data['query'])
        ctx.add_context_message(f"Relevant docs: {docs}")

# Option 7: Backpressure and rate limiting
from good_agent import RateLimitedStream

stream = RateLimitedStream(max_rate=10)  # 10 events/second

@agent.on('high_frequency:event')
async def on_event(event):
    """Handle high-frequency events with backpressure"""
    await stream.emit(event)

async for event in stream.consume():
    # Process at controlled rate
    await process_event(event)
```

**Key Decisions**:
1. **Build on existing event router**: Don't create parallel system
2. **Events during route execution**: `ctx.emit()` within routes
3. **Streaming as events**: Chunk-by-chunk emission
4. **External event bus**: Integrate with external systems
5. **Long-running agents**: Support indefinite execution with event loops

**Implementation Notes**:
- Add `ctx.emit(event_type, data)` to AgentContext
- Support `async for chunk in ctx.llm_call_stream()` for streaming
- Add `EventBus` for cross-agent communication
- Support event filtering with wildcards: `agent.on('system:*')`
- Add backpressure mechanisms for high-frequency events

---

## 5. Advanced Memory Systems

### What It Is

Sophisticated memory management beyond simple conversation history:
- **Semantic memory**: Store and retrieve facts
- **Episodic memory**: Remember important events
- **Working memory**: Current context with capacity limits
- **Memory decay**: Older memories become less relevant
- **Memory consolidation**: Move important memories to long-term storage

### Current State of the Art

**LangGraph**:
```python
from langgraph.prebuilt import MemorySaver

memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

# Memory persisted across runs
```

**CrewAI**:
```python
from crewai import Agent

agent = Agent(
    memory=True,  # Short-term memory
    long_term_memory=True,  # Persists across sessions
    entity_memory=True,  # Remembers entities
)
```

Most frameworks have basic memory but not sophisticated systems.

### Why It's Useful

- **Personalization**: Remember user preferences and history
- **Context management**: Intelligent pruning of old/irrelevant info
- **Learning**: Agents can learn from past interactions
- **Efficiency**: Don't send entire history to LLM every time
- **Long-running agents**: Maintain knowledge over days/weeks

### Proposed Implementation for good-agent

**Design Philosophy**: Start simple, add sophistication gradually. Memory layers are opt-in.

```python
from good_agent import Agent, Memory

agent = Agent("You are a helpful assistant.")

# Option 1: Simple memory layers
agent.add_memory_layer(
    'working',
    Memory.working(capacity=10)  # Last 10 messages
)

agent.add_memory_layer(
    'episodic',
    Memory.episodic(
        storage='sqlite:///memories.db',
        importance_threshold=0.7  # Only store important events
    )
)

agent.add_memory_layer(
    'semantic',
    Memory.semantic(
        storage='chroma',  # Vector DB
        embedding_model='text-embedding-3-small'
    )
)

async with agent:
    # Working memory used automatically
    response = await agent.call("My name is Alice")

    response = await agent.call("What's my name?")
    # Retrieved from working memory: "Alice"

    # Important events auto-stored in episodic memory
    response = await agent.call("I just got promoted to VP!")
    # Stored in episodic (high importance)

    # Facts auto-stored in semantic memory
    response = await agent.call("The capital of France is Paris")
    # Stored in semantic as structured fact

# Option 2: Memory querying
from good_agent.memory import MemoryQuery

@agent.route('ready')
async def ready_with_memory(ctx):
    """Route that leverages memory"""

    query = ctx.agent[-1].content

    # Query all memory layers
    memories = await ctx.agent.memory.recall(query)

    # Add relevant memories to context
    if memories.episodic:
        ctx.add_context_message(
            "# Past conversations\n" +
            "\n".join(m.summary for m in memories.episodic)
        )

    if memories.semantic:
        ctx.add_context_message(
            "# Relevant facts\n" +
            "\n".join(f.text for f in memories.semantic)
        )

    response = await ctx.llm_call()
    return response

# Option 3: Memory consolidation
@agent.background_task(interval=timedelta(hours=1))
async def consolidate_memories():
    """Periodically consolidate memories"""

    # Move important short-term to long-term
    await agent.memory.consolidate()

    # Prune low-importance memories
    await agent.memory.prune(keep_top_k=100)

# Option 4: Temporal memory (decay over time)
agent.add_memory_layer(
    'temporal',
    Memory.temporal(
        decay_rate=0.5,  # 50% decay per day
        half_life=timedelta(days=7)
    )
)

# Older memories automatically weighted less

# Option 5: Hierarchical memory
agent.add_memory_layer(
    'hierarchical',
    Memory.hierarchical(
        levels=['general', 'summary', 'detailed']
    )
)

# Query at different detail levels
general = await agent.memory.recall(query, level='general')
detailed = await agent.memory.recall(query, level='detailed')

# Drill down
full_detail = await agent.memory.drill_down(memory_id)

# Option 6: Explicit memory management
async with agent:
    response = await agent.call("Remember: I prefer dark mode")

    # Manually store in semantic memory
    agent.memory.semantic.store(
        fact="User prefers dark mode",
        tags=['preference', 'ui'],
        importance=0.9
    )

    # Later retrieval
    preferences = await agent.memory.semantic.query(
        "What are user's preferences?",
        tags=['preference']
    )

# Option 7: Memory inspection
memories = agent.memory.list(type='episodic', limit=10)
for mem in memories:
    print(f"{mem.timestamp}: {mem.summary} (importance: {mem.importance})")

# Export memories
agent.memory.export("memories.json")

# Import memories
agent.memory.import_from("memories.json")
```

**Key Decisions**:
1. **Layered architecture**: Different memory types for different purposes
2. **Automatic vs manual**: Automatic storage with manual override
3. **Storage backends**: Support file, SQLite, Redis, vector DBs
4. **Importance scoring**: Auto-calculate or manual override
5. **Query interface**: Unified interface across memory types

**Implementation Notes**:
- Memory interface: `store(item)`, `recall(query)`, `prune()`, `consolidate()`
- Importance calculation: Based on conversation context, emotional content, user signals
- Integration with vector stores: Use existing embeddings/vector DB integrations
- Background tasks: Use asyncio for periodic consolidation
- Privacy controls: Add retention policies and GDPR compliance features

---

## 6. Tool Calling Enhancements

### What It Is

Advanced patterns for tool usage beyond simple function calling:
- **Parallel tool calls**: Call multiple tools simultaneously
- **Tool validation**: Validate tool inputs before execution
- **Tool retries**: Automatic retry on failures
- **Conditional tool availability**: Tools available based on context
- **Tool composition**: Tools that call other tools
- **Tool observability**: Track all tool invocations

### Current State of the Art

Most frameworks support basic tool calling. Advanced features vary:

**Function calling workflow**:
1. LLM decides to call tool and generates arguments
2. Tool executed
3. Result returned to LLM
4. LLM interprets result and decides next action

**Parallel tool calls**: Supported by OpenAI, Anthropic models
**Structured outputs**: Pydantic models for type safety

### Why It's Useful

- **Performance**: Parallel tool calls faster than sequential
- **Reliability**: Validation and retries reduce errors
- **Flexibility**: Dynamic tool availability based on context
- **Debugging**: Observability into tool usage
- **Safety**: Validate before executing dangerous operations

### Proposed Implementation for good-agent

**Design Philosophy**: Make tools first-class citizens with rich capabilities.

```python
from good_agent import Agent, Tool, tool
from pydantic import BaseModel, Field

agent = Agent("You are a helpful assistant.")

# Option 1: Enhanced tool decorator
@tool(
    name="web_search",
    description="Search the web for information",
    validation=True,  # Validate inputs before execution
    retry=3,  # Retry up to 3 times on failure
    timeout=30,  # 30 second timeout
)
async def web_search(
    query: str = Field(description="Search query"),
    max_results: int = Field(default=10, description="Max results to return")
) -> str:
    """Search the web"""
    # Implementation
    return results

agent.add_tool(web_search)

# Option 2: Tool validation
from good_agent import ToolValidator

@tool(validators=[
    ToolValidator.not_empty('query'),
    ToolValidator.max_length('query', 500),
    ToolValidator.positive('max_results'),
])
async def validated_search(query: str, max_results: int):
    """Search with validation"""
    return results

# Option 3: Conditional tool availability
@tool(
    available_when=lambda ctx: ctx.user.tier == 'premium'
)
async def premium_tool():
    """Only available to premium users"""
    return results

@tool(
    available_when=lambda ctx: 9 <= datetime.now().hour <= 17
)
async def business_hours_tool():
    """Only available during business hours"""
    return results

# Dynamic tool registration
@agent.route('research_mode')
async def research_mode(ctx):
    """Add research tools dynamically"""

    # Add tools for this route only
    ctx.add_tools([arxiv_search, pubmed_search, google_scholar])

    response = await ctx.llm_call()

    # Tools automatically removed after route
    return ctx.next('ready')

# Option 4: Tool composition
@tool(name="deep_research")
async def deep_research(topic: str, ctx):
    """Tool that calls other tools"""

    # Call other tools
    web_results = await ctx.call_tool(web_search, query=topic)
    academic_results = await ctx.call_tool(arxiv_search, query=topic)

    # Combine results
    return f"Web: {web_results}\n\nAcademic: {academic_results}"

# Option 5: Parallel tool execution
@tool(parallel=True)
async def search_all_sources(query: str, ctx):
    """Search multiple sources in parallel"""

    # Execute in parallel
    results = await ctx.parallel_tools([
        (web_search, {'query': query}),
        (arxiv_search, {'query': query}),
        (news_search, {'query': query})
    ])

    return results

# Or automatic parallel detection
@agent.route('ready')
async def ready_with_parallel_tools(ctx):
    """Agent can call multiple tools in parallel"""

    response = await ctx.llm_call(parallel_tools=True)
    # LLM can request multiple tool calls
    # Agent executes them in parallel automatically

    return response

# Option 6: Tool retries with backoff
from good_agent import RetryStrategy

@tool(
    retry_strategy=RetryStrategy.exponential_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=10.0
    )
)
async def unreliable_api():
    """Tool with automatic retry"""
    # May fail, will auto-retry
    return results

# Option 7: Tool observability
from good_agent import ToolObserver

observer = ToolObserver()

@tool(observers=[observer])
async def monitored_tool(query: str):
    """Tool with observability"""
    return results

# View tool metrics
stats = observer.get_stats(tool_name="monitored_tool")
print(f"Calls: {stats.total_calls}")
print(f"Failures: {stats.failures}")
print(f"Avg duration: {stats.avg_duration}")

# Option 8: Tool sandboxing (safety)
@tool(
    sandbox=True,  # Execute in sandbox
    allow_network=False,  # No network access
    max_cpu_time=5,  # Max 5 seconds CPU
)
async def safe_code_execution(code: str):
    """Execute user code safely"""
    # Runs in sandbox with restrictions
    return result

# Option 9: Tool mocking for testing
from good_agent.testing import MockTool

# Replace tool with mock in tests
agent.mock_tool('web_search', MockTool(
    return_value="Mocked search results"
))

async with agent:
    response = await agent.call("Search for quantum computing")
    # Uses mock instead of real search

# Option 10: Tool schema generation
# Automatically generate JSON schema from Pydantic models
class SearchParams(BaseModel):
    query: str = Field(description="Search query")
    language: str = Field(default="en", description="Result language")
    max_results: int = Field(default=10, ge=1, le=100)

@tool(params=SearchParams)
async def typed_search(params: SearchParams):
    """Type-safe search"""
    return results

# Schema automatically sent to LLM
# Runtime type validation
```

**Key Decisions**:
1. **Pydantic for schemas**: Use Pydantic models for type safety
2. **Decorator-based**: Familiar @tool decorator pattern
3. **Validation built-in**: Validate before execution
4. **Retry strategies**: Configurable retry logic
5. **Conditional availability**: Context-aware tool filtering
6. **Observability**: Track all tool calls
7. **Sandboxing**: Safety for code execution tools

**Implementation Notes**:
- Extend existing `@tool` decorator with new parameters
- Add `ctx.call_tool()` and `ctx.parallel_tools()` helpers
- Implement ToolValidator with common validators
- Add RetryStrategy with exponential backoff, jitter
- Integrate with observability systems (OpenTelemetry)
- Consider adding tool categories/tags for organization

---

## 7. Structured Outputs and Type Safety

### What It Is

Ensuring LLM outputs match expected schemas:
- **Pydantic models**: Define expected output structure
- **JSON mode**: Force LLM to output valid JSON
- **Enum constraints**: Limit outputs to specific values
- **Validation**: Validate outputs match schema
- **Retry on invalid**: Automatically retry if output doesn't match

### Current State of the Art

**OpenAI Structured Outputs**:
```python
from pydantic import BaseModel

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

completion = client.chat.completions.create(
    model="gpt-4",
    messages=[...],
    response_format=CalendarEvent
)

event = completion.choices[0].message.parsed
```

**Instructor** (Popular library):
```python
import instructor
from pydantic import BaseModel

client = instructor.from_openai(OpenAI())

class UserInfo(BaseModel):
    name: str
    age: int

user = client.chat.completions.create(
    model="gpt-4",
    response_model=UserInfo,
    messages=[...]
)
```

### Why It's Useful

- **Reliability**: Ensure outputs are parseable
- **Type safety**: Catch errors at development time
- **Integration**: Easier to integrate with typed systems
- **Validation**: Automatic validation of outputs
- **Error recovery**: Retry on invalid outputs

### Proposed Implementation for good-agent

**Design Philosophy**: Make structured outputs easy with Pydantic integration.

```python
from good_agent import Agent
from pydantic import BaseModel, Field

agent = Agent("You are a helpful assistant.")

# Option 1: Response model
class Event(BaseModel):
    """Calendar event"""
    name: str = Field(description="Event name")
    date: str = Field(description="Event date in YYYY-MM-DD format")
    location: str = Field(description="Event location")
    participants: list[str] = Field(description="List of participants")

async with agent:
    # Request structured output
    event = await agent.call(
        "Create an event for team meeting tomorrow at 2pm",
        response_model=Event
    )

    # event is typed Event instance
    print(event.name)  # Type-safe
    print(event.date)

# Option 2: JSON mode (less strict)
async with agent:
    result = await agent.call(
        "List 3 programming languages",
        json_mode=True
    )

    # result is valid JSON dict
    languages = result['languages']

# Option 3: Enum constraints
from enum import Enum

class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"

class SentimentAnalysis(BaseModel):
    sentiment: Sentiment
    confidence: float = Field(ge=0.0, le=1.0)

async with agent:
    analysis = await agent.call(
        "Analyze sentiment: I love this product!",
        response_model=SentimentAnalysis
    )

    # analysis.sentiment is guaranteed to be one of the enum values
    assert isinstance(analysis.sentiment, Sentiment)

# Option 4: Validation with retries
async with agent:
    event = await agent.call(
        "Create an event",
        response_model=Event,
        max_retries=3,  # Retry up to 3 times if validation fails
        validation_error_prompt="The output didn't match the schema. Try again."
    )

# Option 5: Partial responses (streaming)
async with agent:
    async for partial in agent.call_stream(
        "Create a detailed event",
        response_model=Event,
        partial=True  # Yield partial models as they're built
    ):
        print(f"Current progress: {partial}")
        # partial is partially filled Event instance

# Option 6: Union types for multiple possible outputs
from typing import Union

class SuccessResponse(BaseModel):
    status: str = "success"
    data: dict

class ErrorResponse(BaseModel):
    status: str = "error"
    error_message: str

async with agent:
    response = await agent.call(
        "Process this request",
        response_model=Union[SuccessResponse, ErrorResponse]
    )

    # Type narrowing
    if isinstance(response, SuccessResponse):
        print(response.data)
    else:
        print(response.error_message)

# Option 7: Route-specific response models
@agent.route('extract_info')
async def extract_info(ctx):
    """Route with structured output"""

    class PersonInfo(BaseModel):
        name: str
        age: int
        occupation: str

    # Use response model for this route
    person = await ctx.llm_call(response_model=PersonInfo)

    return person

# Option 8: Tool outputs as structured models
@tool(response_model=list[str])
async def list_files(directory: str) -> list[str]:
    """Tool with typed output"""
    # Output automatically validated
    return ["file1.txt", "file2.txt"]

# Option 9: Validation error handling
from pydantic import ValidationError

async with agent:
    try:
        event = await agent.call(
            "Create an event",
            response_model=Event,
            max_retries=0  # Don't retry
        )
    except ValidationError as e:
        # Handle validation errors
        print(f"LLM output didn't match schema: {e}")

# Option 10: Schema in system prompt
# Automatically inject schema into system prompt for better results
async with agent:
    event = await agent.call(
        "Create an event",
        response_model=Event,
        inject_schema=True  # Add schema to system prompt
    )
```

**Key Decisions**:
1. **Pydantic models**: Use Pydantic for schemas (already widely adopted)
2. **response_model parameter**: Simple API for structured outputs
3. **Automatic retries**: Retry on validation failures by default
4. **Streaming support**: Partial models during streaming
5. **Union types**: Support multiple possible output types
6. **Schema injection**: Optionally inject schema into prompts

**Implementation Notes**:
- Integrate with LLM providers' structured output features (OpenAI, Anthropic)
- Fallback to prompt-based structured output for models that don't support it natively
- Add validation error messages to context for retries
- Support partial models with `model_construct()` during streaming
- Consider adding schema visualization for debugging

---

## 8. Observability and Debugging

### What It Is

Tools for understanding what agents are doing:
- **Tracing**: Track execution flow through routes, tools, LLM calls
- **Logging**: Detailed logs of agent behavior
- **Metrics**: Performance metrics (latency, token usage, cost)
- **Debugging**: Step-through debugging, breakpoints
- **Visualization**: Visual representation of agent execution

### Current State of the Art

**LangSmith** (LangChain's observability platform):
- Automatic tracing of LangChain/LangGraph applications
- Web UI for viewing traces
- Debugging and testing tools

**LlamaIndex Observability**:
```python
from llama_index.core import set_global_handler

set_global_handler("arize_phoenix")
# Automatic instrumentation
```

**OpenTelemetry Integration**:
Many frameworks now support OpenTelemetry for observability

### Why It's Useful

- **Debugging**: Understand why agent made certain decisions
- **Performance**: Identify bottlenecks
- **Cost tracking**: Monitor token usage and API costs
- **Quality assurance**: Detect issues in production
- **Auditing**: Track agent actions for compliance

### Proposed Implementation for good-agent

**Design Philosophy**: Observability should be opt-in but comprehensive when enabled.

```python
from good_agent import Agent, Observability

# Option 1: Simple logging
agent = Agent(
    "You are a helpful assistant.",
    log_level="DEBUG"  # Log everything
)

async with agent:
    response = await agent.call("Hello")
    # Logs: route transitions, LLM calls, tool calls, etc.

# Option 2: OpenTelemetry integration
from good_agent.observability import OpenTelemetryObserver

observer = OpenTelemetryObserver(
    service_name="my-agent",
    endpoint="http://localhost:4317"
)

agent = Agent(
    "You are a helpful assistant.",
    observers=[observer]
)

async with agent:
    response = await agent.call("Hello")
    # Automatically traced with OpenTelemetry

# Option 3: Custom observers
from good_agent import Observer

class MetricsObserver(Observer):
    """Custom observer for metrics"""

    async def on_llm_call_start(self, ctx):
        self.start_time = time.time()

    async def on_llm_call_end(self, ctx, response):
        duration = time.time() - self.start_time
        self.record_metric("llm_call_duration", duration)
        self.record_metric("tokens_used", response.usage.total_tokens)
        self.record_metric("cost", calculate_cost(response.usage))

    async def on_tool_call(self, ctx, tool_name, args):
        self.record_metric("tool_calls", 1, tags={"tool": tool_name})

agent.add_observer(MetricsObserver())

# Option 4: Trace visualization
from good_agent.observability import TraceVisualizer

visualizer = TraceVisualizer()
agent.add_observer(visualizer)

async with agent:
    response = await agent.call("Research quantum computing")

# View trace
visualizer.show()  # Opens web UI or prints ASCII art

# Export trace
visualizer.export("trace.json")

# Option 5: Step-through debugging
from good_agent import DebugMode

agent = Agent(
    "You are a helpful assistant.",
    debug=DebugMode.STEP  # Step through execution
)

async with agent:
    response = await agent.call("Hello")
    # Pauses before each major operation:
    # - Before route entry
    # - Before LLM call
    # - Before tool call
    # User can inspect state, continue, or skip

# Option 6: Breakpoints
@agent.route('research')
@agent.breakpoint  # Pause when entering this route
async def research(ctx):
    results = await do_research()

    # Conditional breakpoint
    if ctx.debug and len(results) == 0:
        ctx.breakpoint()  # Pause here

    return results

# Option 7: Metrics dashboard
from good_agent.observability import MetricsDashboard

dashboard = MetricsDashboard()
agent.add_observer(dashboard)

# View metrics
dashboard.show()  # Opens web dashboard

# Get metrics programmatically
metrics = dashboard.get_metrics()
print(f"Total LLM calls: {metrics.llm_calls}")
print(f"Total tokens: {metrics.total_tokens}")
print(f"Average latency: {metrics.avg_latency}ms")
print(f"Total cost: ${metrics.total_cost}")

# Option 8: Conversation inspection
async with agent:
    response1 = await agent.call("Hello")
    response2 = await agent.call("Tell me about AI")

    # Inspect conversation
    print(agent.messages)  # All messages
    print(agent.get_metrics())  # Metrics for this conversation
    print(agent.get_trace())  # Execution trace

# Export for analysis
agent.export_conversation("conversation.json")

# Option 9: Performance profiling
from good_agent.observability import Profiler

profiler = Profiler()
agent.add_observer(profiler)

async with agent:
    response = await agent.call("Complex query")

# View profile
profile = profiler.get_profile()
print(f"Time in LLM calls: {profile.llm_time}ms")
print(f"Time in tool calls: {profile.tool_time}ms")
print(f"Time in routing: {profile.routing_time}ms")

# Identify bottlenecks
bottlenecks = profiler.get_bottlenecks()
for bottleneck in bottlenecks:
    print(f"{bottleneck.operation}: {bottleneck.duration}ms")

# Option 10: Error tracking
from good_agent.observability import ErrorTracker

error_tracker = ErrorTracker(
    service="sentry",
    dsn="https://..."
)

agent.add_observer(error_tracker)

# Errors automatically reported
async with agent:
    try:
        response = await agent.call("Problematic query")
    except Exception as e:
        # Error automatically captured with context:
        # - Conversation history
        # - Current route
        # - Agent state
        pass
```

**Key Decisions**:
1. **Observer pattern**: Use observer pattern for extensibility
2. **OpenTelemetry integration**: Industry standard for observability
3. **Multiple observers**: Support multiple observers simultaneously
4. **Opt-in**: Observability is opt-in to avoid overhead
5. **Rich context**: Include full context in traces (messages, state, routes)

**Implementation Notes**:
- Create base `Observer` class with lifecycle hooks
- Built-in observers: `LoggingObserver`, `OpenTelemetryObserver`, `MetricsObserver`
- Add spans for: route transitions, LLM calls, tool calls, context transformations
- Include token counts, costs, latencies in spans
- Consider adding sampling for high-volume production use

---

## 9. Human-in-the-Loop Patterns

### What It Is

Agents that pause and wait for human input at key points:
- **Approval gates**: Get approval before taking action
- **Clarification**: Ask user to clarify ambiguous requests
- **Feedback loops**: Get feedback on agent outputs
- **Progressive disclosure**: Show partial results and get direction
- **Intervention**: Allow humans to override or correct agent

### Current State of the Art

Most frameworks support this through:
- Checkpointing + manual resume
- Special "wait for input" nodes
- Interactive prompts

**LangGraph example**:
```python
def approval_node(state):
    # Pause and wait for approval
    return {"needs_approval": True}

# Resume after approval
graph.invoke(state, config=config)  # Paused
# User approves
graph.invoke(state, config=config)  # Continues
```

### Why It's Useful

- **Safety**: Prevent dangerous actions without approval
- **Quality**: Get feedback before finalizing
- **Learning**: Improve agent based on human feedback
- **Transparency**: Keep humans in the loop
- **Complex decisions**: Defer to humans for judgment calls

### Proposed Implementation for good-agent

**Design Philosophy**: Make HITL natural with async/await patterns.

```python
from good_agent import Agent

agent = Agent("You are a helpful assistant.")

# Option 1: Approval gates
@agent.route('risky_action')
async def risky_action(ctx):
    """Route that requires approval"""

    # Show what we're about to do
    action = await ctx.agent.call("Plan how to delete these files")

    # Ask for approval
    approved = await ctx.request_approval(
        message=f"About to execute: {action}. Approve?",
        timeout=timedelta(minutes=5)
    )

    if approved:
        result = await execute_action(action)
        return result
    else:
        return "Action cancelled by user"

# Option 2: Clarification
@agent.route('ready')
async def ready_with_clarification(ctx):
    """Ask for clarification when needed"""

    query = ctx.agent[-1].content

    # Detect ambiguity
    if is_ambiguous(query):
        # Ask user to clarify
        clarification = await ctx.ask_user(
            "I'm not sure what you mean. Can you clarify: [options]?",
            timeout=timedelta(minutes=10)
        )

        # Add clarification to context
        ctx.agent.append_user(clarification)

    response = await ctx.llm_call()
    return response

# Option 3: Progressive disclosure
@agent.route('research')
async def research_with_feedback(ctx):
    """Show progress and get direction"""

    # Phase 1: Initial research
    initial_results = await quick_research(ctx.agent[-1].content)

    # Show to user and ask for direction
    direction = await ctx.show_and_ask(
        message=f"Found these initial results: {initial_results}",
        question="Should I: (a) Dig deeper, (b) Try different approach, (c) This is enough?",
        options=["dig_deeper", "different_approach", "enough"]
    )

    if direction == "dig_deeper":
        detailed_results = await deep_research(initial_results)
        return detailed_results
    elif direction == "different_approach":
        return ctx.next('research')  # Retry with different strategy
    else:
        return initial_results

# Option 4: Feedback loops
@agent.route('writing')
async def writing_with_feedback(ctx):
    """Iterative writing with feedback"""

    draft = await ctx.agent.call("Write a draft")

    # Get feedback
    feedback = await ctx.request_feedback(
        content=draft,
        prompt="Please review this draft. What should I improve?",
        allow_skip=True
    )

    if feedback:
        # Incorporate feedback
        revised = await ctx.agent.call(
            f"Revise this draft based on feedback:\n"
            f"Draft: {draft}\n"
            f"Feedback: {feedback}"
        )
        return revised
    else:
        return draft

# Option 5: Intervention points
@agent.route('processing')
@agent.intervention_point  # Allow user to intervene
async def processing(ctx):
    """Long-running process with intervention points"""

    results = []

    for i in range(10):
        # Check for intervention
        if await ctx.check_intervention():
            intervention = await ctx.get_intervention()

            if intervention.action == "stop":
                break
            elif intervention.action == "skip":
                continue
            elif intervention.action == "modify":
                # User modifies parameters
                ctx.state.update(intervention.parameters)

        result = await process_item(i)
        results.append(result)

    return results

# Option 6: Approval required decorator
@agent.route('delete_files')
@agent.require_approval(
    prompt="This will delete files. Are you sure?",
    timeout=timedelta(minutes=5),
    default_on_timeout="deny"
)
async def delete_files(ctx):
    """Automatically requires approval"""
    # Only executes if approved
    return await delete(ctx.state['files'])

# Option 7: Multi-option choice
@agent.route('strategy_selection')
async def select_strategy(ctx):
    """Let user choose strategy"""

    # Generate options
    strategies = await ctx.agent.call(
        "Propose 3 different strategies for this problem"
    )

    # User chooses
    choice = await ctx.ask_choice(
        message="Which strategy should I use?",
        options=[
            {"id": "strategy_a", "label": "Strategy A: ...", "description": "..."},
            {"id": "strategy_b", "label": "Strategy B: ...", "description": "..."},
            {"id": "strategy_c", "label": "Strategy C: ...", "description": "..."},
        ]
    )

    # Execute chosen strategy
    return await execute_strategy(choice)

# Option 8: Streaming with intervention
@agent.route('streaming')
async def streaming_with_intervention(ctx):
    """Stream response with option to interrupt"""

    chunks = []

    async for chunk in ctx.llm_call_stream():
        chunks.append(chunk)

        # Check if user wants to stop
        if await ctx.check_interrupt():
            ctx.emit('response:interrupted', {'partial': ''.join(chunks)})

            # Ask what to do
            action = await ctx.ask_user("Continue or start over?")

            if action == "start_over":
                return ctx.next('streaming')  # Retry
            else:
                break

    return ''.join(chunks)

# Option 9: Conditional HITL based on confidence
@agent.route('ready')
async def ready_with_confidence_check(ctx):
    """Only involve human if confidence is low"""

    response = await ctx.llm_call()

    # Check confidence
    confidence = await estimate_confidence(response)

    if confidence < 0.7:
        # Low confidence - ask for validation
        is_correct = await ctx.ask_user(
            f"I'm not very confident about this response: {response}\n"
            f"Is this correct?",
            options=["yes", "no", "revise"]
        )

        if is_correct == "no":
            # Get correct answer from user
            correct = await ctx.ask_user("What's the correct answer?")
            ctx.agent.append_assistant(correct)
            return correct
        elif is_correct == "revise":
            return ctx.next('ready')  # Try again

    return response
```

**Key Decisions**:
1. **Async/await native**: Use async/await for waiting on user input
2. **Timeout handling**: All HITL operations should have timeouts
3. **Default actions**: Configure what happens on timeout
4. **Rich options**: Support multiple choice, text input, approval/deny
5. **Intervention points**: Allow users to intervene in long-running processes

**Implementation Notes**:
- Implement using asyncio queues for user input
- Checkpoint before HITL operations to enable resume
- Add websocket support for real-time interactive UIs
- Consider adding UI components library for rich interactions
- Integrate with existing chat interfaces (Discord, Slack, web UI)

---

## 10. Testing and Evaluation

### What It Is

Tools for testing agent behavior and evaluating quality:
- **Unit tests**: Test individual routes and components
- **Integration tests**: Test full agent workflows
- **Evaluation**: Measure agent performance on benchmarks
- **Regression tests**: Ensure changes don't break existing behavior
- **Mocking**: Mock LLM and tool responses for testing

### Current State of the Art

Most frameworks lack sophisticated testing tools. Some have:
- Basic mocking capabilities
- Manual evaluation scripts
- Integration with LLM evaluation services

### Why It's Useful

- **Quality assurance**: Ensure agent works correctly
- **Regression prevention**: Catch breakages
- **Performance tracking**: Monitor improvements/degradations
- **Cost control**: Test without expensive LLM calls
- **Rapid iteration**: Test changes quickly

### Proposed Implementation for good-agent

**Design Philosophy**: Make testing agents as easy as testing regular Python code.

```python
from good_agent import Agent
from good_agent.testing import MockLLM, MockTool, AgentTester
import pytest

# Option 1: Mock LLM responses
@pytest.fixture
def agent():
    return Agent("You are a helpful assistant.")

@pytest.mark.asyncio
async def test_basic_response(agent):
    """Test with mocked LLM"""

    # Mock LLM response
    agent.mock_llm(response="Hello! How can I help?")

    async with agent:
        response = await agent.call("Hi")
        assert "help" in response.lower()

# Option 2: Mock tool calls
@pytest.mark.asyncio
async def test_tool_usage(agent):
    """Test that agent uses tool correctly"""

    # Mock tool
    agent.mock_tool('web_search', return_value="Quantum computing is...")

    async with agent:
        response = await agent.call("Search for quantum computing")

        # Verify tool was called
        assert agent.tool_called('web_search')
        assert agent.tool_call_args('web_search')['query'] == 'quantum computing'

# Option 3: Sequence of responses
@pytest.mark.asyncio
async def test_multi_turn(agent):
    """Test multi-turn conversation"""

    # Mock sequence of responses
    agent.mock_llm_sequence([
        "I'm a helpful assistant.",
        "Sure, I can help with that.",
        "Here's the information you requested."
    ])

    async with agent:
        r1 = await agent.call("Hello")
        r2 = await agent.call("Can you help?")
        r3 = await agent.call("Tell me more")

        assert "helpful" in r1
        assert "help" in r2
        assert "information" in r3

# Option 4: Route testing
@pytest.mark.asyncio
async def test_route_transition(agent):
    """Test that routes transition correctly"""

    @agent.route('start')
    async def start(ctx):
        return ctx.next('middle')

    @agent.route('middle')
    async def middle(ctx):
        return ctx.next('end')

    @agent.route('end')
    async def end(ctx):
        return "Done"

    # Test route flow
    async with agent:
        result = await agent.call("Test", route='start')

        # Verify route sequence
        assert agent.route_history == ['start', 'middle', 'end']
        assert result == "Done"

# Option 5: Evaluation harness
from good_agent.evaluation import Evaluator, Metric

evaluator = Evaluator(
    agent=agent,
    test_cases=[
        {"input": "What is 2+2?", "expected": "4"},
        {"input": "Capital of France?", "expected": "Paris"},
    ],
    metrics=[
        Metric.exact_match,
        Metric.contains_expected,
        Metric.semantic_similarity,
    ]
)

results = await evaluator.run()

print(f"Accuracy: {results.accuracy}")
print(f"Average score: {results.avg_score}")

# Option 6: Snapshot testing
@pytest.mark.asyncio
async def test_snapshot(agent, snapshot):
    """Test that output matches snapshot"""

    agent.mock_llm(response="Quantum computing uses qubits...")

    async with agent:
        response = await agent.call("What is quantum computing?")

        # Compare to snapshot
        snapshot.assert_match(response)
        # First run: saves snapshot
        # Subsequent runs: compares to saved snapshot

# Option 7: Property-based testing
from hypothesis import given, strategies as st

@given(st.text(min_size=1, max_size=100))
@pytest.mark.asyncio
async def test_never_crashes(agent, user_input):
    """Agent should never crash on any input"""

    try:
        async with agent:
            response = await agent.call(user_input)
            assert response is not None
            assert len(response) > 0
    except Exception as e:
        pytest.fail(f"Agent crashed on input: {user_input}")

# Option 8: Performance testing
from good_agent.testing import PerformanceTester

tester = PerformanceTester(agent)

results = await tester.run_benchmark(
    num_calls=100,
    concurrent=10,
    input_generator=lambda: "Random test query"
)

print(f"Average latency: {results.avg_latency}ms")
print(f"p95 latency: {results.p95_latency}ms")
print(f"Throughput: {results.throughput} calls/sec")
print(f"Error rate: {results.error_rate}%")

# Option 9: Integration testing with real LLM
@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_llm(agent):
    """Test with real LLM (marked as integration test)"""

    # Don't mock - use real LLM
    async with agent:
        response = await agent.call("What is 2+2?")

        # Fuzzy assertions for real LLM
        assert any(word in response for word in ["4", "four"])

# Option 10: Regression test suite
from good_agent.testing import RegressionSuite

suite = RegressionSuite.from_file("test_cases.json")

# Add new test case
suite.add_test(
    name="basic_math",
    input="What is 2+2?",
    expected_output="4",
    tags=["math", "basic"]
)

# Run suite
results = await suite.run(agent)

# Check for regressions
if results.has_regressions:
    print("Regressions detected:")
    for regression in results.regressions:
        print(f"  - {regression.test_name}: {regression.reason}")

# Save updated baseline
suite.save_baseline()
```

**Key Decisions**:
1. **Pytest integration**: Use pytest for familiar testing experience
2. **Mocking at multiple levels**: Mock LLMs, tools, or full agent
3. **Snapshot testing**: Catch unexpected output changes
4. **Property-based testing**: Generate test cases automatically
5. **Performance testing**: Built-in benchmarking tools
6. **Regression suites**: Track and prevent regressions

**Implementation Notes**:
- Create `good_agent.testing` module with test utilities
- Mock implementations should match production APIs exactly
- Support both sync and async tests
- Add fixtures for common test scenarios
- Integrate with CI/CD pipelines
- Consider adding LLM-as-judge for evaluation

---

## Implementation Priorities

Based on impact, effort, and consistency with good-agent philosophy:

### Phase 1: Core Foundations (High Impact, Medium Effort)
1. **Checkpointing and State Persistence** - Critical for real-world agents
2. **Enhanced Tool Calling** - Improves reliability and performance
3. **Structured Outputs** - Makes agents more predictable and integrable

### Phase 2: Advanced Orchestration (High Impact, High Effort)
4. **Graph-Based Workflows** - For complex multi-step tasks
5. **Multi-Agent Collaboration** - Leverage existing agent-as-tool pattern
6. **Event-Driven Architecture** - For real-time and long-running agents

### Phase 3: Quality & Observability (Medium Impact, Medium Effort)
7. **Observability and Debugging** - Essential for production deployments
8. **Testing and Evaluation** - Make agents testable
9. **Human-in-the-Loop** - Critical for safety and quality

### Phase 4: Advanced Features (Lower Priority)
10. **Advanced Memory Systems** - Nice to have, complex to implement
11. **Temporal Routing** - Specialized use cases
12. **Additional patterns from additional-concepts doc**

---

## Consistency with good-agent API Style

All proposals maintain consistency with good-agent's design philosophy:

✅ **Async context managers**: `async with agent:`
✅ **Decorator-based**: `@agent.route`, `@agent.tool`
✅ **Simple Python**: No complex DSLs or configuration files
✅ **Progressive disclosure**: Simple by default, powerful when needed
✅ **Type safety**: Pydantic models throughout
✅ **Explicit over implicit**: Clear what's happening at each step

---

## Comparison Matrix

| Feature | LangGraph | CrewAI | AutoGen | LlamaIndex | good-agent (Proposed) |
|---------|-----------|--------|---------|------------|----------------------|
| **Graph Orchestration** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Simplified) |
| **Checkpointing** | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Proposed) |
| **Multi-Agent** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ (Building on agents-as-tools) |
| **Event-Driven** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Proposed) |
| **Ease of Use** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Goal) |
| **Type Safety** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ (Pydantic everywhere) |
| **Observability** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Proposed) |
| **Testing Tools** | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ (Proposed) |
| **Learning Curve** | Steep | Moderate | Moderate | Moderate | **Gentle** (Goal) |

---

## Next Steps

1. **Validate proposals** with real use cases and user feedback
2. **Prototype** highest-priority features (checkpointing, enhanced tools, structured outputs)
3. **Iterate** on API design based on developer experience
4. **Document** with comprehensive examples and tutorials
5. **Build** testing infrastructure to ensure quality
6. **Release** incrementally with feature flags

---

## Conclusion

The 2025 agent framework landscape is rapidly evolving with sophisticated features for orchestration, collaboration, and reliability. good-agent can learn from these innovations while maintaining its core strength: **simplicity and developer-friendly APIs**.

Key takeaways:
- **Checkpointing is table stakes** for production agents
- **Graph-based orchestration** solves real problems for complex workflows
- **Multi-agent collaboration** builds naturally on agents-as-tools
- **Observability is critical** for debugging and production monitoring
- **Type safety** (Pydantic) improves developer experience
- **Simplicity is a competitive advantage** - don't over-engineer

By selectively adopting these patterns with good-agent's signature clean API style, we can build a framework that's both powerful and approachable.
