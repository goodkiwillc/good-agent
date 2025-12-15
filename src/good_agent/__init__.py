import logging
from typing import TYPE_CHECKING

from good_agent.content import RenderMode
from good_agent.core.components import AgentComponent
from good_agent.events import AgentEvents
from good_agent.utilities.logger import configure_library_logging

# Minimal eager imports - only the most commonly used classes

configure_library_logging()
logging.getLogger(__name__).addHandler(logging.NullHandler())


# Everything else is lazy-loaded via __getattr__
__version__ = "0.6.2"

# For static type checking only
if TYPE_CHECKING:
    from fast_depends import Depends

    from good_agent.agent import (
        Agent,
        AgentConfigParameters,
        AgentState,
        IsolationLevel,
        ModeAccessor,
        ModeContext,
        ModeExitBehavior,
        ModeManager,
        ModeTransition,
        StandaloneMode,
        SystemPromptManager,
        mode,
    )
    from good_agent.agent.config import AgentConfigManager, Context
    from good_agent.agent.conversation import Conversation
    from good_agent.core.components import (
        AgentComponentType,
        ToolAdapter,
        ToolAdapterRegistry,
    )
    from good_agent.core.components.injection import (
        MessageInjectorComponent,
        SimpleMessageInjector,
    )
    from good_agent.core.event_router import EventContext
    from good_agent.extensions.citations import (
        CitationExtractor,
        CitationFormat,
        CitationIndex,
        CitationManager,
        CitationPatterns,
        CitationTransformer,
    )
    from good_agent.extensions.search import AgentSearch
    from good_agent.extensions.task_manager import TaskManager, ToDoItem, ToDoList
    from good_agent.extensions.template_manager import (
        CircularDependencyError,
        ContextInjectionError,
        ContextProviderError,
        ContextResolver,
        ContextValue,
        MissingContextValueError,
        Template,
        TemplateManager,
        global_context_provider,
    )

    # from good_agent.extensions.webfetcher import (
    #     BulkFetchResult,
    #     FetchStats,
    #     SearchFetchResult,
    #     WebFetcher,
    #     WebFetchSummary,
    # )
    from good_agent.mcp import (
        MCPClientManager,
        MCPToolAdapter,
    )
    from good_agent.messages import (
        Annotation,
        AssistantMessage,
        AssistantMessageStructuredOutput,
        FilteredMessageList,
        Message,
        MessageContent,
        MessageList,
        MessageRole,
        SystemMessage,
        ToolMessage,
        UserMessage,
    )
    from good_agent.mock import (
        AgentMockInterface,
        MockAgent,
        MockResponse,
        create_annotation,
        create_citation,
        create_usage,
        mock_message,
        mock_tool_call,
    )
    from good_agent.model.llm import LanguageModel
    from good_agent.model.manager import ManagedRouter, ModelDefinition, ModelManager
    from good_agent.model.overrides import (
        ModelCapabilities,
        ModelOverride,
        ModelOverrideRegistry,
        model_override_registry,
    )
    from good_agent.resources import (
        EditableMDXL,
        EditableResource,
        EditableYAML,
        StatefulResource,
    )
    from good_agent.tools import (
        BoundTool,
        Tool,
        ToolCall,
        ToolManager,
        ToolMetadata,
        ToolRegistration,
        ToolRegistry,
        ToolResponse,
        ToolSignature,
        clear_tool_registry,
        create_component_tool_decorator,
        get_tool_registry,
        get_tool_registry_sync,
        register_tool,
        tool,
    )
    from good_agent.utilities.console import AgentConsole, create_console


