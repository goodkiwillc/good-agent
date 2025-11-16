# Additional Agent Routing & State Management Concepts

This document explores alternative and complementary patterns for agent routing, state management, and context orchestration. These concepts can be used alongside or instead of the core routing system described in `agent-routing-orchestration.md`.

---

## 1. Graph-Based Agent Orchestration (DAG Execution)

**Concept:** Define agent workflows as directed acyclic graphs (DAGs) where nodes are tasks/routes and edges are transitions. Enables parallel execution, fan-out/fan-in patterns, and complex orchestration.

### Core Idea

Instead of linear route transitions, define a graph of operations that can execute in parallel when there are no dependencies.

```python
from good_agent import Agent, Graph, Node, Edge

agent = Agent("You are a helpful assistant.")

# Define workflow as a graph
workflow = Graph()

# Add nodes (operations)
workflow.add_node('start', start_handler)
workflow.add_node('analyze_query', analyze_query_handler)
workflow.add_node('search_web', search_web_handler)
workflow.add_node('search_docs', search_docs_handler)
workflow.add_node('search_code', search_code_handler)
workflow.add_node('synthesize', synthesize_handler)
workflow.add_node('end', end_handler)

# Define edges (transitions)
workflow.add_edge('start', 'analyze_query')

# Conditional fan-out based on query analysis
workflow.add_edge(
    'analyze_query',
    'search_web',
    condition=lambda ctx: ctx.needs_web_search
)
workflow.add_edge(
    'analyze_query',
    'search_docs',
    condition=lambda ctx: ctx.needs_docs
)
workflow.add_edge(
    'analyze_query',
    'search_code',
    condition=lambda ctx: ctx.needs_code
)

# Fan-in - wait for all searches to complete
workflow.add_edge('search_web', 'synthesize')
workflow.add_edge('search_docs', 'synthesize')
workflow.add_edge('search_code', 'synthesize')
workflow.add_edge('synthesize', 'end')

# Attach workflow to agent
agent.set_workflow(workflow)

# Execute
async with agent:
    result = await agent.call("How does authentication work in this codebase?")
    # Executes: start -> analyze_query -> [search_web, search_docs, search_code] in parallel -> synthesize -> end
```

### Advanced: Dynamic Graph Construction

```python
# Build graph dynamically based on query
async def build_research_graph(query: str) -> Graph:
    """Build a custom workflow graph for this query"""

    graph = Graph()
    graph.add_node('start', start_handler)
    graph.add_node('analyze', analyze_handler)

    # Determine what searches we need
    analysis = await analyze_query(query)

    search_nodes = []
    if analysis.needs_web:
        graph.add_node('web_search', web_search_handler)
        graph.add_edge('analyze', 'web_search')
        search_nodes.append('web_search')

    if analysis.needs_academic:
        graph.add_node('arxiv_search', arxiv_search_handler)
        graph.add_edge('analyze', 'arxiv_search')
        search_nodes.append('arxiv_search')

    if analysis.needs_code:
        graph.add_node('code_search', code_search_handler)
        graph.add_edge('analyze', 'code_search')
        search_nodes.append('code_search')

    # Add synthesis node that waits for all searches
    graph.add_node('synthesize', synthesize_handler)
    for node in search_nodes:
        graph.add_edge(node, 'synthesize')

    return graph

# Use dynamic graph
query = "How do neural networks work?"
graph = await build_research_graph(query)
agent.set_workflow(graph)

async with agent:
    result = await agent.call(query)
```

### Graph Patterns

```python
# Pattern 1: Map-Reduce
map_reduce = Graph()
map_reduce.add_node('split', split_task_handler)
map_reduce.add_node('map_1', map_handler)
map_reduce.add_node('map_2', map_handler)
map_reduce.add_node('map_3', map_handler)
map_reduce.add_node('reduce', reduce_handler)

map_reduce.add_edge('split', 'map_1')
map_reduce.add_edge('split', 'map_2')
map_reduce.add_edge('split', 'map_3')
map_reduce.add_edge('map_1', 'reduce')
map_reduce.add_edge('map_2', 'reduce')
map_reduce.add_edge('map_3', 'reduce')

# Pattern 2: Pipeline with error handling
pipeline = Graph()
pipeline.add_node('step1', step1_handler)
pipeline.add_node('step2', step2_handler)
pipeline.add_node('step3', step3_handler)
pipeline.add_node('error_handler', error_handler)
pipeline.add_node('retry', retry_handler)

pipeline.add_edge('step1', 'step2')
pipeline.add_edge('step2', 'step3')

# Error edges
pipeline.add_edge('step1', 'error_handler', condition=lambda ctx: ctx.has_error)
pipeline.add_edge('step2', 'error_handler', condition=lambda ctx: ctx.has_error)
pipeline.add_edge('error_handler', 'retry')
pipeline.add_edge('retry', 'step1')  # Retry from beginning

# Pattern 3: Conditional branching
branch = Graph()
branch.add_node('classify', classify_handler)
branch.add_node('path_a', path_a_handler)
branch.add_node('path_b', path_b_handler)
branch.add_node('path_c', path_c_handler)
branch.add_node('merge', merge_handler)

branch.add_edge('classify', 'path_a', condition=lambda ctx: ctx.classification == 'A')
branch.add_edge('classify', 'path_b', condition=lambda ctx: ctx.classification == 'B')
branch.add_edge('classify', 'path_c', condition=lambda ctx: ctx.classification == 'C')
branch.add_edge('path_a', 'merge')
branch.add_edge('path_b', 'merge')
branch.add_edge('path_c', 'merge')
```

### Use Cases

- **Parallel research**: Search multiple sources simultaneously
- **Map-reduce operations**: Split large task into parallel sub-tasks, then combine results
- **Complex workflows**: Multi-stage document processing, data pipelines
- **Error handling**: Automatic retry with backoff, fallback paths
- **A/B testing**: Run multiple strategies in parallel, pick best result

---

## 2. Agent Behaviors/Traits (Composable Mixins)

**Concept:** Instead of mutually exclusive routes, define reusable behaviors that can be composed together. An agent can have multiple active behaviors simultaneously.

### Core Idea

Behaviors are like traits or mixins - they add capabilities and can be combined.

```python
from good_agent import Agent, Behavior

# Define reusable behaviors
class VerboseBehavior(Behavior):
    """Makes agent explain its reasoning"""

    async def before_llm_call(self, ctx: AgentContext):
        ctx.add_system_message(
            "Think step by step and explain your reasoning."
        )

    async def after_llm_call(self, ctx: AgentContext, response: str):
        # Could add additional analysis
        return response

class FactCheckBehavior(Behavior):
    """Verifies facts before responding"""

    async def after_llm_call(self, ctx: AgentContext, response: str):
        # Extract claims
        claims = extract_claims(response)

        # Verify each claim
        for claim in claims:
            verification = await ctx.agent.invoke(fact_check_tool, claim=claim)
            if not verification.is_true:
                response += f"\n\n[Note: {claim} may not be accurate]"

        return response

class RAGBehavior(Behavior):
    """Injects relevant context from vector store"""

    def __init__(self, vector_store):
        self.vector_store = vector_store

    async def before_llm_call(self, ctx: AgentContext):
        query = ctx.agent[-1].content
        docs = await self.vector_store.search(query)
        ctx.add_context_message(f"# Relevant Context\n{docs}")

class ConciseBehavior(Behavior):
    """Makes agent responses more concise"""

    async def before_llm_call(self, ctx: AgentContext):
        ctx.add_system_message(
            "Be concise. Aim for 2-3 sentences maximum."
        )

# Compose behaviors
agent = Agent(
    "You are a helpful assistant.",
    behaviors=[
        RAGBehavior(vector_store),
        VerboseBehavior(),
        FactCheckBehavior()
    ]
)

# Behaviors are active for all calls
async with agent:
    response = await agent.call("What is quantum computing?")
    # RAG injects context, agent thinks verbosely, facts are checked

# Can dynamically add/remove behaviors
async with agent:
    agent.add_behavior(ConciseBehavior())  # Now also be concise
    response = await agent.call("Explain relativity")

    agent.remove_behavior(VerboseBehavior)  # Stop being verbose
    response = await agent.call("What is gravity?")
```

