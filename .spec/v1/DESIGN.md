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

## Known Issues

- LiteLLM's background logging worker binds an async queue to the event loop that created the router; under pytest's repeated loop creation this sometimes logs `Task exception was never retrieved ... Queue ... is bound to a different event loop`. The warnings are harmless but noisy; we should either upstream a fix to LiteLLM's logging worker or patch our router wrapper to recreate the queue per loop before release.

Agent Configuration:

```python

async with Agent(
    "You are a helpful assistant.",

    # initial global context state (can be modified at different scopes)
    # primarily for in-template usage
    context={
        'variable': 'value',
        'another_varliable': lambda ctx: 'computed value',
    },
    # register tools
    tools=[
        # supports: Tool instances (from @tool decorator), plain functions, string names of already-registered tools
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
    ...
```



## Structured output (Pydantic/Instructor)
```python
from pydantic import BaseModel
from good_agent import Agent

class Weather(BaseModel):
    temp_c: float
    summary: str

async with Agent("Return JSON matching the schema.") as agent:
    agent.append("Weather tomorrow in Paris")
    result = await agent.call(response_model=Weather)

    if result.output.temp_c > 20:
        agent.append("Will it be warm enough to go to the park?")

    else:
        # too cold for park
        agent.append("Come up with some indoor activities ideas for Paris tomorrow.")

    result2 = await agent.call()
    print(result2.content)

```


## Iterate on each LLM response
```python
from good_agent import Agent, AssistantMessage, ToolMessage,

async def get_ip() -> str:
    return "XXX.XXX.XXX.XXX"

async def get_location(ip: str) -> str:
    return "San Francisco, CA"

async def get_weather(city: str) -> str:
    return f"In {city}, It's sunny and 75 degrees."


async with Agent(
    "You are a helpful assistant",
    tools=[get_ip, get_location, get_weather],
) as agent:
    """
    Each message yielded from execute() can be matched using structural pattern
    matching. Properties of the message can be extracted directly in the match
    statement for easy access.
    """
    agent.append("What's the weather like today?")
    async for message in agent.execute():
        match message:
            # Structural pattern matching with message types
            case ToolMessage(i=i, tool_name=tool_name):
                print(f"{i}: Tool {message.tool_name} output:", message.content)
            case AssistantMessage(i=i, tool_calls=tool_calls):
                if tool_calls:
                    for call in tool_calls:
                        print(f"{i}: Assistant requested tool call:", call.name)
                else:
                    print(f"{i}: Assistant:", message.content)

            case Message(
                i=i,
                role=role,
                content=content,
                tool_response=tool_response,
                ok=ok,
                index=index,
                attempt=attempt,
                retry=retry,
                last_attempt=last_attempt,
                agent=agent,
            ):
                # i: int current iteration loop index
                # role: Literal["system", "user", "assistant", "tool"] role of the message
                # content: message content
                # tool_response: tool response if applicable
                # ok: whether the message was successfully generated
                # index: index of the message in current history context
                # attempt: current attempt number for this message
                # retry: whether this is a retry of a previous message
                # last_attempt: whether this is the last attempt allowed
                # agent: reference to the agent instance
                pass

    # Output:
    """
    0: Assistant requested tool call: get_ip
    1: Tool get_ip output: XXX.XXX.XXX.XXX
    2: Assistant requested tool call: get_location
    3: Tool get_location output: San Francisco, CA
    4: Assistant requested tool call: get_weather
    5: Tool get_weather output: In San Francisco, It's sunny and 75 degrees.
    6: Assistant: The weather in San Francisco today is sunny with a temperature of 75 degrees.
    """

```


