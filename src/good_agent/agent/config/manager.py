import annotationlib
import inspect
import sys
import types
from collections import ChainMap
from collections.abc import Callable, Iterator, MutableMapping
from contextlib import contextmanager
from typing import (
    Any,
    Literal,
    TypeAlias,
    TypedDict,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from httpx import Timeout

T = TypeVar("T", bound="ConfigStack")


class ConfigField:
    """A descriptor for typed configuration fields"""

    def __init__(self, default: Any = None, type_hint: type | None = None):
        self.default = default
        self.type_hint = type_hint

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj._chainmap.get(self.name, self.default)

    def __set__(self, obj, value):
        # Simple type validation
        if self.type_hint and value is not None and not self._validate_type(value, self.type_hint):
            raise TypeError(f"Field '{self.name}' expected {self.type_hint}, got {type(value)}")
        obj._chainmap[self.name] = value

    def _validate_type(self, value: Any, expected_type: type) -> bool:
        """Basic type validation with support for generic types"""
        try:
            # Handle generic types
            origin = get_origin(expected_type)

            if origin is list:
                if not isinstance(value, list):
                    return False
                # Optionally validate list elements
                args = get_args(expected_type)
                if args:
                    return all(isinstance(item, args[0]) for item in value)
                return True

            # Handle Union types (including Optional) - both typing.Union and types.UnionType (Python 3.10+)
            elif origin is Union or isinstance(expected_type, types.UnionType):
                args = get_args(expected_type)
                # For Union types, check if value matches any of the types
                for arg in args:
                    try:
                        if (
                            arg is type(None)
                            and value is None
                            or arg is not type(None)
                            and isinstance(value, arg)
                        ):
                            return True
                    except TypeError:
                        # If isinstance fails, try recursive validation
                        if self._validate_type(value, arg):
                            return True
                return False

            # Handle other generic types
            elif origin is not None:
                # For other generic types, just check the origin
                return isinstance(value, origin)

            # Basic type check - catch TypeError for subscripted generics
            return isinstance(value, expected_type)
        except TypeError:
            # Fallback for subscripted generics that can't be used with isinstance
            return True


class ConfigStackMeta(type):
    """Metaclass to process field annotations and create descriptors"""

    def __new__(mcs, name, bases, namespace, **_kwargs):
        # Python 3.14+ uses __annotate_func__ instead of __annotations__
        if sys.version_info >= (3, 14) and "__annotate_func__" in namespace:
            try:
                annotations = namespace["__annotate_func__"](annotationlib.Format.VALUE)
            except Exception:
                annotations = {}
        else:
            annotations = namespace.get("__annotations__", {})

        # Create descriptors for annotated fields
        for field_name, field_type in annotations.items():
            if not field_name.startswith("_"):
                # Get default value if provided
                default = namespace.get(field_name, None)
                # Create descriptor
                namespace[field_name] = ConfigField(default=default, type_hint=field_type)

        return super().__new__(mcs, name, bases, namespace)


class ConfigStack(metaclass=ConfigStackMeta):
    """
    A configuration stack using ChainMap with type hints and defaults.

    Supports temporary overrides via context manager.
    """

    def __init__(self, **kwargs):
        self._chainmap: ChainMap[str, Any] = ChainMap({})

        # Set defaults from class definition
        for key, value in inspect.getmembers(self.__class__):
            if isinstance(value, ConfigField) and value.default is not None:
                self._chainmap[key] = value.default

        # Set provided values (will be validated by descriptors)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name: str) -> Any:
        """Get attribute from ChainMap for dynamic fields"""
        if name.startswith("_"):
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

        try:
            return self._chainmap[name]
        except KeyError as e:
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            ) from e

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute in ChainMap"""
        if name.startswith("_"):
            # Handle private attributes normally
            object.__setattr__(self, name, value)
        else:
            # Check if it's a defined field with a descriptor
            if hasattr(self.__class__, name) and isinstance(
                getattr(self.__class__, name), ConfigField
            ):
                # Let the descriptor handle it
                object.__setattr__(self, name, value)
            else:
                # Dynamic field
                self._chainmap[name] = value

    @contextmanager
    def __call__(self: T, **kwargs) -> Iterator[T]:
        """Context manager for temporary overrides"""
        # Validate field types if they're defined fields
        validated_kwargs = {}
        for key, value in kwargs.items():
            if hasattr(self.__class__, key) and isinstance(
                getattr(self.__class__, key), ConfigField
            ):
                field = getattr(self.__class__, key)
                if (
                    field.type_hint
                    and value is not None
                    and not field._validate_type(value, field.type_hint)
                ):
                    raise TypeError(
                        f"Override for '{key}' expected {field.type_hint}, got {type(value)}"
                    )
            validated_kwargs[key] = value

        self._chainmap = self._chainmap.new_child(validated_kwargs)
        try:
            yield self
        finally:
            self._chainmap = self._chainmap.parents

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value with optional default"""
        try:
            return self._chainmap[key]
        except KeyError:
            return default

    def as_dict(self) -> dict[str, Any]:
        """Return current configuration as a dictionary"""
        return dict(self._chainmap)

    def __getitem__(self, key: str) -> Any:
        """Get item like a dictionary"""
        return self._chainmap[key]

    def __setitem__(self, key: str, value: Any) -> None:
        """Set item like a dictionary"""
        self._chainmap[key] = value

    def __contains__(self, key: str) -> bool:
        """Check if key exists"""
        return key in self._chainmap

    def __repr__(self) -> str:
        items = ", ".join(f"{k}={v!r}" for k, v in self._chainmap.items())
        return f"{self.__class__.__name__}({items})"

    def update(self, updates: MutableMapping[str, Any]) -> None:
        """Update context with new values"""
        if not isinstance(updates, MutableMapping):
            raise TypeError("Updates must be a mapping")

        self._chainmap = self._chainmap.new_child(updates)

        # # Update config context first
        # config_context = self._get_config_context()
        # config_context.update(updates)

        # # Then update local context
        # super().update(updates)


