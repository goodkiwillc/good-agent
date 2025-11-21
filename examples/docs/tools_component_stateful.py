"""Stateful components that maintain state across tool calls."""

import asyncio

from good_agent import Agent, AgentComponent, tool


class TaskManager(AgentComponent):
    """Task management component with persistent state."""

    def __init__(self):
        super().__init__()
        self.tasks: list[str] = []
        self.completed: list[str] = []

    @tool
    def create_task(self, task: str) -> str:
        """Create a new task."""
        self.tasks.append(task)
        return f"Created task: {task}"

    @tool
    def complete_task(self, task: str) -> str:
        """Mark a task as completed."""
        if task in self.tasks:
            self.tasks.remove(task)
            self.completed.append(task)
            return f"Completed task: {task}"
        return f"Task not found: {task}"

    @tool
    def list_tasks(self) -> dict[str, list[str]]:
        """List all tasks."""
        return {"pending": self.tasks, "completed": self.completed}


async def main():
    """Demonstrate stateful component usage."""
    # Component tools integrate with agent state
    task_mgr = TaskManager()
    async with Agent("Task assistant", extensions=[task_mgr]) as agent:
        agent.append("Create a task to 'Review documentation' and then complete it")
        response = await agent.call()
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
