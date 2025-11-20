# Multi-Agent Orchestration

Good Agent provides powerful multi-agent orchestration capabilities that allow you to coordinate multiple agents, create agent conversations, manage agent pools for concurrent workloads, and build complex multi-agent workflows. These features enable sophisticated AI systems where specialized agents work together to solve complex problems.

## Overview

### Key Concepts

- **Agent Conversations** - Direct agent-to-agent communication using the pipe operator (`|`)
- **Message Forwarding** - Automatic forwarding of assistant messages as user messages
- **Agent Pools** - Collections of agents for concurrent task distribution
- **Workflow Orchestration** - Chaining agents together for multi-step processes
- **Event Coordination** - Synchronizing agent actions through events
- **Resource Sharing** - Sharing tools, context, and state across agents

### Multi-Agent Benefits

- **Specialization** - Different agents can have specialized roles and capabilities
- **Scalability** - Distribute workload across multiple agent instances  
- **Collaboration** - Agents can work together on complex multi-step problems
- **Fault Tolerance** - System continues working even if individual agents fail
- **Modularity** - Compose complex behaviors from simpler agent components

## Agent Conversations

### Basic Agent Piping

Use the pipe operator (`|`) to create conversations between agents:

```python
from good_agent import Agent

async with Agent("You are a researcher.") as researcher:
    async with Agent("You are a writer.") as writer:
        # Create a conversation between agents
        async with researcher | writer as conversation:
            # Messages from researcher will be forwarded to writer
            researcher.assistant.append("I found interesting data about AI trends.")
            
            # This message will automatically appear in writer's message history
            assert len(writer.user) == 1
            assert writer.user[-1].content == "I found interesting data about AI trends."
```

### Bidirectional Communication

Conversations automatically forward messages in both directions:

```python
async with Agent("You are Alice, a data scientist.") as alice:
    async with Agent("You are Bob, a product manager.") as bob:
        async with alice | bob as conversation:
            # Alice sends a message
            alice.assistant.append("I've analyzed the user engagement data.")
            
            # Bob receives it and responds
            bob.assistant.append("Great! What are the key insights?")
            
            # Alice now sees Bob's question
            assert alice.user[-1].content == "Great! What are the key insights?"
            
            # Alice can respond
            alice.assistant.append("Users prefer the new interface by 40%.")
            
            # Conversation flows naturally between agents
            assert len(bob.user) == 2  # Alice's original message + response
```

### Multi-Agent Conversations

Chain multiple agents together for group conversations:

```python
async with Agent("You are a researcher.") as researcher:
    async with Agent("You are a analyst.") as analyst:  
        async with Agent("You are a presenter.") as presenter:
            # Create 3-way conversation
            async with researcher | analyst | presenter as conversation:
                # Researcher starts
                researcher.assistant.append("I collected data on market trends.")
                
                # Both analyst and presenter receive the message
                assert analyst.user[-1].content == "I collected data on market trends."
                assert presenter.user[-1].content == "I collected data on market trends."
                
                # Analyst responds
                analyst.assistant.append("The data shows 25% growth in Q3.")
                
                # Both researcher and presenter get analyst's message
                assert len(researcher.user) == 1  # From analyst
                assert len(presenter.user) == 2   # From researcher + analyst
```

## Agent Workflows

### Sequential Agent Processing

Create workflows where each agent processes the output of the previous agent:

```python
async def multi_agent_workflow():
    """Demonstrate sequential agent processing."""
    
    # Specialized agents
    async with Agent("You extract key facts from text.") as extractor:
        async with Agent("You analyze and categorize facts.") as analyzer:
            async with Agent("You create executive summaries.") as summarizer:
                
                # Step 1: Extract facts
                await extractor.call(
                    "Extract key facts from this report: [long report text...]"
                )
                
                # Step 2: Pass facts to analyzer  
                facts = extractor.assistant[-1].content
                async with extractor | analyzer:
                    analyzer.user.append(f"Analyze these facts: {facts}")
                    analysis = await analyzer.call()
                
                # Step 3: Pass analysis to summarizer
                async with analyzer | summarizer:
                    summarizer.user.append(f"Summarize this analysis: {analysis.content}")
                    summary = await summarizer.call()
                
                return summary

# Usage
final_summary = await multi_agent_workflow()
print(f"Final summary: {final_summary.content}")
```

