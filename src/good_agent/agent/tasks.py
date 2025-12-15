"""Task management utilities for :class:`~good_agent.agent.core.Agent`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:  # pragma: no cover - import cycles guarded at type-check time
    from good_agent.agent.core import Agent
    from good_agent.core.components import AgentComponent

T = TypeVar("T")

logger = logging.getLogger(__name__)


class AgentTaskManager:
    """Manages background tasks created via :meth:`Agent.tasks.create`."""

    def __init__(self, agent: Agent):
        self.agent = agent
        self._managed_tasks: dict[asyncio.Task[Any], dict[str, Any]] = {}
        self._task_stats: dict[str, Any] = {
            "total": 0,
            "pending": 0,
            "completed": 0,
            "failed": 0,
        }

    @property
    def managed_tasks(self) -> MappingProxyType[asyncio.Task[Any], dict[str, Any]]:
        """Read-only view of currently tracked tasks."""

        return MappingProxyType(self._managed_tasks)

    @property
    def count(self) -> int:
        """Number of active managed tasks."""

        return len(self._managed_tasks)

    def create(
        self,
        coro: Coroutine[Any, Any, T],
        *,
        name: str | None = None,
        component: AgentComponent | str | None = None,
        wait_on_ready: bool = True,
        cleanup_callback: Callable[[asyncio.Task[T]], None] | None = None,
    ) -> asyncio.Task[T]:
        """Create and track an asyncio task tied to this agent."""

        task = asyncio.create_task(coro, name=name)

        if component is None:
            component_name = None
        elif isinstance(component, str):
            component_name = component
        else:
            component_name = component.__class__.__name__

        try:
            created_at = asyncio.get_running_loop().time()
        except RuntimeError:  # pragma: no cover - fallback for legacy contexts
            created_at = asyncio.get_event_loop().time()

        task_info = {
            "component": component_name,
            "wait_on_ready": wait_on_ready,
            "cleanup_callback": cleanup_callback,
            "created_at": created_at,
        }
        self._managed_tasks[task] = task_info

        self._task_stats["total"] += 1
        self._task_stats["pending"] += 1

        def _cleanup(completed: asyncio.Task[T]) -> None:
            if completed not in self._managed_tasks:
                return

            info = self._managed_tasks.pop(completed)
            self._task_stats["pending"] -= 1

            if completed.cancelled():
                pass
            elif completed.exception():
                self._task_stats["failed"] += 1
                logger.warning("Task %s failed: %s", completed.get_name(), completed.exception())
            else:
                self._task_stats["completed"] += 1

            callback = info.get("cleanup_callback")
            if callback:
                try:
                    callback(completed)
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Task cleanup callback failed: %s", exc)

        task.add_done_callback(_cleanup)
        return task

    def stats(self) -> dict[str, Any]:
        """Return task statistics with component breakdowns."""

        stats = dict(self._task_stats)
        by_component: dict[str, int] = {}
        by_wait_on_ready: dict[str, int] = {"true": 0, "false": 0}

        for info in self._managed_tasks.values():
            component = info.get("component", "unknown")
            by_component[component] = by_component.get(component, 0) + 1

            wait_key = "true" if info.get("wait_on_ready", True) else "false"
            by_wait_on_ready[wait_key] += 1

        stats["by_component"] = by_component
        stats["by_wait_on_ready"] = by_wait_on_ready
        return stats

    def waitable_tasks(self) -> list[asyncio.Task[Any]]:
        """List of tasks that should block :meth:`Agent.initialize`."""

        return [
            task for task, info in self._managed_tasks.items() if info.get("wait_on_ready", True)
        ]

    async def wait_for_all(self, timeout: float | None = None) -> None:
        """Wait for all tracked tasks to finish."""

        if not self._managed_tasks:
            return

        await asyncio.wait_for(
            asyncio.gather(*self._managed_tasks.keys(), return_exceptions=True),
            timeout,
        )

    async def cancel_all(self, timeout: float = 1.0) -> None:
        """Cancel all tracked tasks and wait for termination."""

        if not self._managed_tasks:
            return

        tasks = list(self._managed_tasks.keys())
        for task in tasks:
            if not task.done():
                task.cancel()

        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except TimeoutError:
            logger.warning("Some managed tasks did not cancel within %s seconds", timeout)


__all__ = ["AgentTaskManager"]