### Manipulate Agent State During Iteration
```python
async with Agent(
    "You are a helpful assistant",
    tools=[get_ip, get_location, get_weather],
) as agent:
    agent.append("What's the weather like today?")
    async for message in agent.execute():
        match message:
            case ToolMessage(i=i, tool_name=tool_name):
                print(f"{i}: Tool {message.tool_name} output:", message.content)
                if tool_name == "get_ip":
                    agent.append(
                        """
                        <injected_context>
                            IP Lookup inaccurate, using geolocation instead...
                            User location is: Palo Alto, CA
                        </injected_content>
                        """
                    )
                    print(f"Injected message:\n{agent[-1].content}")
            case AssistantMessage(i=i, tool_calls=tool_calls):
                if tool_calls:
                    for call in tool_calls:
                        print(f"{i}: Assistant requested tool call:", call.name)
                else:
                    print(f"{i}: Assistant:", message.content)

    # Output:
    """
    0: Assistant requested tool call: get_ip
    1: Tool get_ip output: XXX.XXX.XXX.XXX
    Injected message:
    <injected_context>
        IP Lookup inaccurate, using geolocation instead...
        User location is: Palo Alto, CA
    </injected_content>
    2: Assistant requested tool call: get_weather
    3: Tool get_weather output: In Palo Alto, It's sunny and 75 degrees.
    4: Assistant: The weather in Palo Alto today is sunny with a temperature of 75 degrees.
    """
```


## Tools

## Use simple functions as tools directly
```python
from good_agent import Agent

async def calculate(x: int, y: int) -> int:
    """Add two integers together."""
    return x + y

async with Agent("Use tools when helpful.", tools=[calculate]) as agent:
    agent.append("Add 2 and 3")
    await agent.call()
    assert agent[-1].role = "assistant"
    assert agent[-1].content == "5" # final response from agent
    assert agent.assistant[-2].tool_calls[0].name == "calculate"  # tool call record
    assert agent.assistant[-2].tool_calls[0].arguments == {"x": 2, "y": 3}
    assert agent.tools[-1].tool_response.response == 5 # typed tool response
```


### Tool Registration and Dependency Injection
```python
from fast_depends import Depends
from good_agent import Agent, Renderable, tool
from .. import SearchClient, WebFetcher, get_search_client, get_web_fetcher


class SearchResult(Renderable):
    url: str
    title: str | None = None
    content: str | None = None

class SearchResults(Renderable):
    __template__ = '''
    {% for item in items %}
    !# section 'item' url=item.url
       {{item.title}}
       ---
       {{item.content}}
    !# end section
    {% endfor %}
    '''

    items: list[SearchResult]

    # convenience for dictionary-like access
    def __getitem__(self, url: str) -> SearchResult:
        for item in self.items:
            if item.url == url:
                return item
        raise KeyError(url)

@tool
async def search_web(
    query: str,
    limit: int = 5,
    fetch_pages: bool = False,
    search_client: SearchClient = Depends(get_search_client),  # FastAPI-style DI with Fast Depends
    fetcher: WebFetcher = Depends(get_web_fetcher),

    # Also supports automatic dependency injection for Agent components: @TODO: need to document this more
) -> str:
    """Search the web and return results."""
    # Dummy implementation
    results: SearchResults = await search_client.search(query, limit=limit)
    if fetch_pages:
        pages: dict[str, str] = await fetcher.fetch_urls([r.url for r in results.items])
        for url, page in pages.items():
            results[url].content = page

    return ToolResponse(
        response=results
    )


```

## Direct tool invocation (declarative)
Call a tool like any other function, but the agent "remembers" the tool call as if it made the call itself.

```python
# Orchestrate tools without an LLM roundtrip and record them in context
async with Agent(
    "You are a research agent. Search for information and write a report based on the results.",
    tools=[search_web]
) as agent:
    hits = await agent.invoke(search_web, query="python decorators", limit=5, fetch_pages=True)

    assert agent[-1].content == """
    <item url="...">
    Title
    ---
    Text
    </item>
    """
```


