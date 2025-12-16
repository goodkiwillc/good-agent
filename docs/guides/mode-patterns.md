# Mode Patterns and Best Practices

This guide covers common patterns and best practices for using Agent Modes effectively.

## Pattern Categories

1. **Workflow Patterns** - Sequential mode pipelines
2. **Routing Patterns** - Dynamic mode selection
3. **Specialization Patterns** - Domain-specific modes
4. **Composition Patterns** - Combining modes effectively
5. **State Patterns** - Managing mode state

---

## Workflow Patterns

### Pipeline Mode

Process requests through a sequence of specialized stages:

```python
from good_agent import Agent

async with Agent("Assistant") as agent:
    
    @agent.modes("intake")
    async def intake_mode(agent: Agent):
        """Gather initial requirements."""
        agent.prompt.append(
            "Gather all necessary information from the user. "
            "Ask clarifying questions. Don't proceed until you have "
            "a clear understanding of what they need."
        )
        agent.mode.state["requirements"] = []
        yield agent
    
    @agent.modes("process")
    async def process_mode(agent: Agent):
        """Execute the main work."""
        requirements = agent.mode.state.get("requirements", [])
        agent.prompt.append(
            f"Process these requirements: {requirements}\n"
            "Work systematically through each item."
        )
        yield agent
    
    @agent.modes("deliver")
    async def deliver_mode(agent: Agent):
        """Present results and gather feedback."""
        agent.prompt.append(
            "Present the results clearly. Ask if the user needs "
            "any adjustments or has questions."
        )
        yield agent
    
    # Usage
    async with agent.mode("intake"):
        response = await agent.call("I need help with my resume")
        agent.mode.state["requirements"].append(response.content)
    
    async with agent.mode("process"):
        await agent.call("Now process the requirements")
    
    async with agent.mode("deliver"):
        await agent.call("Present the final results")
```

### Gate Mode

Validate conditions before proceeding to main work:

```python
@agent.modes("validation")
async def validation_mode(agent: Agent):
    """Validate input before processing."""
    agent.prompt.append(
        "Validate the user's request:\n"
        "1. Is the request within scope?\n"
        "2. Do we have all required information?\n"
        "3. Are there any potential issues?\n"
        "If validation fails, explain why and what's needed."
    )
    yield agent
    
    if agent.mode.state.get("validation_passed"):
        agent.modes.schedule_mode_switch("processing")
    
@agent.modes("processing")
async def processing_mode(agent: Agent):
    """Main processing after validation."""
    agent.prompt.append("Process the validated request.")
    yield agent
```

### Retry Mode

Handle failures with specialized retry logic:

```python
@agent.modes("attempt")
async def attempt_mode(agent: Agent):
    """Try to accomplish a task."""
    agent.mode.state["attempts"] = agent.mode.state.get("attempts", 0) + 1
    max_attempts = agent.mode.state.get("max_attempts", 3)
    
    agent.prompt.append(
        f"Attempt {agent.mode.state['attempts']}/{max_attempts}. "
        "Try your best to complete the task."
    )
    yield agent

@agent.modes("recovery")
async def recovery_mode(agent: Agent):
    """Analyze failure and prepare for retry."""
    last_error = agent.mode.state.get("last_error", "Unknown")
    agent.prompt.append(
        f"The previous attempt failed: {last_error}\n"
        "Analyze what went wrong and adjust approach."
    )
    yield agent
    
    if agent.mode.state.get("can_retry"):
        agent.modes.schedule_mode_switch("attempt")
    else:
        agent.modes.schedule_mode_switch("escalate")
```

---

## Routing Patterns

### Intent Router

Route to specialized modes based on detected intent:

