# New citation management system
from .citations import (
    CitationExtractor,
    CitationFormat,
    CitationManager,
    CitationPatterns,
    CitationTransformer,
)
from .citations import CitationIndex as NewCitationIndex
from .search import AgentSearch
from .task_manager import TaskManager, ToDoItem, ToDoList
from .template_manager import Template, TemplateManager

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
    # Search
    "AgentSearch",
    # To-Do List
    "ToDoItem",
    "ToDoList",
    "TaskManager",
    # Template Manager
    "Template",
    "TemplateManager",
    # Web Fetcher
    #     "WebFetcher",
    #     "WebFetchSummary",
    #     "BulkFetchResult",
    #     "SearchFetchResult",
    #     "FetchStats",
]