### Parallel Agent Processing

Process multiple tasks concurrently with different agents:

```python
import asyncio

async def parallel_agent_processing(tasks: list[str]):
    """Process multiple tasks in parallel with specialized agents."""
    
    # Create specialized agents for different task types
    agents = {
        "research": Agent("You are a research specialist."),
        "analysis": Agent("You are a data analyst."), 
        "writing": Agent("You are a content writer."),
        "review": Agent("You are a quality reviewer.")
    }
    
    # Initialize all agents
    for agent in agents.values():
        await agent.initialize()
    
    async def process_task(task_type: str, task_description: str):
        """Process a single task with the appropriate specialist."""
        agent = agents[task_type]
        return await agent.call(task_description)
    
    # Process tasks in parallel
    results = await asyncio.gather(
        process_task("research", "Research AI market trends"),
        process_task("analysis", "Analyze user engagement metrics"),
        process_task("writing", "Write product announcement"),
        process_task("review", "Review draft documentation"),
        return_exceptions=True
    )
    
    # Clean up
    for agent in agents.values():
        await agent.close()
    
    return results

# Usage
results = await parallel_agent_processing([...])
for i, result in enumerate(results):
    if isinstance(result, Exception):
        print(f"Task {i} failed: {result}")
    else:
        print(f"Task {i} result: {result.content}")
```

## Agent Pools

### Creating Agent Pools

Use `AgentPool` to manage collections of agents for concurrent workloads:

```python
from good_agent.agent.pool import AgentPool

async def create_worker_pool(pool_size: int = 4) -> AgentPool:
    """Create a pool of worker agents."""
    
    # Create multiple identical agents
    agents = []
    for i in range(pool_size):
        agent = Agent(f"You are worker #{i+1}. Handle tasks efficiently.")
        await agent.initialize()
        agents.append(agent)
    
    return AgentPool(agents)

# Usage
pool = await create_worker_pool(4)
print(f"Created pool with {len(pool)} agents")

# Access agents by index
first_agent = pool[0]
last_agent = pool[-1]

# Iterate over pool
for i, agent in enumerate(pool):
    print(f"Agent {i}: {agent}")
```

### Round-Robin Task Distribution

Distribute tasks across pool agents using round-robin:

```python
async def distribute_tasks_round_robin(pool: AgentPool, tasks: list[str]):
    """Distribute tasks across pool using round-robin scheduling."""
    
    async def process_task(task_index: int, task: str):
        # Select agent using round-robin
        agent = pool[task_index % len(pool)]
        
        # Process the task
        result = await agent.call(f"Process this task: {task}")
        
        return {
            "task_index": task_index,
            "worker_id": task_index % len(pool),
            "task": task,
            "result": result.content
        }
    
    # Process all tasks concurrently
    results = await asyncio.gather(
        *[process_task(i, task) for i, task in enumerate(tasks)],
        return_exceptions=True
    )
    
    return [r for r in results if not isinstance(r, Exception)]

# Usage
pool = await create_worker_pool(3)
tasks = [
    "Analyze customer feedback",
    "Generate product descriptions", 
    "Review code quality",
    "Write test cases",
    "Create documentation",
    "Optimize performance"
]

results = await distribute_tasks_round_robin(pool, tasks)
for result in results:
    print(f"Worker {result['worker_id']}: {result['result'][:50]}...")
```

### Load Balancing

Implement intelligent load balancing based on agent performance:

