# Agent Modes

!!! warning "Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Agent modes provide a powerful way to give your agents distinct behavioral states, specialized tools, and contextual knowledge. Modes enable agents to switch between different "personalities" or capabilities dynamically, while maintaining state isolation and composability.

## Overview

### What Are Modes?

Modes are **behavioral configurations** that change how your agent responds. Think of them like "hats" your agent can wear:

- A **research mode** might make the agent focus on citations and thorough investigation
- A **creative mode** might encourage imaginative, expressive responses
- A **code review mode** might focus on security, performance, and best practices

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Mode Handlers** | Functions that configure agent behavior when entering a mode |
| **Mode State** | Per-mode storage that persists across calls via `agent.mode.state` |
| **Mode Stacking** | Modes can be nested - inner modes inherit from outer modes |
| **Transitions** | Modes can switch to other modes via `agent.mode.switch()` |
| **Isolation Levels** | Control state isolation: `none`, `config`, `thread`, `fork` |
| **Invokable Modes** | Generate tools so the agent can switch modes autonomously |
| **Standalone Modes** | Define reusable modes with `@mode()` decorator |

### Why Use Modes?

- **Specialization** - Configure agents for specific tasks without creating multiple agents
- **State Isolation** - Keep mode-specific data separate and clean
- **Dynamic Adaptation** - Let agents switch capabilities based on conversation context
- **Workflow Management** - Chain modes for complex multi-step processes
- **Cleaner Code** - Encapsulate related behaviors instead of monolithic system prompts

---

## Quick Start

### Basic Mode Definition

```python
from good_agent import Agent

async with Agent("You are a helpful assistant.") as agent:
    
    @agent.modes("research")
    async def research_mode(agent: Agent):
        """Deep research mode with citations."""
        agent.prompt.append("Focus on accuracy and cite your sources.")
        agent.mode.state["depth"] = "comprehensive"
    
    # Use the mode
    async with agent.modes["research"]:
        response = await agent.call("Explain quantum entanglement")
        print(agent.mode.name)  # "research"
```

### Mode Handler Signature (v2 API)

Mode handlers receive the agent instance directly:

```python
@agent.modes("mode_name")
async def my_mode(agent: Agent):
    # Access mode state
    agent.mode.state["key"] = "value"
    
    # Modify system prompt (auto-restored on exit)
    agent.prompt.append("Mode-specific instructions...")
    
    # Check mode info
    print(agent.mode.name)   # Current mode name
    print(agent.mode.stack)  # Full mode stack
    
    # Optionally transition to another mode
    return agent.mode.switch("other_mode")
```

---

## API Reference

### Mode Accessor (`agent.mode`)

The `agent.mode` property provides access to the current mode context:

| Property/Method | Type | Description |
|-----------------|------|-------------|
| `agent.mode.name` | `str \| None` | Current mode name (top of stack) |
| `agent.mode.stack` | `list[str]` | All active modes (LIFO order) |
| `agent.mode.state` | `dict` | Current mode's state dictionary |
| `agent.mode.in_mode(name)` | `bool` | Check if mode is anywhere in stack |
| `agent.mode.switch(name)` | `ModeTransition` | Request transition to another mode |
| `agent.mode.exit()` | `ModeTransition` | Request exit from current mode |

### System Prompt Manager (`agent.prompt`)

| Method | Description |
|--------|-------------|
| `agent.prompt.append(msg, persist=False)` | Add to end of system prompt |
| `agent.prompt.prepend(msg, persist=False)` | Add to start of system prompt |
| `agent.prompt.sections[name] = content` | Set a named section |
| `agent.prompt.render()` | Get the composed prompt string |

!!! note "Auto-Restore Behavior"
    Prompt modifications are automatically restored when exiting a mode, unless `persist=True` is specified.

### Mode Manager (`agent.modes`)

| Method | Description |
|--------|-------------|
| `agent.modes["name"]` | Get mode context manager |
| `agent.modes.list_modes()` | List all registered mode names |
| `agent.modes.get_info(name)` | Get mode metadata (name, description, handler) |
| `agent.modes.enter_mode(name)` | Enter mode directly (not as context manager) |
| `agent.modes.exit_mode()` | Exit current mode |
| `agent.modes.schedule_mode_switch(name)` | Schedule switch for next call |
| `agent.modes.schedule_mode_exit()` | Schedule exit for next call |
| `agent.modes.get_state(key)` | Get value from current mode state |
| `agent.modes.set_state(key, value)` | Set value in current mode state |
| `agent.modes.register(mode)` | Register a standalone mode |

