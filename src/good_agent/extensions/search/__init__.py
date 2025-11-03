"""
AgentSearch Component - Discovery operations across multiple data sources.

This module provides a unified search interface that intelligently routes
queries to appropriate providers based on capabilities and requirements.
"""

from .component import AgentSearch
from .models import (
    DataDomain,
    MediaItem,
    OperationType,
    Platform,
    ProviderCapability,
    SearchConstraints,
    SearchQuery,
    SearchResult,
    UserResult,
)
from .providers import BaseSearchProvider, SearchProvider, SearchProviderRegistry

__all__ = [
    # Component
    "AgentSearch",
    # Providers
    "BaseSearchProvider",
    "SearchProvider",
    "SearchProviderRegistry",
    # Data Models
    "SearchResult",
    "UserResult",
    "MediaItem",
    # Query Models
    "SearchQuery",
    "SearchConstraints",
    # Enums
    "DataDomain",
    "OperationType",
    "Platform",
    # Capabilities
    "ProviderCapability",
]