```python
import time
from collections import defaultdict

class LoadBalancedPool:
    """Agent pool with load balancing based on response time."""
    
    def __init__(self, agents: list[Agent]):
        self.pool = AgentPool(agents)
        self.performance_stats = defaultdict(list)
        self.active_tasks = defaultdict(int)
    
    def get_best_agent(self) -> Agent:
        """Select agent with best performance and lowest load."""
        best_agent = None
        best_score = float('inf')
        
        for i, agent in enumerate(self.pool):
            # Calculate average response time
            stats = self.performance_stats[i]
            avg_time = sum(stats[-10:]) / len(stats[-10:]) if stats else 0
            
            # Factor in current load
            current_load = self.active_tasks[i]
            
            # Combined score (lower is better)
            score = avg_time + (current_load * 0.1)
            
            if score < best_score:
                best_score = score
                best_agent = (i, agent)
        
        if best_agent is None:
            return self.pool[0]  # Fallback
            
        return best_agent
    
    async def process_task(self, task: str) -> str:
        """Process task with best available agent."""
        agent_index, agent = self.get_best_agent()
        
        # Track active tasks
        self.active_tasks[agent_index] += 1
        
        try:
            start_time = time.time()
            result = await agent.call(task)
            end_time = time.time()
            
            # Record performance
            response_time = end_time - start_time
            self.performance_stats[agent_index].append(response_time)
            
            return result.content
            
        finally:
            self.active_tasks[agent_index] -= 1

# Usage
agents = [Agent(f"Worker {i}") for i in range(5)]
for agent in agents:
    await agent.initialize()

lb_pool = LoadBalancedPool(agents)

# Process tasks with automatic load balancing
tasks = ["Task 1", "Task 2", "Task 3", "Task 4", "Task 5"]
results = await asyncio.gather(
    *[lb_pool.process_task(task) for task in tasks]
)
```

## Streaming Multi-Agent Workflows

### Streaming Conversations

Stream messages between agents in real-time:

```python
from good_agent.messages import AssistantMessage, ToolMessage

async def streaming_conversation():
    """Stream a conversation between multiple agents."""
    
    async with Agent("You are a problem solver.") as solver:
        async with Agent("You are a critic who finds issues.") as critic:
            async with Agent("You are a synthesizer.") as synthesizer:
                
                # Start the conversation
                async with solver | critic | synthesizer as conversation:
                    
                    # Stream solver's thinking process
                    async for message in solver.execute("How can we reduce customer churn?"):
                        print(f"SOLVER: {message.content}")
                        
                        # Process solver's output with critic
                        if isinstance(message, AssistantMessage):
                            async for critic_msg in critic.execute(max_iterations=2):
                                print(f"CRITIC: {critic_msg.content}")
                                
                                # Synthesizer combines perspectives
                                if isinstance(critic_msg, AssistantMessage):
                                    synthesis = await synthesizer.call(
                                        "Synthesize the solver and critic perspectives"
                                    )
                                    print(f"SYNTHESIS: {synthesis.content}")
                                    break

await streaming_conversation()
```

### Pipeline Processing

Create agent pipelines with streaming processing:

```python
async def agent_pipeline(input_data: str):
    """Process data through a pipeline of specialized agents."""
    
    agents = [
        Agent("You preprocess and clean data."),
        Agent("You extract features and insights."), 
        Agent("You generate recommendations."),
        Agent("You format final output.")
    ]
    
    # Initialize pipeline
    for agent in agents:
        await agent.initialize()
    
    current_data = input_data
    
    # Process through pipeline with streaming
    for i, agent in enumerate(agents):
        print(f"\n--- Stage {i+1}: {agent.system[0].content[:30]}... ---")
        
        # Stream processing at each stage
        async for message in agent.execute(f"Process this data: {current_data}"):
            print(f"Stage {i+1}: {message.content}")
            
            # Use final assistant message as input to next stage
            if isinstance(message, AssistantMessage):
                current_data = message.content
        
        print(f"Stage {i+1} complete")
    
    # Clean up
    for agent in agents:
        await agent.close()
    
    return current_data

# Usage
final_result = await agent_pipeline("Raw customer feedback data...")
print(f"Final pipeline result: {final_result}")
```

## Event Coordination