### Agent-driven tool calls (LLM decides when to use tools)
```python

async with Agent(
    """
    You are a research agent. Search for information and write a report based on the results.
    """,
    tools=[search_web]
) as agent:
    agent.append("Research python decorators and summarize.")
    response = await agent.call()
    assert response.content.startswith("<item url=")
    assert len(response.tool_response.response.items) == 5
    assert agent[-2].tool_calls[0].name == "search_web"

```


## Component tools (method-based) and auto-registration
```python
from good_agent import Agent, AgentComponent, tool

class Math(AgentComponent):

    async def append_system_prompt(self) -> str:
        return (
            "Always use mul tool to perform multiplication tasks."
        )

    @tool
    def mul(self, x: int, y: int) -> int:
        return x * y

async with Agent("system prompt", extensions=[Math()]) as agent:
    agent.append("Multiply 6 by 7")
    await agent.call()
```


## Component tools (method-based) and auto-registration
```python
from good_agent import Agent, AgentComponent, tool

class Math(AgentComponent):
    @tool
    def mul(self, x: int, y: int) -> int:
        return x * y

    async def append_system_prompt(self) -> str:
        return (
            "Always use mul tool to perform multiplication tasks."
        )

async with Agent("system prompt", extensions=[Math()]) as agent:
    agent.append("Multiply 6 by 7")
    await agent.call()
```


## MCP and registry tools
```python
from good_agent import Agent

async with Agent(
    "Use external tools when available."
) as agent:
    await agent.tools.load_mcp_servers(["my-mcp-server-config"])  # MCP integration
    for name in agent.tools.keys():
        print("tool:", name)
    # Call via invoke for proper context capture
    result = await agent.invoke("server:search", query="latest PRs")
    print(result.response)
```


## Streaming and iterative execution
```python
from good_agent import Agent

async with Agent("Stream a very short story.") as agent:
    agent.append("Tell a 2-sentence story")
    async for message in agent.execute(streaming=True):
        for chunk in message.stream():
            print(chunk, end='', flush=True)

# TODO: add example of instructor-based streaming structured output compilation


```

## Multi‑agent conversations (pipe operator)
```python
from good_agent import Agent

researcher = Agent("Research assistant. Find information online.", name="Researcher")

async with researcher:
    await researcher.call(
        "Do some research on the the best open-source AI frameworks available in 2025."
    )

async with (
    researcher |
    (writer := Agent("Technical writer. Create clear summaries.", name="Writer"))
) as conversation:
        # Automatically wires the two agents together:
        # - Assistant messages from A are delivered to B as user messages
        # - Assistant messages from B are delivered to A as user messages
        # - Ensures both agents are initialized and closed properly

        # append an assistant message -- this is sent to the writer as a user message
        researcher.append("Write a report based on your research findings.", role="assistant")

        async for message in conversation.execute():
            match message:
                case Message(agent=researcher):
                    print(f"[Researcher] {message.content}")
                case Message(agent=writer):
                    print(f"[Writer] {message.content}")

```

## Concurrency: AgentPool
```python
from good_agent.pool import AgentPool
from good_agent import Agent

pool = AgentPool([Agent("You help.") for _ in range(3)])
# Distribute work: pool[i].call(...)
```

## Components: hooks, suites, and shared state
```python
from good_agent import Agent, CitationManager, TaskManager

# Components can modify messages/tool calls and maintain shared state
cites = CitationManager()           # maps URLs -> indices; presents [!CITE_{x}!] to LLM
tasks = TaskManager()               # exposes todo tools and renders task state into context

async with Agent("Research with citations and todos.", extensions=[cites, tasks]) as agent:
    # Use component tools directly via invoke
    await agent.invoke("create_list", name="plan", items=["search", "summarize"])
    agent.append("Research Python pattern matching; cite sources.")
    await agent.call()
```

### Component “suites” of tools (e.g., AgentSearch)
```python
from good_agent import Agent, AgentSearch

async with Agent("Use search tools where needed.", extensions=[AgentSearch()]) as agent:
    await agent.tools["search"](_agent=agent, query="vector databases", limit=5)
    await agent.tools["trending_topics"](_agent=agent)
```


