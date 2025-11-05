import asyncio
import logging

from good_agent.utilities.observable import current_test_nodeid

logger = logging.getLogger(__name__)


def pytest_configure(config):
    """Configure custom warning handling"""
    # Patch asyncio to add more context to task destruction warnings
    original_task_del = (
        asyncio.Task.__del__ if hasattr(asyncio.Task, "__del__") else None
    )

    def enhanced_task_del(self):
        if not self.done() and not self._log_destroy_pending:
            # Get current test context
            test_info = current_test_nodeid.get() or "unknown test"

            # Log with more context
            logger.error(
                f"Task '{self.get_name()}' destroyed while pending in test: {test_info}\n"
                f"Task was created at: {getattr(self, '_source_traceback', 'unknown')}"
            )

        if original_task_del:
            original_task_del(self)

    # Only patch if not already patched
    if not hasattr(asyncio.Task.__del__, "_patched"):
        asyncio.Task.__del__ = enhanced_task_del
        asyncio.Task.__del__._patched = True


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