### Cross-Agent Event Handling

Coordinate agents using the event system:

```python
from good_agent.events import AgentEvents
from good_agent.core.event_router import EventContext

class AgentCoordinator:
    """Coordinates multiple agents using events."""
    
    def __init__(self, agents: list[Agent]):
        self.agents = agents
        self.coordinator_state = {"active_agents": set(), "completed_tasks": []}
        
        # Set up cross-agent event handlers
        for agent in agents:
            self.setup_agent_monitoring(agent)
    
    def setup_agent_monitoring(self, agent: Agent):
        """Set up event monitoring for an agent."""
        
        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def on_tool_complete(ctx: EventContext):
            agent_id = id(agent)
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            
            print(f"Agent {agent_id} completed tool {tool_name}: {'✅' if success else '❌'}")
            
            # Notify other agents of tool completion
            self.notify_agents(f"Agent {agent_id} completed {tool_name}")
        
        @agent.on(AgentEvents.EXECUTE_AFTER)
        def on_execution_complete(ctx: EventContext):
            agent_id = id(agent)
            self.coordinator_state["completed_tasks"].append(agent_id)
            
            print(f"Agent {agent_id} completed execution")
            
            # Check if all agents are done
            if len(self.coordinator_state["completed_tasks"]) == len(self.agents):
                print("🎉 All agents completed their tasks!")
    
    def notify_agents(self, message: str):
        """Send notification to all agents."""
        for agent in self.agents:
            agent.append(f"[COORDINATOR] {message}", role="system")
    
    async def run_coordinated_tasks(self, tasks: list[str]):
        """Run tasks across agents with coordination."""
        
        # Assign tasks to agents
        task_assignments = list(zip(self.agents, tasks))
        
        # Execute tasks concurrently with coordination
        async def run_agent_task(agent: Agent, task: str):
            async for message in agent.execute(task, max_iterations=3):
                yield f"Agent {id(agent)}: {message.content}"
        
        # Stream results from all agents
        for agent, task in task_assignments:
            print(f"\nStarting agent {id(agent)} with task: {task}")
            async for update in run_agent_task(agent, task):
                print(update)

# Usage
agents = [
    Agent("You handle data processing tasks."),
    Agent("You handle analysis tasks."),
    Agent("You handle reporting tasks.")
]

for agent in agents:
    await agent.initialize()

coordinator = AgentCoordinator(agents)
await coordinator.run_coordinated_tasks([
    "Process customer data",
    "Analyze trends", 
    "Generate report"
])
```

### Agent Synchronization

Synchronize agent actions using events and barriers:

```python
import asyncio

class AgentSynchronizer:
    """Synchronizes agent execution using barriers."""
    
    def __init__(self, agents: list[Agent]):
        self.agents = agents
        self.barriers = {}
        self.agent_status = {id(agent): "ready" for agent in agents}
    
    async def create_barrier(self, barrier_name: str):
        """Create a synchronization barrier for all agents."""
        self.barriers[barrier_name] = asyncio.Barrier(len(self.agents))
    
    async def wait_for_barrier(self, barrier_name: str, agent: Agent):
        """Wait for all agents to reach this barrier."""
        agent_id = id(agent)
        self.agent_status[agent_id] = f"waiting at {barrier_name}"
        
        print(f"Agent {agent_id} waiting at barrier '{barrier_name}'")
        
        await self.barriers[barrier_name].wait()
        
        self.agent_status[agent_id] = "ready"
        print(f"Agent {agent_id} passed barrier '{barrier_name}'")
    
    async def synchronized_workflow(self, tasks: list[str]):
        """Run workflow with synchronized phases."""
        
        # Create barriers for each phase
        await self.create_barrier("analysis_complete")
        await self.create_barrier("review_complete")
        
        async def agent_workflow(agent: Agent, task: str):
            agent_id = id(agent)
            
            # Phase 1: Analysis
            print(f"Agent {agent_id}: Starting analysis phase")
            await agent.call(f"Analyze: {task}")
            
            # Wait for all agents to complete analysis
            await self.wait_for_barrier("analysis_complete", agent)
            
            # Phase 2: Review (can now use results from all agents)
            print(f"Agent {agent_id}: Starting review phase")
            await agent.call("Review your analysis and others' work")
            
            # Wait for all reviews to complete
            await self.wait_for_barrier("review_complete", agent)
            
            # Phase 3: Final output
            print(f"Agent {agent_id}: Generating final output")
            result = await agent.call("Generate final recommendations")
            return result
        
        # Run all agent workflows concurrently
        results = await asyncio.gather(
            *[agent_workflow(agent, task) for agent, task in zip(self.agents, tasks)],
            return_exceptions=True
        )
        
        return results

# Usage
agents = [Agent(f"Specialist {i}") for i in range(3)]
for agent in agents:
    await agent.initialize()

synchronizer = AgentSynchronizer(agents)
results = await synchronizer.synchronized_workflow([
    "Market analysis task",
    "Technical analysis task", 
    "Risk analysis task"
])
```