```python
@agent.modes("router", invokable=True)
async def router_mode(agent: Agent):
    """Analyze intent and route to appropriate mode."""
    agent.prompt.append(
        "Analyze the user's request and determine the best mode:\n"
        "- 'research': For questions needing investigation\n"
        "- 'creative': For writing or brainstorming\n"
        "- 'technical': For code or technical tasks\n"
        "- 'support': For help or troubleshooting"
    )
    yield agent
    
    # Handler can examine conversation and decide
    intent = agent.mode.state.get("detected_intent")
    
    if intent == "research":
        agent.modes.schedule_mode_switch("research")
    elif intent == "creative":
        agent.modes.schedule_mode_switch("creative")
    elif intent == "technical":
        agent.modes.schedule_mode_switch("technical")
    elif intent == "support":
        agent.modes.schedule_mode_switch("support")
```

### Fallback Router

Try primary mode, fall back if needed:

```python
@agent.modes("primary")
async def primary_mode(agent: Agent):
    """Try the primary approach first."""
    agent.prompt.append("Attempt the primary approach.")
    yield agent
    
    if agent.mode.state.get("needs_fallback"):
        agent.modes.schedule_mode_switch("fallback")

@agent.modes("fallback")
async def fallback_mode(agent: Agent):
    """Fallback approach when primary fails."""
    primary_result = agent.mode.state.get("primary_result")
    agent.prompt.append(
        f"Primary approach was insufficient: {primary_result}\n"
        "Try an alternative approach."
    )
    yield agent
```

### Priority Router

Route based on urgency or importance:

```python
@agent.modes("triage")
async def triage_mode(agent: Agent):
    """Assess priority and route accordingly."""
    agent.prompt.append(
        "Assess the urgency of this request:\n"
        "- Critical: Security issue, data loss, system down\n"
        "- High: Blocking work, deadline imminent\n"
        "- Medium: Important but not urgent\n"
        "- Low: Nice to have, no deadline"
    )
    yield agent
    
    priority = agent.mode.state.get("priority", "medium")
    
    if priority == "critical":
        agent.modes.schedule_mode_switch("emergency")
    elif priority == "high":
        agent.modes.schedule_mode_switch("urgent")
    else:
        agent.modes.schedule_mode_switch("standard")
```

---

## Specialization Patterns

### Domain Expert Mode

Specialize for specific knowledge domains:

```python
@agent.modes("legal_expert")
async def legal_expert_mode(agent: Agent):
    """Legal domain expertise."""
    agent.prompt.append(
        "You are a legal expert assistant.\n"
        "- Use precise legal terminology\n"
        "- Cite relevant laws and precedents\n"
        "- Include appropriate disclaimers\n"
        "- Note jurisdiction-specific considerations"
    )
    agent.mode.state["domain"] = "legal"
    yield agent

@agent.modes("medical_expert")
async def medical_expert_mode(agent: Agent):
    """Medical domain expertise."""
    agent.prompt.append(
        "You are a medical information assistant.\n"
        "- Use accurate medical terminology\n"
        "- Reference clinical guidelines\n"
        "- ALWAYS recommend consulting a healthcare provider\n"
        "- Never provide diagnoses or treatment advice"
    )
    agent.mode.state["domain"] = "medical"
    yield agent
```

### Persona Mode

Adopt specific communication styles:

```python
@agent.modes("formal")
async def formal_mode(agent: Agent):
    """Formal, professional communication style."""
    agent.prompt.append(
        "Communication style: Formal and professional\n"
        "- Use proper titles and formal language\n"
        "- Avoid contractions and colloquialisms\n"
        "- Maintain professional distance\n"
        "- Structure responses clearly"
    )
    yield agent

@agent.modes("friendly")
async def friendly_mode(agent: Agent):
    """Casual, approachable communication style."""
    agent.prompt.append(
        "Communication style: Friendly and approachable\n"
        "- Use conversational language\n"
        "- Be warm and encouraging\n"
        "- Use appropriate humor when suitable\n"
        "- Make the user feel comfortable"
    )
    yield agent

@agent.modes("technical")
async def technical_mode(agent: Agent):
    """Technical, precise communication style."""
    agent.prompt.append(
        "Communication style: Technical and precise\n"
        "- Use exact terminology\n"
        "- Include code examples when relevant\n"
        "- Be concise and specific\n"
        "- Assume technical background"
    )
    yield agent
```

