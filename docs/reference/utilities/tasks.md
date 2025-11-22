# Task Management

!!! warning "⚠️ Under Active Development"
    This project is in early-stage development. APIs may change, break, or be completely rewritten without notice. Use at your own risk in production environments.

Good Agent provides comprehensive task management capabilities for both background asyncio tasks and conceptual todo list management. The system includes lifecycle management, monitoring, and cleanup mechanisms for robust task orchestration.

## Background Task Management

### AgentTaskManager

The `AgentTaskManager` handles creation, tracking, and cleanup of background asyncio tasks within agent contexts:

--8<-- "src/good_agent/agent/tasks.py:16:33"

### Creating Background Tasks

Create and manage background tasks using the agent's task manager:

```python
from good_agent import Agent
import asyncio

async with Agent("Task coordinator") as agent:
    
    # Basic task creation
    task = agent.tasks.create(
        process_data_async(),
        name="data_processor"
    )
    
    # Wait for result
    result = await task
```

### Task Configuration Options

Control task behavior with comprehensive configuration:

--8<-- "tests/unit/agent/test_agent_create_task.py:16:43"

**Key Parameters:**

- **`name`**: Optional task name for identification and debugging
- **`component`**: Associate task with specific `AgentComponent` for tracking
- **`wait_on_ready`**: Whether `agent.initialize()` should wait for this task
- **`cleanup_callback`**: Custom function to call when task completes

### Task Lifecycle and States

Tasks progress through a defined lifecycle with automatic cleanup:

```python
async with Agent("Lifecycle demo") as agent:
    
    async def long_running_process():
        """Example long-running task"""
        await asyncio.sleep(1.0)
        return "Process completed"
    
    # Create task - moves to 'pending'
    task = agent.tasks.create(
        long_running_process(),
        name="processor",
        wait_on_ready=True  # Block initialization until complete
    )
    
    # Task is now tracked in agent.tasks.managed_tasks
    print(f"Active tasks: {agent.tasks.count}")
    
    # Automatic cleanup when task completes
    result = await task  # Returns "Process completed"
    
    # Task automatically removed from managed_tasks
    await asyncio.sleep(0.01)  # Allow cleanup
    print(f"Active tasks: {agent.tasks.count}")  # Should be 0
```

### Task Statistics and Monitoring

Monitor task performance with detailed statistics:

--8<-- "tests/unit/agent/test_agent_create_task.py:207:222"

**Statistics Include:**

- **Total tasks created** (cumulative counter)
- **Pending tasks** (currently running)
- **Completed tasks** (successful completions)
- **Failed tasks** (exceptions or cancellations)
- **Breakdown by component** (which components created tasks)
- **Breakdown by wait_on_ready** (blocking vs non-blocking tasks)

### Component-Specific Tasks

Associate tasks with components for better organization:

```python
from good_agent import AgentComponent
import asyncio

class DataProcessor(AgentComponent):
    def __init__(self):
        super().__init__()
        self.processed_items = []
    
    async def process_batch(self, items: list[str]):
        """Process items in background"""
        
        async def process_item(item: str):
            await asyncio.sleep(0.1)  # Simulate processing
            self.processed_items.append(f"processed_{item}")
        
        # Create tasks associated with this component
        tasks = []
        for item in items:
            task = self.agent.tasks.create(
                process_item(item),
                name=f"process_{item}",
                component=self,  # Associate with component
                wait_on_ready=False  # Don't block initialization
            )
            tasks.append(task)
        
        # Wait for all processing to complete
        await asyncio.gather(*tasks)
        return self.processed_items

# Usage
async with Agent("Data processor", extensions=[DataProcessor()]) as agent:
    processor = agent[DataProcessor]
    
    # Process items in background
    results = await processor.process_batch(["item1", "item2", "item3"])
    
    # Check component-specific statistics
    stats = agent.tasks.stats()
    print(f"DataProcessor created: {stats['by_component']['DataProcessor']} tasks")
```

