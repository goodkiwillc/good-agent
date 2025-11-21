# New citation management system
from good_agent.extensions.citations import (
    CitationExtractor,
    CitationFormat,
    CitationManager,
    CitationPatterns,
    CitationTransformer,
)
from good_agent.extensions.citations import CitationIndex as NewCitationIndex
from good_agent.extensions.search import AgentSearch
from good_agent.extensions.task_manager import TaskManager, ToDoItem, ToDoList
from good_agent.extensions.template_manager import Template, TemplateManager

# Alias NewCitationIndex to CitationIndex for backward compatibility (as a type/class, not component)
CitationIndex = NewCitationIndex

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
    "CitationIndex",
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