ExtractionMode = Literal[
    "tools",
    "parallel_tools",
    "mistral_tools",
    "json",
    "json_o1",
    "md_json",
    "json_schema",
    "anthropic_tools",
    "anthropic_json",
    "cohere_tools",
    "vertexai_tools",
    "vertexai_json",
    "gemini_json",
    "gemini_tools",
    "cohere_json_schema",
    "tools_strict",
    "cerebras_tools",
    "cerebras_json",
    "fireworks_tools",
    "fireworks_json",
]


class PredictedContent:
    type: str
    text: str


class PredictedOutput(TypedDict):
    type: Literal["content"]
    content: str | PredictedContent


class ResponseFormat(TypedDict):
    type: Literal["json_schema", "json_object"]
    json_schema: dict


FilterPattern: TypeAlias = str


class AgentConfigManager(ConfigStack):
    model: str = "gpt-4.1-mini"
    timeout: float | str | Timeout | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    temperature: float = 0.0
    top_p: float = 1.0
    n: int = 1
    stop: list[str] | str | None = None
    stream_options: dict | None = None
    parallel_tool_calls: bool = True
    presence_penalty: float | None = None
    frequency_penalty: float | None = None
    logit_bias: dict[str, float] | None = None
    user: str | None = None
    reasoning_effort: Literal["low", "medium", "high"] | None = None
    reasoning: dict | None = None
    seed: int | None = None
    metadata: dict | None = None
    prediction: PredictedOutput | None = None
    response_format: ResponseFormat | None = None
    stream: bool
    tool_choice: str | dict | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None

    mcp_servers: list[str | dict[str, Any]] | None = None
    # tools: list[str | Callable[..., Any] | ToolCallFunction]
    include_tool_filters: list[FilterPattern] | None = None
    exclude_tool_filters: list[FilterPattern] | None = None

    web_search_options: dict | None = None
    deployment_id: str | None = None
    extra_headers: dict | None = None
    instructor_mode: str | None = None
    base_url: str | None = None
    api_version: str | None = None
    api_key: str | None = None
    model_list: list | None = None
    thinking: dict | None = None
    # OpenRouter extras
    transforms: list | dict | None = None
    route: str | None = None
    models: list[str] | None = None
    provider: dict | None = None
    include_reasoning: bool | None = None
    usage: dict | None = None
    top_k: int | None = None
    repetition_penalty: float | None = None
    min_p: float | None = None
    top_a: float | None = None

    undefined_behavior: Literal["strict", "silent", "log"]

    extract_mode: ExtractionMode = "tools"
    extract_strict: bool = False
    extract_fallbacks = ["gpt-4.1", "gpt-5-mini", "gpt-4o-mini", "gpt-4o"]
    extract_temperature = 0.0

    template_functions: dict[str, Callable]
    enable_template_cache: bool
    load_entry_points: bool
    name: str | None = None
    litellm_debug: bool = False
    debug: bool = False
    print_messages: bool = False
    print_messages_mode: Literal["display", "llm", "raw"] = "display"
    print_messages_markdown: bool | None = None  # None = auto-detect, True = always, False = never
    print_messages_role: list[Literal["system", "user", "assistant", "tool"]] | None = None
    message_validation_mode: Literal["strict", "warn", "silent"] = "warn"

    def __init__(self, *args, **kwargs):
        if kwargs.get("print_messages_role") is None:
            kwargs["print_messages_role"] = ["system", "user", "assistant", "tool"]
        super().__init__(*args, **kwargs)
        self._agent = None  # Will be set by the agent after creation

    def _set_agent(self, agent):
        """Set the parent agent reference"""
        self._agent = agent

    @contextmanager
    def __call__(
        self, disable_extensions: list[type] | None = None, **kwargs
    ) -> Iterator[AgentConfigManager]:
        """
        Context manager for temporary overrides that notifies the agent.

        Args:
            disable_extensions: List of extension types to disable temporarily
            **kwargs: Other config parameters to override temporarily

        Example:
            with agent.config(disable_extensions=[TaskManager]):
                # TaskManager will be disabled here
                response = await agent.call("Process without task manager")
        """
        from good_agent.core.components import AgentComponent

        # Track original enabled states for extensions
        original_states: dict[AgentComponent, bool] = {}

        if disable_extensions and self._agent:
            # Disable specified extensions
            for ext_type in disable_extensions:
                if hasattr(self._agent, "_extensions") and ext_type in self._agent._extensions:
                    extension = self._agent._extensions[ext_type]
                    if hasattr(extension, "enabled"):
                        original_states[extension] = extension.enabled
                        extension.enabled = False

        # Validate field types if they're defined fields
        validated_kwargs = {}
        for key, value in kwargs.items():
            if hasattr(self.__class__, key) and isinstance(
                getattr(self.__class__, key), ConfigField
            ):
                field = getattr(self.__class__, key)
                if (
                    field.type_hint
                    and value is not None
                    and not field._validate_type(value, field.type_hint)
                ):
                    raise TypeError(
                        f"Override for '{key}' expected {field.type_hint}, got {type(value)}"
                    )
            validated_kwargs[key] = value

        # Notify agent of config change before entering context
        if self._agent:
            self._agent._update_version()

        self._chainmap = self._chainmap.new_child(validated_kwargs)
        try:
            yield self
        finally:
            self._chainmap = self._chainmap.parents

            # Restore original extension states
            for extension, original_state in original_states.items():
                extension.enabled = original_state

            # Notify agent of config change after exiting context
            if self._agent:
                self._agent._update_version()