### Task Synchronization

Coordinate multiple tasks with synchronization utilities:

```python
async with Agent("Coordinator") as agent:
    
    results = []
    
    async def worker_task(worker_id: str, delay: float):
        await asyncio.sleep(delay)
        results.append(f"worker_{worker_id}_done")
        return worker_id
    
    # Create multiple worker tasks
    tasks = [
        agent.tasks.create(worker_task("A", 0.1)),
        agent.tasks.create(worker_task("B", 0.2)),
        agent.tasks.create(worker_task("C", 0.15))
    ]
    
    # Wait for all tasks to complete
    await agent.tasks.wait_for_all(timeout=5.0)
    
    # All workers should be done
    assert len(results) == 3
    assert set(results) == {"worker_A_done", "worker_B_done", "worker_C_done"}
```

### Error Handling and Recovery

Handle task failures gracefully with built-in error management:

--8<-- "tests/unit/agent/test_agent_create_task.py:113:130"

**Error Handling Features:**

- **Automatic cleanup** on task failure or cancellation
- **Exception logging** without crashing the agent
- **Custom cleanup callbacks** for resource cleanup
- **Graceful cancellation** on agent shutdown

### Advanced Task Patterns

#### Producer-Consumer Pattern

```python
import asyncio
from asyncio import Queue

async with Agent("Producer-Consumer") as agent:
    
    work_queue: Queue[str] = Queue()
    results: Queue[str] = Queue()
    
    async def producer():
        """Produce work items"""
        for i in range(10):
            await work_queue.put(f"item_{i}")
            await asyncio.sleep(0.01)
        await work_queue.put(None)  # Signal completion
    
    async def consumer(consumer_id: str):
        """Consume and process work items"""
        while True:
            item = await work_queue.get()
            if item is None:
                work_queue.task_done()
                break
            
            # Process item
            await asyncio.sleep(0.1)
            await results.put(f"processed_{item}_by_{consumer_id}")
            work_queue.task_done()
    
    # Create producer and consumer tasks
    producer_task = agent.tasks.create(producer(), name="producer")
    consumer_tasks = [
        agent.tasks.create(consumer(f"worker_{i}"), name=f"consumer_{i}")
        for i in range(3)
    ]
    
    # Wait for producer to finish
    await producer_task
    
    # Wait for all work to be processed
    await work_queue.join()
    
    # Stop consumers
    for _ in consumer_tasks:
        await work_queue.put(None)
    
    # Wait for consumers to stop
    await agent.tasks.wait_for_all()
    
    # Collect results
    processed_items = []
    while not results.empty():
        processed_items.append(await results.get())
```

#### Task Pools with Rate Limiting

```python
import asyncio
from typing import AsyncGenerator

class RateLimitedTaskPool:
    def __init__(self, agent: Agent, max_concurrent: int = 5, rate_limit: float = 0.1):
        self.agent = agent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limit = rate_limit
        self.last_task_time = 0.0
    
    async def submit_task(self, coro, name: str | None = None):
        """Submit task with rate limiting and concurrency control"""
        
        async def rate_limited_task():
            async with self.semaphore:
                # Rate limiting
                current_time = asyncio.get_running_loop().time()
                time_since_last = current_time - self.last_task_time
                if time_since_last < self.rate_limit:
                    await asyncio.sleep(self.rate_limit - time_since_last)
                
                self.last_task_time = asyncio.get_running_loop().time()
                return await coro
        
        return self.agent.tasks.create(rate_limited_task(), name=name)

# Usage
async with Agent("Rate limited processor") as agent:
    
    pool = RateLimitedTaskPool(agent, max_concurrent=3, rate_limit=0.2)
    
    async def api_call(item: str):
        """Simulate API call that needs rate limiting"""
        await asyncio.sleep(0.1)
        return f"api_result_for_{item}"
    
    # Submit many tasks - pool manages concurrency and rate
    tasks = []
    for i in range(20):
        task = await pool.submit_task(
            api_call(f"item_{i}"), 
            name=f"api_call_{i}"
        )
        tasks.append(task)
    
    # Wait for all API calls to complete
    results = await asyncio.gather(*tasks)
    print(f"Processed {len(results)} items with rate limiting")
```

