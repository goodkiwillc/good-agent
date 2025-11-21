"""Tools with complex Pydantic models."""

import asyncio
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from good_agent import Agent, tool


class TaskModel(BaseModel):
    """Task data model."""

    title: str
    description: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: datetime | None = None
    tags: list[str] = []


@tool
async def create_complex_task(task: TaskModel) -> dict:
    """Create a task using a complex model."""
    return {"created": True, "task_id": "task_456", "task": task.model_dump()}


async def main():
    """Demonstrate complex type support."""
    # LLM receives full schema for TaskModel
    async with Agent("Task manager", tools=[create_complex_task]) as agent:
        await agent.call(
            """
            Create a high-priority task titled 'Review documentation'
            due tomorrow with tags 'urgent' and 'docs'
        """
        )


if __name__ == "__main__":
    asyncio.run(main())