## Rich templating and context providers
```python
from good_agent import Agent, Template, global_context_provider

@global_context_provider("timestamp")
def now():
    import datetime; return datetime.datetime.utcnow().isoformat()

tmpl = Template("You are {{ role }}; time={{ timestamp }}")
async with Agent(tmpl.render(role="assistant")) as agent:
    agent.append("Say hi with time")
    await agent.call()
```

## Stateful Resources

```python

from good_agent import Agent
from good_agent.resources import EditableYAML

file = EditableYAML('config.yaml')
"""
config.yaml
---
setting1: value1
setting2: value2
options:
    - opt1
    - opt2
    - opt3
"""

async with Agent(
    "system prompt",
) as agent:

    async with file(
        agent,
        context_mode='full', # 'full' = all tool calls, 'final' = only final state, 'delta' = only changes
    ): # swaps in read/update/insert/delete tools
        await agent.call(
            '''
            Update config.yaml to add setting3 with value3, and add opt4 to the options list.
            '''
        )
        await file.save('config.yaml')


###
# as a tool that

@tool
async def modify_file(
    path: str,
    agent: Agent = Context()
):
    '''
    Call this tool if you need to modify a specific file in any way. Calling this tool will make other tools for file manipulation available to you.
    '''

    file = EditableYAML.open(path)

    async with file(
        agent,
        context_mode='final', # 'full' = all tool calls, 'final' = only final state, 'delta' = only changes
    ): # swaps in read/update/insert/delete tools
        await agent.call(
            '''
            Make desired changes to the file.
            '''
        )
        await file.save(path)


```

Stateful resources allow an agent to interact with an object with external state over multiple steps with a narrowly defined set of methods. The resource manages the state and provides tools to the agent to manipulate the resource. At the end of the interaction, the resource's state can be persisted or otherwise utilized, and the agent can continue, either will the full history of interactions or just the final state (or something else).



# Agent Modes

```python
agent = Agent(
    'system prompt',
    model='gpt-4',
    tools=[...]
)

@agent.modes.add('code-review')
async def code_review(
    agent: Agent
):

    code_review_toolkit = [
        BashTool(),
        FileReaderTool(),
        CodeAnalyzerTool(),
    ]

    with agent.context(
        append_system_prompt='''
        !# section mode type='code-review'
            Agent in code review mode.
            - Only read and analyze code.
            - Do not write or modify code.
            - You may write markdown or reference files as needed.
        !# section end
        ''',
        tools=code_review_toolkit
    ):

        agent.append(
            '''
            Analyze the codebase in your environment `{{cwd}}`.
            '''
        )

        # passes control back to the caller to manage the agent lifecycle
        yield agent

        # mandate final review write-up
        await agent.call(
            'Make sure you have written any of your findings to a file called REVIEW.md'
        )

        # any cleanup logic can go here


async with agent:

    with agent.mode('code-review') as code_reviewer: # yielded from mode function
        pass

###

async with agent.mode('code-review') as code_reviewer:
    pass


agent.modes.list()  # ['code-review']


```

# Commands
Interative shortcuts for specific prompting patterns and workflows.

```python
from good_agent import Agent, command

agent = Agent(
    'system prompt',
    model='gpt-4',
    tools=[...]
)

agent.commands.add(
    'pytester',
    description='Run pytest',
    prompt='''
    Run pytest on {{directory}} and analyze the results.

    Instructions:
     - Run tests
     - Analyze failures
     - Fix code

    {{input}}
    ''',
    parameters={
        'directory': {
            'type': 'string',
            'description': 'Directory to run pytest in',
            'default': '.',
        },
    }
)

###

# Simple command registration via dectorator - default doesn't even need to take arguments and can just use docstrings

@command(
    name='code_auditor',
    description='Audit code for style and best practices.',
)
async def code_auditor_command():
    """
    Audit code in the specified directory for style and best practices.
    """


###

# Command can also take arguments
@command(
    name='format_code',
    description='Format code using black.',
)
async def format_code_command(
    directory: Path = Context('cwd'),
    agent: Agent = Context()  # DI of agent instance
):
    """
    Format code using black in the specified directory.
    """
    # Dummy implementation
    import subprocess

    subprocess.run(['black', str(directory)])
    return f"Code formatted using black in {directory}"


# File-based commands

agent = Agent(
    'system prompt',
    model='gpt-5',
    commands_directory='./commands',
    tools=[...]
)

```
 - commands/
    - pytester.md
    - code_auditor.md
    - format.sh
    - researcher.py

