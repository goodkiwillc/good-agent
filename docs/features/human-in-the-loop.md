# Human-in-the-Loop

Human-in-the-loop (HITL) patterns enable agents to pause execution and wait for user input, approval, or intervention at critical points. Good Agent provides both interactive CLI interfaces and programmatic APIs for seamless human-agent collaboration.

## Core Concepts

### Interactive Sessions

The Good Agent CLI provides built-in interactive sessions for real-time conversation with agents:

--8<-- "src/good_agent/cli/run.py:19:44"

**Key Features:**

- **Real-time Interaction**: Type commands directly to agents
- **Tool Visibility**: See tool calls and outputs as they happen
- **Rich Display**: Markdown rendering and structured output
- **Session Management**: History, clear screen, graceful exit

### Human Input API (Planned)

The core agent API will support programmatic user input requests:

```python
from good_agent import Agent

async with Agent("You are a deployment assistant") as agent:
    # Request user approval with typed response
    response = await agent.user_input(
        "Approve deployment to production?", 
        response_model=bool
    )
    
    if response.data:
        await agent.call("Proceeding with deployment...")
    else:
        await agent.call("Deployment cancelled by user")
```

## Interactive CLI Interface

### Basic Usage

Start an interactive session with any agent:

```bash
# Run agent interactively
good run agents/research_assistant.py

# With custom configuration
good run agents/researcher.py --model gpt-4o --temperature 0.2
```

### Session Features

**Real-time Tool Visibility:**

```text
➜ Find the latest quantum computing research

🛠️  Calling: web_search
{"query": "quantum computing research 2024", "max_results": 10}

🔧 Tool Output: web_search
Found 10 research papers on quantum computing breakthroughs in 2024...

Recent advances in quantum computing include new error correction 
methods and improved qubit stability. Key research areas are:

1. Quantum error correction algorithms
2. Topological qubits development  
3. Quantum networking protocols
```

**Session Commands:**

- `exit` or `quit` - End session gracefully
- `clear` - Clear screen and continue
- Standard chat interaction for all other input

### CLI Implementation

The interactive loop handles streaming execution with rich display:

--8<-- "src/good_agent/cli/run.py:58:95"

## User Input Patterns

### Approval Workflows

Request user approval before taking critical actions:

```python
from good_agent import Agent
from typing import Literal

async with Agent("System administrator") as agent:
    
    @agent.route('deploy')
    async def deploy_with_approval(ctx):
        """Deploy after getting user approval"""
        
        # Show deployment plan
        plan = await ctx.llm_call("Generate deployment plan")
        
        # Request approval with timeout
        approved = await ctx.ask_user(
            message=f"About to execute: {plan}. Approve?",
            response_model=bool,
            timeout=timedelta(minutes=5)
        )
        
        if approved:
            result = await execute_deployment(plan)
            return f"Deployment completed: {result}"
        else:
            return "Deployment cancelled by user"
```

### Clarification Requests

Handle ambiguous user requests by asking for clarification:

```python
@agent.route('ready')
async def ready_with_clarification(ctx):
    """Ask for clarification when needed"""
    
    query = ctx.agent[-1].content
    
    # Detect ambiguity using LLM
    ambiguity_check = await ctx.llm_call(
        f"Is this request ambiguous? {query}",
        response_model=bool
    )
    
    if ambiguity_check.data:
        # Ask user to clarify
        clarification = await ctx.ask_user(
            "I'm not sure what you mean. Can you provide more details?",
            timeout=timedelta(minutes=10)
        )
        
        # Add clarification to context
        ctx.agent.append_user(clarification)
    
    response = await ctx.llm_call()
    return response
```

### Progressive Disclosure

Show partial results and get user direction:

```python
@agent.route('research')
async def research_with_feedback(ctx):
    """Show progress and get direction"""
    
    # Phase 1: Initial research
    initial_results = await quick_research(ctx.agent[-1].content)
    
    # Show to user and ask for direction
    direction = await ctx.show_and_ask(
        content=f"Initial findings: {initial_results}",
        message="What would you like me to focus on next?",
        options=[
            "Deep dive into technical details",
            "Find more recent sources", 
            "Compare with alternatives",
            "This is sufficient"
        ]
    )
    
    # Continue based on user choice
    if direction == "This is sufficient":
        return initial_results
    else:
        return await focused_research(initial_results, direction)
```

## Advanced Patterns

### Multiple Choice Interactions

Present structured choices to users:

```python
@agent.route('analysis')
async def analysis_with_options(ctx):
    """Present analysis options to user"""
    
    # Generate multiple approaches
    approaches = await ctx.llm_call(
        "Generate 3 different analysis approaches",
        response_model=list[str]
    )
    
    # Let user choose approach
    choice = await ctx.ask_user(
        message="Which analysis approach would you prefer?",
        options=approaches,
        response_model=str
    )
    
    # Execute chosen approach
    return await execute_analysis(choice)
```

### Confidence-Based Intervention

Only involve humans when agent confidence is low:

```python
@agent.route('ready')
async def ready_with_confidence_check(ctx):
    """Only involve human if confidence is low"""
    
    response = await ctx.llm_call()
    
    # Estimate confidence in response
    confidence = await ctx.llm_call(
        f"Rate confidence in this response (0-1): {response}",
        response_model=float
    )
    
    if confidence.data < 0.7:
        # Low confidence - ask for validation
        validation = await ctx.ask_user(
            f"I'm not very confident about this response: {response}\n"
            f"Is this correct?",
            options=["yes", "no", "revise"]
        )
        
        if validation == "no":
            # Get correct answer from user
            correct = await ctx.ask_user("What's the correct answer?")
            ctx.agent.append_assistant(correct)
            return correct
        elif validation == "revise":
            return ctx.next('ready')  # Try again
    
    return response
```

### Streaming with Interruption

Allow users to interrupt long-running responses:

```python
@agent.route('streaming')
async def streaming_with_intervention(ctx):
    """Stream response with option to interrupt"""
    
    chunks = []
    
    async for chunk in ctx.llm_call_stream():
        chunks.append(chunk)
        
        # Check if user wants to stop
        if await ctx.check_interrupt():
            ctx.emit('response:interrupted', {'partial': ''.join(chunks)})
            
            # Ask what to do next
            action = await ctx.ask_user(
                "Response interrupted. What would you like to do?",
                options=["Continue", "Start over", "Stop here"]
            )
            
            if action == "Start over":
                return ctx.next('streaming')  # Retry
            elif action == "Stop here":
                return ''.join(chunks)
            # else continue
    
    return ''.join(chunks)
```

### Validation Workflows

Get user validation for generated content:

```python
@agent.route('generate')
async def generate_with_validation(ctx):
    """Generate content with user validation"""
    
    # Generate initial content
    draft = await ctx.llm_call("Generate draft content")
    
    # Show draft and get feedback
    feedback = await ctx.ask_user(
        message=f"Here's a draft:\n\n{draft}\n\nWhat changes would you like?",
        response_model=str,
        optional=True  # User can approve as-is
    )
    
    if feedback:
        # Apply user feedback
        revised = await ctx.llm_call(
            f"Revise this content based on feedback:\n"
            f"Original: {draft}\n"
            f"Feedback: {feedback}"
        )
        return revised
    else:
        return draft
```

## Timeout and Error Handling

### Timeout Configuration

All human input operations support timeouts:

```python
from datetime import timedelta

# Short timeout for approvals
approved = await ctx.ask_user(
    "Approve this action?",
    response_model=bool,
    timeout=timedelta(minutes=2),
    default=False  # Default if timeout
)

# Longer timeout for complex input
response = await ctx.ask_user(
    "Please provide detailed feedback:",
    timeout=timedelta(minutes=30),
    default="No feedback provided"
)
```

