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
    
    @agent.modes("process")
    async def process_mode(agent: Agent):
        """Execute the main work."""
        requirements = agent.mode.state.get("requirements", [])
        agent.prompt.append(
            f"Process these requirements: {requirements}\n"
            "Work systematically through each item."
        )
    
    @agent.modes("deliver")
    async def deliver_mode(agent: Agent):
        """Present results and gather feedback."""
        agent.prompt.append(
            "Present the results clearly. Ask if the user needs "
            "any adjustments or has questions."
        )
    
    # Usage
    async with agent.modes["intake"]:
        response = await agent.call("I need help with my resume")
        agent.mode.state["requirements"].append(response.content)
    
    async with agent.modes["process"]:
        await agent.call("Now process the requirements")
    
    async with agent.modes["deliver"]:
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
    
    if agent.mode.state.get("validation_passed"):
        return agent.mode.switch("processing")
    
@agent.modes("processing")
async def processing_mode(agent: Agent):
    """Main processing after validation."""
    agent.prompt.append("Process the validated request.")
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

@agent.modes("recovery")
async def recovery_mode(agent: Agent):
    """Analyze failure and prepare for retry."""
    last_error = agent.mode.state.get("last_error", "Unknown")
    agent.prompt.append(
        f"The previous attempt failed: {last_error}\n"
        "Analyze what went wrong and adjust approach."
    )
    
    if agent.mode.state.get("can_retry"):
        return agent.mode.switch("attempt")
    return agent.mode.switch("escalate")
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
    
    # Handler can examine conversation and decide
    intent = agent.mode.state.get("detected_intent")
    
    if intent == "research":
        return agent.mode.switch("research")
    elif intent == "creative":
        return agent.mode.switch("creative")
    elif intent == "technical":
        return agent.mode.switch("technical")
    elif intent == "support":
        return agent.mode.switch("support")
```

### Fallback Router

Try primary mode, fall back if needed:

```python
@agent.modes("primary")
async def primary_mode(agent: Agent):
    """Try the primary approach first."""
    agent.prompt.append("Attempt the primary approach.")
    
    if agent.mode.state.get("needs_fallback"):
        return agent.mode.switch("fallback")

@agent.modes("fallback")
async def fallback_mode(agent: Agent):
    """Fallback approach when primary fails."""
    primary_result = agent.mode.state.get("primary_result")
    agent.prompt.append(
        f"Primary approach was insufficient: {primary_result}\n"
        "Try an alternative approach."
    )
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
    
    priority = agent.mode.state.get("priority", "medium")
    
    if priority == "critical":
        return agent.mode.switch("emergency")
    elif priority == "high":
        return agent.mode.switch("urgent")
    else:
        return agent.mode.switch("standard")
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

# Narrow modes (nest inside analysis)
@agent.modes("quantitative")
async def quantitative_mode(agent: Agent):
    """Focus on numbers and data."""
    agent.prompt.append("Focus on quantitative metrics and data.")

@agent.modes("qualitative")
async def qualitative_mode(agent: Agent):
    """Focus on patterns and meanings."""
    agent.prompt.append("Focus on qualitative patterns and insights.")

# Usage: nested for combined effect
async with agent.modes["analysis"]:
    async with agent.modes["quantitative"]:
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

@agent.modes("fact_check")
async def fact_check_mode(agent: Agent):
    """Adds fact-checking to research."""
    agent.prompt.append(
        "Additionally, verify all claims:\n"
        "- Cross-reference multiple sources\n"
        "- Flag unverified claims\n"
        "- Rate confidence levels"
    )

# Stack for enhanced research
async with agent.modes["base_research"]:
    async with agent.modes["fact_check"]:
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

@agent.modes("synthesize")
async def synthesize_mode(agent: Agent):
    """Synthesize gathered information."""
    findings = agent.mode.state.get("findings", [])
    agent.prompt.append(
        f"Synthesize these findings: {findings}\n"
        "Create a coherent narrative."
    )

# Sequential with state inheritance
async with agent.modes["gather"]:
    await agent.call("Gather info about renewable energy")
    agent.mode.state["findings"].append("solar growth")
    agent.mode.state["findings"].append("wind efficiency")

async with agent.modes["synthesize"]:
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

# Usage: accumulate across calls
async with agent.modes["session"]:
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

# Can restore to checkpoint if needed
async with agent.modes["exploration"]:
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

# After mode exit, temp_calculations and working_draft are gone
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

# Use via state
agent.mode.state["style"] = "formal"
async with agent.modes["greeting"]:
    ...
```

### Deep Nesting

❌ **Bad**: Deeply nested modes

```python
async with agent.modes["level1"]:
    async with agent.modes["level2"]:
        async with agent.modes["level3"]:
            async with agent.modes["level4"]:
                async with agent.modes["level5"]:
                    # Too deep - hard to reason about
                    pass
```

✅ **Good**: Flatten or use composition differently

```python
# Flatten into sequential
async with agent.modes["phase1"]:
    pass
async with agent.modes["phase2"]:
    pass

# Or use state to compose
@agent.modes("combined")
async def combined_mode(agent: Agent):
    features = agent.mode.state.get("features", [])
    for feature in features:
        agent.prompt.append(f"Feature: {feature}")
```

### Hidden Transitions

❌ **Bad**: Implicit, hard-to-track transitions

```python
@agent.modes("mysterious")
async def mysterious_mode(agent: Agent):
    # Hidden transition logic
    if some_condition():
        return agent.mode.switch("somewhere")
    elif other_condition():
        return agent.mode.switch("elsewhere")
    # Where will we end up?
```

✅ **Good**: Explicit, logged transitions

```python
@agent.modes("explicit")
async def explicit_mode(agent: Agent):
    # Clear transition logic
    next_mode = determine_next_mode(agent.mode.state)
    agent.mode.state["transition_reason"] = f"Moving to {next_mode}"
    
    if next_mode:
        return agent.mode.switch(next_mode)
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
    
    async with agent:
        async with agent.modes["research"]:
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
        return agent.mode.switch("end")
    
    @agent.modes("end")
    async def end_mode(agent: Agent):
        transitions.append("end")
    
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
    
    async with agent:
        initial_count = len(agent.messages)
        
        with agent.mock("response"):
            async with agent.modes["isolated"]:
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