### Task-Specific Mode

Optimize for specific task types:

```python
@agent.modes("code_review")
async def code_review_mode(agent: Agent):
    """Optimized for reviewing code."""
    agent.prompt.append(
        "Review code systematically:\n"
        "1. Security vulnerabilities\n"
        "2. Performance issues\n"
        "3. Code style and readability\n"
        "4. Test coverage\n"
        "5. Documentation completeness\n"
        "Rate severity and provide specific line references."
    )
    agent.mode.state["review_type"] = "code"
    yield agent

@agent.modes("document_review")
async def document_review_mode(agent: Agent):
    """Optimized for reviewing documents."""
    agent.prompt.append(
        "Review document thoroughly:\n"
        "1. Clarity and structure\n"
        "2. Factual accuracy\n"
        "3. Grammar and spelling\n"
        "4. Tone consistency\n"
        "5. Target audience fit\n"
        "Provide specific suggestions with locations."
    )
    agent.mode.state["review_type"] = "document"
    yield agent
```

---

## Composition Patterns

### Nested Specialization

Combine broad and narrow modes:

```python
# Broad mode
@agent.modes("analysis")
async def analysis_mode(agent: Agent):
    """General analysis mode."""
    agent.prompt.append("Analyze carefully and thoroughly.")
    yield agent

# Narrow modes (nest inside analysis)
@agent.modes("quantitative")
async def quantitative_mode(agent: Agent):
    """Focus on numbers and data."""
    agent.prompt.append("Focus on quantitative metrics and data.")
    yield agent

@agent.modes("qualitative")
async def qualitative_mode(agent: Agent):
    """Focus on patterns and meanings."""
    agent.prompt.append("Focus on qualitative patterns and insights.")
    yield agent

# Usage: nested for combined effect
async with agent.mode("analysis"):
    async with agent.mode("quantitative"):
        # Both analysis + quantitative behaviors active
        await agent.call("Analyze the sales data")
```

### Mode Augmentation

Add capabilities to an existing mode:

```python
@agent.modes("base_research")
async def base_research_mode(agent: Agent):
    """Basic research capabilities."""
    agent.prompt.append("Research thoroughly and cite sources.")
    yield agent

@agent.modes("fact_check")
async def fact_check_mode(agent: Agent):
    """Adds fact-checking to research."""
    agent.prompt.append(
        "Additionally, verify all claims:\n"
        "- Cross-reference multiple sources\n"
        "- Flag unverified claims\n"
        "- Rate confidence levels"
    )
    yield agent

# Stack for enhanced research
async with agent.mode("base_research"):
    async with agent.mode("fact_check"):
        # Research + fact-checking combined
        await agent.call("Research and verify claims about climate change")
```

### Mode Inheritance via State

Pass context between sequential modes:

```python
@agent.modes("gather")
async def gather_mode(agent: Agent):
    """Gather information into state."""
    agent.prompt.append("Gather all relevant information.")
    # Store findings in state for next mode
    agent.mode.state["findings"] = []
    yield agent

@agent.modes("synthesize")
async def synthesize_mode(agent: Agent):
    """Synthesize gathered information."""
    findings = agent.mode.state.get("findings", [])
    agent.prompt.append(
        f"Synthesize these findings: {findings}\n"
        "Create a coherent narrative."
    )
    yield agent

# Sequential with state inheritance
async with agent.mode("gather"):
    await agent.call("Gather info about renewable energy")
    agent.mode.state["findings"].append("solar growth")
    agent.mode.state["findings"].append("wind efficiency")

async with agent.mode("synthesize"):
    await agent.call("Synthesize the findings")
```

---

## State Patterns

### Accumulator State

Build up state across interactions:

