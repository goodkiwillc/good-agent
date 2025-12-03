from typing import TYPE_CHECKING

# For static type checking only - lazy load everything
if TYPE_CHECKING:
    from good_agent.model.llm import LanguageModel, ModelConfig
    from good_agent.model.manager import (
        ManagedRouter,
        ModelDefinition,
        ModelManager,
        create_managed_router,
        get_managed_router_class,
    )
    from good_agent.model.overrides import (
        ModelCapabilities,
        ModelOverride,
        ModelOverrideRegistry,
        ParameterOverride,
        model_override_registry,
    )
    from good_agent.model.protocols import (
        CompletionEvent,
        ModelResponseProtocol,
        ResponseWithHiddenParams,
        ResponseWithResponseHeaders,
        ResponseWithUsage,
        StreamChunk,
    )

# Lazy loading implementation
_LAZY_IMPORTS = {
    # From llm.py
    "LanguageModel": "llm",
    "ModelConfig": "llm",
    # From protocols.py
    "CompletionEvent": "protocols",
    "StreamChunk": "protocols",
    "ModelResponseProtocol": "protocols",
    "ResponseWithUsage": "protocols",
    "ResponseWithHiddenParams": "protocols",
    "ResponseWithResponseHeaders": "protocols",
    # From manager.py
    "ManagedRouter": "manager",
    "ModelDefinition": "manager",
    "ModelManager": "manager",
    "create_managed_router": "manager",
    "get_managed_router_class": "manager",
    # From overrides.py
    "ModelCapabilities": "overrides",
    "ModelOverride": "overrides",
    "ModelOverrideRegistry": "overrides",
    "ParameterOverride": "overrides",
    "model_override_registry": "overrides",
}


def __getattr__(name: str):
    """Lazy load modules on demand."""
    if name in _LAZY_IMPORTS:
        module_path = _LAZY_IMPORTS[name]
        import importlib

        module = importlib.import_module(f".{module_path}", __package__)
        attr = getattr(module, name)
        globals()[name] = attr
        return attr

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """List all available attributes for autocompletion."""
    return list(_LAZY_IMPORTS.keys())


__all__ = [
    # Core language model
    "LanguageModel",
    "CompletionEvent",
    "StreamChunk",
    "ModelConfig",
    "ModelResponseProtocol",
    "ResponseWithUsage",
    "ResponseWithHiddenParams",
    "ResponseWithResponseHeaders",
    # Model management
    "ManagedRouter",
    "ModelDefinition",
    "ModelManager",
    "create_managed_router",
    "get_managed_router_class",
    # Model overrides
    "ModelCapabilities",
    "ModelOverride",
    "ModelOverrideRegistry",
    "ParameterOverride",
    "model_override_registry",
]