---

## Real-World Use Cases

### 1. Customer Support Workflow

Create an agent that handles support tickets through distinct phases:

```python
from good_agent import Agent

async with Agent("You are a customer support agent.") as agent:
    
    @agent.modes("greeting")
    async def greeting_mode(agent: Agent):
        """Initial greeting and problem identification."""
        agent.prompt.append(
            "Greet the customer warmly. Ask clarifying questions "
            "to understand their issue. Be empathetic and patient."
        )
    
    @agent.modes("diagnosis")
    async def diagnosis_mode(agent: Agent):
        """Analyze the problem and find solutions."""
        agent.prompt.append(
            "You're now diagnosing the issue. Ask technical questions "
            "to narrow down the problem. Reference the knowledge base."
        )
        agent.mode.state["possible_solutions"] = []
    
    @agent.modes("resolution")
    async def resolution_mode(agent: Agent):
        """Provide step-by-step solution."""
        solutions = agent.mode.state.get("possible_solutions", [])
        agent.prompt.append(
            f"Provide clear, numbered steps to resolve the issue. "
            f"Known solutions: {solutions}"
        )
    
    @agent.modes("escalation")
    async def escalation_mode(agent: Agent):
        """Escalate to human support."""
        agent.prompt.append(
            "The issue requires human intervention. Collect all relevant "
            "details and prepare a summary for the support team."
        )
        agent.mode.state["escalation_reason"] = "Complex issue"
    
    # Usage flow
    async with agent.modes["greeting"]:
        await agent.call("Hi, I can't log into my account")
    
    async with agent.modes["diagnosis"]:
        await agent.call("I've tried resetting my password but it didn't work")
        agent.mode.state["possible_solutions"].append("Manual password reset")
    
    async with agent.modes["resolution"]:
        await agent.call("How do I fix this?")
```

### 2. Code Review Assistant

An agent that performs thorough code reviews with specialized focus areas:

```python
from good_agent import Agent

async with Agent("You are a senior software engineer.") as agent:
    
    @agent.modes("security_review")
    async def security_review(agent: Agent):
        """Focus on security vulnerabilities."""
        agent.prompt.append(
            "Review this code for security issues:\n"
            "- SQL injection, XSS, CSRF vulnerabilities\n"
            "- Authentication/authorization flaws\n"
            "- Sensitive data exposure\n"
            "- Input validation issues\n"
            "Rate severity: Critical, High, Medium, Low"
        )
        agent.mode.state["findings"] = {"security": []}
    
    @agent.modes("performance_review")
    async def performance_review(agent: Agent):
        """Focus on performance optimization."""
        agent.prompt.append(
            "Review this code for performance issues:\n"
            "- Algorithm complexity (time/space)\n"
            "- Database query optimization\n"
            "- Memory leaks and resource management\n"
            "- Caching opportunities\n"
            "Estimate impact: High, Medium, Low"
        )
        agent.mode.state["findings"] = {"performance": []}
    
    @agent.modes("style_review")
    async def style_review(agent: Agent):
        """Focus on code style and maintainability."""
        agent.prompt.append(
            "Review this code for style and maintainability:\n"
            "- Naming conventions and readability\n"
            "- Code duplication (DRY violations)\n"
            "- Function/class complexity\n"
            "- Documentation and comments\n"
            "- Test coverage suggestions"
        )
    
    @agent.modes("comprehensive_review")
    async def comprehensive_review(agent: Agent):
        """Full code review combining all aspects."""
        agent.prompt.append(
            "Perform a comprehensive code review covering:\n"
            "1. Security vulnerabilities\n"
            "2. Performance optimizations\n"
            "3. Code style and maintainability\n"
            "4. Architecture and design patterns\n"
            "Prioritize findings by business impact."
        )
    
    # Run focused reviews
    code = "def get_user(id): return db.execute(f'SELECT * FROM users WHERE id={id}')"
    
    async with agent.modes["security_review"]:
        response = await agent.call(f"Review this code:\n```python\n{code}\n```")
        print("Security findings:", response.content)
```

### 3. Writing Assistant Pipeline

An agent that guides users through a structured writing process:

```python
from good_agent import Agent

async with Agent("You are a professional writing coach.") as agent:
    
    @agent.modes("brainstorm")
    async def brainstorm_mode(agent: Agent):
        """Generate ideas without judgment."""
        agent.prompt.append(
            "Help brainstorm ideas freely. No idea is too wild. "
            "Generate diverse perspectives and unexpected angles. "
            "Use 'yes, and...' thinking to build on ideas."
        )
        agent.mode.state["ideas"] = []
    
    @agent.modes("outline")
    async def outline_mode(agent: Agent):
        """Structure ideas into a coherent outline."""
        ideas = agent.mode.state.get("ideas", [])
        agent.prompt.append(
            f"Create a structured outline from these ideas: {ideas}\n"
            "Organize into: Introduction, Main Points, Conclusion. "
            "Ensure logical flow and smooth transitions."
        )
    
    @agent.modes("draft")
    async def draft_mode(agent: Agent):
        """Write the first draft quickly."""
        agent.prompt.append(
            "Write a first draft. Focus on getting ideas down, "
            "not perfection. Maintain consistent voice and tone. "
            "Don't self-edit - that comes later."
        )
    
    @agent.modes("edit")
    async def edit_mode(agent: Agent):
        """Refine and improve the draft."""
        agent.prompt.append(
            "Edit for clarity, conciseness, and impact:\n"
            "- Eliminate redundancy\n"
            "- Strengthen weak verbs\n"
            "- Vary sentence structure\n"
            "- Check logical flow\n"
            "- Ensure consistent tone"
        )
    
    @agent.modes("proofread")
    async def proofread_mode(agent: Agent):
        """Final polish and error checking."""
        agent.prompt.append(
            "Proofread carefully for:\n"
            "- Grammar and punctuation errors\n"
            "- Spelling mistakes\n"
            "- Formatting consistency\n"
            "- Fact accuracy\n"
            "Flag any remaining concerns."
        )
    
    # Full writing pipeline
    topic = "The future of remote work"
    
    async with agent.modes["brainstorm"]:
        response = await agent.call(f"Let's brainstorm ideas about: {topic}")
        agent.mode.state["ideas"] = response.content.split("\n")
    
    async with agent.modes["outline"]:
        outline = await agent.call("Create an outline from those ideas")
    
    async with agent.modes["draft"]:
        draft = await agent.call("Write the first draft")
    
    async with agent.modes["edit"]:
        edited = await agent.call("Edit this draft for clarity")
    
    async with agent.modes["proofread"]:
        final = await agent.call("Final proofread")
```

### 4. Data Analysis Assistant

An agent that guides through data exploration and analysis:

```python
from good_agent import Agent

async with Agent("You are a data scientist.") as agent:
    
    @agent.modes("exploration")
    async def exploration_mode(agent: Agent):
        """Initial data exploration and profiling."""
        agent.prompt.append(
            "Explore the dataset:\n"
            "- Describe shape, types, and basic statistics\n"
            "- Identify missing values and anomalies\n"
            "- Note interesting patterns or correlations\n"
            "- Suggest potential analyses"
        )
        agent.mode.state["observations"] = []
    
    @agent.modes("cleaning")
    async def cleaning_mode(agent: Agent):
        """Data cleaning and preprocessing."""
        observations = agent.mode.state.get("observations", [])
        agent.prompt.append(
            f"Clean the data based on observations: {observations}\n"
            "- Handle missing values (impute, drop, flag)\n"
            "- Fix data types and formats\n"
            "- Remove or fix outliers\n"
            "- Standardize/normalize as needed"
        )
    
    @agent.modes("analysis")
    async def analysis_mode(agent: Agent):
        """Statistical analysis and modeling."""
        agent.prompt.append(
            "Perform analysis:\n"
            "- Test hypotheses with appropriate methods\n"
            "- Build models if applicable\n"
            "- Validate results and check assumptions\n"
            "- Quantify uncertainty and confidence"
        )
    
    @agent.modes("visualization")
    async def visualization_mode(agent: Agent):
        """Create effective visualizations."""
        agent.prompt.append(
            "Suggest visualizations:\n"
            "- Choose chart types based on data and message\n"
            "- Design for clarity and impact\n"
            "- Include appropriate labels and legends\n"
            "- Consider accessibility (color blindness, etc.)"
        )
    
    @agent.modes("reporting")
    async def reporting_mode(agent: Agent):
        """Summarize findings for stakeholders."""
        agent.prompt.append(
            "Create an executive summary:\n"
            "- Lead with key findings and recommendations\n"
            "- Use plain language (avoid jargon)\n"
            "- Include actionable insights\n"
            "- Note limitations and next steps"
        )
```