```python
@agent.modes("session")
async def session_mode(agent: Agent):
    """Track session-level state."""
    if "interactions" not in agent.mode.state:
        agent.mode.state["interactions"] = []
        agent.mode.state["topics"] = set()
        agent.mode.state["preferences"] = {}
    
    agent.prompt.append(
        f"Session context:\n"
        f"- Previous topics: {agent.mode.state['topics']}\n"
        f"- User preferences: {agent.mode.state['preferences']}"
    )
    yield agent

# Usage: accumulate across calls
async with agent.mode("session"):
    response = await agent.call("Tell me about Python")
    agent.mode.state["topics"].add("Python")
    agent.mode.state["interactions"].append(response.content)
    
    response = await agent.call("Now about JavaScript")
    agent.mode.state["topics"].add("JavaScript")
    # State accumulates: topics = {"Python", "JavaScript"}
```

### Checkpoint State

Save and restore state for branching:

```python
@agent.modes("exploration")
async def exploration_mode(agent: Agent):
    """Explore options with checkpointing."""
    # Save checkpoint at entry
    if "checkpoint" not in agent.mode.state:
        agent.mode.state["checkpoint"] = {
            "original_context": agent.messages[-5:],
            "starting_point": True
        }
    
    agent.prompt.append("Explore this option thoroughly.")
    yield agent

# Can restore to checkpoint if needed
async with agent.mode("exploration"):
    await agent.call("Try option A")
    # If option A fails, can restore and try B
```

### Scoped Temporary State

Use state that auto-cleans on mode exit:

```python
@agent.modes("temporary_context")
async def temporary_context_mode(agent: Agent):
    """State that exists only during this mode."""
    # This state automatically cleans up on mode exit
    agent.mode.state["temp_calculations"] = []
    agent.mode.state["working_draft"] = ""
    
    agent.prompt.append("Use working state for calculations.")
    yield agent

# After mode exit, temp_calculations and working_draft are gone
```

---

## Generator Patterns

Generator handlers provide setup/cleanup lifecycle semantics for modes.

### Resource Management Pattern

Acquire and release resources safely:

```python
@agent.modes("database")
async def database_mode(agent: Agent):
    # SETUP: Acquire resources
    pool = await create_connection_pool()
    agent.mode.state["db_pool"] = pool
    agent.prompt.append("You have database access.")
    
    yield agent  # Mode active
    
    # CLEANUP: Release resources (guaranteed)
    await pool.close()

# Usage - pool is always closed, even on exception
async with agent.mode("database"):
    await agent.call("Query the users table")
```

### Session Tracking Pattern

Track activity and generate summaries:

```python
@agent.modes("session")
async def session_mode(agent: Agent):
    # SETUP: Initialize tracking
    agent.mode.state["start_time"] = datetime.now()
    agent.mode.state["queries"] = []
    
    yield agent
    
    # CLEANUP: Generate summary
    duration = datetime.now() - agent.mode.state["start_time"]
    queries = agent.mode.state["queries"]
    
    # Store for later access
    agent.mode.state["summary"] = {
        "duration": duration.total_seconds(),
        "query_count": len(queries),
        "queries": queries,
    }
```

### Error Recovery Pattern

Handle and recover from exceptions:

```python
@agent.modes("resilient")
async def resilient_mode(agent: Agent):
    agent.mode.state["attempts"] = 0
    agent.mode.state["errors"] = []
    
    try:
        yield agent
    except RateLimitError as e:
        agent.mode.state["errors"].append(str(e))
        # Suppress and let caller retry
        agent.mode.state["should_retry"] = True
    except CriticalError as e:
        # Log but re-raise
        await log_critical_error(e)
        raise
    finally:
        # Always log completion
        await log_session_end(agent.mode.state)
```

### Context Isolation Pattern

Safely experiment with isolated state:

```python
@agent.modes("sandbox", isolation="fork")
async def sandbox_mode(agent: Agent):
    # SETUP: Note original state
    original_model = agent.config.model
    
    # Change configuration (isolated from parent)
    agent.config.model = "gpt-4o"
    agent.prompt.append("Experimental mode.")
    
    yield agent
    
    # CLEANUP: Export results before isolation restores
    agent.mode.state["experiment_results"] = {
        "model_used": agent.config.model,
        "messages_count": len(agent.messages),
    }
```

