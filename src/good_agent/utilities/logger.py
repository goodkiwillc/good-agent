from __future__ import annotations

import logging


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
    try:
        from prefect import get_run_logger  # type: ignore[import-not-found]

        return get_run_logger()
    except Exception:
        # Fallback to standard logging logger if get_run_logger fails
        return logging.getLogger(name or __name__)