# Lazy loading implementation
_LAZY_IMPORTS = {
    # Core agent classes
    "Agent": "agent",
    "AgentConfigParameters": "agent",
    "AgentState": "agent",
    "AgentConfigManager": "agent.config",
    # Mode system
    "IsolationLevel": "agent",
    "ModeAccessor": "agent",
    "ModeManager": "agent",
    "ModeContext": "agent",
    "ModeExitBehavior": "agent",
    "ModeTransition": "agent",
    "StandaloneMode": "agent",
    "SystemPromptManager": "agent",
    "mode": "agent",
    # Content parts (beyond the eager imports)
    "BaseContentPart": "content",
    "ContentPartType": "content",
    "FileContentPart": "content",
    "ImageContentPart": "content",
    "TemplateContentPart": "content",
    "TextContentPart": "content",
    "deserialize_content_part": "content",
    "is_template": "content",
    # Component system
    "AgentComponentType": "core.components",
    "MessageInjectorComponent": "core.components",
    "SimpleMessageInjector": "core.components",
    "ToolAdapter": "core.components",
    "ToolAdapterRegistry": "core.components",
    # Context and conversation
    "Context": "agent.config",
    "Conversation": "agent.conversation",
    # Extensions - Citations
    "CitationIndex": "extensions.citations",
    "CitationManager": "extensions.citations",
    "CitationFormat": "extensions.citations",
    "CitationTransformer": "extensions.citations",
    "CitationExtractor": "extensions.citations",
    "CitationPatterns": "extensions.citations",
    # "Paragraph": "extensions.citations",
    # Extensions - Other
    "AgentSearch": "extensions.search",
    "TaskManager": "extensions.task_manager",
    "ToDoItem": "extensions.task_manager",
    "ToDoList": "extensions.task_manager",
    # "WebFetcher": "extensions.webfetcher",
    # "WebFetchSummary": "extensions.webfetcher",
    # "BulkFetchResult": "extensions.webfetcher",
    # "SearchFetchResult": "extensions.webfetcher",
    # "FetchStats": "extensions.webfetcher",
    # Language model - heaviest import
    "LanguageModel": "model.llm",
    # MCP integration
    "MCPClientManager": "mcp",
    "MCPToolAdapter": "mcp",
    # Messages
    "Annotation": "messages",
    "AssistantMessage": "messages",
    "AssistantMessageStructuredOutput": "messages",
    "FilteredMessageList": "messages",
    "Message": "messages",
    "MessageContent": "messages",
    "MessageList": "messages",
    "MessageRole": "messages",
    "SystemMessage": "messages",
    "ToolMessage": "messages",
    "UserMessage": "messages",
    # Mock components
    "AgentMockInterface": "mock",
    "MockAgent": "mock",
    "MockResponse": "mock",
    "create_annotation": "mock",
    "create_citation": "mock",
    "create_usage": "mock",
    "mock_message": "mock",
    "mock_tool_call": "mock",
    # Model management
    "ManagedRouter": "model.manager",
    "ModelDefinition": "model.manager",
    "ModelManager": "model.manager",
    "ModelCapabilities": "model.overrides",
    "ModelOverride": "model.overrides",
    "ModelOverrideRegistry": "model.overrides",
    "model_override_registry": "model.overrides",
    # Resources
    "StatefulResource": "resources",
    "EditableResource": "resources",
    "EditableMDXL": "resources",
    # Templates
    "Template": "extensions.template_manager",
    "TemplateManager": "extensions.template_manager",
    "global_context_provider": "extensions.template_manager",
    # Context dependency injection
    "ContextValue": "extensions.template_manager",
    "ContextResolver": "extensions.template_manager",
    "ContextInjectionError": "extensions.template_manager",
    "MissingContextValueError": "extensions.template_manager",
    "ContextProviderError": "extensions.template_manager",
    "CircularDependencyError": "extensions.template_manager",
    # Tools - Core
    "Tool": "tools",
    "ToolCall": "tools",
    "ToolManager": "tools",
    "ToolMetadata": "tools",
    "ToolResponse": "tools",
    "ToolSignature": "tools",
    "tool": "tools",
    # Tools - Registry
    "ToolRegistry": "tools",
    "ToolRegistration": "tools",
    "get_tool_registry": "tools",
    "get_tool_registry_sync": "tools",
    "register_tool": "tools",
    "clear_tool_registry": "tools",
    # Tools - Bound tools
    "BoundTool": "tools",
    "create_component_tool_decorator": "tools",
    # Console utilities
    "AgentConsole": "utilities.console",
    "create_console": "utilities.console",
    # External
    "EventContext": "good_agent.core.event_router",
    "Depends": "fast_depends",
}


