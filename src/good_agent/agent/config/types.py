from __future__ import annotations

from typing import Any, Literal, NotRequired, TypeAlias, TypedDict

from httpx import Timeout
from instructor.mode import Mode as InstructorMode

ModelName: TypeAlias = str


class ReasoningConfig(TypedDict, total=False):
    effort: NotRequired[Literal["low", "medium", "high"]]
    max_tokens: NotRequired[int]


class LLMCommonConfig(TypedDict, total=False):
    # Core
    model: ModelName
    timeout: NotRequired[float | str | Timeout]
    temperature: NotRequired[float]
    top_p: NotRequired[float]
    n: NotRequired[int]
    stream_options: NotRequired[dict]
    stop: NotRequired[str | list[str]]
    max_completion_tokens: NotRequired[int]
    max_tokens: NotRequired[int]
    presence_penalty: NotRequired[float]
    frequency_penalty: NotRequired[float]
    logit_bias: NotRequired[dict]
    user: NotRequired[str]
    reasoning_effort: NotRequired[Literal["low", "medium", "high"]]
    reasoning: NotRequired[ReasoningConfig]
    seed: NotRequired[int]
    tool_choice: NotRequired[str | dict]
    logprobs: NotRequired[bool]
    top_logprobs: NotRequired[int]
    parallel_tool_calls: NotRequired[bool]
    web_search_options: NotRequired[dict]
    deployment_id: NotRequired[str]
    extra_headers: NotRequired[dict]
    instructor_mode: NotRequired[InstructorMode]
    custom_llm_provider: NotRequired[str]

    # Provider/client
    base_url: NotRequired[str]
    api_version: NotRequired[str]
    api_key: NotRequired[str]
    model_list: NotRequired[list]
    thinking: NotRequired[dict]

    # Diagnostics
    debug: NotRequired[bool]

    # OpenRouter-specific (OpenAI-compatible via extra_body)
    transforms: NotRequired[list | dict]
    route: NotRequired[str]
    models: NotRequired[list[str]]
    provider: NotRequired[dict]
    include_reasoning: NotRequired[bool]
    usage: NotRequired[dict]
    top_k: NotRequired[int]
    repetition_penalty: NotRequired[float]
    min_p: NotRequired[float]
    top_a: NotRequired[float]


class AgentOnlyConfig(TypedDict, total=False):
    # Agent/tooling/templates behavior
    mcp_servers: NotRequired[list[str | dict[str, Any]]]
    include_tool_filters: NotRequired[list[str]]
    exclude_tool_filters: NotRequired[list[str]]
    context: NotRequired[dict[str, Any] | None]
    template_path: NotRequired[str]
    undefined_behavior: NotRequired[Literal["strict", "silent", "log"]]
    template_functions: NotRequired[dict[str, Any]]
    enable_template_cache: NotRequired[bool]
    use_template_sandbox: NotRequired[bool]
    load_entry_points: NotRequired[bool]
    name: NotRequired[str]
    print_messages: NotRequired[bool]
    print_messages_mode: NotRequired[Literal["display", "llm", "raw"]]
    print_messages_role: NotRequired[list[Literal["system", "user", "assistant", "tool"]]]
    print_messages_markdown: NotRequired[bool | None]
    litellm_debug: NotRequired[bool]
    message_validation_mode: NotRequired[Literal["strict", "warn", "silent"]]
    enable_signal_handling: NotRequired[bool]


class ModelConfig(LLMCommonConfig, TypedDict, total=False):
    # Per-call options used by LanguageModel (tools may be injected by Agent)
    tools: NotRequired[list]


# Keys passed from AgentConfigManager/AgentConfigParameters to LanguageModel/_prepare_request_config
PASS_THROUGH_KEYS: set[str] = {
    "timeout",
    "top_p",
    "n",
    "stream_options",
    "stop",
    "max_completion_tokens",
    "max_tokens",
    "presence_penalty",
    "frequency_penalty",
    "logit_bias",
    "user",
    "reasoning_effort",
    "reasoning",
    "seed",
    "tools",
    "tool_choice",
    "logprobs",
    "top_logprobs",
    "parallel_tool_calls",
    "web_search_options",
    "deployment_id",
    "extra_headers",
    "base_url",
    "api_version",
    "api_key",
    "model_list",
    "thinking",
    "custom_llm_provider",
    # OpenRouter extras
    "transforms",
    "route",
    "models",
    "provider",
    "include_reasoning",
    "usage",
    "top_k",
    "repetition_penalty",
    "min_p",
    "top_a",
}


# Union of keys supported by Agent constructor
AGENT_CONFIG_KEYS: set[str] = PASS_THROUGH_KEYS | {
    # Core
    "model",
    "temperature",
    # Agent-only
    "mcp_servers",
    "include_tool_filters",
    "exclude_tool_filters",
    "tools",
    "context",
    "template_path",
    "undefined_behavior",
    "template_functions",
    "enable_template_cache",
    "use_template_sandbox",
    "load_entry_points",
    "name",
    "print_messages",
    "print_messages_mode",
    "print_messages_markdown",
    "litellm_debug",
    "message_validation_mode",
    "enable_signal_handling",
}
