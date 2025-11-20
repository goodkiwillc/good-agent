# Agent Modes

Agent modes provide a powerful way to give your agents distinct behavioral states, specialized tools, and contextual knowledge. Modes enable agents to switch between different "personalities" or capabilities dynamically, while maintaining state isolation and composability.

## Overview

### Key Concepts

- **Mode Handlers** - Functions that configure agent behavior when entering a mode
- **State Scoping** - Each mode maintains isolated state with inheritance
- **Mode Stacking** - Modes can be nested and composed hierarchically  
- **Transitions** - Modes can automatically switch to other modes
- **Scheduling** - Mode changes can be scheduled for future calls
- **Tool Integration** - Tools can trigger mode switches programmatically

### Benefits

- **Behavioral Specialization** - Configure agents for specific tasks or domains
- **Context Isolation** - Keep state and configuration separate between modes
- **Dynamic Adaptation** - Switch agent capabilities based on user needs
- **Workflow Management** - Chain modes together for complex multi-step processes
- **State Persistence** - Maintain mode-specific state across conversations

## Basic Mode Usage

### Defining Modes

Create modes using the `@agent.modes()` decorator:

```python
from good_agent import Agent, ModeContext

async with Agent("You are a versatile assistant.") as agent:
    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        """Deep research mode with specialized instructions."""
        ctx.add_system_message(
            "You are in research mode. Focus on finding accurate, "
            "authoritative sources and provide detailed citations."
        )
        
        # Store mode-specific state
        ctx.state["research_depth"] = "comprehensive"
        ctx.state["sources_required"] = True
    
    @agent.modes("creative")
    async def creative_mode(ctx: ModeContext):
        """Creative writing mode with imaginative prompts."""
        ctx.add_system_message(
            "You are in creative mode. Be imaginative, expressive, "
            "and think outside the box. Use vivid language and storytelling."
        )
        
        ctx.state["creativity_level"] = "high"
        ctx.state["format_style"] = "narrative"
```

### Entering Modes

Use modes as context managers to activate specific behaviors:

```python
async with Agent("Versatile assistant") as agent:
    # Define modes (research_mode and creative_mode from above)
    
    # Normal mode - default behavior
    response = await agent.call("Tell me about quantum physics")
    print(f"Normal: {response.content}")
    
    # Research mode - specialized for deep investigation
    async with agent.modes["research"]:
        response = await agent.call("Tell me about quantum physics")
        print(f"Research: {response.content}")
        
        # Check current mode
        print(f"Current mode: {agent.current_mode}")  # "research"
        
    # Creative mode - specialized for imaginative responses
    async with agent.modes["creative"]:
        response = await agent.call("Tell me about quantum physics")
        print(f"Creative: {response.content}")
        
    # Back to normal mode
    print(f"Current mode: {agent.current_mode}")  # None
```

## Mode State Management

### Scoped State

Each mode maintains its own state that persists across calls:

```python
@agent.modes("session")
async def session_mode(ctx: ModeContext):
    """Track session information."""
    # Initialize session state
    if "start_time" not in ctx.state:
        ctx.state["start_time"] = datetime.now()
        ctx.state["interaction_count"] = 0
        ctx.state["topics_discussed"] = []
    
    # Increment interaction counter
    ctx.state["interaction_count"] += 1
    
    # Add session context to system message
    duration = ctx.duration
    interactions = ctx.state["interaction_count"]
    ctx.add_system_message(
        f"Session info: {interactions} interactions over {duration}. "
        f"Previous topics: {ctx.state['topics_discussed']}"
    )

async with agent.modes["session"]:
    # First call
    await agent.call("Hello! Let's discuss AI")
    print(f"Interactions: {agent.modes.get_state('interaction_count')}")  # 1
    
    # Add topic to our tracking
    agent.modes.set_state("topics_discussed", ["AI"])
    
    # Second call
    await agent.call("What about robotics?")
    print(f"Interactions: {agent.modes.get_state('interaction_count')}")  # 2
    
    # State persists throughout the mode session
    topics = agent.modes.get_state("topics_discussed")
    topics.append("robotics")
    agent.modes.set_state("topics_discussed", topics)
```

### State Inheritance

When modes are nested, inner modes inherit state from outer modes:

