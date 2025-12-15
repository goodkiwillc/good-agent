import asyncio
import logging
from collections.abc import Callable
from typing import Any, cast

from good_agent.core.event_router import current_test_nodeid

logger = logging.getLogger(__name__)


TaskDestructor = Callable[[asyncio.Task[Any]], None]


def _is_patched(func: object | None) -> bool:
    return bool(getattr(func, "_patched", False))


def pytest_configure(config):
    """Configure custom warning handling"""
    # Patch asyncio to add more context to task destruction warnings
    original_task_del = getattr(asyncio.Task, "__del__", None)
    task_destructor: TaskDestructor | None = (
        cast(TaskDestructor, original_task_del) if callable(original_task_del) else None
    )

    def enhanced_task_del(self: asyncio.Task[Any]) -> None:
        if not self.done() and not getattr(self, "_log_destroy_pending", False):
            # Get current test context
            test_info = current_test_nodeid.get() or "unknown test"

            # Log with more context
            logger.error(
                "Task '%s' destroyed while pending in test: %s\nTask was created at: %s",
                self.get_name(),
                test_info,
                getattr(self, "_source_traceback", "unknown"),
            )

        if task_destructor is not None:
            task_destructor(self)

    # Only patch if not already patched
    if not _is_patched(task_destructor):
        asyncio.Task.__del__ = enhanced_task_del
        enhanced_task_del._patched = True


def pytest_runtest_setup(item):
    """Track current test"""
    current_test_nodeid.set(item.nodeid)


def pytest_runtest_teardown(item):
    """Clear test tracking"""
    current_test_nodeid.set(None)

    # Force garbage collection to catch pending tasks
    import gc

    gc.collect()


def pytest_warning_recorded(warning_message, when, nodeid, location):
    """Capture warnings about coroutines and tasks"""
    if "coroutine" in str(warning_message.message) or "Task was destroyed" in str(
        warning_message.message
    ):
        logger.warning(f"Warning in {nodeid}: {warning_message.message}")