## Todo List Management

### TaskManager Component

The `TaskManager` component provides structured todo list functionality for organizing conceptual tasks:

--8<-- "src/good_agent/extensions/task_manager.py:29:48"

### Creating and Managing Todo Lists

```python
from good_agent import Agent
from good_agent.extensions.task_manager import TaskManager

async with Agent("Project manager", extensions=[TaskManager()]) as agent:
    
    task_manager = agent[TaskManager]
    
    # Create todo lists
    project_list = task_manager.create_list(
        name="Project Alpha",
        items=["Setup repository", "Design database", "Implement API"]
    )
    
    personal_list = task_manager.create_list(
        name="Personal Tasks",
        items=["Review code", "Update documentation"]
    )
    
    # Add new items
    task_manager.add_item("Project Alpha", "Write tests")
    task_manager.add_item("Personal Tasks", "Schedule team meeting")
    
    # Mark items complete
    task_manager.complete_item("Project Alpha", item_text="Setup repository")
    task_manager.complete_item("Personal Tasks", item_index=0)  # "Review code"
    
    # View lists
    project_status = task_manager.view_list("Project Alpha")
    print(project_status)
```

### Agent Tool Integration

Todo lists are automatically exposed as agent tools:

--8<-- "src/good_agent/extensions/task_manager.py:91:105"

**Available Tools:**

- **`create_list`**: Create new todo lists
- **`add_item`**: Add items to existing lists  
- **`complete_item`**: Mark items as complete
- **`view_list`**: Display list contents

### System Message Integration

Todo lists automatically appear in the agent's system context:

--8<-- "src/good_agent/extensions/task_manager.py:107:126"

This makes todo lists visible to the agent during all interactions, enabling natural task management through conversation.

### Todo List Templates and Rendering

Todo lists use a structured template for consistent display:

--8<-- "src/good_agent/extensions/task_manager.py:13:26"

The rendered output provides clear visual feedback:

```text
# To-Do List: Project Alpha
- [x] Setup repository
- [ ] Design database  
- [ ] Implement API
- [ ] Write tests

# To-Do List: Personal Tasks
- [x] Review code
- [ ] Update documentation
- [ ] Schedule team meeting
```

### Advanced Todo Management

#### Programmatic Todo Operations

```python
from good_agent.extensions.task_manager import TaskManager, ToDoItem

# Create todo manager
task_manager = TaskManager()

# Bulk create items
project_items = [
    ToDoItem(item="Research requirements", complete=True),
    ToDoItem(item="Create wireframes", complete=False),
    ToDoItem(item="Setup development environment", complete=True),
    ToDoItem(item="Implement core features", complete=False)
]

# Create list with predefined items
project_list = task_manager.create_list("Development Sprint", [])
project_list.items = project_items

# Filter and analyze
completed_items = [item for item in project_list.items if item.complete]
pending_items = [item for item in project_list.items if not item.complete]

print(f"Progress: {len(completed_items)}/{len(project_list.items)} complete")
```

#### Dynamic Todo Management

```python
async with Agent("Dynamic task manager", extensions=[TaskManager()]) as agent:
    
    task_manager = agent[TaskManager]
    
    # Agent can manage todos through conversation
    response = await agent.call(
        "Create a todo list for today and add three important tasks"
    )
    
    # Agent can check progress
    status_response = await agent.call(
        "Show me the current status of all todo lists"
    )
    
    # Agent can prioritize and complete tasks
    completion_response = await agent.call(
        "Mark the first task as complete and add a high-priority task"
    )
```

## Integration Patterns

### Combining Background Tasks with Todo Management

