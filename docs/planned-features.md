# Planned Features

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

This page documents features that are under design or development but not yet available in Good Agent. These features are informed by design specifications in `.spec/v1/features/` and will be implemented in future releases.

!!! info "Tracking Progress"
    For updates on feature development, check the [project roadmap](https://github.com/goodkiwi/good-agent) and [changelog](CHANGELOG.md).

---

## Commands and Routing

**Status:** Design Phase
**Related Spec:** `.spec/v1/features/agent-routing-orchestration.md`

### Overview

Commands will provide a declarative way to define agent workflows, user-facing slash commands, and deterministic routing between different agent behaviors. This feature builds on Agent Modes but adds explicit routing capabilities.

### Proposed API

```python
from good_agent import Agent, command

agent = Agent("You are a deployment assistant")

@agent.command("deploy")
async def deploy_command(ctx, environment: str = "staging"):
    """Deploy to specified environment with approval workflow."""

    # Show deployment plan
    plan = await ctx.llm_call(f"Generate deployment plan for {environment}")

    # Request approval (HITL integration)
    approved = await ctx.ask_user(
        f"About to deploy to {environment}. Approve?",
        response_model=bool
    )

    if approved:
        result = await execute_deployment(environment)
        return f"Deployment to {environment} completed: {result}"
    else:
        return "Deployment cancelled"

# Usage in CLI
# > /deploy production
# > /deploy staging

# Usage in code
await agent.command.deploy(environment="production")
```

### Routing Capabilities

Commands will support:

- **Named Routes** - Explicit routing to specific behaviors
- **Parameter Binding** - Type-safe parameters with validation
- **Middleware Chains** - Composable interceptors for logging, auth, etc.
- **Context Transformation** - Filter/transform messages before LLM calls
- **Conditional Routing** - Guard conditions for transitions
- **User Commands** - Expose commands as `/slash` commands in interfaces

### Relationship to Modes

Commands build on Agent Modes by adding:

- Explicit routing syntax (`@agent.command()` vs implicit mode switching)
- User-facing command interface for chat UIs
- Parameter binding and validation
- Middleware support
- Deterministic workflow orchestration

Agent Modes remain the preferred approach for behavioral state management, while Commands handle explicit routing and user interactions.

---

## Human-in-the-Loop APIs

**Status:** Design Phase
**Related:** [Human-in-the-Loop Documentation](features/human-in-the-loop.md)

### Overview

Programmatic APIs for agent-initiated user input requests, including approvals, clarifications, and structured data collection.

### Proposed APIs

```python
# Simple approval
approved = await agent.user_input(
    "Approve this action?",
    response_model=bool,
    timeout=timedelta(minutes=5)
)

# Structured data collection
config = await agent.user_input(
    "Configure deployment settings:",
    response_model=DeploymentConfig  # Pydantic model
)

# Handoff to interactive session
await agent.handoff(
    "I need more context. Let's discuss.",
    mode="interactive_chat"
)
```

### Integration Points

- **Web UIs** - Browser-based input collection
- **CLI** - Currently implemented for interactive sessions
- **Slack/Discord** - Chat platform integration
- **API Endpoints** - RESTful callback mechanisms

---

## Agent Pool Advanced Features

**Status:** Design Phase
**Current:** Basic container available (see [Multi-Agent](features/multi-agent.md#agent-pools))

### Planned Capabilities

```python
from good_agent.agent.pool import AgentPool, LoadBalancingStrategy

# Create pool with load balancing
pool = AgentPool(
    agents=[Agent(f"Worker {i}") for i in range(10)],
    strategy=LoadBalancingStrategy.LEAST_LOADED,
    health_check_interval=30,
    failover=True
)

# Automatic task distribution
async with pool.task_queue() as queue:
    for task in tasks:
        await queue.submit(task)

    # Results collected automatically
    results = await queue.gather()

# Performance monitoring
stats = pool.performance_stats()
print(f"Average latency: {stats.avg_latency_ms}ms")
print(f"Success rate: {stats.success_rate}%")
```

### Features

- **Load Balancing** - Round-robin, least-loaded, performance-based
- **Health Monitoring** - Automatic agent health checks
- **Failover** - Automatic retry on agent failure
- **Dynamic Sizing** - Scale pool based on load
- **Task Queue** - Built-in queue management
- **Metrics** - Performance tracking and monitoring

---

## Persistent Agent State

**Status:** Early Design

### Overview

Built-in persistence layer for long-running agents that need to survive restarts.

### Proposed API

```python
from good_agent.persistence import PostgresStore

# Agent with persistence
store = PostgresStore(connection_url="postgresql://...")
agent = Agent(
    "Long-running assistant",
    persistence=store,
    session_id="user-123"
)

# State is automatically saved/restored
async with agent:
    # Continue from last session
    print(f"Previous message count: {len(agent.messages)}")

    # Conversation history persisted
    await agent.call("What did we discuss last time?")
```

### Storage Backends

- PostgreSQL
- Redis
- DynamoDB
- File system (development)

---

## Agent Observability

**Status:** Early Design

### Overview

Comprehensive observability and debugging tools for production agents.

### Proposed Features

```python
from good_agent.observability import Tracer, Metrics

# Distributed tracing
tracer = Tracer(provider="datadog")
agent = Agent("Assistant", tracer=tracer)

# Automatic trace spans for:
# - LLM calls with token counts
# - Tool executions with latency
# - Mode transitions
# - Event emissions

# Metrics collection
metrics = Metrics(provider="prometheus")
agent = Agent("Assistant", metrics=metrics)

# Track:
# - Request rate
# - Token usage
# - Error rates
# - P50/P95/P99 latencies
# - Cost per request
```

### Integrations

- OpenTelemetry
- Datadog
- New Relic
- Prometheus
- Custom exporters

---

## Web UI Framework

**Status:** Concept Phase

### Overview

Built-in web UI components for building chat interfaces with Good Agent.

### Proposed API

```python
from good_agent.web import AgentUI, StreamingChat

ui = AgentUI(agent)

@ui.route("/")
async def chat_page():
    return StreamingChat(
        agent=agent,
        theme="dark",
        show_tool_calls=True,
        markdown_rendering=True
    )

# Run server
ui.run(host="0.0.0.0", port=8000)
```

### Features

- Real-time streaming responses
- Tool call visualization
- Structured output rendering
- Mobile-responsive design
- Customizable themes
- HITL integration

---
