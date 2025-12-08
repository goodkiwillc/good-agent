from __future__ import annotations

import logging
import warnings


def get_logger(name: str | None = None):
    """
    Get appropriate logger based on execution context.

    RETURNS:
        Logger instance - Prefect run logger in flow context, standard logger otherwise.

    NOTES:
        - Automatically detects Prefect execution context
        - Falls back to standard logging for standalone execution
        - Provides consistent logging interface across environments
    """
    warnings.warn(
        "get_logger is deprecated; use logging.getLogger directly instead",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        from prefect import get_run_logger  # type: ignore[import-not-found]

        return get_run_logger()
    except Exception:
        # Fallback to standard logging logger if get_run_logger fails
        return logging.getLogger(name or __name__)


DEFAULT_FORMAT = "%(levelname)s %(name)s - %(message)s"


def configure_library_logging(level: int = logging.INFO, format: str = DEFAULT_FORMAT, **kwargs):
    """Configure a basic logging setup for the library if none is present."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(level=level, format=format, **kwargs)