### Conditional Behaviors

```python
class ConditionalBehavior(Behavior):
    """Only active under certain conditions"""

    def should_activate(self, ctx: AgentContext) -> bool:
        """Override to control when behavior is active"""
        return True

    async def before_llm_call(self, ctx: AgentContext):
        if self.should_activate(ctx):
            # Apply behavior
            pass

class DebugBehavior(ConditionalBehavior):
    """Only active in debug mode"""

    def should_activate(self, ctx: AgentContext) -> bool:
        return ctx.agent.debug_mode

    async def before_llm_call(self, ctx: AgentContext):
        ctx.add_system_message(
            f"[DEBUG] Message count: {ctx.message_count}, "
            f"Tokens: {ctx.estimated_tokens}"
        )

class LongConversationBehavior(ConditionalBehavior):
    """Only active for long conversations"""

    def should_activate(self, ctx: AgentContext) -> bool:
        return ctx.message_count > 20

    async def before_llm_call(self, ctx: AgentContext):
        # Inject conversation summary
        summary = await self.summarize_conversation(ctx.agent.messages[:-10])
        ctx.add_context_message(f"# Conversation so far\n{summary}")
```

### Behavior Priorities

```python
class PrioritizedBehavior(Behavior):
    """Behaviors with explicit priorities"""

    priority: int = 0  # Higher = runs first

    async def before_llm_call(self, ctx: AgentContext):
        pass

class CriticalSecurityBehavior(PrioritizedBehavior):
    """Runs first - filters sensitive data"""
    priority = 100

    async def before_llm_call(self, ctx: AgentContext):
        # Filter sensitive data from context
        for message in ctx.get_llm_messages():
            message.content = filter_pii(message.content)

class RAGBehavior(PrioritizedBehavior):
    """Runs after security - injects context"""
    priority = 50

    async def before_llm_call(self, ctx: AgentContext):
        # Inject RAG context
        pass

# Behaviors automatically sorted by priority
agent = Agent(
    "You are a helper.",
    behaviors=[
        RAGBehavior(),
        CriticalSecurityBehavior(),  # Will run first despite order
    ]
)
```

### Behavior Stacks

```python
# Push/pop behaviors like a stack
async with agent:
    # Normal mode
    response = await agent.call("Hello")

    # Push concise behavior temporarily
    with agent.push_behavior(ConciseBehavior()):
        response = await agent.call("Explain quantum physics")
        # Concise response

    # Behavior automatically popped
    response = await agent.call("Tell me more")
    # Back to normal verbosity
```

### Use Cases

- **Cross-cutting concerns**: Logging, monitoring, security filtering
- **Personality traits**: Verbose, concise, formal, casual, humorous
- **Quality controls**: Fact-checking, citation, bias detection
- **Context management**: RAG, summarization, pruning
- **A/B testing**: Randomly enable/disable behaviors to test impact

---

## 3. Temporal/Time-Based Routing

**Concept:** Routes and behaviors that are aware of time, schedules, and timeouts. Enables time-bounded operations and scheduled transitions.

### Core Idea

Agent behavior changes based on time constraints and schedules.

```python
from good_agent import Agent, TemporalRouter, TimeConstraint
from datetime import datetime, timedelta

agent = Agent("You are a helpful assistant.")

# Route with timeout
@agent.route('research_mode')
@agent.timeout(seconds=30)
async def research_mode(ctx: AgentContext):
    """Research mode that times out after 30 seconds"""

    # Do extensive research
    results = []
    async for result in search_stream(ctx.agent[-1].content):
        results.append(result)

        # Check if we're running out of time
        if ctx.time_remaining < timedelta(seconds=5):
            break

    # Synthesize what we have
    synthesis = await ctx.llm_call(f"Summarize: {results}")

    return ctx.next('ready')

# Scheduled routes
@agent.route('morning_briefing')
@agent.schedule(hour=9, minute=0)  # Run at 9am
async def morning_briefing(ctx: AgentContext):
    """Daily morning briefing"""

    news = await fetch_news()
    ctx.agent.append_system(f"Good morning! Here's your briefing:\n{news}")

    return ctx.next('ready')

# Time-window routes (only active during certain times)
@agent.route('after_hours')
@agent.active_hours(start=18, end=8)  # 6pm to 8am
async def after_hours(ctx: AgentContext):
    """Different behavior after hours"""

    ctx.add_system_message(
        "It's after hours. Responses will be delayed until morning "
        "unless urgent."
    )

    if not ctx.is_urgent:
        return "Your message has been received and will be addressed "
               "during business hours."

    response = await ctx.llm_call()
    return response
```

### Rate Limiting with Time Windows

```python
from good_agent import RateLimitBehavior

# Rate limiting behavior
rate_limiter = RateLimitBehavior(
    max_calls=10,
    window=timedelta(minutes=1),
    on_limit_exceeded=lambda ctx: "Rate limit exceeded. Please wait."
)

agent = Agent(
    "You are a helper.",
    behaviors=[rate_limiter]
)

# Advanced rate limiting with different tiers
class TieredRateLimiter(Behavior):
    def __init__(self):
        self.limits = {
            'basic': (10, timedelta(minutes=1)),    # 10 per minute
            'premium': (100, timedelta(minutes=1)),  # 100 per minute
        }

    async def before_llm_call(self, ctx: AgentContext):
        user_tier = ctx.user.tier
        max_calls, window = self.limits[user_tier]

        if not self.can_call(ctx.user, max_calls, window):
            raise RateLimitError(f"Rate limit exceeded for {user_tier} tier")
```

### Temporal Transitions

```python
# Automatically transition after a time period
@agent.route('processing')
@agent.auto_transition_after(seconds=5, to='timeout_handler')
async def processing(ctx: AgentContext):
    """Long-running process with timeout"""

    try:
        result = await long_running_task()
        return ctx.next('ready', result=result)
    except TimeoutError:
        # Auto-transitions to timeout_handler
        pass

@agent.route('timeout_handler')
async def timeout_handler(ctx: AgentContext):
    """Handle timeout gracefully"""
    return "Task took too long. Here's what we have so far: ..."

# Idle timeout - transition if no activity
@agent.route('active')
@agent.idle_timeout(minutes=5, to='archived')
async def active(ctx: AgentContext):
    """Active conversation"""
    response = await ctx.llm_call()
    return response

@agent.route('archived')
async def archived(ctx: AgentContext):
    """Archived conversation - warn user"""
    ctx.add_system_message(
        "This conversation has been idle for 5+ minutes. "
        "Context may be stale."
    )
    response = await ctx.llm_call()
    return ctx.next('active')  # Reactivate
```

### Time-Based Context Management

