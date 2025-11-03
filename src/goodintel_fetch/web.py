"""
Lightweight test stub for goodintel_fetch.web used in WebFetcher tests.

Provides minimal Request and ExtractedContent classes to satisfy imports
and type usage in tests without requiring the external dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Request:
    url: str


@dataclass
class ExtractedContent:
    request: Request
    url: str
    status_code: int
    title: str | None = None
    main: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class Response:  # very small placeholder for TYPE_CHECKING
    pass


__all__ = ["Request", "ExtractedContent", "Response"]