### Exit Behavior Pattern

Control post-exit LLM behavior:

```python
from good_agent import ModeExitBehavior

@agent.modes("research")
async def research_mode(agent: Agent):
    agent.mode.state["findings"] = []
    agent.prompt.append("Research mode active.")
    
    yield agent
    
    # Decide based on what happened
    if agent.mode.state.get("needs_followup"):
        # Continue conversation
        agent.mode.set_exit_behavior(ModeExitBehavior.CONTINUE)
    else:
        # Return control to caller
        agent.mode.set_exit_behavior(ModeExitBehavior.STOP)
```

### Nested Generator Pattern

Combine generators for layered behavior:

```python
@agent.modes("outer")
async def outer_mode(agent: Agent):
    events = []
    events.append("outer:setup")
    agent.mode.state["events"] = events
    
    try:
        yield agent
    finally:
        events.append("outer:cleanup")

@agent.modes("inner")
async def inner_mode(agent: Agent):
    events = agent.mode.state.get("events", [])
    events.append("inner:setup")
    
    try:
        yield agent
    finally:
        events.append("inner:cleanup")

# Usage
async with agent.mode("outer"):
    async with agent.mode("inner"):
        pass
# events = ["outer:setup", "inner:setup", "inner:cleanup", "outer:cleanup"]
```

---

## Anti-Patterns to Avoid

### Mode Explosion

❌ **Bad**: Creating too many granular modes

```python
# Too many modes - hard to manage
@agent.modes("greeting_formal")
@agent.modes("greeting_casual")
@agent.modes("greeting_technical")
@agent.modes("farewell_formal")
@agent.modes("farewell_casual")
# ... dozens more
```

✅ **Good**: Use parameters or state instead

```python
@agent.modes("greeting")
async def greeting_mode(agent: Agent):
    style = agent.mode.state.get("style", "casual")
    agent.prompt.append(f"Greet in a {style} manner.")
    yield agent

# Use via state
agent.mode.state["style"] = "formal"
async with agent.mode("greeting"):
    ...
```

### Deep Nesting

❌ **Bad**: Deeply nested modes

```python
async with agent.mode("level1"):
    async with agent.mode("level2"):
        async with agent.mode("level3"):
            async with agent.mode("level4"):
                async with agent.mode("level5"):
                    # Too deep - hard to reason about
                    pass
```

✅ **Good**: Flatten or use composition differently

```python
# Flatten into sequential
async with agent.mode("phase1"):
    pass
async with agent.mode("phase2"):
    pass

# Or use state to compose
@agent.modes("combined")
async def combined_mode(agent: Agent):
    features = agent.mode.state.get("features", [])
    for feature in features:
        agent.prompt.append(f"Feature: {feature}")
    yield agent
```

### Hidden Transitions

❌ **Bad**: Implicit, hard-to-track transitions

```python
@agent.modes("mysterious")
async def mysterious_mode(agent: Agent):
    yield agent
    # Hidden transition logic buried in cleanup
    if some_condition():
        agent.modes.schedule_mode_switch("somewhere")
    elif other_condition():
        agent.modes.schedule_mode_switch("elsewhere")
    # Where will we end up?
```

✅ **Good**: Explicit, logged transitions

```python
@agent.modes("explicit")
async def explicit_mode(agent: Agent):
    yield agent
    
    # Clear transition logic with logging
    next_mode = determine_next_mode(agent.mode.state)
    agent.mode.state["transition_reason"] = f"Moving to {next_mode}"
    
    if next_mode:
        agent.modes.schedule_mode_switch(next_mode)
```

### Multiple Yields (Generator Anti-Pattern)

❌ **Bad**: Yielding more than once