pytester.md
```markdown
---
name: pytester
description: Run pytest.
parameters:
  directory:
    type: string
    description: Directory to run pytest in
    default: .
---
Run pytest on {{directory}} and analyze the results.

Instructions:
 - Run tests
 - Analyze failures
 - Fix code

{{input}}
```

format.sh
```bash
#!/bin/env bash
# Format code using black
black $directory

echo "Code formatted using black in $directory"

```


researcher.py

```python
# single-file dependencies?
from good_agent import Agent, tool, command

@tool
async def research_topic(topic: str) -> str:
    '''Research a topic and return a summary.'''
    # Dummy implementation
    return f"Research summary for {topic}."


@command(
    name='researcher',
    description='Research a topic and summarize findings.',
)
async def researcher_command(
    agent: Agent,
    topic: str,
):
    summary = await agent.invoke(research_topic, topic=topic)
    agent.append(f"Research summary:\n{summary.response}")
    return agent

```

Invoked in a chat session:

```bash
 > /pytester directory='./my_project' pay attention to edge cases

```

# Sub-Agents

```python

from good_agent import Agent

parent_agent = Agent(
    'system prompt for parent agent',
    model='gpt-4',
    tools=[...]
)



```

## Agent Components

```python

from good_agent import Agent, AgentComponent, tool


class CitationManager(AgentComponent):
    def __init__(self):
        pass


    async def append_system_prompt(self) -> str:
        ...

    async def before_tool_call(
        self,
        agent: Agent,
        tool_name: str,
        arguments: dict,
    ):
        pass

    async def after_tool_call(
        self,
        agent: Agent,
        tool_name: str,
        arguments: dict,
        tool_response: Any,
    ):
        pass

    async def before_user_message(
        self,
        agent: Agent,
        message: str,
        context: dict,
        response_model: type | None,
    ):
        pass

    async def after_assistant_message(
        self,
        agent: Agent,
        message: Message,
    ):
        pass

    ... # other hooks as needed


```

# Launch Agent Interactively via CLI

```python

from good_agent import Agent, tool
from good_agent.components import BashTool, FileReaderTool

agent = Agent(
    "You are an interactive assistant. Use tools as needed.",
    tools=[
        BashTool(),
        FileReaderTool(),
        # other tools...
    ],
    model='gpt-4',
)


@agent.modes.add(
    'code-review'
)
async def code_review_mode(
    agent: Agent
):
    with agent.context(
        append_system_prompt='''
        !# section mode type='code-review'
            Agent in code review mode.
            - Only read and analyze code.
            - Do not write or modify code.
            - You may write markdown or reference files as needed.
        !# section end
        ''',
        tools=[
            BashTool(),
            FileReaderTool(),
            # other code review specific tools...
        ]
    ):

        yield agent


class FollowUpQuestions(Renderable):
    __template__ = '''
    Before we begin, please answer these questions:
    {% for question in questions %}
    - {{ question }}
    {% endfor %}
    '''
    have_questions: bool
    questions: list[str]

@agent.modes.add('planner')
async def planner_mode(agent: Agent):
    with agent.context(
        append_system_prompt='''
        !# section mode type='planner'
            Agent in planner mode.
            - Focus on high-level task planning.
            - Use tools to gather information as needed.
        !# section end
        ''',
        tools=[
            # planner specific tools...
        ]
    ):

        async with agent.fork() as subagent:
            response = await subagent.call(
                f'''
                Based on the user's request, do you have any follow-up questions to clarify the task before proceeding?
                ''',
                response_model=FollowUpQuestions
            )

            if response.output.have_questions:
                # user input generates assistant message and blocks until answered (assuming interactive mode) - will raise if non-interactive
                response = await agent.user_input(
                    response.output # Renderable instance can be passed directly
                )


        yield agent



agent.commands.add(
    'pytester',
    description='Run pytest',
    prompt='''
    Run pytest on {{directory}} and analyze the results.

    Instructions:
     - Run tests
     - Analyze failures
     - Fix code

    {{input}}
    ''',
    parameters={
        'directory': {
            'type': 'string',
            'description': 'Directory to run pytest in',
            'default': '.',
        },
    }
)

```