```python
from good_agent import Agent, AgentComponent
from good_agent.extensions import TaskManager
import asyncio

class ProjectManager(AgentComponent):
    async def execute_project_tasks(self):
        """Execute tasks from todo lists as background jobs"""
        
        task_manager = self.agent[TaskManager]
        
        for list_name, todo_list in task_manager.lists.items():
            for i, item in enumerate(todo_list.items):
                if not item.complete:
                    # Create background task for each pending item
                    task = self.agent.tasks.create(
                        self.process_todo_item(list_name, i, item.item),
                        name=f"execute_{list_name}_{i}",
                        component=self
                    )
    
    async def process_todo_item(self, list_name: str, item_index: int, item_text: str):
        """Process a todo item as a background task"""
        
        try:
            # Simulate task processing
            await asyncio.sleep(1.0)
            
            # Mark as complete
            task_manager = self.agent[TaskManager]
            result = task_manager.complete_item(list_name, item_index=item_index)
            
            return f"Completed: {item_text}"
            
        except Exception as e:
            return f"Failed: {item_text} - {e}"

# Usage
async with Agent(
    "Project executor", 
    extensions=[TaskManager(), ProjectManager()]
) as agent:
    
    # Create project tasks
    await agent.call("Create a project list with 5 development tasks")
    
    # Execute all pending tasks in background
    project_manager = agent[ProjectManager]
    await project_manager.execute_project_tasks()
    
    # Wait for all background tasks to complete
    await agent.tasks.wait_for_all()
    
    # Check final status
    await agent.call("Show me the updated project status")
```

### Task Monitoring and Alerts

```python
import asyncio
from datetime import datetime, timedelta

class TaskMonitor(AgentComponent):
    def __init__(self, alert_threshold: float = 5.0):
        super().__init__()
        self.alert_threshold = alert_threshold
        self.monitoring = False
    
    async def start_monitoring(self):
        """Start monitoring long-running tasks"""
        self.monitoring = True
        
        monitor_task = self.agent.tasks.create(
            self.monitor_tasks(),
            name="task_monitor",
            component=self,
            wait_on_ready=False
        )
        
        return monitor_task
    
    async def monitor_tasks(self):
        """Monitor tasks for performance issues"""
        while self.monitoring:
            await asyncio.sleep(1.0)  # Check every second
            
            current_time = asyncio.get_running_loop().time()
            
            for task, info in self.agent.tasks.managed_tasks.items():
                task_age = current_time - info['created_at']
                
                if task_age > self.alert_threshold and not task.done():
                    # Alert on long-running tasks
                    task_name = task.get_name() or "unnamed"
                    print(f"⚠️ Task '{task_name}' running for {task_age:.1f}s")
                    
                    # Could also emit events or log warnings
                    await self.agent.apply("task:long_running", {
                        "task_name": task_name,
                        "duration": task_age
                    })
    
    def stop_monitoring(self):
        """Stop task monitoring"""
        self.monitoring = False

# Usage
async with Agent(
    "Monitored agent", 
    extensions=[TaskMonitor(alert_threshold=2.0)]
) as agent:
    
    monitor = agent[TaskMonitor]
    
    # Start monitoring
    await monitor.start_monitoring()
    
    # Create some long-running tasks
    slow_task = agent.tasks.create(asyncio.sleep(3.0), name="slow_task")
    fast_task = agent.tasks.create(asyncio.sleep(0.5), name="fast_task")
    
    # Monitor will alert on slow_task
    await asyncio.sleep(2.5)  # Let monitor run
    
    # Clean up
    monitor.stop_monitoring()
    await agent.tasks.wait_for_all()
```

## Testing Task Management

### Testing Background Tasks

