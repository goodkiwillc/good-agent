from __future__ import annotations

import logging

DEFAULT_FORMAT = "%(levelname)s %(name)s - %(message)s"


def configure_library_logging(level: int = logging.INFO, format: str = DEFAULT_FORMAT, **kwargs):
    """Configure a basic logging setup for the library if none is present."""

    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    logging.basicConfig(level=level, format=format, **kwargs)
