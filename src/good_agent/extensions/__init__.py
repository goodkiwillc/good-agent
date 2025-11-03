# New citation management system
from .citations import (
    CitationExtractor,
    CitationFormat,
    CitationManager,
    CitationPatterns,
    CitationTransformer,
)
from .citations import CitationIndex as NewCitationIndex
from .index import CitationIndex, Paragraph

# Optional dependency: logfire
try:
    from .logfire_tracking import LogfireExtension
except Exception:  # pragma: no cover - optional dependency may be missing

    class LogfireExtension:  # type: ignore
        pass


from .search import AgentSearch
from .task_manager import TaskManager, ToDoItem, ToDoList

__all__ = [
    # New citation management system
    "CitationManager",
    "NewCitationIndex",
    "CitationFormat",
    "CitationTransformer",
    "CitationExtractor",
    "CitationPatterns",
    # Legacy citation support (for backward compatibility)
    "CitationIndex",
    "Paragraph",
    # Logfire tracking
    "LogfireExtension",
    # Search
    "AgentSearch",
    # To-Do List
    "ToDoItem",
    "ToDoList",
    "TaskManager",
    # Web Fetcher
    # "WebFetcher",
    # "WebFetchSummary",
    # "BulkFetchResult",
    # "SearchFetchResult",
    # "FetchStats",
]