```python
class TemporalContextBehavior(Behavior):
    """Manages context based on time"""

    async def before_llm_call(self, ctx: AgentContext):
        now = datetime.now()

        # Filter messages older than 1 hour
        recent_messages = [
            msg for msg in ctx.agent.messages
            if now - msg.timestamp < timedelta(hours=1)
        ]

        # Add temporal context
        ctx.add_system_message(
            f"Current time: {now.strftime('%I:%M %p')}\n"
            f"Recent messages: {len(recent_messages)}"
        )

        # Only send recent messages to LLM
        ctx.set_llm_messages(recent_messages)

# Temporal memory decay
class DecayingMemoryBehavior(Behavior):
    """Memories fade over time"""

    def calculate_relevance(self, message: Message, now: datetime) -> float:
        """Calculate relevance based on age"""
        age = now - message.timestamp

        # Exponential decay: relevance = e^(-age/half_life)
        half_life = timedelta(hours=24)
        decay_factor = math.exp(-age / half_life)

        return decay_factor

    async def before_llm_call(self, ctx: AgentContext):
        now = datetime.now()

        # Score all messages by relevance
        scored_messages = [
            (msg, self.calculate_relevance(msg, now))
            for msg in ctx.agent.messages
        ]

        # Keep only messages above relevance threshold
        relevant_messages = [
            msg for msg, score in scored_messages
            if score > 0.3
        ]

        ctx.set_llm_messages(relevant_messages)
```

### Use Cases

- **Rate limiting**: Prevent abuse, manage costs
- **Timeouts**: Bound long-running operations
- **Scheduled tasks**: Daily briefings, periodic cleanup
- **Business hours**: Different behavior during work hours vs after hours
- **Context decay**: Older messages become less relevant over time
- **Session management**: Auto-archive idle conversations

---

## 4. Conversation Patterns (Structured Dialogue)

**Concept:** Define high-level conversation patterns like "interview", "negotiation", "tutoring", each with specific rules for turn-taking, question-asking, and flow control.

### Core Idea

Encode common conversation structures as reusable patterns.

```python
from good_agent import Agent, ConversationPattern

# Define interview pattern
class InterviewPattern(ConversationPattern):
    """Structured interview with predefined questions"""

    def __init__(self, questions: list[str]):
        self.questions = questions
        self.current_question = 0
        self.answers = {}

    async def start(self, ctx: AgentContext):
        """Start interview"""
        return await self.ask_next_question(ctx)

    async def ask_next_question(self, ctx: AgentContext):
        """Ask next question in sequence"""
        if self.current_question >= len(self.questions):
            return await self.complete(ctx)

        question = self.questions[self.current_question]
        ctx.agent.append_assistant(question)
        return ctx.wait_for_user_response()

    async def handle_response(self, ctx: AgentContext, response: str):
        """Handle user's answer"""
        question = self.questions[self.current_question]
        self.answers[question] = response

        self.current_question += 1
        return await self.ask_next_question(ctx)

    async def complete(self, ctx: AgentContext):
        """Interview complete"""
        summary = self.summarize_answers()
        ctx.agent.append_assistant(f"Thank you! Here's a summary:\n{summary}")
        return ctx.next('ready')

# Use interview pattern
interview = InterviewPattern([
    "What is your name?",
    "What brings you here today?",
    "Can you describe the problem in detail?",
    "When did this start?",
    "Have you tried any solutions?"
])

agent = Agent("You are a support agent.")
agent.use_pattern('intake_interview', interview)

async with agent:
    # Start interview
    await agent.start_pattern('intake_interview')

    # Pattern handles the conversation flow
    # Automatically asks each question in sequence
```

### Tutoring Pattern

```python
class TutoringPattern(ConversationPattern):
    """Socratic tutoring - guide student to answer"""

    def __init__(self, topic: str):
        self.topic = topic
        self.attempts = 0
        self.max_attempts = 3

    async def start(self, ctx: AgentContext):
        """Start with a question"""
        question = await self.generate_question(ctx)
        ctx.agent.append_assistant(question)
        return ctx.wait_for_user_response()

    async def handle_response(self, ctx: AgentContext, response: str):
        """Evaluate answer and guide"""

        is_correct = await self.check_answer(response)

        if is_correct:
            ctx.agent.append_assistant("Correct! Well done.")
            # Move to next concept
            return await self.next_concept(ctx)
        else:
            self.attempts += 1

            if self.attempts < self.max_attempts:
                # Give hint
                hint = await self.generate_hint(ctx, self.attempts)
                ctx.agent.append_assistant(
                    f"Not quite. Here's a hint: {hint}\n\nTry again?"
                )
                return ctx.wait_for_user_response()
            else:
                # Explain answer
                explanation = await self.explain_answer(ctx)
                ctx.agent.append_assistant(
                    f"Let me explain: {explanation}\n\n"
                    "Let's move on to the next concept."
                )
                self.attempts = 0
                return await self.next_concept(ctx)

# Use tutoring pattern
tutor = TutoringPattern(topic="Python functions")
agent = Agent("You are a programming tutor.")
agent.use_pattern('tutoring', tutor)
```

### Negotiation Pattern

```python
class NegotiationPattern(ConversationPattern):
    """Back-and-forth negotiation"""

    def __init__(self, initial_offer: float, min_acceptable: float):
        self.initial_offer = initial_offer
        self.min_acceptable = min_acceptable
        self.current_offer = initial_offer
        self.rounds = 0
        self.max_rounds = 5

    async def start(self, ctx: AgentContext):
        ctx.agent.append_assistant(
            f"I can offer you ${self.initial_offer}. What do you think?"
        )
        return ctx.wait_for_user_response()

    async def handle_response(self, ctx: AgentContext, response: str):
        self.rounds += 1

        # Parse counter-offer
        counter_offer = self.parse_offer(response)

        if counter_offer is None:
            # Not an offer, just discussion
            response = await ctx.llm_call()
            return ctx.wait_for_user_response()

        # Evaluate counter-offer
        if counter_offer <= self.current_offer * 1.1:  # Within 10%
            # Accept
            ctx.agent.append_assistant(
                f"I can accept ${counter_offer}. Deal!"
            )
            return ctx.next('deal_complete', final_price=counter_offer)

        elif self.rounds >= self.max_rounds:
            # Too many rounds, walk away
            ctx.agent.append_assistant(
                "I don't think we can reach an agreement. "
                "Let me know if you change your mind."
            )
            return ctx.next('negotiation_failed')

        else:
            # Make counter-offer
            new_offer = self.calculate_counter_offer(counter_offer)
            self.current_offer = new_offer

            ctx.agent.append_assistant(
                f"I understand. How about ${new_offer}?"
            )
            return ctx.wait_for_user_response()
```

### Brainstorming Pattern

```python
class BrainstormingPattern(ConversationPattern):
    """Facilitated brainstorming session"""

    def __init__(self, topic: str, duration_minutes: int = 10):
        self.topic = topic
        self.duration = timedelta(minutes=duration_minutes)
        self.ideas = []
        self.start_time = None

    async def start(self, ctx: AgentContext):
        self.start_time = datetime.now()

        ctx.agent.append_assistant(
            f"Let's brainstorm about {self.topic}! "
            f"We have {duration_minutes} minutes. "
            "Share any ideas that come to mind - no judgment!"
        )

        return ctx.wait_for_user_response()

    async def handle_response(self, ctx: AgentContext, response: str):
        # Capture idea
        self.ideas.append(response)

        # Check time
        elapsed = datetime.now() - self.start_time
        remaining = self.duration - elapsed

        if remaining <= timedelta(0):
            return await self.complete(ctx)

        # Encourage more ideas
        encouragement = await self.generate_encouragement(ctx)
        ctx.agent.append_assistant(
            f"Great! {encouragement}\n\n"
            f"What else? ({remaining.seconds // 60} minutes left)"
        )

        return ctx.wait_for_user_response()

    async def complete(self, ctx: AgentContext):
        # Organize and categorize ideas
        organized = await self.organize_ideas(ctx)

        ctx.agent.append_assistant(
            f"Time's up! We generated {len(self.ideas)} ideas.\n\n"
            f"Here they are organized:\n{organized}"
        )

        return ctx.next('ready')
```