## Advanced Multi-Agent Patterns

### Hierarchical Agent Systems

Create hierarchical systems with manager and worker agents:

```python
class HierarchicalAgentSystem:
    """Hierarchical system with manager and worker agents."""
    
    def __init__(self, manager: Agent, workers: list[Agent]):
        self.manager = manager
        self.workers = workers
        self.task_queue = asyncio.Queue()
        self.results = {}
    
    async def delegate_task(self, task: str) -> str:
        """Manager delegates task to available worker."""
        
        # Manager analyzes task and decides delegation
        delegation_plan = await self.manager.call(
            f"Analyze this task and create a delegation plan: {task}"
        )
        
        # Find best worker for the task
        worker_assignments = await self.assign_workers(delegation_plan.content)
        
        # Execute tasks with assigned workers
        results = []
        for worker, subtask in worker_assignments:
            result = await worker.call(subtask)
            results.append(result.content)
        
        # Manager consolidates results
        final_result = await self.manager.call(
            f"Consolidate these worker results: {results}"
        )
        
        return final_result.content
    
    async def assign_workers(self, delegation_plan: str) -> list[tuple[Agent, str]]:
        """Assign subtasks to workers based on delegation plan."""
        
        # Simple assignment - in practice, this would be more sophisticated
        subtasks = delegation_plan.split('\n')[:len(self.workers)]
        
        assignments = []
        for worker, subtask in zip(self.workers, subtasks):
            if subtask.strip():
                assignments.append((worker, subtask.strip()))
        
        return assignments

# Usage
manager = Agent("You are a project manager who delegates and consolidates work.")
workers = [
    Agent("You are a research specialist."),
    Agent("You are a data analyst."), 
    Agent("You are a writer.")
]

# Initialize all agents
await manager.initialize()
for worker in workers:
    await worker.initialize()

hierarchy = HierarchicalAgentSystem(manager, workers)
result = await hierarchy.delegate_task("Create a market analysis report")
print(f"Hierarchical result: {result}")
```

### Democratic Agent Consensus

Implement consensus mechanisms for agent decision-making:

