from collections.abc import Callable
from dataclasses import MISSING, dataclass, field, fields
from typing import Any


@dataclass
class ParameterOverride:
    """Configuration for how to handle a specific parameter for a model"""

    action: str  # "drop", "override", "transform"
    value: Any = None  # Used for "override" action
    transform: Callable[[Any], Any] | None = None  # Used for "transform" action

    def apply(self, original_value: Any) -> tuple[bool, Any]:
        """
        Apply the override to a parameter value.
        Returns (should_include, transformed_value)
        """
        if self.action == "drop":
            return False, None
        elif self.action == "override":
            return True, self.value
        elif self.action == "transform":
            if self.transform:
                return True, self.transform(original_value)
            return True, original_value
        else:
            return True, original_value


@dataclass
class ModelCapabilities:
    """Capabilities that a model supports (fields without 'supports_' prefix)."""

    # Canonical capability flags (no 'supports_' prefix)
    function_calling: bool = False
    parallel_function_calling: bool = False
    vision: bool = False
    pdf_input: bool = False
    response_schema: bool = False
    native_streaming: bool = True
    prompt_caching: bool = False
    audio_input: bool = False
    audio_output: bool = False
    web_search: bool = False
    url_context: bool = False
    reasoning: bool = False
    computer_use: bool = False
    system_messages: bool = False
    embedding_image_input: bool = False
    tool_choice: bool = False
    assistant_prefill: bool = False

    # Legacy/non-LiteLLM additional flags retained for backward compatibility
    citations: bool = False
    video_input: bool = False

    def to_dict(self) -> dict[str, bool]:
        """Convert capabilities to dictionary."""
        base = {f.name: getattr(self, f.name) for f in fields(self)}
        # Add legacy aliases for compatibility (no 'supports_' keys here)
        alias_map = {
            "images": self.vision,
            "structured_output": self.response_schema,
            "streaming": self.native_streaming,
            "context_caching": self.prompt_caching,
            "thinking": self.reasoning,
        }
        base.update(alias_map)
        return base

    def __init__(self, **kwargs: Any):
        # Initialize defaults
        for f in fields(type(self)):
            default_val = f.default if f.default is not MISSING else False
            setattr(self, f.name, default_val)

        # Accept both legacy and litellm-style names
        incoming_map = {
            # canonical -> itself
            "function_calling": "function_calling",
            "parallel_function_calling": "parallel_function_calling",
            "vision": "vision",
            "pdf_input": "pdf_input",
            "response_schema": "response_schema",
            "native_streaming": "native_streaming",
            "prompt_caching": "prompt_caching",
            "audio_input": "audio_input",
            "audio_output": "audio_output",
            "web_search": "web_search",
            "url_context": "url_context",
            "reasoning": "reasoning",
            "computer_use": "computer_use",
            "system_messages": "system_messages",
            "embedding_image_input": "embedding_image_input",
            "tool_choice": "tool_choice",
            "assistant_prefill": "assistant_prefill",
            "citations": "citations",
            "video_input": "video_input",
            # legacy aliases
            "images": "vision",
            "structured_output": "response_schema",
            "streaming": "native_streaming",
            "context_caching": "prompt_caching",
            "thinking": "reasoning",
            # litellm-style supports_* inputs
            "supports_function_calling": "function_calling",
            "supports_parallel_function_calling": "parallel_function_calling",
            "supports_vision": "vision",
            "supports_pdf_input": "pdf_input",
            "supports_response_schema": "response_schema",
            "supports_native_streaming": "native_streaming",
            "supports_prompt_caching": "prompt_caching",
            "supports_audio_input": "audio_input",
            "supports_audio_output": "audio_output",
            "supports_web_search": "web_search",
            "supports_url_context": "url_context",
            "supports_reasoning": "reasoning",
            "supports_computer_use": "computer_use",
            "supports_system_messages": "system_messages",
            "supports_embedding_image_input": "embedding_image_input",
            "supports_tool_choice": "tool_choice",
            "supports_assistant_prefill": "assistant_prefill",
        }

        for key, value in kwargs.items():
            target = incoming_map.get(key)
            if target and hasattr(self, target):
                setattr(self, target, value)

    # Backwards-compatibility aliases (pre-standardization names and supports_* aliases)
    @property
    def images(self) -> bool:
        return self.vision

    @property
    def structured_output(self) -> bool:
        return self.response_schema

    @property
    def streaming(self) -> bool:
        return self.native_streaming

    @property
    def context_caching(self) -> bool:
        return self.prompt_caching

    @property
    def thinking(self) -> bool:
        return self.reasoning

    @property
    def supports_function_calling(self) -> bool:
        return self.function_calling

    @property
    def supports_parallel_function_calling(self) -> bool:
        return self.parallel_function_calling

    @property
    def supports_vision(self) -> bool:
        return self.vision

    @property
    def supports_pdf_input(self) -> bool:
        return self.pdf_input

    @property
    def supports_response_schema(self) -> bool:
        return self.response_schema

    @property
    def supports_native_streaming(self) -> bool:
        return self.native_streaming

    @property
    def supports_prompt_caching(self) -> bool:
        return self.prompt_caching

    @property
    def supports_audio_input(self) -> bool:
        return self.audio_input

    @property
    def supports_audio_output(self) -> bool:
        return self.audio_output

    @property
    def supports_web_search(self) -> bool:
        return self.web_search

    @property
    def supports_url_context(self) -> bool:
        return self.url_context

    @property
    def supports_reasoning(self) -> bool:
        return self.reasoning

    @property
    def supports_computer_use(self) -> bool:
        return self.computer_use

    @property
    def supports_system_messages(self) -> bool:
        return self.system_messages

    @property
    def supports_embedding_image_input(self) -> bool:
        return self.embedding_image_input

    @property
    def supports_tool_choice(self) -> bool:
        return self.tool_choice

    @property
    def supports_assistant_prefill(self) -> bool:
        return self.assistant_prefill


