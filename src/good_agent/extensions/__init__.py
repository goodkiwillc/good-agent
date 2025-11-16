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
from .search import AgentSearch
from .task_manager import TaskManager, ToDoItem, ToDoList

# from .webfetcher import (
#     BulkFetchResult,
#     FetchStats,
#     SearchFetchResult,
#     WebFetcher,
#     WebFetchSummary,
# )

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
    # Search
    "AgentSearch",
    # To-Do List
    "ToDoItem",
    "ToDoList",
    "TaskManager",
    # Web Fetcher
    #     "WebFetcher",
    #     "WebFetchSummary",
    #     "BulkFetchResult",
    #     "SearchFetchResult",
    #     "FetchStats",
]