```python
@agent.modes("project")
async def project_mode(ctx: ModeContext):
    """Project management mode."""
    ctx.state["project_name"] = "Website Redesign"
    ctx.state["team_size"] = 5
    ctx.state["deadline"] = "2024-12-01"

@agent.modes("planning") 
async def planning_mode(ctx: ModeContext):
    """Planning phase within project mode."""
    # Can access project state
    project_name = ctx.state.get("project_name", "Unknown")
    
    ctx.add_system_message(
        f"Planning mode for {project_name}. Focus on breaking down "
        f"tasks and timelines for {ctx.state.get('team_size')} team members."
    )
    
    # Set planning-specific state
    ctx.state["planning_phase"] = "initial"
    ctx.state["tasks"] = []

async with agent.modes["project"]:
    async with agent.modes["planning"]:
        # Inner mode can see both project and planning state
        response = await agent.call("What's our first milestone?")
        
        # State is scoped - planning state shadows project if keys conflict
        print(f"Project: {agent.modes.get_state('project_name')}")
        print(f"Planning: {agent.modes.get_state('planning_phase')}")
```

## Mode Stacking and Composition

### Nested Modes

Modes can be stacked to combine behaviors:

```python
@agent.modes("expert")
async def expert_mode(ctx: ModeContext):
    """Expert knowledge mode."""
    ctx.add_system_message("Provide expert-level, technical responses.")
    ctx.state["expertise_level"] = "advanced"

@agent.modes("teaching")
async def teaching_mode(ctx: ModeContext):
    """Educational mode."""
    ctx.add_system_message("Explain concepts clearly with examples.")
    ctx.state["teaching_style"] = "socratic"

@agent.modes("patient")
async def patient_mode(ctx: ModeContext):
    """Patient, supportive interaction mode."""
    ctx.add_system_message("Be patient and encouraging. Break down complex ideas.")
    ctx.state["interaction_style"] = "supportive"

async with agent.modes["expert"]:
    async with agent.modes["teaching"]:
        async with agent.modes["patient"]:
            # Agent now combines all three behavioral modes
            print(f"Mode stack: {agent.mode_stack}")  
            # ["expert", "teaching", "patient"]
            
            print(f"In expert mode: {agent.in_mode('expert')}")    # True
            print(f"In teaching mode: {agent.in_mode('teaching')}")  # True
            print(f"Current mode: {agent.current_mode}")          # "patient"
            
            # Agent will be expert + teaching + patient
            response = await agent.call("Explain quantum entanglement")
```

### Mode Stack Operations

Access and manipulate the mode stack:

```python
# Check what modes are active
available_modes = agent.modes.list_modes()
print(f"Available modes: {available_modes}")

# Get current mode information
if agent.current_mode:
    mode_info = agent.modes.get_info(agent.current_mode)
    print(f"Mode: {mode_info['name']}")
    print(f"Description: {mode_info['description']}")

# Check if specific modes are active
if agent.in_mode("research"):
    print("Research mode is active somewhere in the stack")

# View the full mode stack
print(f"Complete mode stack: {agent.mode_stack}")
```

## Mode Transitions

### Manual Mode Switching

Modes can programmatically switch to other modes:

```python
@agent.modes("intake")
async def intake_mode(ctx: ModeContext):
    """Initial intake mode that routes to specialized modes."""
    ctx.add_system_message("Determine the user's needs and route appropriately.")
    
    # Analyze the user's request and decide next mode
    user_intent = ctx.state.get("user_intent", "unknown")
    
    if "research" in user_intent.lower():
        return ctx.switch_mode("research")
    elif "creative" in user_intent.lower():
        return ctx.switch_mode("creative") 
    elif "technical" in user_intent.lower():
        return ctx.switch_mode("technical")
    else:
        return ctx.exit_mode()  # Go back to normal mode

@agent.modes("technical")
async def technical_mode(ctx: ModeContext):
    """Technical analysis mode."""
    ctx.add_system_message("Provide detailed technical analysis with code examples.")
    
    # After one technical response, switch to review mode
    if ctx.state.get("analysis_complete"):
        return ctx.switch_mode("review", analysis_topic=ctx.state.get("topic"))
    
    ctx.state["analysis_complete"] = True

@agent.modes("review")
async def review_mode(ctx: ModeContext):
    """Review and summarization mode."""
    topic = ctx.state.get("analysis_topic", "the analysis")
    ctx.add_system_message(f"Provide a concise review and summary of {topic}.")
    
    # After review, exit back to normal mode
    return ctx.exit_mode()

# Usage - modes will automatically transition
async with agent.modes["intake"]:
    agent.modes.set_state("user_intent", "technical analysis")
    
    # This will trigger: intake → technical → review → normal
    response = await agent.call("Analyze this Python code performance")
```