### Debate Pattern

```python
class DebatePattern(ConversationPattern):
    """Structured debate with turn-taking"""

    def __init__(self, resolution: str, agent_position: str):
        self.resolution = resolution
        self.agent_position = agent_position  # 'pro' or 'con'
        self.turn = 'user'  # 'user' or 'agent'
        self.round = 1
        self.max_rounds = 3

    async def start(self, ctx: AgentContext):
        ctx.agent.append_assistant(
            f"Let's debate: {self.resolution}\n\n"
            f"I'll argue {self.agent_position}. You'll argue "
            f"{'con' if self.agent_position == 'pro' else 'pro'}.\n\n"
            f"You have 2 minutes for your opening statement. Go ahead."
        )

        self.turn = 'user'
        return ctx.wait_for_user_response()

    async def handle_response(self, ctx: AgentContext, response: str):
        if self.turn != 'user':
            ctx.agent.append_assistant("It's not your turn yet.")
            return ctx.wait_for_user_response()

        # User made their argument
        self.turn = 'agent'

        # Agent's turn to respond
        argument = await self.generate_argument(ctx)
        ctx.agent.append_assistant(argument)

        # Check if debate is over
        if self.round >= self.max_rounds:
            return await self.complete(ctx)

        # Next round
        self.round += 1
        self.turn = 'user'

        ctx.agent.append_assistant(
            f"Round {self.round}. Your turn to respond."
        )

        return ctx.wait_for_user_response()

    async def complete(self, ctx: AgentContext):
        # Judge the debate
        judgment = await self.judge_debate(ctx)

        ctx.agent.append_assistant(
            f"Debate complete!\n\n{judgment}"
        )

        return ctx.next('ready')
```

### Use Cases

- **Customer support**: Guided troubleshooting, intake interviews
- **Education**: Socratic tutoring, quizzes, explanations
- **Sales**: Qualification, negotiation, closing
- **Collaboration**: Brainstorming, planning, decision-making
- **Entertainment**: Games, debates, storytelling

---

## 5. Agent Memory Layers (Multi-Tier Memory)

**Concept:** Different types of memory with different retention policies, similar to human memory systems (working memory, episodic memory, semantic memory).

### Core Idea

Separate memory systems for different types of information.

```python
from good_agent import Agent, Memory

agent = Agent("You are a helpful assistant.")

# Working memory - current conversation context
working_memory = Memory(
    type='working',
    capacity=10,  # Keep last 10 messages
    retention='session'  # Clear after session ends
)

# Episodic memory - memorable events/conversations
episodic_memory = Memory(
    type='episodic',
    capacity=100,
    retention='permanent',
    importance_threshold=0.7  # Only store important moments
)

# Semantic memory - learned facts/knowledge
semantic_memory = Memory(
    type='semantic',
    capacity='unlimited',
    retention='permanent',
    structure='knowledge_graph'  # Store as structured knowledge
)

# Short-term memory - recent context
short_term_memory = Memory(
    type='short_term',
    capacity=50,
    retention=timedelta(hours=1),  # Forget after 1 hour
    decay='exponential'
)

agent.add_memory_layer('working', working_memory)
agent.add_memory_layer('episodic', episodic_memory)
agent.add_memory_layer('semantic', semantic_memory)
agent.add_memory_layer('short_term', short_term_memory)

async with agent:
    # Working memory used for immediate context
    response = await agent.call("My name is Alice")

    response = await agent.call("What's my name?")
    # Retrieves from working memory: "Alice"

    # Important moments stored in episodic memory
    response = await agent.call("I just got promoted to VP!")
    # Stored in episodic memory (high importance)

    # Facts stored in semantic memory
    response = await agent.call("The capital of France is Paris")
    # Stored in semantic memory as fact
```

### Memory Query System

```python
class MemoryManager:
    """Manages multi-tier memory system"""

    def __init__(self):
        self.layers = {}

    async def recall(self, query: str, ctx: AgentContext) -> dict:
        """Query all memory layers"""

        results = {}

        # Working memory - exact recent context
        results['working'] = self.layers['working'].get_recent(limit=10)

        # Short-term memory - recent but may have faded
        results['short_term'] = self.layers['short_term'].search(
            query,
            decay_adjusted=True
        )

        # Episodic memory - relevant past events
        results['episodic'] = await self.layers['episodic'].search(
            query,
            semantic_similarity=True,
            limit=5
        )

        # Semantic memory - relevant facts
        results['semantic'] = await self.layers['semantic'].query_graph(
            query,
            max_hops=2  # Related concepts
        )

        return results

    async def consolidate(self):
        """Move important short-term memories to long-term"""

        short_term = self.layers['short_term']
        episodic = self.layers['episodic']
        semantic = self.layers['semantic']

        # Find important short-term memories
        important = short_term.get_by_importance(threshold=0.7)

        for memory in important:
            if memory.is_event:
                # Move to episodic
                episodic.store(memory)
            elif memory.is_fact:
                # Extract fact and add to semantic
                fact = extract_fact(memory)
                semantic.add_fact(fact)

            # Remove from short-term
            short_term.remove(memory)

# Use memory manager
@agent.route('ready')
async def ready_with_memory(ctx: AgentContext):
    """Route that leverages memory system"""

    query = ctx.agent[-1].content

    # Recall relevant memories
    memories = await ctx.agent.memory.recall(query, ctx)

    # Add to context
    if memories['episodic']:
        ctx.add_context_message(
            "# Relevant past conversations\n" +
            "\n".join(m.summary for m in memories['episodic'])
        )

    if memories['semantic']:
        ctx.add_context_message(
            "# Relevant facts\n" +
            "\n".join(f.statement for f in memories['semantic'])
        )

    response = await ctx.llm_call()

    # Store new memory
    await ctx.agent.memory.store(
        content=query + "\n" + response,
        importance=calculate_importance(response),
        tags=['conversation', 'user_interaction']
    )

    return response
```

### Memory Consolidation

```python
# Background task for memory consolidation
@agent.background_task(interval=timedelta(hours=1))
async def consolidate_memories(agent: Agent):
    """Periodically consolidate memories"""

    # Move short-term to long-term
    await agent.memory.consolidate()

    # Prune low-importance episodic memories
    await agent.memory.layers['episodic'].prune(
        keep_top_k=100,
        importance_threshold=0.5
    )

    # Update semantic knowledge graph
    await agent.memory.layers['semantic'].update_graph()
```

### Hierarchical Memory

```python
class HierarchicalMemory:
    """Memory organized in hierarchy (general -> specific)"""

    def __init__(self):
        self.levels = {
            'general': {},      # High-level summaries
            'summary': {},      # Mid-level summaries
            'detailed': {},     # Detailed memories
        }

    async def store(self, memory: Memory):
        """Store at appropriate level"""

        # Always store detailed
        self.levels['detailed'][memory.id] = memory

        # Create summary
        summary = await summarize(memory)
        self.levels['summary'][memory.id] = summary

        # Update general knowledge
        await self.update_general_knowledge(memory)

    async def recall(self, query: str, detail_level: str = 'summary'):
        """Recall at requested detail level"""

        if detail_level == 'general':
            # Return high-level overview
            return self.levels['general']

        elif detail_level == 'summary':
            # Return summaries
            results = self.search_level('summary', query)
            return results

        elif detail_level == 'detailed':
            # Return full details
            results = self.search_level('detailed', query)
            return results

    async def drill_down(self, memory_id: str):
        """Get more detailed version of a memory"""

        if memory_id in self.levels['summary']:
            return self.levels['detailed'].get(memory_id)

        return None
```