@dataclass
class ModelOverride:
    """Model-specific configuration overrides"""

    model_pattern: str  # Can be exact match or pattern like "gpt-5*"
    parameter_overrides: dict[str, ParameterOverride] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)  # Default values for this model
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)  # Model capabilities

    def matches(self, model_name: str) -> bool:
        """Check if this override applies to the given model"""
        if self.model_pattern == model_name:
            return True

        # Simple wildcard matching
        if "*" in self.model_pattern:
            import fnmatch

            return fnmatch.fnmatch(model_name, self.model_pattern)

        return False

    def apply_to_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Apply overrides to a configuration dictionary"""
        result = {}

        # Start with defaults for this model
        result.update(self.defaults)

        # Process each config parameter
        for key, value in config.items():
            if key in self.parameter_overrides:
                override = self.parameter_overrides[key]
                should_include, new_value = override.apply(value)
                if should_include:
                    result[key] = new_value
            else:
                # No override, keep original
                result[key] = value

        return result


class ModelOverrideRegistry:
    """Registry for model-specific configuration overrides"""

    def __init__(self):
        self._overrides: list[ModelOverride] = []
        self._initialize_defaults()

    def _initialize_defaults(self):
        """Initialize with known model-specific overrides"""

        # GPT-5 series only supports temperature=1
        self.register(
            ModelOverride(
                model_pattern="gpt-5*",
                parameter_overrides={
                    "temperature": ParameterOverride(action="drop"),
                    "top_p": ParameterOverride(action="drop"),
                },
                defaults={},
                capabilities=ModelCapabilities(
                    function_calling=True,
                    parallel_function_calling=True,
                    vision=True,
                    response_schema=True,
                    native_streaming=True,
                    web_search=True,
                ),
            )
        )

        # Claude 3.5 Sonnet specific overrides
        self.register(
            ModelOverride(
                model_pattern="claude-3-5-sonnet*",
                parameter_overrides={
                    # Claude doesn't support certain OpenAI parameters
                    "logit_bias": ParameterOverride(action="drop"),
                    "n": ParameterOverride(action="drop"),
                },
                defaults={
                    "max_tokens": 8192,
                },
                capabilities=ModelCapabilities(
                    function_calling=True,
                    parallel_function_calling=False,
                    vision=True,
                    pdf_input=True,
                    response_schema=True,
                    native_streaming=True,
                    prompt_caching=True,
                ),
            )
        )

        # o1 models have specific constraints
        self.register(
            ModelOverride(
                model_pattern="o1*",
                parameter_overrides={
                    "temperature": ParameterOverride(action="override", value=1.0),
                    "top_p": ParameterOverride(action="override", value=1.0),
                    "presence_penalty": ParameterOverride(action="drop"),
                    "frequency_penalty": ParameterOverride(action="drop"),
                    "logit_bias": ParameterOverride(action="drop"),
                },
                defaults={
                    "max_completion_tokens": 32768,
                },
                capabilities=ModelCapabilities(
                    function_calling=True,
                    parallel_function_calling=True,
                    vision=True,
                    response_schema=True,
                    native_streaming=False,  # o1 doesn't support streaming
                    reasoning=True,  # o1 has reasoning/thinking tokens
                ),
            )
        )

        # GPT-4 models
        self.register(
            ModelOverride(
                model_pattern="gpt-4*",
                parameter_overrides={},
                defaults={},
                capabilities=ModelCapabilities(
                    function_calling=True,
                    parallel_function_calling=True,
                    vision=True,  # GPT-4V supports images
                    response_schema=True,
                    native_streaming=True,
                ),
            )
        )

        # Gemini models
        self.register(
            ModelOverride(
                model_pattern="gemini*",
                parameter_overrides={
                    # Gemini uses different parameter names
                    "max_tokens": ParameterOverride(
                        action="transform",
                        transform=lambda v: {"max_output_tokens": v} if v else {},
                    ),
                },
                defaults={},
                capabilities=ModelCapabilities(
                    function_calling=True,
                    parallel_function_calling=True,
                    vision=True,
                    pdf_input=True,
                    audio_input=True,
                    video_input=True,  # legacy flag retained
                    response_schema=True,
                    native_streaming=True,
                ),
            )
        )

    def register(self, override: ModelOverride):
        """Register a new model override"""
        # Add to beginning so more specific patterns can override general ones
        self._overrides.insert(0, override)

    def apply(self, model_name: str, config: dict[str, Any]) -> dict[str, Any]:
        """Apply all matching overrides to a configuration"""
        result = config.copy()

        # Apply overrides in order (first match wins for each parameter)
        applied_params: set[str] = set()
        for override in self._overrides:
            if override.matches(model_name):
                # Only apply overrides for parameters not yet processed
                filtered_config = {k: v for k, v in result.items() if k not in applied_params}
                override_result = override.apply_to_config(filtered_config)

                # Track which parameters were processed
                applied_params.update(override_result.keys())

                # Update result
                result = override_result

        return result

    def get_model_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get the capabilities for a specific model"""
        # Start with default capabilities (no capabilities)
        capabilities = ModelCapabilities()

        # Populate from litellm support helpers when available
        try:
            import litellm

            capability_to_litellm = {
                "function_calling": "supports_function_calling",
                "parallel_function_calling": "supports_parallel_function_calling",
                "vision": "supports_vision",
                "pdf_input": "supports_pdf_input",
                "response_schema": "supports_response_schema",
                "native_streaming": "supports_native_streaming",
                "prompt_caching": "supports_prompt_caching",
                "audio_input": "supports_audio_input",
                "audio_output": "supports_audio_output",
                "web_search": "supports_web_search",
                "url_context": "supports_url_context",
                "reasoning": "supports_reasoning",
                "computer_use": "supports_computer_use",
                "system_messages": "supports_system_messages",
                "embedding_image_input": "supports_embedding_image_input",
                "tool_choice": "supports_tool_choice",
                "assistant_prefill": "supports_assistant_prefill",
            }

            for cap_name, litellm_name in capability_to_litellm.items():
                if hasattr(litellm, litellm_name):
                    try:
                        setattr(
                            capabilities,
                            cap_name,
                            getattr(litellm, litellm_name)(model_name),
                        )
                    except Exception:
                        # Leave default if litellm helper errors
                        pass
        except Exception:
            # If litellm checks fail, continue with our overrides
            pass

        # Apply our custom overrides (these take precedence)
        for override in self._overrides:
            if override.matches(model_name):
                capabilities = override.capabilities
                break

        return capabilities

    def get_model_info(self, model_name: str) -> dict[str, Any]:
        """Get information about what overrides apply to a model"""
        info: dict[str, Any] = {
            "model": model_name,
            "overrides": [],
            "dropped_parameters": [],
            "forced_parameters": {},
            "defaults": {},
            "capabilities": {},
        }

        for override in self._overrides:
            if override.matches(model_name):
                info["overrides"].append(override.model_pattern)

                for param, param_override in override.parameter_overrides.items():
                    if param_override.action == "drop":
                        info["dropped_parameters"].append(param)
                    elif param_override.action == "override":
                        info["forced_parameters"][param] = param_override.value

                info["defaults"].update(override.defaults)
                info["capabilities"] = override.capabilities.to_dict()
                break  # Use first matching override

        return info


# Global registry instance
model_override_registry = ModelOverrideRegistry()
