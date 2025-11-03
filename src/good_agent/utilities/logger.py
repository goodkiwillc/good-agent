"""
CONTEXT: Logging utility with Prefect integration and fallback support.
ROLE: Provide consistent logging across the library with automatic Prefect context
      detection and standard logging fallback for non-Prefect environments.
DEPENDENCIES: prefect for run context, Python's standard logging module.
ARCHITECTURE: Simple factory function that detects environment and returns appropriate logger.
KEY EXPORTS: get_logger
USAGE PATTERNS:
  1) Use get_logger(__name__) in any module for environment-appropriate logging
  2) Works seamlessly in Prefect flows/tasks and standalone execution
  3) Provides consistent interface regardless of logging backend
"""

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
        from prefect import get_run_logger

        return get_run_logger()
    except Exception:
        # Fallback to standard logging logger if get_run_logger fails
        return logging.getLogger(name or __name__)