### Use Cases

- **Context management**: Different memory tiers for different contexts
- **Long-running agents**: Maintain knowledge over weeks/months
- **Personalization**: Remember user preferences and history
- **Learning**: Extract and retain facts from conversations
- **Privacy**: Different retention policies for sensitive data

---

## 6. Context Scopes (Hierarchical Context)

**Concept:** Context organized in scopes like variable scoping in programming (global, route, local, ephemeral).

### Core Idea

Different levels of context visibility and lifetime.

```python
from good_agent import Agent, ContextScope

agent = Agent("You are a helpful assistant.")

# Global context - always available
agent.global_context.set('user_timezone', 'America/New_York')
agent.global_context.set('user_language', 'en')

@agent.route('research_mode')
async def research_mode(ctx: AgentContext):
    """Route with route-scoped context"""

    # Route context - available while in this route
    ctx.route_context.set('search_depth', 'deep')
    ctx.route_context.set('sources', ['web', 'academic', 'code'])

    # Local context - only for this LLM call
    with ctx.local_context() as local:
        local.set('instruction', 'Focus on recent developments')
        local.set('format', 'bullet_points')

        response = await ctx.llm_call()
        # Can access: global + route + local context

    # local context destroyed after with block

    # Ephemeral context - doesn't persist in history
    ctx.add_ephemeral("Current time: " + datetime.now())

    response = await ctx.llm_call()
    # Can access: global + route + ephemeral
    # ephemeral not saved to conversation history

    return ctx.next('ready')

# Context inheritance
@agent.route('deep_research')
@agent.extends('research_mode')  # Inherit context from parent route
async def deep_research(ctx: AgentContext):
    """Child route inherits parent's context"""

    # Can access parent's route_context
    search_depth = ctx.route_context.get('search_depth')  # 'deep'

    # Can override
    ctx.route_context.set('search_depth', 'exhaustive')

    response = await ctx.llm_call()

    return ctx.next('ready')
```

### Context Layers

```python
class ContextManager:
    """Manages hierarchical context"""

    def __init__(self):
        self.global_context = {}
        self.route_context_stack = []
        self.local_context = {}
        self.ephemeral_context = []

    def get_all_context(self) -> dict:
        """Merge all context layers"""

        context = {}

        # Global (lowest priority)
        context.update(self.global_context)

        # Route contexts (in stack order)
        for route_ctx in self.route_context_stack:
            context.update(route_ctx)

        # Local (highest priority)
        context.update(self.local_context)

        return context

    def push_route_context(self, context: dict):
        """Push new route context onto stack"""
        self.route_context_stack.append(context)

    def pop_route_context(self):
        """Pop route context from stack"""
        if self.route_context_stack:
            self.route_context_stack.pop()

    def add_ephemeral(self, key: str, value: Any, ttl: timedelta = None):
        """Add ephemeral context with optional TTL"""
        self.ephemeral_context.append({
            'key': key,
            'value': value,
            'expires_at': datetime.now() + ttl if ttl else None
        })

    def get_ephemeral(self) -> list:
        """Get non-expired ephemeral context"""
        now = datetime.now()

        # Filter expired
        self.ephemeral_context = [
            ctx for ctx in self.ephemeral_context
            if ctx['expires_at'] is None or ctx['expires_at'] > now
        ]

        return [
            {ctx['key']: ctx['value']}
            for ctx in self.ephemeral_context
        ]
```

### Shadowing and Resolution

```python
# Context variable shadowing (like variable scoping)
agent.global_context.set('mode', 'normal')

@agent.route('research')
async def research(ctx: AgentContext):
    # Shadow global context
    ctx.route_context.set('mode', 'research')  # Shadows global

    # Resolution order: local > route > global
    print(ctx.get('mode'))  # 'research' (route shadows global)

    with ctx.local_context() as local:
        local.set('mode', 'deep_research')  # Shadows route
        print(ctx.get('mode'))  # 'deep_research' (local shadows route)

    print(ctx.get('mode'))  # 'research' (back to route)

    return ctx.next('ready')

# Back in 'ready' route
# ctx.get('mode') => 'normal' (global, no shadowing)
```

### Context Sections

```python
# Named context sections that can be added/removed
@agent.route('ready')
async def ready_with_sections(ctx: AgentContext):
    """Use named context sections"""

    # Add RAG context section
    ctx.add_context_section(
        'rag',
        content="# Relevant Documents\n...",
        priority=10
    )

    # Add user info section
    ctx.add_context_section(
        'user_info',
        content=f"User: {ctx.user.name}\nTimezone: {ctx.user.timezone}",
        priority=5
    )

    # Add temporary instruction
    ctx.add_context_section(
        'instruction',
        content="Use bullet points for this response",
        priority=100,  # Highest priority
        ephemeral=True  # Don't persist
    )

    response = await ctx.llm_call()
    # LLM sees sections in priority order

    # Remove section
    ctx.remove_context_section('rag')

    return response
```

### Use Cases

- **Context isolation**: Prevent context leakage between routes
- **Temporary modifications**: Local context for single calls
- **Context inheritance**: Child routes inherit parent context
- **Ephemeral context**: Inject context that doesn't persist in history
- **Context priority**: Control what takes precedence

---

## 7. Agent Modes with Affordances

**Concept:** Define what agent "can" and "cannot" do in each mode, similar to capabilities or permissions.

### Core Idea

Modes restrict/enable specific capabilities.

```python
from good_agent import Agent, Mode, Affordance

agent = Agent("You are a helpful assistant.")

# Define modes with affordances
normal_mode = Mode(
    name='normal',
    affordances=[
        Affordance.CAN_CHAT,
        Affordance.CAN_SEARCH_WEB,
        Affordance.CAN_USE_TOOLS,
    ]
)

read_only_mode = Mode(
    name='read_only',
    affordances=[
        Affordance.CAN_CHAT,
        Affordance.CAN_SEARCH_WEB,
        # Cannot use tools that modify state
    ]
)

restricted_mode = Mode(
    name='restricted',
    affordances=[
        Affordance.CAN_CHAT,
        # No search, no tools
    ]
)

admin_mode = Mode(
    name='admin',
    affordances=[
        Affordance.CAN_CHAT,
        Affordance.CAN_SEARCH_WEB,
        Affordance.CAN_USE_TOOLS,
        Affordance.CAN_MODIFY_SYSTEM,
        Affordance.CAN_ACCESS_SENSITIVE_DATA,
    ]
)

# Set mode
agent.set_mode(normal_mode)

async with agent:
    # Normal operations
    response = await agent.call("Search for quantum computing")
    # Works - CAN_SEARCH_WEB is enabled

    # Switch to restricted mode
    agent.set_mode(restricted_mode)

    response = await agent.call("Search for AI")
    # Fails or returns: "I don't have permission to search the web"
```

### Affordance Checking