---

## Mode State Management

### Scoped State

Each mode maintains its own state dictionary that persists across calls:

```python
@agent.modes("research")
async def research_mode(agent: Agent):
    # Initialize state
    agent.mode.state["sources"] = []
    agent.mode.state["confidence"] = 0.0

async with agent.modes["research"]:
    # State persists across multiple calls
    await agent.call("Find sources about climate change")
    agent.mode.state["sources"].append("IPCC Report 2023")
    
    await agent.call("What's our confidence level?")
    print(agent.mode.state["sources"])  # ["IPCC Report 2023"]
```

### State Inheritance

Inner modes inherit state from outer modes (read access), but writes are scoped:

```python
@agent.modes("outer")
async def outer_mode(agent: Agent):
    agent.mode.state["shared"] = "from outer"
    agent.mode.state["outer_only"] = "exists"

@agent.modes("inner")
async def inner_mode(agent: Agent):
    # Read: inherits from outer
    print(agent.mode.state["shared"])  # "from outer"
    
    # Write: shadows (doesn't modify outer)
    agent.mode.state["shared"] = "overridden in inner"
    agent.mode.state["inner_only"] = "new value"

async with agent.modes["outer"]:
    print(agent.mode.state["shared"])  # "from outer"
    
    async with agent.modes["inner"]:
        print(agent.mode.state["shared"])  # "overridden in inner"
        print(agent.mode.state["inner_only"])  # "new value"
    
    # After inner exits - outer state restored
    print(agent.mode.state["shared"])  # "from outer"
    print(agent.mode.state.get("inner_only"))  # None
```

---

## Mode Stacking

### Nested Modes

Modes can be stacked to combine behaviors:

```python
async with agent.modes["research"]:
    print(agent.mode.stack)  # ["research"]
    
    async with agent.modes["summary"]:
        print(agent.mode.stack)  # ["research", "summary"]
        print(agent.mode.name)   # "summary" (current/top)
        
        # Check if specific mode is active
        print(agent.mode.in_mode("research"))  # True
        print(agent.mode.in_mode("summary"))   # True
    
    print(agent.mode.stack)  # ["research"]
```

### Cleanup Order (LIFO)

When modes exit, cleanup runs in reverse order:

```python
# Entry order:  outer -> middle -> inner
# Cleanup order: inner -> middle -> outer

# Even with exceptions:
async with agent.modes["outer"]:
    async with agent.modes["inner"]:
        raise ValueError("oops")
    # inner cleanup runs FIRST
# outer cleanup runs SECOND
# Exception propagates after all cleanup completes
```

---

## Mode Transitions

### Programmatic Transitions

Mode handlers can request transitions to other modes:

```python
@agent.modes("intake")
async def intake_mode(agent: Agent):
    """Determine where to route the user."""
    agent.prompt.append("Understand the user's needs.")

@agent.modes("research")
async def research_mode(agent: Agent):
    """Deep research mode."""
    # Check if we should transition
    if agent.mode.state.get("needs_summary"):
        return agent.mode.switch("summary")

@agent.modes("summary")
async def summary_mode(agent: Agent):
    """Summarize findings."""
    # Exit back to no mode when done
    if agent.mode.state.get("complete"):
        return agent.mode.exit()
```

### Scheduled Transitions

Schedule mode changes for the next agent call:

```python
# Inside a tool or handler
agent.modes.schedule_mode_switch("research")  # Switch on next call
agent.modes.schedule_mode_exit()              # Exit on next call

# In tools
@tool
async def switch_to_research(agent: Agent) -> str:
    agent.modes.schedule_mode_switch("research")
    return "Switching to research mode..."
```

---

## Isolation Levels

Control how much state isolation each mode has:

### Available Levels

| Level | Messages | Config/Tools | State | Use Case |
|-------|----------|--------------|-------|----------|
| `none` | Shared | Shared | Scoped | Default, full collaboration |
| `config` | Shared | Isolated | Scoped | Different tools, same conversation |
| `thread` | Temp view | Shared | Scoped | Safe to truncate messages |
| `fork` | Isolated | Isolated | Isolated | Complete sandbox |

### Usage