```python
import pytest
import asyncio
from good_agent import Agent

@pytest.mark.asyncio
async def test_background_task_completion():
    """Test that background tasks complete successfully"""
    
    results = []
    
    async def test_task(value: str):
        await asyncio.sleep(0.01)
        results.append(value)
        return value
    
    async with Agent("Test agent") as agent:
        # Create multiple tasks
        tasks = [
            agent.tasks.create(test_task(f"task_{i}"))
            for i in range(5)
        ]
        
        # Wait for all tasks
        await asyncio.gather(*tasks)
        
        # Verify all tasks completed
        assert len(results) == 5
        assert set(results) == {f"task_{i}" for i in range(5)}

@pytest.mark.asyncio
async def test_task_cleanup():
    """Test that tasks are properly cleaned up"""
    
    async with Agent("Test agent") as agent:
        initial_count = agent.tasks.count
        
        # Create task
        task = agent.tasks.create(asyncio.sleep(0.01))
        assert agent.tasks.count == initial_count + 1
        
        # Wait for completion
        await task
        await asyncio.sleep(0.01)  # Allow cleanup
        
        # Verify cleanup
        assert agent.tasks.count == initial_count
```

### Testing Todo Management

```python
import pytest
from good_agent import Agent
from good_agent.extensions import TaskManager

@pytest.mark.asyncio
async def test_todo_operations():
    """Test todo list operations"""
    
    async with Agent("Test", extensions=[TaskManager()]) as agent:
        task_manager = agent[TaskManager]
        
        # Create list
        todo_list = task_manager.create_list("Test List", ["task1", "task2"])
        assert len(todo_list.items) == 2
        assert not todo_list.items[0].complete
        
        # Add item
        task_manager.add_item("Test List", "task3")
        assert len(todo_list.items) == 3
        
        # Complete item
        task_manager.complete_item("Test List", item_index=0)
        assert todo_list.items[0].complete
        
        # View list
        viewed = task_manager.view_list("Test List")
        assert viewed.name == "Test List"
        assert len(viewed.items) == 3

@pytest.mark.asyncio 
async def test_todo_agent_integration():
    """Test todo integration with agent conversation"""
    
    async with Agent("Test", extensions=[TaskManager()]) as agent:
        # Create list through agent conversation
        response = await agent.call("Create a todo list called 'Daily Tasks' with 2 items")
        
        # Verify list was created
        task_manager = agent[TaskManager]
        assert "Daily Tasks" in task_manager.lists
        
        # Check agent can see todos in system context
        assert "todo_lists" in agent.context
```

## Best Practices

### 1. Use Appropriate wait_on_ready Settings

```python
# Block initialization for critical setup tasks
setup_task = agent.tasks.create(
    initialize_database(),
    wait_on_ready=True  # Agent won't be ready until this completes
)

# Don't block for background monitoring
monitor_task = agent.tasks.create(
    monitor_system_health(),
    wait_on_ready=False  # Can run in background
)
```

### 2. Handle Task Failures Gracefully

```python
async def robust_task():
    try:
        result = await risky_operation()
        return result
    except Exception as e:
        logger.error(f"Task failed: {e}")
        # Return default or signal failure appropriately
        return None

task = agent.tasks.create(robust_task())
```

### 3. Use Cleanup Callbacks for Resources

```python
def cleanup_resources(task: asyncio.Task):
    """Clean up resources when task completes"""
    if hasattr(task, '_custom_resources'):
        for resource in task._custom_resources:
            resource.close()

task = agent.tasks.create(
    process_with_resources(),
    cleanup_callback=cleanup_resources
)
```

### 4. Monitor Long-Running Tasks

```python
# Set reasonable timeouts
try:
    await agent.tasks.wait_for_all(timeout=30.0)
except asyncio.TimeoutError:
    logger.warning("Some tasks did not complete within timeout")
    # Handle timeout appropriately
```

### 5. Organize Tasks by Component

```python
class DataProcessor(AgentComponent):
    async def process_batch(self, items):
        tasks = []
        for item in items:
            task = self.agent.tasks.create(
                self.process_item(item),
                component=self,  # Associate with component
                name=f"process_{item['id']}"
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)
```

Task management in Good Agent provides both low-level control over background execution and high-level organization of conceptual work, enabling robust and well-organized agent implementations.