```python
class AffordanceManager:
    """Manages what agent can do"""

    def __init__(self, mode: Mode):
        self.mode = mode

    def can(self, affordance: Affordance) -> bool:
        """Check if affordance is available"""
        return affordance in self.mode.affordances

    def require(self, affordance: Affordance):
        """Require affordance or raise error"""
        if not self.can(affordance):
            raise PermissionError(
                f"Mode '{self.mode.name}' does not have "
                f"affordance: {affordance.name}"
            )

    async def execute_if_allowed(
        self,
        affordance: Affordance,
        action: callable
    ):
        """Execute action only if affordance is available"""
        if self.can(affordance):
            return await action()
        else:
            return f"Cannot perform this action in {self.mode.name} mode"

# Use in routes
@agent.route('search')
async def search(ctx: AgentContext):
    """Search route respects affordances"""

    # Check affordance
    if not ctx.agent.affordances.can(Affordance.CAN_SEARCH_WEB):
        return "Search is not available in current mode"

    # Or require it (raises error if not available)
    ctx.agent.affordances.require(Affordance.CAN_SEARCH_WEB)

    query = ctx.agent[-1].content
    results = await ctx.agent.invoke(web_search, query=query)

    return ctx.next('ready')
```

### Dynamic Affordances

```python
# Affordances can be dynamic based on context
class DynamicAffordance:
    """Affordance that checks condition at runtime"""

    def __init__(self, name: str, condition: callable):
        self.name = name
        self.condition = condition

    def is_available(self, ctx: AgentContext) -> bool:
        """Check if available right now"""
        return self.condition(ctx)

# Example: Time-based affordances
time_restricted_search = DynamicAffordance(
    name='CAN_SEARCH_WEB',
    condition=lambda ctx: 9 <= datetime.now().hour <= 17  # 9am-5pm
)

# Example: Rate-limited affordances
rate_limited_api = DynamicAffordance(
    name='CAN_CALL_EXTERNAL_API',
    condition=lambda ctx: ctx.api_calls_today < ctx.api_limit
)

# Example: User-tier based affordances
premium_feature = DynamicAffordance(
    name='CAN_USE_ADVANCED_SEARCH',
    condition=lambda ctx: ctx.user.tier in ['premium', 'enterprise']
)
```

### Mode Transitions with Affordance Changes

```python
@agent.route('normal')
async def normal(ctx: AgentContext):
    """Normal mode with full affordances"""

    # Check if we should restrict
    if ctx.detect_risky_request():
        # Switch to restricted mode
        ctx.agent.set_mode(restricted_mode)
        return ctx.next('restricted')

    response = await ctx.llm_call()
    return response

@agent.route('restricted')
async def restricted(ctx: AgentContext):
    """Restricted mode with limited affordances"""

    # Notify user
    ctx.add_system_message(
        "Running in restricted mode. Some features unavailable."
    )

    response = await ctx.llm_call()

    # Can escalate back to normal if request is safe
    if ctx.request_is_safe():
        ctx.agent.set_mode(normal_mode)
        return ctx.next('normal')

    return response
```

### Tool Filtering by Affordances

```python
# Tools can declare required affordances
class Tool:
    def __init__(self, name: str, func: callable, requires: list[Affordance]):
        self.name = name
        self.func = func
        self.requires = requires

web_search_tool = Tool(
    name='web_search',
    func=web_search,
    requires=[Affordance.CAN_SEARCH_WEB]
)

file_delete_tool = Tool(
    name='delete_file',
    func=delete_file,
    requires=[Affordance.CAN_MODIFY_SYSTEM, Affordance.CAN_DELETE_FILES]
)

# Agent automatically filters tools based on affordances
@agent.route('ready')
async def ready_with_filtered_tools(ctx: AgentContext):
    """Only expose tools that agent can use"""

    # Get available tools based on affordances
    available_tools = [
        tool for tool in ctx.agent.tools
        if all(
            ctx.agent.affordances.can(req)
            for req in tool.requires
        )
    ]

    # Set available tools for this call
    ctx.set_tools(available_tools)

    response = await ctx.llm_call()
    return response
```

### Use Cases

- **Security**: Restrict dangerous operations
- **User permissions**: Different capabilities for different users
- **Safety**: Prevent risky actions in certain contexts
- **Billing**: Limit expensive operations by tier
- **Compliance**: Enforce regulatory restrictions

---

## 8. Streaming/Reactive Routes

**Concept:** Routes that can emit events in real-time, respond to external events, and be chained together reactively.

### Core Idea

Routes as reactive streams that emit/consume events.

```python
from good_agent import Agent, ReactiveRoute, Stream

agent = Agent("You are a helpful assistant.")

# Reactive route that emits events
@agent.reactive_route('monitor')
async def monitor_route(ctx: AgentContext):
    """Monitor external system and emit events"""

    async for event in monitor_external_system():
        # Emit event
        ctx.emit('system_event', {
            'type': event.type,
            'severity': event.severity,
            'data': event.data
        })

        # Can transition based on event
        if event.severity == 'critical':
            return ctx.next('alert')

# Route that reacts to events
@agent.route('alert')
@agent.on_event('system_event')
async def alert_route(ctx: AgentContext, event: dict):
    """React to system events"""

    if event['severity'] == 'critical':
        # Notify immediately
        await notify_admin(event)

        # Have agent analyze
        analysis = await ctx.llm_call(
            f"Analyze this critical event: {event['data']}"
        )

        ctx.emit('alert_sent', {'analysis': analysis})

    return ctx.next('monitor')

# Chain reactive routes
@agent.reactive_route('data_processor')
async def data_processor(ctx: AgentContext):
    """Process incoming data stream"""

    async for data in ctx.input_stream():
        # Process data
        processed = await process_data(data)

        # Emit to next stage
        ctx.output_stream.emit(processed)

@agent.reactive_route('data_analyzer')
@agent.subscribes_to('data_processor')
async def data_analyzer(ctx: AgentContext):
    """Analyze processed data"""

    async for data in ctx.input_stream():
        # Analyze with LLM
        analysis = await ctx.llm_call(
            f"Analyze this data: {data}"
        )

        ctx.output_stream.emit(analysis)
```

### Streaming LLM Responses

```python
@agent.route('streaming_response')
async def streaming_response(ctx: AgentContext):
    """Stream LLM response as it's generated"""

    # Start streaming response
    async for chunk in ctx.llm_call_stream():
        # Emit each chunk
        ctx.emit('response_chunk', {'chunk': chunk})

        # Can also do real-time processing
        if detect_error_in_chunk(chunk):
            # Interrupt and correct
            ctx.interrupt()
            return ctx.next('error_correction')

    return ctx.next('ready')

# Client receives chunks in real-time
@agent.on_event('response_chunk')
async def handle_chunk(chunk: str):
    """Handle streaming chunks"""
    print(chunk, end='', flush=True)
```

### Event-Driven Architecture

```python
# Define event bus
event_bus = EventBus()

# Agents subscribe to events
@agent.on_event('user_message')
async def handle_user_message(ctx: AgentContext, event: dict):
    """React to user messages"""
    response = await ctx.llm_call()
    event_bus.emit('agent_response', {'response': response})

@agent.on_event('external_notification')
async def handle_notification(ctx: AgentContext, event: dict):
    """React to external notifications"""
    ctx.agent.append_system(f"Notification: {event['message']}")

    # Check if should notify user
    if event['priority'] == 'high':
        event_bus.emit('notify_user', event)

# Multiple agents can subscribe to same events
research_agent = Agent("Research agent")

@research_agent.on_event('research_request')
async def handle_research_request(ctx: AgentContext, event: dict):
    """Perform research when requested"""
    results = await research(event['query'])
    event_bus.emit('research_complete', {'results': results})

# Coordinate between agents via events
main_agent = Agent("Main agent")

@main_agent.route('ready')
async def ready(ctx: AgentContext):
    """Main agent can request research"""

    if 'research' in ctx.agent[-1].content:
        # Request research from research agent
        event_bus.emit('research_request', {
            'query': extract_query(ctx.agent[-1].content)
        })

        # Wait for research to complete
        research_results = await event_bus.wait_for('research_complete')

        # Use results
        ctx.add_context_message(f"Research results: {research_results}")

    response = await ctx.llm_call()
    return response
```