def __getattr__(name: str):
    """Lazy load modules on demand to minimize import time."""
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        import importlib

        # Internal modules start with these prefixes
        _INTERNAL_PREFIXES = (
            "agent",
            "content",
            "core",
            "extensions",
            "model",
            "mcp",
            "messages",
            "mock",
            "resources",
            "tools",
        )

        # Check if this is an internal module (relative to good_agent package)
        if any(module_path.split(".")[0] == prefix for prefix in _INTERNAL_PREFIXES):
            # Internal import - relative to this package
            module = importlib.import_module(f".{module_path}", __package__)
        else:
            # External import - absolute import
            module = importlib.import_module(module_path)

        # Get the attribute from the module
        attr = getattr(module, name)

        # Cache it in globals for future access
        globals()[name] = attr
        return attr

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """List all available attributes for autocompletion."""
    return list(_LAZY_IMPORTS.keys()) + [
        "AgentComponent",
        "AgentEvents",
        "RenderMode",
        "__version__",
    ]


__all__ = [
    # Eagerly loaded
    "AgentComponent",
    "AgentEvents",
    "RenderMode",
    # Agent components
    "Agent",
    "AgentConfigParameters",
    "AgentConfigManager",
    "AgentState",
    # Mode system
    "IsolationLevel",
    "ModeAccessor",
    "ModeManager",
    "ModeContext",
    "ModeExitBehavior",
    "ModeTransition",
    "StandaloneMode",
    "SystemPromptManager",
    "mode",
    # Component system
    "AgentComponentType",
    "MessageInjectorComponent",
    "SimpleMessageInjector",
    "ToolAdapter",
    "ToolAdapterRegistry",
    # Content parts
    "BaseContentPart",
    "ContentPartType",
    "FileContentPart",
    "ImageContentPart",
    "TemplateContentPart",
    "TextContentPart",
    "deserialize_content_part",
    "is_template",
    # Context and conversation
    "Context",
    "Conversation",
    # Extensions - Citations
    "CitationIndex",
    "CitationManager",
    "CitationFormat",
    "CitationTransformer",
    "CitationExtractor",
    "CitationPatterns",
    # "Paragraph",
    # Extensions - Other
    "AgentSearch",
    "TaskManager",
    "ToDoItem",
    "ToDoList",
    # "WebFetcher",
    # "WebFetchSummary",
    # "BulkFetchResult",
    # "SearchFetchResult",
    # "FetchStats",
    # Language model
    "LanguageModel",
    # MCP integration
    "MCPClientManager",
    "MCPToolAdapter",
    # Model management
    "ManagedRouter",
    "ModelDefinition",
    "ModelManager",
    "ModelCapabilities",
    "ModelOverride",
    "ModelOverrideRegistry",
    "model_override_registry",
    # Messages
    "Annotation",
    "AssistantMessage",
    "AssistantMessageStructuredOutput",
    "FilteredMessageList",
    "Message",
    "MessageContent",
    "MessageList",
    "MessageRole",
    "SystemMessage",
    "ToolMessage",
    "UserMessage",
    # Mock components
    "AgentMockInterface",
    "MockAgent",
    "MockResponse",
    "create_annotation",
    "create_citation",
    "create_usage",
    "mock_message",
    "mock_tool_call",
    # Resources
    "StatefulResource",
    "EditableResource",
    "EditableMDXL",
    "EditableYAML",
    # Templates
    "Template",
    "TemplateManager",
    "global_context_provider",
    # Context dependency injection
    "ContextValue",
    "ContextResolver",
    "ContextInjectionError",
    "MissingContextValueError",
    "ContextProviderError",
    "CircularDependencyError",
    # Tools
    "Tool",
    "ToolCall",
    "ToolManager",
    "ToolMetadata",
    "ToolResponse",
    "ToolSignature",
    "tool",
    "ToolRegistry",
    "ToolRegistration",
    "get_tool_registry",
    "get_tool_registry_sync",
    "register_tool",
    "clear_tool_registry",
    "BoundTool",
    "create_component_tool_decorator",
    # Console utilities
    "AgentConsole",
    "create_console",
    # External
    "EventContext",
    "Depends",
]