```python
@agent.modes("sandbox", isolation="fork")
async def sandbox_mode(agent: Agent):
    """Complete isolation - nothing persists back."""
    # Safe to experiment - changes don't affect parent
    await agent.call("Try risky approach")
    
    # Store results to pass back via mode state
    agent.mode.state["result"] = "findings"

@agent.modes("focus", isolation="thread")
async def focus_mode(agent: Agent):
    """Messages are a temp view, but new ones are kept."""
    # Can truncate safely - original preserved
    agent.messages.truncate(5)
```

### Isolation Rules

Child modes cannot be LESS isolated than parents:

```python
# VALID: Increasing isolation
@agent.modes("outer", isolation="thread")
@agent.modes("inner", isolation="fork")  # fork > thread

# INVALID: Decreasing isolation (raises ValueError)
@agent.modes("outer", isolation="fork")
@agent.modes("inner", isolation="none")  # ERROR!
```

---

## Invokable Modes

Generate tools that let the agent switch modes autonomously:

```python
@agent.modes("research", invokable=True)
async def research_mode(agent: Agent):
    """Enter research mode for deep investigation.
    
    Use this when you need to find authoritative sources
    and provide detailed citations.
    """
    agent.prompt.append("Focus on research and citations.")

# This creates a tool called "enter_research_mode"
# The agent can call it to switch modes on its own

# Custom tool name
@agent.modes("writing", invokable=True, tool_name="start_writing")
async def writing_mode(agent: Agent):
    """Start writing mode for drafting content."""
    agent.prompt.append("Focus on clear writing.")
```

---

## Standalone Modes

Define reusable modes that can be shared across agents:

```python
from good_agent import Agent, mode

# Define standalone modes
@mode("research", invokable=True)
async def research_mode(agent: Agent):
    """Reusable research mode."""
    agent.prompt.append("Research mode active.")

@mode("writing", isolation="thread")
async def writing_mode(agent: Agent):
    """Reusable writing mode."""
    agent.prompt.append("Writing mode active.")

# Use via constructor
agent = Agent("Assistant", modes=[research_mode, writing_mode])

# Or register after creation
agent.modes.register(research_mode)
```

---

## Event Integration

Monitor mode changes with the event system:

```python
from good_agent.events import AgentEvents

@agent.on(AgentEvents.MODE_ENTERED)
async def on_mode_entered(ctx):
    print(f"Entered mode: {ctx.parameters['mode_name']}")
    print(f"Stack: {ctx.parameters['mode_stack']}")

@agent.on(AgentEvents.MODE_EXITED)
async def on_mode_exited(ctx):
    print(f"Exited mode: {ctx.parameters['mode_name']}")
```

---

## Best Practices

### Mode Design Guidelines

1. **Single Responsibility** - Each mode should have one clear purpose
2. **Clear Boundaries** - Make it obvious when to enter/exit modes
3. **Predictable Transitions** - Document how modes flow into each other
4. **Stateless When Possible** - Minimize mode state to reduce complexity
5. **Use Isolation Wisely** - Match isolation level to your use case

### Common Patterns

```python
# Pattern 1: Pipeline modes (sequential)
async with agent.modes["intake"]:
    # Gather requirements
    pass
async with agent.modes["process"]:
    # Do work
    pass
async with agent.modes["deliver"]:
    # Return results
    pass

# Pattern 2: Nested modes (hierarchical)
async with agent.modes["project"]:
    async with agent.modes["research"]:
        pass
    async with agent.modes["draft"]:
        pass

# Pattern 3: Self-switching (autonomous)
@agent.modes("router", invokable=True)
async def router(agent: Agent):
    """Route to appropriate mode based on context."""
    if "code" in agent.mode.state.get("topic", ""):
        return agent.mode.switch("code_review")
    return agent.mode.switch("general")
```

### Anti-Patterns to Avoid

- **Mode explosion** - Too many modes becomes hard to manage
- **Deep nesting** - More than 3 levels is usually a code smell
- **Hidden state** - Mode state should be inspectable and documented
- **Implicit transitions** - Make mode changes explicit and logged

---

## Next Steps

- **[Events](../core/events.md)** - Monitor and respond to mode changes
- **[Tools](../core/tools.md)** - Build tools that interact with agent modes
- **[Multi-Agent](./multi-agent.md)** - Coordinate modes across multiple agents
- **[Context Management](./context-management.md)** - Manage agent context and state