### Backpressure and Flow Control

```python
class RateLimitedStream:
    """Stream with backpressure"""

    def __init__(self, max_rate: int):
        self.max_rate = max_rate
        self.queue = asyncio.Queue(maxsize=max_rate)

    async def emit(self, item: Any):
        """Emit with backpressure"""
        # Blocks if queue is full
        await self.queue.put(item)

    async def consume(self) -> AsyncIterator[Any]:
        """Consume with rate limiting"""
        while True:
            item = await self.queue.get()
            yield item
            await asyncio.sleep(1.0 / self.max_rate)

# Use in route
@agent.reactive_route('rate_limited_processor')
async def rate_limited_processor(ctx: AgentContext):
    """Process data with rate limiting"""

    stream = RateLimitedStream(max_rate=10)  # 10 items/second

    async for data in ctx.input_stream():
        await stream.emit(data)

    async for data in stream.consume():
        result = await process_data(data)
        ctx.output_stream.emit(result)
```

### Use Cases

- **Real-time monitoring**: React to system events
- **Streaming responses**: Progressive response generation
- **Multi-agent coordination**: Agents communicate via events
- **Data pipelines**: Chain reactive processing stages
- **Live analysis**: Process streaming data with LLMs

---

## 9. Agent Checkpoints and Rollbacks

**Concept:** Save agent state at various points and rollback to previous states, like version control for conversations.

### Core Idea

Checkpoint conversation state and restore it later.

```python
from good_agent import Agent, Checkpoint

agent = Agent("You are a helpful assistant.")

async with agent:
    response1 = await agent.call("Tell me about quantum computing")

    # Create checkpoint
    checkpoint1 = agent.create_checkpoint(name='before_deep_dive')

    response2 = await agent.call("Explain quantum entanglement in detail")
    response3 = await agent.call("Now explain quantum superposition")

    # Create another checkpoint
    checkpoint2 = agent.create_checkpoint(name='after_deep_dive')

    # Continue conversation
    response4 = await agent.call("Actually, I want to learn about AI instead")

    # Rollback to checkpoint
    agent.rollback(checkpoint1)
    # Conversation state restored to before deep dive

    # Can now take a different path
    response5 = await agent.call("Tell me about practical applications")
```

### Automatic Checkpointing

```python
# Auto-checkpoint at route transitions
@agent.route('research_mode')
@agent.auto_checkpoint(name='before_research')
async def research_mode(ctx: AgentContext):
    """Automatically checkpointed before entry"""

    # Do extensive research
    results = await research(ctx.agent[-1].content)

    # If research fails, can rollback
    if not results.success:
        ctx.agent.rollback('before_research')
        return ctx.next('ready')

    response = await ctx.llm_call()
    return ctx.next('ready')

# Checkpoint before risky operations
@agent.route('experiment')
async def experiment(ctx: AgentContext):
    """Try experimental approach with rollback"""

    checkpoint = ctx.agent.create_checkpoint('before_experiment')

    try:
        # Try experimental approach
        result = await experimental_operation(ctx)

        if not result.satisfactory:
            # Rollback and try different approach
            ctx.agent.rollback(checkpoint)
            result = await fallback_operation(ctx)

    except Exception as e:
        # Rollback on error
        ctx.agent.rollback(checkpoint)
        return ctx.next('error_handler')

    return ctx.next('ready')
```

### Branching Conversations

```python
# Create branches from checkpoints
async with agent:
    response1 = await agent.call("Tell me about space exploration")

    checkpoint = agent.create_checkpoint('main')

    # Branch A: Focus on Mars
    branch_a = agent.create_branch('mars_branch', from_checkpoint=checkpoint)
    async with agent.use_branch(branch_a):
        response2 = await agent.call("Tell me about Mars missions")
        response3 = await agent.call("What about Mars colonization?")

    # Branch B: Focus on Moon
    branch_b = agent.create_branch('moon_branch', from_checkpoint=checkpoint)
    async with agent.use_branch(branch_b):
        response4 = await agent.call("Tell me about Moon missions")
        response5 = await agent.call("What about Moon bases?")

    # Compare branches
    mars_summary = branch_a.summarize()
    moon_summary = branch_b.summarize()

    # Pick best branch or merge
    if mars_summary.quality > moon_summary.quality:
        agent.merge_branch(branch_a)
    else:
        agent.merge_branch(branch_b)
```

### Checkpoint Metadata

```python
class Checkpoint:
    """Checkpoint with metadata"""

    def __init__(
        self,
        name: str,
        state: AgentState,
        metadata: dict = None
    ):
        self.name = name
        self.state = state
        self.timestamp = datetime.now()
        self.metadata = metadata or {}
        self.id = generate_id()

    def describe(self) -> str:
        """Describe checkpoint"""
        return (
            f"Checkpoint '{self.name}' at {self.timestamp}\n"
            f"Messages: {len(self.state.messages)}\n"
            f"Current route: {self.state.current_route}\n"
            f"Metadata: {self.metadata}"
        )

# Create checkpoint with metadata
checkpoint = agent.create_checkpoint(
    name='before_decision',
    metadata={
        'reason': 'User wants to explore options',
        'quality_score': calculate_quality(agent),
        'message_count': len(agent.messages)
    }
)

# List checkpoints
checkpoints = agent.list_checkpoints()
for cp in checkpoints:
    print(cp.describe())

# Restore specific checkpoint by ID or name
agent.rollback(checkpoint_id='abc123')
agent.rollback(checkpoint_name='before_decision')
```

### Checkpoint Diff

```python
# Compare two checkpoints
diff = agent.diff_checkpoints(checkpoint1, checkpoint2)

print(f"Messages added: {len(diff.added_messages)}")
print(f"Messages removed: {len(diff.removed_messages)}")
print(f"Route changes: {diff.route_changes}")
print(f"State changes: {diff.state_changes}")

# Visualize conversation tree
tree = agent.get_conversation_tree()
tree.visualize()  # ASCII art of conversation branches
```

### Use Cases

- **Exploration**: Try different conversation paths
- **Error recovery**: Rollback on errors
- **A/B testing**: Compare different agent behaviors
- **Undo functionality**: Let users undo recent messages
- **Debugging**: Replay conversations from checkpoints

---

## 10. Collaborative Multi-Agent Patterns

**Concept:** Patterns for how multiple agents work together - leader-follower, peer-to-peer, hierarchical, democratic voting.

### Core Idea

Define collaboration protocols between agents.