### Default Actions

Configure what happens when users don't respond:

```python
@agent.route('deploy')
async def deploy_with_defaults(ctx):
    """Deploy with smart defaults on timeout"""
    
    try:
        approved = await ctx.ask_user(
            "Deploy to production?",
            response_model=bool,
            timeout=timedelta(minutes=5)
        )
    except TimeoutError:
        # Log timeout and use safe default
        ctx.logger.warning("Deployment approval timed out")
        approved = False
    
    if not approved:
        return "Deployment cancelled (timeout or denial)"
    
    return await execute_deployment()
```

### Error Recovery

Handle errors gracefully in interactive workflows:

```python
@agent.route('interactive_task')
async def interactive_task_with_recovery(ctx):
    """Task with error recovery"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Attempt task
            result = await complex_task()
            return result
            
        except Exception as e:
            if attempt < max_retries - 1:
                # Ask user how to proceed
                action = await ctx.ask_user(
                    f"Task failed with error: {e}\nHow should I proceed?",
                    options=["Retry", "Skip this step", "Abort task"]
                )
                
                if action == "Skip this step":
                    return "Step skipped by user"
                elif action == "Abort task":
                    return "Task aborted by user"
                # else retry
            else:
                return f"Task failed after {max_retries} attempts"
```

## Integration Patterns

### Web UI Integration

Human-in-the-loop works seamlessly with web interfaces:

```python
from good_agent import Agent
from good_agent.web import WebUI

# Create agent with HITL capabilities
agent = Agent("Assistant with human input")

# Web UI handles user input collection
web_ui = WebUI(agent)

@web_ui.route('/chat')
async def chat_endpoint(request):
    """Chat endpoint with HITL support"""
    
    # Start agent execution
    async with agent:
        # Agent can request user input via web interface
        response = await agent.call(request.json['message'])
        
    return {'response': response}
```

### Slack/Discord Integration

Integrate with chat platforms:

```python
from good_agent.integrations import SlackBot

bot = SlackBot(agent)

@bot.command('/deploy')
async def deploy_command(context):
    """Deploy command with approval flow"""
    
    # Agent requests approval in Slack channel
    approved = await agent.user_input(
        "Deploy version 2.1.4 to production?",
        response_model=bool,
        channel=context.channel
    )
    
    if approved:
        result = await deploy_version("2.1.4")
        await context.respond(f"Deployment completed: {result}")
    else:
        await context.respond("Deployment cancelled")
```

### API Integration

Use HITL patterns in API endpoints:

```python
from fastapi import FastAPI, BackgroundTasks
from good_agent import Agent

app = FastAPI()
agent = Agent("Processing assistant")

@app.post("/process-document")
async def process_document(
    document_id: str,
    background_tasks: BackgroundTasks
):
    """Process document with human review"""
    
    async def process_with_review():
        # Process document
        result = await agent.call(f"Process document {document_id}")
        
        # Request human review if needed
        if result.confidence < 0.8:
            review_needed = await agent.user_input(
                f"Review required for document {document_id}",
                response_model=bool,
                notification_channel="reviews"
            )
            
            if review_needed:
                # Wait for human review
                feedback = await agent.user_input(
                    f"Please review: {result}",
                    response_model=str,
                    timeout=timedelta(hours=24)
                )
                
                # Apply feedback
                final_result = await agent.call(f"Apply feedback: {feedback}")
                return final_result
        
        return result
    
    background_tasks.add_task(process_with_review)
    return {"status": "processing", "document_id": document_id}
```

## Testing Human-in-the-Loop

### Mocking User Input

Test interactive agents by mocking user responses:

```python
import pytest
from good_agent.testing import MockUserInput

@pytest.mark.asyncio
async def test_approval_workflow():
    """Test approval workflow with mocked input"""
    
    agent = Agent("Test assistant")
    
    # Mock user approval
    with MockUserInput(responses={
        "Approve deployment?": True,
        "Confirm settings?": True
    }):
        async with agent:
            result = await agent.call("Deploy the application")
            
    assert "Deployment completed" in result

@pytest.mark.asyncio
async def test_timeout_handling():
    """Test timeout handling"""
    
    agent = Agent("Test assistant")
    
    # Mock timeout (no response provided)
    with MockUserInput(timeout=True):
        async with agent:
            result = await agent.call("Request user input")
            
    assert "timeout" in result.lower()
```

### Integration Testing

Test complete interactive workflows:

```python
@pytest.mark.asyncio
async def test_interactive_workflow():
    """Test complete interactive workflow"""
    
    agent = Agent("Interactive assistant")
    
    # Simulate user interaction sequence
    responses = [
        "Yes, proceed",           # Initial approval
        "Option 2",               # Choice selection  
        "Looks good to me",       # Final validation
    ]
    
    with MockUserInput(sequence=responses):
        async with agent:
            result = await agent.call("Start interactive process")
            
    assert result == "Process completed successfully"
```

## Best Practices

### 1. Always Set Timeouts

Prevent indefinite waiting by always setting appropriate timeouts:

```python
# Good - Always specify timeout
response = await ctx.ask_user(
    "Approve this action?",
    timeout=timedelta(minutes=5),
    default=False
)

# Avoid - No timeout can hang indefinitely
response = await ctx.ask_user("Approve this action?")  # No timeout
```

### 2. Provide Clear Context

Give users enough information to make informed decisions:

```python
# Good - Detailed context
approved = await ctx.ask_user(
    message=(
        "About to delete 1,247 old log files (2.3GB total) "
        "from /var/log/app/. This action cannot be undone. "
        "Proceed with deletion?"
    ),
    response_model=bool
)

# Avoid - Vague request
approved = await ctx.ask_user("Delete files?", response_model=bool)
```

### 3. Handle Edge Cases

Account for timeouts, errors, and unexpected responses:

```python
try:
    choice = await ctx.ask_user(
        "Select processing mode:",
        options=["fast", "thorough", "balanced"],
        timeout=timedelta(minutes=2)
    )
except TimeoutError:
    # Use intelligent default
    choice = "balanced"
    ctx.logger.info("Using default processing mode due to timeout")
except ValueError as e:
    # Handle invalid response
    ctx.logger.error(f"Invalid user response: {e}")
    choice = "balanced"
```

### 4. Minimize Interruptions

Only request human input when truly necessary:

```python
@agent.route('process')
async def smart_processing(ctx):
    """Only interrupt user when confidence is low"""
    
    result = await ctx.llm_call()
    confidence = await estimate_confidence(result)
    
    # Only ask for validation if confidence is low
    if confidence < 0.7:
        validated = await ctx.ask_user(
            f"I'm {confidence:.0%} confident about this result. Validate?",
            response_model=bool
        )
        
        if not validated:
            # Get correct answer
            result = await ctx.ask_user("What's the correct result?")
    
    return result
```

### 5. Provide Escape Hatches

Always give users ways to abort or modify workflows:

```python
@agent.route('long_task')
async def long_task_with_escape(ctx):
    """Long task with escape options"""
    
    # Check in periodically
    for step in range(10):
        result = await process_step(step)
        
        if step % 3 == 0:  # Check every 3 steps
            action = await ctx.ask_user(
                f"Completed step {step}/10. Continue?",
                options=["continue", "skip_to_end", "abort"],
                timeout=timedelta(seconds=30),
                default="continue"  # Auto-continue if no response
            )
            
            if action == "abort":
                return "Task aborted by user"
            elif action == "skip_to_end":
                return await process_final_step()
    
    return "Task completed successfully"
```

Human-in-the-loop patterns make agents more trustworthy and effective by involving humans at critical decision points while maintaining the speed and efficiency of automated processing.