```python
from collections import Counter

class ConsensusAgentSystem:
    """System where agents reach consensus on decisions."""
    
    def __init__(self, agents: list[Agent]):
        self.agents = agents
        self.voting_history = []
    
    async def reach_consensus(self, question: str, max_rounds: int = 3) -> str:
        """Agents discuss and reach consensus on a question."""
        
        consensus_reached = False
        round_count = 0
        discussion_history = []
        
        while not consensus_reached and round_count < max_rounds:
            round_count += 1
            print(f"\n--- Consensus Round {round_count} ---")
            
            # Each agent provides their perspective
            round_responses = []
            for i, agent in enumerate(self.agents):
                
                # Include discussion history in prompt
                context = ""
                if discussion_history:
                    context = f"Previous discussion: {discussion_history[-3:]}"
                
                prompt = f"{context}\n\nQuestion: {question}\nProvide your answer and reasoning:"
                response = await agent.call(prompt)
                
                round_responses.append({
                    "agent_id": i,
                    "response": response.content
                })
                
                print(f"Agent {i}: {response.content[:100]}...")
            
            discussion_history.extend(round_responses)
            
            # Check for consensus
            consensus_reached, consensus_answer = await self.check_consensus(round_responses)
            
            if consensus_reached:
                print(f"✅ Consensus reached: {consensus_answer}")
                return consensus_answer
            else:
                print("❌ No consensus, continuing discussion...")
        
        # If no consensus, use majority vote
        return await self.majority_vote(discussion_history[-len(self.agents):])
    
    async def check_consensus(self, responses: list[dict]) -> tuple[bool, str]:
        """Check if agents have reached consensus."""
        
        # Use a separate agent to analyze consensus
        consensus_judge = Agent("You analyze if a group has reached consensus.")
        await consensus_judge.initialize()
        
        try:
            analysis = await consensus_judge.call(
                f"Analyze if these responses show consensus: {responses}"
                f"Return 'CONSENSUS: [answer]' if yes, 'NO_CONSENSUS' if no."
            )
            
            if "CONSENSUS:" in analysis.content:
                return True, analysis.content.split("CONSENSUS:")[1].strip()
            else:
                return False, ""
                
        finally:
            await consensus_judge.close()
    
    async def majority_vote(self, responses: list[dict]) -> str:
        """Use majority vote as fallback."""
        
        # Extract key themes/answers
        answers = [r["response"][:50] for r in responses]  # Simplified
        most_common = Counter(answers).most_common(1)[0]
        
        return f"Majority decision: {most_common[0]} ({most_common[1]} votes)"

# Usage
agents = [
    Agent("You are a conservative decision-maker who values stability."),
    Agent("You are an innovative thinker who embraces change."),
    Agent("You are a pragmatic analyst who considers trade-offs.")
]

for agent in agents:
    await agent.initialize()

consensus_system = ConsensusAgentSystem(agents)
decision = await consensus_system.reach_consensus(
    "Should we adopt a new AI technology for our product?"
)
print(f"Final consensus: {decision}")
```

## Testing Multi-Agent Systems

### Unit Testing Conversations

Test agent conversations in isolation:

```python
import pytest
from unittest.mock import Mock

@pytest.mark.asyncio
async def test_agent_conversation():
    """Test basic agent conversation functionality."""
    
    async with Agent("Agent 1") as agent1:
        async with Agent("Agent 2") as agent2:
            
            # Test conversation creation
            conversation = agent1 | agent2
            assert len(conversation.participants) == 2
            
            # Test message forwarding
            async with conversation:
                agent1.assistant.append("Hello from agent 1")
                
                # Give time for forwarding
                await asyncio.sleep(0.01)
                
                # Check message was forwarded
                user_messages = [m for m in agent2.messages if m.role == "user"]
                assert len(user_messages) == 1
                assert user_messages[0].content == "Hello from agent 1"

@pytest.mark.asyncio
async def test_multi_agent_workflow():
    """Test multi-agent workflow processing."""
    
    agents = [
        Agent("You process input"),
        Agent("You analyze output"),
        Agent("You generate summary")
    ]
    
    # Mock agent responses
    for i, agent in enumerate(agents):
        await agent.initialize()
    
    try:
        # Test workflow
        input_data = "Test input data"
        
        # Process through workflow
        result1 = await agents[0].call(f"Process: {input_data}")
        result2 = await agents[1].call(f"Analyze: {result1.content}")
        result3 = await agents[2].call(f"Summarize: {result2.content}")
        
        # Verify results exist
        assert result1.content
        assert result2.content
        assert result3.content
        
    finally:
        for agent in agents:
            await agent.close()

@pytest.mark.asyncio
async def test_agent_pool_distribution():
    """Test task distribution across agent pool."""
    
    # Create pool
    agents = [Agent(f"Worker {i}") for i in range(3)]
    for agent in agents:
        await agent.initialize()
    
    pool = AgentPool(agents)
    
    # Test round-robin distribution
    tasks = ["Task 1", "Task 2", "Task 3", "Task 4"]
    
    async def process_task(task_index: int, task: str):
        agent = pool[task_index % len(pool)]
        result = await agent.call(task)
        return {
            "task_index": task_index,
            "worker_id": task_index % len(pool),
            "result": result.content
        }
    
    results = await asyncio.gather(
        *[process_task(i, task) for i, task in enumerate(tasks)]
    )
    
    # Verify distribution
    worker_usage = {}
    for result in results:
        worker_id = result["worker_id"]
        worker_usage[worker_id] = worker_usage.get(worker_id, 0) + 1
    
    # Should distribute evenly
    assert len(worker_usage) == min(len(tasks), len(pool))
    
    # Clean up
    for agent in agents:
        await agent.close()
```