### Scheduled Mode Changes

Schedule mode changes for future agent calls:

```python
from good_agent import tool
from good_agent.agent.config import Context

@tool
async def enter_research_mode(agent: Agent = Context()) -> str:
    """Schedule research mode for the next call."""
    agent.modes.schedule_mode_switch("research")
    return "Will enter research mode for the next response."

@tool
async def exit_current_mode(agent: Agent = Context()) -> str:
    """Schedule exiting current mode."""
    if not agent.current_mode:
        return "Not currently in any mode."
    
    agent.modes.schedule_mode_exit()
    return f"Will exit {agent.current_mode} mode after this response."

# Usage with tools
async with Agent("Assistant with mode control", tools=[enter_research_mode, exit_current_mode]) as agent:
    
    # Normal call
    response = await agent.call("Hello")
    print(f"Mode: {agent.current_mode}")  # None
    
    # Tool schedules research mode
    await enter_research_mode(agent=agent)
    
    # Next call will be in research mode
    response = await agent.call("Tell me about AI")
    print(f"Mode: {agent.current_mode}")  # "research"
    
    # Tool schedules mode exit
    await exit_current_mode(agent=agent)
    
    # Next call will be in normal mode
    response = await agent.call("Thanks!")
    print(f"Mode: {agent.current_mode}")  # None
```

## Advanced Mode Patterns

### Conditional Mode Logic

Create modes with complex conditional behavior:

```python
@agent.modes("adaptive")
async def adaptive_mode(ctx: ModeContext):
    """Mode that adapts based on conversation context."""
    
    # Analyze conversation history
    message_count = len(ctx.agent.messages)
    user_messages = len(ctx.agent.user)
    
    # Adapt behavior based on conversation length
    if user_messages < 3:
        ctx.add_system_message(
            "Early conversation - be welcoming and establish rapport."
        )
        ctx.state["conversation_phase"] = "greeting"
        
    elif user_messages < 10:
        ctx.add_system_message(
            "Mid conversation - be helpful and focused on user needs."
        )
        ctx.state["conversation_phase"] = "working"
        
    else:
        ctx.add_system_message(
            "Extended conversation - check if user needs summary or wrap-up."
        )
        ctx.state["conversation_phase"] = "concluding"
        
        # Consider transitioning to summary mode
        if ctx.state.get("should_summarize", False):
            return ctx.switch_mode("summary")
    
    # Store conversation metrics
    ctx.state["message_count"] = message_count
    ctx.state["engagement_level"] = "high" if user_messages > 5 else "normal"

@agent.modes("summary")
async def summary_mode(ctx: ModeContext):
    """Summarization mode for long conversations."""
    ctx.add_system_message(
        "Provide a helpful summary of our conversation and key takeaways."
    )
    return ctx.exit_mode()  # Return to normal after summary

# Usage
async with agent.modes["adaptive"]:
    for i in range(12):
        response = await agent.call(f"Message number {i+1}")
        phase = agent.modes.get_state("conversation_phase")
        print(f"Call {i+1} - Phase: {phase}")
        
        if i == 8:  # Trigger summarization
            agent.modes.set_state("should_summarize", True)
```

### Mode-Specific Tool Access

Provide different tools based on current mode:

```python
from good_agent import tool

# Research-specific tools
@tool
async def search_academic_papers(query: str) -> str:
    """Search academic databases for papers."""
    return f"Found 5 papers about {query}"

@tool  
async def cite_source(url: str, title: str) -> str:
    """Add a citation to the research."""
    return f"Cited: {title} ({url})"

# Creative-specific tools
@tool
async def generate_character(name: str, traits: list[str]) -> str:
    """Generate a character profile."""
    return f"Character {name}: {', '.join(traits)}"

@tool
async def story_prompt(genre: str) -> str:
    """Generate a story prompt."""
    return f"Story prompt for {genre}: [generated prompt]"

@agent.modes("research")
async def research_mode(ctx: ModeContext):
    """Research mode with academic tools."""
    ctx.add_system_message(
        "Research mode: Use search_academic_papers and cite_source tools."
    )
    
    # Temporarily add research tools
    async with ctx.agent.temporary_tools([search_academic_papers, cite_source]):
        return await ctx.call()

@agent.modes("creative")
async def creative_mode(ctx: ModeContext):
    """Creative mode with storytelling tools."""
    ctx.add_system_message(
        "Creative mode: Use generate_character and story_prompt tools."
    )
    
    # Temporarily add creative tools
    async with ctx.agent.temporary_tools([generate_character, story_prompt]):
        return await ctx.call()

# Usage - tools are automatically available in each mode
async with agent.modes["research"]:
    await agent.call("Research quantum computing applications")

async with agent.modes["creative"]:
    await agent.call("Create a sci-fi story about quantum computers")
```

### Workflow Modes

Create complex workflows using mode chains:

```python
@agent.modes("workflow_start")
async def workflow_start_mode(ctx: ModeContext):
    """Initialize a multi-step workflow."""
    workflow_id = ctx.state.get("workflow_id", f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    ctx.state["workflow_id"] = workflow_id
    ctx.state["workflow_steps"] = ["analyze", "design", "implement", "test"]
    ctx.state["current_step"] = 0
    
    ctx.add_system_message(f"Starting workflow {workflow_id}. Step 1: Analysis phase.")
    
    # Automatically transition to first step
    return ctx.switch_mode("workflow_analyze")

@agent.modes("workflow_analyze")
async def workflow_analyze_mode(ctx: ModeContext):
    """Analysis phase of workflow."""
    ctx.add_system_message("Analysis mode: Break down requirements and identify key components.")
    
    if ctx.state.get("analysis_complete"):
        ctx.state["current_step"] = 1
        return ctx.switch_mode("workflow_design", analysis_results=ctx.state.get("analysis"))
    
    ctx.state["analysis_complete"] = True

@agent.modes("workflow_design")
async def workflow_design_mode(ctx: ModeContext):
    """Design phase of workflow."""
    analysis_results = ctx.state.get("analysis_results", "previous analysis")
    ctx.add_system_message(f"Design mode: Create detailed design based on {analysis_results}.")
    
    if ctx.state.get("design_complete"):
        ctx.state["current_step"] = 2
        return ctx.switch_mode("workflow_implement")
    
    ctx.state["design_complete"] = True

@agent.modes("workflow_implement")
async def workflow_implement_mode(ctx: ModeContext):
    """Implementation phase of workflow."""
    ctx.add_system_message("Implementation mode: Provide concrete implementation steps.")
    
    if ctx.state.get("implementation_complete"):
        return ctx.switch_mode("workflow_complete")
    
    ctx.state["implementation_complete"] = True

@agent.modes("workflow_complete")
async def workflow_complete_mode(ctx: ModeContext):
    """Workflow completion mode."""
    workflow_id = ctx.state.get("workflow_id", "unknown")
    ctx.add_system_message(f"Workflow {workflow_id} complete. Provide summary and next steps.")
    
    return ctx.exit_mode()  # Return to normal mode

# Usage - automatic workflow progression
async with agent.modes["workflow_start"]:
    agent.modes.set_state("project_type", "web application")
    
    # This will progress through: start → analyze → design → implement → complete
    response = await agent.call("Help me build a task management system")
    
    workflow_id = agent.modes.get_state("workflow_id")
    current_step = agent.modes.get_state("current_step")
    print(f"Workflow {workflow_id}, Step {current_step}")
```

## Context Management

### Mode Context Operations

Access and modify conversation context within modes:

```python
@agent.modes("context_aware")
async def context_aware_mode(ctx: ModeContext):
    """Mode that analyzes and responds to conversation context."""
    
    # Access conversation history
    total_messages = len(ctx.agent.messages)
    user_messages = len(ctx.agent.user)  
    assistant_messages = len(ctx.agent.assistant)
    
    # Analyze recent conversation
    recent_topics = []
    for message in ctx.agent.user[-3:]:  # Last 3 user messages
        # Simple topic extraction (in practice, use NLP)
        if "python" in message.content.lower():
            recent_topics.append("programming")
        elif "ai" in message.content.lower():
            recent_topics.append("artificial intelligence")
    
    # Add contextual system message
    ctx.add_system_message(
        f"Context: {total_messages} total messages, recent topics: {recent_topics}. "
        f"Tailor your response to build on this conversation history."
    )
    
    # Store context analysis
    ctx.state["conversation_length"] = total_messages
    ctx.state["recent_topics"] = recent_topics
    ctx.state["analysis_timestamp"] = datetime.now().isoformat()

# Usage
async with agent.modes["context_aware"]:
    # Each call builds on conversation history
    await agent.call("Tell me about Python")
    await agent.call("How does it relate to AI?")
    await agent.call("What's the best framework?")
    
    # Mode has full context of the conversation
    context = {
        "length": agent.modes.get_state("conversation_length"),
        "topics": agent.modes.get_state("recent_topics"),
        "analyzed": agent.modes.get_state("analysis_timestamp")
    }
    print(f"Context analysis: {context}")
```

### Dynamic System Messages

Modify system messages based on mode state:

```python
@agent.modes("dynamic")
async def dynamic_mode(ctx: ModeContext):
    """Mode with dynamic system messages based on state."""
    
    # Get mode state
    user_expertise = ctx.state.get("user_expertise", "beginner")
    preferred_style = ctx.state.get("preferred_style", "conversational")
    session_length = ctx.state.get("session_length", "short")
    
    # Build dynamic system message
    system_parts = ["You are a helpful assistant."]
    
    if user_expertise == "expert":
        system_parts.append("The user is an expert - use technical language and skip basic explanations.")
    elif user_expertise == "beginner":
        system_parts.append("The user is a beginner - explain concepts clearly with examples.")
    
    if preferred_style == "formal":
        system_parts.append("Use formal, professional language.")
    elif preferred_style == "casual":
        system_parts.append("Use casual, friendly language.")
    
    if session_length == "extended":
        system_parts.append("This is an extended session - provide comprehensive responses.")
    else:
        system_parts.append("Keep responses concise and focused.")
    
    # Add the dynamic system message
    ctx.add_system_message(" ".join(system_parts))
    
    # Update session state
    ctx.state["last_update"] = datetime.now().isoformat()

# Configure and use dynamic mode
async with agent.modes["dynamic"]:
    # Configure user preferences
    agent.modes.set_state("user_expertise", "expert")
    agent.modes.set_state("preferred_style", "formal")
    agent.modes.set_state("session_length", "extended")
    
    response = await agent.call("Explain machine learning algorithms")
    # Response will be technical, formal, and comprehensive
    
    # Change preferences mid-session
    agent.modes.set_state("user_expertise", "beginner")
    agent.modes.set_state("preferred_style", "casual")
    
    response = await agent.call("What about neural networks?")
    # Response will be beginner-friendly and casual
```

## Event Integration

### Mode Events

Monitor mode changes with the event system:

```python
from good_agent.events import AgentEvents
from good_agent.core.event_router import EventContext

async with Agent("Event-monitored agent") as agent:
    # Set up mode event handlers
    @agent.on("mode:enter")
    def on_mode_enter(ctx: EventContext):
        mode_name = ctx.parameters.get("mode_name")
        print(f"🎭 Entering mode: {mode_name}")
        
    @agent.on("mode:exit")  
    def on_mode_exit(ctx: EventContext):
        mode_name = ctx.parameters.get("mode_name")
        duration = ctx.parameters.get("duration")
        print(f"🎭 Exiting mode: {mode_name} (active for {duration})")
    
    @agent.on("mode:switch")
    def on_mode_switch(ctx: EventContext):
        old_mode = ctx.parameters.get("old_mode")
        new_mode = ctx.parameters.get("new_mode")
        print(f"🎭 Mode switch: {old_mode} → {new_mode}")
    
    # Define modes
    @agent.modes("monitored")
    async def monitored_mode(ctx: ModeContext):
        ctx.add_system_message("This mode is being monitored by events.")
        return await ctx.call()
    
    # Use mode - events will fire
    async with agent.modes["monitored"]:
        await agent.call("Hello from monitored mode")
```

### Mode State Events

Monitor mode state changes:

```python
@agent.on("mode:state_change")
def on_state_change(ctx: EventContext):
    mode_name = ctx.parameters.get("mode_name")
    key = ctx.parameters.get("key")
    old_value = ctx.parameters.get("old_value")
    new_value = ctx.parameters.get("new_value")
    
    print(f"🔄 Mode {mode_name} state change: {key} = {old_value} → {new_value}")

@agent.modes("stateful")
async def stateful_mode(ctx: ModeContext):
    """Mode that tracks state changes."""
    ctx.state["counter"] = ctx.state.get("counter", 0) + 1
    ctx.state["last_access"] = datetime.now().isoformat()
    
    ctx.add_system_message(f"Stateful mode - Call #{ctx.state['counter']}")

# Usage - state changes will emit events  
async with agent.modes["stateful"]:
    await agent.call("First call")
    await agent.call("Second call")
```

## Testing Modes

### Unit Testing Mode Handlers

Test mode functionality in isolation:

```python
import pytest
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_research_mode():
    """Test research mode behavior."""
    agent = Agent("Test agent")
    
    @agent.modes("research")
    async def research_mode(ctx: ModeContext):
        ctx.add_system_message("Research mode active")
        ctx.state["research_active"] = True
        return await ctx.call()
    
    await agent.initialize()
    
    # Test mode registration
    assert "research" in agent.modes.list_modes()
    
    # Test mode context
    async with agent.modes["research"]:
        assert agent.current_mode == "research"
        assert agent.modes.get_state("research_active") == True
        
        # Test mode info
        info = agent.modes.get_info("research")
        assert info["name"] == "research"

@pytest.mark.asyncio
async def test_mode_transitions():
    """Test mode transition logic."""
    agent = Agent("Test agent")
    transition_log = []
    
    @agent.modes("source")
    async def source_mode(ctx: ModeContext):
        transition_log.append("source_entered")
        return ctx.switch_mode("target")
    
    @agent.modes("target")
    async def target_mode(ctx: ModeContext):
        transition_log.append("target_entered")
        return ctx.exit_mode()
    
    await agent.initialize()
    
    # Mock the LLM to avoid actual calls
    with agent.mock("Test response"):
        async with agent.modes["source"]:
            await agent.call("Test transition")
    
    # Verify transition sequence
    assert "source_entered" in transition_log
    assert "target_entered" in transition_log
    assert agent.current_mode is None  # Should exit back to normal

@pytest.mark.asyncio  
async def test_mode_state_scoping():
    """Test state inheritance and scoping."""
    agent = Agent("Test agent")
    
    @agent.modes("outer")
    async def outer_mode(ctx: ModeContext):
        ctx.state["shared"] = "outer_value"
        ctx.state["outer_only"] = "outer"
    
    @agent.modes("inner")
    async def inner_mode(ctx: ModeContext):
        # Should inherit outer state
        assert ctx.state.get("shared") == "outer_value"
        assert ctx.state.get("outer_only") == "outer"
        
        # Shadow shared state
        ctx.state["shared"] = "inner_value"
        ctx.state["inner_only"] = "inner"
    
    await agent.initialize()
    
    async with agent.modes["outer"]:
        async with agent.modes["inner"]:
            # Inner mode sees its own values
            assert agent.modes.get_state("shared") == "inner_value"
            assert agent.modes.get_state("inner_only") == "inner"
            
        # Back to outer - original values restored
        assert agent.modes.get_state("shared") == "outer_value"
        assert "inner_only" not in agent.modes.get_all_state()
```

### Mock Testing with Modes

Test mode behavior with mocked responses:

```python
@pytest.mark.asyncio
async def test_mode_workflow_with_mocks():
    """Test complex mode workflow with mocked LLM responses."""
    agent = Agent("Workflow agent")
    
    workflow_steps = []
    
    @agent.modes("step1")
    async def step1_mode(ctx: ModeContext):
        workflow_steps.append("step1")
        return ctx.switch_mode("step2")
    
    @agent.modes("step2")  
    async def step2_mode(ctx: ModeContext):
        workflow_steps.append("step2")
        return ctx.switch_mode("step3")
    
    @agent.modes("step3")
    async def step3_mode(ctx: ModeContext):
        workflow_steps.append("step3")
        return ctx.exit_mode()
    
    await agent.initialize()
    
    # Mock responses for each step
    with agent.mock(
        agent.mock.create("Step 1 response"),
        agent.mock.create("Step 2 response"), 
        agent.mock.create("Step 3 response")
    ):
        async with agent.modes["step1"]:
            response = await agent.call("Start workflow")
        
        # Verify workflow progression
        assert workflow_steps == ["step1", "step2", "step3"]
        assert agent.current_mode is None  # Should exit after step3
        assert "Step 3 response" in response.content
```