```python
@agent.modes("bad_generator")
async def bad_mode(agent: Agent):
    yield agent  # First yield - OK
    # ... do something ...
    yield agent  # Second yield - ERROR!
```

This will raise `RuntimeError: Mode handler 'bad_generator' yielded more than once`.

✅ **Good**: Single yield with conditional cleanup

```python
@agent.modes("good_generator")
async def good_mode(agent: Agent):
    yield agent  # Only yield once
    
    # All cleanup logic goes after the single yield
    if agent.mode.state.get("needs_extra_cleanup"):
        await extra_cleanup()
    await normal_cleanup()
```

### Cleanup Without Try/Finally (Generator Anti-Pattern)

❌ **Bad**: Cleanup not guaranteed

```python
@agent.modes("fragile")
async def fragile_mode(agent: Agent):
    resource = acquire_resource()
    yield agent
    # If exception occurs, this never runs!
    release_resource(resource)
```

✅ **Good**: Use try/finally for guaranteed cleanup

```python
@agent.modes("robust")
async def robust_mode(agent: Agent):
    resource = acquire_resource()
    try:
        yield agent
    finally:
        # Always runs, even on exception
        release_resource(resource)
```

### Blocking Operations in Generator Setup (Anti-Pattern)

❌ **Bad**: Long synchronous operations block mode entry

```python
@agent.modes("slow_entry")
async def slow_mode(agent: Agent):
    # Blocks entire event loop!
    data = slow_sync_load_from_disk()  
    yield agent
```

✅ **Good**: Use async operations or run in executor

```python
@agent.modes("fast_entry")
async def fast_mode(agent: Agent):
    # Non-blocking
    data = await asyncio.to_thread(slow_sync_load_from_disk)
    yield agent
```

---

## Testing Mode Patterns

### Unit Test Mode Handlers

```python
import pytest
from good_agent import Agent

@pytest.mark.asyncio
async def test_research_mode_sets_state():
    agent = Agent("Test agent")
    
    @agent.modes("research")
    async def research_mode(agent: Agent):
        agent.mode.state["depth"] = "deep"
        agent.prompt.append("Research mode.")
        yield agent
    
    async with agent:
        async with agent.mode("research"):
            assert agent.mode.state["depth"] == "deep"
            assert agent.mode.name == "research"
```

### Test Mode Transitions

```python
@pytest.mark.asyncio
async def test_mode_transitions():
    agent = Agent("Test agent")
    transitions = []
    
    @agent.modes("start")
    async def start_mode(agent: Agent):
        transitions.append("start")
        yield agent
        agent.modes.schedule_mode_switch("end")
    
    @agent.modes("end")
    async def end_mode(agent: Agent):
        transitions.append("end")
        yield agent
    
    async with agent:
        with agent.mock("ok"):
            await agent.modes.enter_mode("start")
            await agent.call("trigger")
    
    assert transitions == ["start", "end"]
```

### Test Mode Isolation

```python
@pytest.mark.asyncio
async def test_fork_isolation():
    agent = Agent("Test agent")
    
    @agent.modes("isolated", isolation="fork")
    async def isolated_mode(agent: Agent):
        agent.append("This won't persist", role="user")
        yield agent
    
    async with agent:
        initial_count = len(agent.messages)
        
        with agent.mock("response"):
            async with agent.mode("isolated"):
                await agent.call("test")
        
        # Messages from fork mode shouldn't persist
        # (depends on isolation implementation)
```

---

## Summary

| Pattern | Use Case | Key Benefit |
|---------|----------|-------------|
| Pipeline | Sequential processing | Clear workflow stages |
| Router | Dynamic dispatch | Flexible routing |
| Specialist | Domain expertise | Focused capabilities |
| Nested | Combined behaviors | Composability |
| Accumulator | Session state | Persistent context |

Choose patterns based on your needs:
- **Simple tasks**: Single mode or pipeline
- **Complex routing**: Router pattern
- **Domain-specific**: Specialist modes
- **Rich state**: Accumulator + checkpoints
