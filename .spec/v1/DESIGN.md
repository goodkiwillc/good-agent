# Good Agent Design Specification

## Core APIs

Basic Usage:

```python
from good_agent import Agent

async with Agent("You are a helpful assistant.") as agent:
    # Async context manager ensures proper async resource management
    agent.append("What is 2+2?")
    resp = await agent.call()
    assert resp.content == "4"

    # Typed, role-aware message history
    assert agent[-1].content == "4"  # last message
    assert agent[-1].role == "assistant"

    assert agent.assistant[-1].content == "4"  # last assistant message
    assert agent.assistant[-1] == agent[-1]

    assert agent.user[-1].content == "What is 2+2?"  # last user message

```

Agent Configuration:

```python

async with Agent(
    "You are a helpful assistant.",

    # initial global context state (can be modified at different scopes)
    # primarily for in-template usage
    context={
        'variable': 'value'
    },
    # register tools
    tools=[

    ],

    # auto-initialized components that can be overridden:
    # config_manager = AgentConfigManager(**config),
    # language_model: LanguageModel | None = None,
    # tool_manager: ToolManager(),
    # agent_context = AgentContext()
    # template_manager = TemplateManager(),
    # mock = AgentMockInterface()

    extensions=[...],  # add components/extensions

    # Agent instance configuration
    model: ModelName ='gpt-4',
    timeout: float | str | Timeout = 30,
    temperature: float = 1.0,
    top_p: float | None = None,
    n: int | None = 1,
    stream_options: dict | None = None,
    stop: str | list[str] | None = None,
    max_completion_tokens: int | None = None,
    max_tokens: int | None = None,
    presence_penalty: float | None = None,
    frequency_penalty: float = None = None,
    logit_bias: dict | None = None,
    user: str | None = None,
    # reasoning_effort: Literal["low", "medium", "high"] #TODO: this is duplicative
    reasoning: ReasoningConfig = {
        'effort': 'medium', # low, medium, high,
        'max_tokens': 1000,
    },
    seed: int | None = None,
    tool_choice: str | dict | None = None,
    parallel_tool_calls: bool = True, # if available
    tool_call_timeout: float | str | Timeout | None = None, # TODO: implement default tool timeout (can be overridden per-tool)

    logprobs: bool | None = None,
    top_logprobs: int | None = None,

    web_search_options: dict | None = None,
    deployment_id: str | None = None,
    extra_headers: dict | None = None,
    instructor_mode: InstructorMode = InstructorMode.PARALELL_TOOLS,
    custom_llm_provider: str | None = None,

    # Provider/client
    base_url: str
    api_version: str
    api_key: str
    model_list: list
    thinking: dict

    # Diagnostics
    debug: bool = False,
    telemetry: bool = True, # TODO: implement
    telemetry_options: dict | None = None, # TODO: implement

    # OpenRouter-specific (OpenAI-compatible via extra_body)
    transforms: list | dict | None = None,
    route: str | None = None,
    models: list[str] | None = None,

    provider: dict | None = None,
    include_reasoning: bool = False,
    usage: dict | None = None,
    top_k: int | None = None,
    repetition_penalty: float | None = None,
    min_p: float | None = None,
    top_a: float | None = None,

    fallback_models: list[str] | None = None, # list of fallback model names (litellm-style). Need to reconcile this with openrouter-specific logic

    mcp_servers: list[str | dict[str, Any]] | None = None,
    include_tool_filters: list[str] | None = None,
    exclude_tool_filters: list[str] | None = None,
    template_path: str = Path('~/.goodagent/templates'),
    undefined_behavior: Literal["strict", "silent", "log"] = "log",
    template_functions: dict[str, Any] | None = None,
    enable_template_cache: bool = True,
    use_template_sandbox: bool = True,
    load_entry_points: bool = True,
    name: str | None = None,
    print_messages: bool = False,
    print_messages_mode: Literal["display", "llm", "raw"] = "display",
    print_messages_role: list[Literal["system", "user", "assistant", "tool"]] | None = None,
    print_messages_markdown: bool | None = None,
    litellm_debug: bool = False,
    message_validation_mode: Literal["strict", "warn", "silent"] = "warn",
    enable_signal_handling: bool = True,
) as agent:

```
