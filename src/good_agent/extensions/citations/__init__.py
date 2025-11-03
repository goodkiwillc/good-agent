"""
Citation management system for the goodintel_agent.

This package provides a complete citation management system that:
- Tracks and deduplicates URLs across conversations
- Supports multiple citation formats (markdown, LLM-optimized, XML)
- Transforms citations between formats for different contexts
- Maintains both local (per-message) and global citation indices
"""

from .formats import (
    CitationExtractor,
    CitationFormat,
    CitationMatch,
    CitationPatterns,
    CitationTransformer,
)
from .index import CitationIndex
from .manager import CitationManager

__all__ = [
    # Manager
    "CitationManager",
    # Index
    "CitationIndex",
    # Formats
    "CitationFormat",
    "CitationMatch",
    "CitationTransformer",
    "CitationExtractor",
    "CitationPatterns",
]