### Integration Testing

Test complex multi-agent interactions:

```python
@pytest.mark.asyncio
async def test_hierarchical_system():
    """Test hierarchical agent system integration."""
    
    manager = Agent("You are a project manager.")
    workers = [
        Agent("You are a researcher."),
        Agent("You are an analyst.")
    ]
    
    # Initialize system
    await manager.initialize()
    for worker in workers:
        await worker.initialize()
    
    try:
        # Mock responses for predictable testing
        with manager.mock("Delegate task 1 to researcher, task 2 to analyst"):
            with workers[0].mock("Research completed"):
                with workers[1].mock("Analysis completed"):
                    
                    hierarchy = HierarchicalAgentSystem(manager, workers)
                    result = await hierarchy.delegate_task("Complete project analysis")
                    
                    # Verify system worked
                    assert result is not None
                    assert len(result) > 0
                    
    finally:
        await manager.close()
        for worker in workers:
            await worker.close()

@pytest.mark.asyncio
async def test_consensus_system():
    """Test consensus mechanism."""
    
    agents = [Agent(f"Agent {i}") for i in range(3)]
    
    for agent in agents:
        await agent.initialize()
    
    try:
        # Mock consensus responses
        responses = ["Yes, we should proceed", "Yes, agreed", "Yes, I concur"]
        
        for i, agent in enumerate(agents):
            agent.mock(responses[i]).__enter__()
        
        consensus_system = ConsensusAgentSystem(agents)
        result = await consensus_system.reach_consensus("Should we proceed?", max_rounds=1)
        
        # Verify consensus reached
        assert "consensus" in result.lower() or "majority" in result.lower()
        
    finally:
        for agent in agents:
            await agent.close()
```

## Performance and Optimization

### Efficient Agent Management

Optimize multi-agent systems for production use:

```python
class OptimizedAgentManager:
    """Optimized manager for large-scale multi-agent systems."""
    
    def __init__(self, max_agents: int = 10):
        self.max_agents = max_agents
        self.agent_pool = []
        self.available_agents = asyncio.Queue()
        self.busy_agents = set()
        self.performance_metrics = {}
    
    async def initialize_pool(self, agent_configs: list[dict]):
        """Initialize agent pool with configurations."""
        
        for i, config in enumerate(agent_configs[:self.max_agents]):
            agent = Agent(**config)
            await agent.initialize()
            self.agent_pool.append(agent)
            await self.available_agents.put(agent)
        
        print(f"Initialized pool with {len(self.agent_pool)} agents")
    
    async def get_agent(self) -> Agent:
        """Get an available agent from the pool."""
        agent = await self.available_agents.get()
        self.busy_agents.add(agent)
        return agent
    
    async def return_agent(self, agent: Agent):
        """Return agent to the available pool."""
        self.busy_agents.discard(agent)
        await self.available_agents.put(agent)
    
    async def process_with_pooling(self, task: str) -> str:
        """Process task using agent pooling."""
        
        agent = await self.get_agent()
        start_time = time.time()
        
        try:
            result = await agent.call(task)
            
            # Track performance
            duration = time.time() - start_time
            agent_id = id(agent)
            if agent_id not in self.performance_metrics:
                self.performance_metrics[agent_id] = []
            self.performance_metrics[agent_id].append(duration)
            
            return result.content
            
        finally:
            await self.return_agent(agent)
    
    async def batch_process(self, tasks: list[str], max_concurrent: int = 5) -> list[str]:
        """Process tasks in batches to control concurrency."""
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_limit(task: str):
            async with semaphore:
                return await self.process_with_pooling(task)
        
        results = await asyncio.gather(
            *[process_with_limit(task) for task in tasks],
            return_exceptions=True
        )
        
        return [r for r in results if not isinstance(r, Exception)]
    
    async def cleanup(self):
        """Clean up agent pool."""
        for agent in self.agent_pool:
            await agent.close()

# Usage
manager = OptimizedAgentManager(max_agents=5)

await manager.initialize_pool([
    {"system_prompt": "You are a task processor."},
    {"system_prompt": "You are a data analyzer."},
    {"system_prompt": "You are a content generator."},
])

# Process large batch efficiently
large_task_list = [f"Process item {i}" for i in range(100)]
results = await manager.batch_process(large_task_list, max_concurrent=3)

print(f"Processed {len(results)} tasks")
await manager.cleanup()
```