## With stateful resource integration.

```python
from good_agent import Agent
from good_agent.resources import PlanningDocument

# modes

@agent.modes.add(
    'with-plan',
    create_isolated_context=True,
    append_system_prompt='''
    !# section mode type='with-plan'
        You are operating in planning mode.
        - Use the provided plan to guide your actions.
        - Refer to the plan as needed.
    !# section end
    '''
)
async def planning_mode(
    agent: Agent,
    plan: PlanningDocument = Context('current_plan') # the plan doc is required - should already have been created - do we need some kind of state or predicate check?
):
    with agent.context(
        ...
    ):
        # read plan
        await agent.invoke(plan.read)

        await agent.call(
            'Based on the planning document, create a todo list of your immediate next steps.',
            tools=[agent[ToDoManager].create_todo_list],
            force_tool_use=True,
        )

        """
        @TODO/Note:
         - we have .invoke which calls a tool directly and records it in context
         - we have .call which lets the LLM decide to use tools
         - do we want a .execute which yields each message (like multi-agent) but within the same agent?
         - do we have a method that forces the llm to call a tool (like force_tool_use above) but allows for the currying of specific tool arguments - the agent would either not see those parameters or the type signature would change to show single Literal values for those parameters (i.e. only one possible value)

         what could this method be? (brainstorm ideas)
            agent.execute_tool_call(tool_name: str, /, **curried_arguments) -> AsyncIterator[Message]:

            agent.make_tool_call(tool_name: str, /, **curried_arguments) -> ToolResponse:

            agent.run_tool_call(tool_name: str, /, **curried_arguments) -> ToolResponse:

        """

        await agent.call(
            'Now, execute the next steps from your todo list.',
        )

        yield agent

        # verify acceptance criteria met

        async with plan(agent):
            # plan as stateful resource, overrides toolset within context

            await agent.call(
                'Review the planning document and update it based on the work completed. Make sure the acceptance criteria have been met for each task before checking it off. If something is missing/incomplete, add notes/update the pan accordingly so that work can be completed in the next session.'
            )




```


```bash
good-agent run module.path:agent -i


```


## Human-in-the-loop interactions

### Design goals

- Support interactive pauses without assuming a local TTY; callers should be able to satisfy a prompt via CLI, UI, API callback, or another agent.
- Provide deterministic orchestration semantics in multi-agent graphs: the requesting agent pauses, while the orchestrator decides whether the rest of the graph should continue.
- Allow declarative policies (auto-continue, require explicit approval, custom validators) and rich payloads (Renderable prompts, schemas, metadata).
- Ensure that every human step is auditable with structured records that can be replayed or stubbed for testing.

### Interaction primitives

```python
class InteractionRequest(Renderable):
    id: str
    agent_name: str | None
    prompt: Renderable | str
    schema: BaseModel | type | None = None
    metadata: dict[str, Any] = {}
    blocking_policy: Literal["agent", "graph", "none"] = "agent"
    timeout: float | None = None

class InteractionResult(Renderable):
    id: str
    content: str | Renderable | None
    data: Any | None  # typed response when schema provided
    responder: Literal["user", "agent", "auto"]
    metadata: dict[str, Any] = {}
```