## Performance Considerations

### Mode Overhead

Minimize mode overhead for production use:

```python
# ❌ Heavy mode handler
@agent.modes("heavy")
async def heavy_mode(ctx: ModeContext):
    # Expensive operations in every call
    complex_analysis = await expensive_computation()
    large_data = load_massive_dataset()
    
    ctx.add_system_message(f"Heavy mode with {len(large_data)} items")

# ✅ Optimized mode handler  
@agent.modes("optimized")
async def optimized_mode(ctx: ModeContext):
    # Cache expensive operations
    if "analysis_cache" not in ctx.state:
        ctx.state["analysis_cache"] = await expensive_computation()
    
    # Use cached data
    analysis = ctx.state["analysis_cache"]
    ctx.add_system_message(f"Optimized mode using cached analysis")
    
    # Cleanup state when appropriate
    if ctx.state.get("cleanup_needed"):
        del ctx.state["analysis_cache"]
```

### State Management Efficiency

Optimize mode state handling:

```python
@agent.modes("efficient")
async def efficient_mode(ctx: ModeContext):
    """Efficient state management patterns."""
    
    # Use state for caching, not computation
    if "config" not in ctx.state:
        ctx.state["config"] = load_mode_config()  # Load once
    
    # Store references, not copies
    ctx.state["agent_ref"] = ctx.agent  # Reference, not copy
    
    # Clean up unused state
    if ctx.state.get("call_count", 0) > 10:
        # Clean up old data after 10 calls
        ctx.state.pop("old_data", None)
    
    ctx.state["call_count"] = ctx.state.get("call_count", 0) + 1
```

## Complete Examples

Here's a comprehensive example demonstrating advanced mode usage:

```python
--8<-- "examples/modes/comprehensive_modes.py"
```

## Best Practices

### Mode Design Guidelines

- **Single responsibility** - Each mode should have a focused purpose
- **State management** - Use mode state for persistence, not computation
- **Transition logic** - Keep mode transitions predictable and documented
- **Resource cleanup** - Clean up mode state when exiting long-running modes
- **Event integration** - Use events to monitor mode behavior in production

### Production Recommendations

```python
# Production mode pattern
@agent.modes("production_ready")
async def production_ready_mode(ctx: ModeContext):
    """Production-ready mode with comprehensive features."""
    
    # Initialize mode with safety checks
    if not ctx.state.get("initialized"):
        # Validate prerequisites
        if not hasattr(ctx.agent, "required_tools"):
            raise ValueError("Mode requires specific tools")
        
        # Set up monitoring
        ctx.state["start_time"] = datetime.now()
        ctx.state["call_count"] = 0
        ctx.state["error_count"] = 0
        ctx.state["initialized"] = True
    
    try:
        # Update metrics
        ctx.state["call_count"] += 1
        ctx.state["last_call"] = datetime.now()
        
        # Add contextual system message
        call_num = ctx.state["call_count"]
        ctx.add_system_message(f"Production mode - Call #{call_num}")
        
        # Automatic cleanup after extended use
        if call_num > 100:
            ctx.state.clear()
            ctx.state["initialized"] = True
            
        return await ctx.call()
        
    except Exception as e:
        ctx.state["error_count"] += 1
        ctx.state["last_error"] = str(e)
        
        # Consider exiting mode after too many errors
        if ctx.state["error_count"] > 5:
            return ctx.exit_mode()
        
        raise
```

## Next Steps

- **[Multi-Agent](./multi-agent.md)** - Coordinate modes across multiple agents
- **[Interactive Execution](./interactive-execution.md)** - Use modes in interactive execution contexts
- **[Events](../core/events.md)** - Monitor and respond to mode changes
- **[Tools](../core/tools.md)** - Build tools that interact with agent modes
- **[Components](../extensibility/components.md)** - Create reusable mode-aware components