## Best Practices

### Multi-Agent Architecture Guidelines

- **Agent Specialization** - Give each agent a focused, specialized role
- **Clear Communication** - Use structured message formats between agents
- **Resource Management** - Properly initialize and clean up agent resources
- **Error Handling** - Implement robust error handling for agent failures
- **Performance Monitoring** - Track agent performance and resource usage
- **Scalability** - Design systems to scale with agent count and task volume

### Production Recommendations

```python
# Production-ready multi-agent system pattern
class ProductionMultiAgentSystem:
    """Production-ready multi-agent system with monitoring and error handling."""
    
    def __init__(self, config: dict):
        self.config = config
        self.agents = {}
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_response_time": 0,
            "agent_health": {}
        }
        self.logger = logging.getLogger(__name__)
    
    async def health_check_agent(self, agent: Agent) -> bool:
        """Check if an agent is healthy and responsive."""
        try:
            health_check = await agent.call("Respond with 'OK' if you're working properly.")
            return "OK" in health_check.content
        except Exception as e:
            self.logger.error(f"Agent health check failed: {e}")
            return False
    
    async def process_with_monitoring(self, agent: Agent, task: str) -> str:
        """Process task with comprehensive monitoring."""
        start_time = time.time()
        agent_id = id(agent)
        
        try:
            # Check agent health before processing
            if not await self.health_check_agent(agent):
                raise RuntimeError(f"Agent {agent_id} failed health check")
            
            # Process task
            result = await agent.call(task)
            
            # Update metrics
            duration = time.time() - start_time
            self.metrics["tasks_completed"] += 1
            self.metrics["avg_response_time"] = (
                (self.metrics["avg_response_time"] * (self.metrics["tasks_completed"] - 1) + duration)
                / self.metrics["tasks_completed"]
            )
            
            self.logger.info(f"Task completed in {duration:.2f}s")
            return result.content
            
        except Exception as e:
            self.metrics["tasks_failed"] += 1
            self.logger.error(f"Task failed: {e}")
            raise
    
    def get_metrics(self) -> dict:
        """Get system performance metrics."""
        return self.metrics.copy()
```

## Complete Examples

Here's a comprehensive example demonstrating advanced multi-agent coordination:

```python
--8<-- "examples/multi-agent/comprehensive_orchestration.py"
```

## Next Steps

- **[Resources](./resources.md)** - Learn about stateful resources shared across agents
- **[Human-in-the-Loop](./human-in-the-loop.md)** - Add human oversight to multi-agent systems
- **[Events](../core/events.md)** - Use events for advanced agent coordination
- **[Tasks](./tasks.md)** - Manage background tasks across multiple agents
- **[Components](../extensibility/components.md)** - Build reusable multi-agent components
