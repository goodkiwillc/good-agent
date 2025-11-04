"""good_agent - Advanced agent framework with optimized lazy loading.

This module uses lazy loading to minimize import time. Heavy dependencies
like litellm are only imported when actually needed.
"""

import logging
from typing import TYPE_CHECKING

# Minimal eager imports - only the most commonly used classes
from .components import AgentComponent
from .content import RenderMode
from .events import AgentEvents

logging.getLogger(__name__).addHandler(logging.NullHandler())


# Everything else is lazy-loaded via __getattr__
__version__ = "0.1.0"

# For static type checking only
if TYPE_CHECKING:
    from good_agent.core.event_router import EventContext

    from .agent import Agent, AgentConfigParameters, AgentState
    from .components import (
        AgentComponentType,
        ToolAdapter,
        ToolAdapterRegistry,
    )
    from .components.injection import MessageInjectorComponent, SimpleMessageInjector
    from .config import AgentConfigManager
    from .content import (
        BaseContentPart,
        ContentPartType,
        FileContentPart,
        ImageContentPart,
        TemplateContentPart,
        TextContentPart,
        deserialize_content_part,
        is_template,
    )
    from .context import Context
    from .conversation import Conversation
    from .extensions import (
        AgentSearch,
        BulkFetchResult,
        CitationExtractor,
        CitationFormat,
        CitationIndex,
        CitationManager,
        CitationPatterns,
        CitationTransformer,
        FetchStats,
        LogfireExtension,
        Paragraph,
        SearchFetchResult,
        TaskManager,
        ToDoItem,
        ToDoList,
        WebFetcher,
        WebFetchSummary,
    )
    from .mcp import (
        MCPClientManager,
        MCPToolAdapter,
    )
    from .messages import (
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
    from .mock import (
        AgentMockInterface,
        MockAgent,
        MockResponse,
        create_annotation,
        create_citation,
        create_usage,
        mock_message,
        mock_tool_call,
    )
    from .model.llm import LanguageModel
    from .model.manager import ManagedRouter, ModelDefinition, ModelManager
    from .model.overrides import (
        ModelCapabilities,
        ModelOverride,
        ModelOverrideRegistry,
        model_override_registry,
    )
    from .resources import (
        EditableMDXL,
        EditableResource,
        EditableYAML,
        StatefulResource,
    )
    from .templating import (
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
    from .tools import (
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


# Lazy loading implementation
_LAZY_IMPORTS = {
    # Core agent classes
    "Agent": "agent",
    "AgentConfigParameters": "agent",
    "AgentState": "agent",
    "AgentConfigManager": "config",
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
    "AgentComponentType": "components",
    "MessageInjectorComponent": "components.injection",
    "SimpleMessageInjector": "components.injection",
    "ToolAdapter": "components",
    "ToolAdapterRegistry": "components",
    # Context and conversation
    "Context": "context",
    "Conversation": "conversation",
    # Extensions - Citations
    "CitationIndex": "extensions",
    "CitationManager": "extensions",
    "CitationFormat": "extensions",
    "CitationTransformer": "extensions",
    "CitationExtractor": "extensions",
    "CitationPatterns": "extensions",
    "Paragraph": "extensions",
    # Extensions - Other
    "LogfireExtension": "extensions",
    "AgentSearch": "extensions",
    "TaskManager": "extensions",
    "ToDoItem": "extensions",
    "ToDoList": "extensions",
    "WebFetcher": "extensions",
    "WebFetchSummary": "extensions",
    "BulkFetchResult": "extensions",
    "SearchFetchResult": "extensions",
    "FetchStats": "extensions",
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
    "Template": "templating",
    "TemplateManager": "templating",
    "global_context_provider": "templating",
    # Context dependency injection
    "ContextValue": "templating",
    "ContextResolver": "templating",
    "ContextInjectionError": "templating",
    "MissingContextValueError": "templating",
    "ContextProviderError": "templating",
    "CircularDependencyError": "templating",
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
    # External
    "EventContext": "good_agent.utilities.event_router",
}


def __getattr__(name: str):
    """Lazy load modules on demand to minimize import time."""
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        import importlib

        # Check if this is an external module (starts with a known external package)
        if module_path.startswith("good_agent."):
            # External import from another package
            module = importlib.import_module(module_path)
        else:
            # Internal import - always relative to this package
            module = importlib.import_module(f".{module_path}", __package__)

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
    "Paragraph",
    # Extensions - Other
    "LogfireExtension",
    "AgentSearch",
    "TaskManager",
    "ToDoItem",
    "ToDoList",
    "WebFetcher",
    "WebFetchSummary",
    "BulkFetchResult",
    "SearchFetchResult",
    "FetchStats",
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
    # External
    "EventContext",
]