- `blocking_policy="agent"` pauses only the requesting agent; other agents continue unless the orchestrator escalates.
- `blocking_policy="graph"` signals the orchestrator to pause all linked agents (default for critical approvals).
- `blocking_policy="none"` emits a notification but does not await a response; the agent can watch for an eventual `InteractionResult` via callbacks/futures.

### Agent API

```python
class Agent:
    async def user_input(
        self,
        prompt: str | Renderable | InteractionRequest,
        *,
        schema: type[BaseModel] | None = None,
        blocking_policy: Literal["agent", "graph", "none"] | None = None,
        context: dict[str, Any] | None = None,
    ) -> InteractionResult:
        ...

    @contextmanager
    def interaction_policy(...):
        """Override default blocking/approval behavior for a scope."""

    async def submit_interaction_result(self, result: InteractionResult):
        """Called by orchestrators/UI to resume a pending request."""
```

- Passing an `InteractionRequest` instance allows advanced callers to set IDs, metadata, or custom blocking policies.
- `schema` enables typed responses; when provided, `result.data` contains parsed output while `result.content` retains the raw string.
- `submit_interaction_result` lets non-interactive workflows inject answers (e.g., another agent mediating the request).

### Interaction manager

```python
class InteractionManager:
    async def request(self, agent: Agent, req: InteractionRequest) -> InteractionResult:
        ...

    async def resolve(self, result: InteractionResult) -> None:
        ...

    def subscribe(self, callback: Callable[[InteractionRequest], Awaitable[None]]):
        ...
```

- Default implementation surfaces prompts to the CLI/GUI; advanced deployments can override to route through queues, Slack, or other agents.
- Subscriptions make it easy to layer auditing/logging without coupling to presentation.

### Multi-agent orchestration

```python
async with (researcher | writer) as convo:
    async for message in convo.execute():
        match message:
            case InteractionRequest(agent=researcher, blocking_policy="agent"):
                # only researcher paused; writer keeps going
                await ui.present(message)
            case InteractionRequest(blocking_policy="graph"):
                convo.pause_all()
                await escalate(message)
```

- The pipe/orchestrator receives `InteractionRequest` events in the same stream as messages; it decides whether to honor the requested blocking policy or override it.
- Agents awaiting a response get a Future tied to the request ID; once `InteractionManager.resolve` fires, only that agent resumes.
- Non-blocking requests (`blocking_policy="none"`) still produce a Future the agent can await later (e.g., `await agent.interactions.wait(id)`), allowing background approval flows.

### Non-interactive + testing

- `Agent(mock=AgentMockInterface(user_inputs=[...])))` or context-local `interaction_policy(auto_responder=...)` lets tests provide canned answers.
- For batch jobs, attach an auto-responder that either raises (to fail fast when human input is required) or supplies deterministic defaults.
- Interaction transcripts (`InteractionRequest` + `InteractionResult`) are appended to history as `role="user"`/`role="assistant"` pairs with an additional `source="human"` flag so retries/rewrites remain deterministic.

### Error handling

- Timeouts raise `InteractionTimeoutError(agent_name, request_id)`; orchestrators can catch and decide to retry, abort, or auto-resolve.
- `InteractionValidationError` is raised when schema validation fails; the request is re-sent with validation messages appended via `metadata["errors"]`.
- Cancellation (`agent.cancel_interaction(id)`) notifies the orchestrator/UI and unblocks the agent with `responder="auto"` and `data=None`.


WIP Concepts:

## Typesafe Templates

```python

from good_agent import Template, Agent

tmpl = Template(
    'Hello, {{ name }}! Today is {{ day_of_week }}.',
    parameters={
        'name': str,
        'day_of_week': str,

    }
)