```python
from good_agent import Agent, Collaboration

# Leader-Follower pattern
leader = Agent("You are the team leader.")
follower1 = Agent("You are a research specialist.")
follower2 = Agent("You are a writing specialist.")

collaboration = Collaboration.leader_follower(
    leader=leader,
    followers=[follower1, follower2]
)

async with collaboration:
    # Leader delegates tasks
    result = await collaboration.execute("Write a report on AI")

    # Leader decides what to delegate
    # follower1 does research
    # follower2 writes report
    # Leader reviews and synthesizes

# Peer-to-peer pattern
agent1 = Agent("You are agent 1.")
agent2 = Agent("You are agent 2.")
agent3 = Agent("You are agent 3.")

collaboration = Collaboration.peer_to_peer([agent1, agent2, agent3])

async with collaboration:
    # Agents collaborate as equals
    result = await collaboration.brainstorm("How to improve user experience")

    # Each agent contributes ideas
    # Ideas are merged into final output

# Hierarchical pattern
ceo = Agent("You are the CEO.")
manager1 = Agent("You are engineering manager.")
manager2 = Agent("You are product manager.")
engineer1 = Agent("You are a senior engineer.")
engineer2 = Agent("You are a junior engineer.")

collaboration = Collaboration.hierarchical({
    ceo: [manager1, manager2],
    manager1: [engineer1, engineer2],
    manager2: []
})

async with collaboration:
    # Top-down delegation
    result = await collaboration.execute("Build new feature")

    # CEO assigns to managers
    # Managers assign to engineers
    # Results roll up the hierarchy

# Democratic voting pattern
agents = [
    Agent("You are voter 1."),
    Agent("You are voter 2."),
    Agent("You are voter 3."),
    Agent("You are voter 4."),
    Agent("You are voter 5."),
]

collaboration = Collaboration.democratic(agents, threshold=0.6)

async with collaboration:
    # Agents vote on decisions
    decision = await collaboration.decide("Should we proceed with this plan?")

    # Each agent votes yes/no
    # Decision made if threshold reached (60%)

    print(f"Decision: {decision.outcome}")
    print(f"Votes: {decision.yes_votes}/{decision.total_votes}")
```

### Delegation Pattern

```python
class DelegationPattern:
    """Leader delegates specific tasks to specialists"""

    def __init__(self, leader: Agent, specialists: dict[str, Agent]):
        self.leader = leader
        self.specialists = specialists

    async def execute(self, task: str) -> str:
        """Execute task with delegation"""

        # Leader breaks down task
        subtasks = await self.leader.call(
            f"Break this task into subtasks that can be delegated: {task}"
        )

        # Delegate each subtask to appropriate specialist
        results = {}
        for subtask in subtasks:
            specialist_type = await self.leader.call(
                f"What type of specialist needed for: {subtask.description}"
            )

            specialist = self.specialists.get(specialist_type)
            if specialist:
                result = await specialist.call(subtask.description)
                results[subtask.id] = result

        # Leader synthesizes results
        final = await self.leader.call(
            f"Synthesize these results into final output: {results}"
        )

        return final

# Use delegation
leader = Agent("You are a project manager.")
specialists = {
    'research': Agent("You are a researcher."),
    'design': Agent("You are a designer."),
    'implementation': Agent("You are an engineer."),
}

delegation = DelegationPattern(leader, specialists)
result = await delegation.execute("Create a new user authentication system")
```

### Debate Pattern

```python
class DebateCollaboration:
    """Agents debate to reach best solution"""

    def __init__(self, agents: list[Agent], moderator: Agent):
        self.agents = agents
        self.moderator = moderator

    async def debate(self, topic: str, rounds: int = 3) -> str:
        """Run debate"""

        # Initial positions
        positions = {}
        for agent in self.agents:
            position = await agent.call(f"What is your position on: {topic}")
            positions[agent] = position

        # Rounds of debate
        for round in range(rounds):
            # Each agent responds to others
            for agent in self.agents:
                other_positions = [
                    positions[other]
                    for other in self.agents
                    if other != agent
                ]

                response = await agent.call(
                    f"Other agents said: {other_positions}\n"
                    f"Respond to their arguments."
                )

                positions[agent] = response

        # Moderator synthesizes
        synthesis = await self.moderator.call(
            f"These agents debated {topic}. Their final positions:\n"
            f"{positions}\n\n"
            f"Synthesize the best solution."
        )

        return synthesis

# Use debate
agents = [
    Agent("You argue for approach A."),
    Agent("You argue for approach B."),
    Agent("You argue for approach C."),
]
moderator = Agent("You are an impartial moderator.")

debate = DebateCollaboration(agents, moderator)
solution = await debate.debate("How should we implement caching?")
```

### Ensemble Pattern

```python
class EnsemblePattern:
    """Multiple agents solve same problem, best answer chosen"""

    def __init__(self, agents: list[Agent], selector: Agent):
        self.agents = agents
        self.selector = selector

    async def solve(self, problem: str) -> str:
        """Solve with ensemble"""

        # All agents solve independently
        solutions = []
        for agent in self.agents:
            solution = await agent.call(problem)
            solutions.append(solution)

        # Selector picks best
        best = await self.selector.call(
            f"Pick the best solution:\n{solutions}"
        )

        return best

# Use ensemble (good for reducing errors)
agents = [
    Agent("You are solver 1.", model='gpt-4'),
    Agent("You are solver 2.", model='claude-3'),
    Agent("You are solver 3.", model='gemini'),
]
selector = Agent("You are a solution evaluator.")

ensemble = EnsemblePattern(agents, selector)
answer = await ensemble.solve("What is the capital of France?")
```

### Swarm Pattern

```python
class SwarmCollaboration:
    """Many simple agents collaborate like a swarm"""

    def __init__(self, num_agents: int, agent_template: Agent):
        self.agents = [
            agent_template.clone(id=i)
            for i in range(num_agents)
        ]

    async def search(self, query: str) -> list[str]:
        """Swarm search"""

        # Each agent searches independently
        tasks = [
            agent.call(f"Search for: {query}")
            for agent in self.agents
        ]

        results = await asyncio.gather(*tasks)

        # Aggregate results
        aggregated = self.aggregate(results)

        return aggregated

    def aggregate(self, results: list) -> list:
        """Aggregate swarm results"""
        # Combine, deduplicate, rank
        return list(set(results))

# Use swarm (good for parallel exploration)
swarm = SwarmCollaboration(
    num_agents=10,
    agent_template=Agent("You are a search agent.")
)

results = await swarm.search("Latest AI research")
```

### Use Cases

- **Complex tasks**: Break down and delegate
- **Decision making**: Multiple perspectives, voting
- **Quality improvement**: Debate, ensemble for better answers
- **Parallel work**: Swarm for exploration
- **Review process**: Peer review, approval chains

---

## Summary Table

| Concept | Key Feature | Best For |
|---------|-------------|----------|
| **Graph/DAG Orchestration** | Parallel execution, fan-out/fan-in | Complex workflows, data pipelines |
| **Behaviors/Traits** | Composable, multiple active simultaneously | Cross-cutting concerns, personality |
| **Temporal Routing** | Time-aware, scheduled, timeouts | Rate limiting, scheduled tasks |
| **Conversation Patterns** | Structured dialogue flows | Interviews, tutoring, debates |
| **Memory Layers** | Multi-tier memory with different retention | Long-running agents, personalization |
| **Context Scopes** | Hierarchical context visibility | Context isolation, temporary mods |
| **Affordances** | Capability-based restrictions | Security, permissions, safety |
| **Reactive Routes** | Event-driven, streaming | Real-time monitoring, pipelines |
| **Checkpoints** | Save/restore conversation state | Exploration, error recovery, undo |
| **Multi-Agent** | Collaboration patterns | Complex tasks, decision making |

---

## Implementation Priority

Suggested order for implementation:

1. **Behaviors/Traits** - Most immediately useful, composable
2. **Context Scopes** - Critical for context management
3. **Memory Layers** - Enables long-running agents
4. **Temporal Routing** - Adds time awareness
5. **Checkpoints** - Enables exploration and recovery
6. **Graph Orchestration** - For complex workflows
7. **Conversation Patterns** - For structured interactions
8. **Affordances** - For security/permissions
9. **Reactive Routes** - For real-time systems
10. **Multi-Agent** - Advanced collaboration
