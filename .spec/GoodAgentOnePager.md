# Good Agent


## Quickstart
```python
from goodintel_agent import Agent

async with Agent("You are a helpful assistant.") as agent:
    agent.append("What is 2+2?")
    resp = await agent.call()
    assert resp.content == "4"

    # Typed, role-aware message history
    assert agent[-1].content == "4"  # last message
    assert agent.assistant[-1].content == "4"  # last assistant message
    assert agent.user[-1].content == "What is 2+2?"  # last user message

# Configuration

async with Agent(
    "You are a helpful assistant.",
    model="gpt-4o",  # specify model
    context={
        'variable': 'value'  # provide context variables
    },
    tools=[...],  # register tools
    extensions=[...],  # add components/extensions
) as agent:

```


## Structured output (Pydantic)
```python
from pydantic import BaseModel
from goodintel_agent import Agent

class Weather(BaseModel):
    temp_c: float
    summary: str

async with Agent("Return JSON matching the schema.") as agent:
    agent.append("Weather tomorrow in Paris")
    result = await agent.call(response_model=Weather)
    print(result.output.temp_c, result.output.summary)
    # Can continue longer interactions; structured output just for this turn
    agent.append("Summarize that in one sentence")
    await agent.call()
```


## Iterate on each LLM response
```python
from goodintel_agent import Agent, AssistantMessage, ToolMessage,

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
            case ToolMessage(i=i, tool_name=tool_name):
                print(f"{i}: Tool {message.tool_name} output:", message.content)
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
from goodintel_agent import Agent

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
from goodintel_agent import Agent, Renderable, tool
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


## Direct tool invocation (preferred, declarative)

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
from goodintel_agent import Agent, AgentComponent, tool

class Math(AgentComponent):
    @tool
    def mul(self, x: int, y: int) -> int:
        return x * y

async with Agent("Use mul for multiplication.", extensions=[Math()]) as agent:
    agent.append("Multiply 6 by 7")
    await agent.call()
```


## Component tools (method-based) and auto-registration
```python
from goodintel_agent import Agent, AgentComponent, tool

class Math(AgentComponent):
    @tool
    def mul(self, x: int, y: int) -> int:
        return x * y

async with Agent("Use mul for multiplication.", extensions=[Math()]) as agent:
    agent.append("Multiply 6 by 7")
    await agent.call()
```

## MCP and registry tools
```python
from goodintel_agent import Agent

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


## Events (observe/steer lifecycle)
```python
from goodintel_agent import Agent, AgentEvents
from goodintel_agent.events.types import ToolCallAfterParams
from goodintel_core.utilities.event_router import EventContext

async with Agent("Log tool calls") as agent:
    @agent.on(AgentEvents.TOOL_CALL_AFTER)
    async def on_tool(ctx: EventContext[ToolCallAfterParams, None]) -> None:
        tool = ctx.parameters.get("tool_name")
        success = ctx.parameters.get("success", False)
        print(f"Tool: {tool}, success={success}")
    agent.append("Say hi")
    await agent.call()
```

## Streaming and iterative execution
```python
from goodintel_agent import Agent

async with Agent("Stream a very short story.") as agent:
    agent.append("Tell a 2-sentence story")
    async for msg in agent.execute(streaming=True):
        match msg:
            case Agent.AssistantMessage(tool_calls=tool_calls) if tool_calls:
                print("Assistant requested tools:", [tc.name for tc in tool_calls])
            case Agent.ToolMessage() as tool_msg:
                print("Tool result:", tool_msg.content)
            case Agent.AssistantMessage() as a:
                print("Assistant:", a.content)
```

## Multi‑agent conversations (pipe operator)
```python
from goodintel_agent import Agent

async with Agent("You are A") as a, Agent("You are B") as b:
    async with a | b:
        # Inside this context:
        # - Assistant messages from A are delivered to B as user messages
        # - Assistant messages from B are delivered to A as user messages

        # A talks to B
        a.append("Hello B, please introduce yourself.", role="assistant")
        await b.call()  # B sees the above as role="user" and responds

        # B asks A to do something
        b.append("Summarize the last exchange.", role="assistant")
        await a.call()  # A sees the above as role="user" and responds
```

## Resource‑scoped editing (MDXL)
```python
from goodintel_agent import Agent, EditableMDXL
from goodintel_core.mdxl import MDXL

doc = MDXL.from_string("<document><summary>draft</summary></document>")
async with Agent("Use provided tools to edit the doc.") as agent:
    res = EditableMDXL(doc)
    async with res(agent):  # swaps in read/update/insert/delete tools
        await agent.invoke("update_element", xpath="//summary", new_content="final")
print(doc.llm_outer_text)
```
Notes:
- Stateful resources enable precise edits without polluting the main convo.
- MDXL shipped; EditableYAML and other types follow the same pattern.

## Components: hooks, suites, and shared state
```python
from goodintel_agent import Agent, CitationManager, TaskManager

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
from goodintel_agent import Agent, AgentSearch

async with Agent("Use search tools where needed.", extensions=[AgentSearch()]) as agent:
    await agent.tools["search"](_agent=agent, query="vector databases", limit=5)
    await agent.tools["trending_topics"](_agent=agent)
```

## Rich templating and context providers
```python
from goodintel_agent import Agent, Template, global_context_provider

@global_context_provider("timestamp")
def now():
    import datetime; return datetime.datetime.utcnow().isoformat()

tmpl = Template("You are {{ role }}; time={{ timestamp }}")
async with Agent(tmpl.render(role="assistant")) as agent:
    agent.append("Say hi with time")
    await agent.call()
```

## Mocking for development
```python
from goodintel_agent import Agent, AgentMockInterface, MockResponse

mock = AgentMockInterface()
mock.queue(MockResponse.message("assistant", "Hello (mocked)"))

async with Agent("Test", extensions=[mock]) as agent:
    agent.append("Hi")
    print((await agent.call()).content)  # -> Hello (mocked)
```


## Agent‑as‑Tool (compose specialists)
```python
from goodintel_agent import Agent, tool

def wrap_agent_as_tool(name: str, specialist: Agent):
    @tool(name=name)
    async def call_specialist(prompt: str) -> str:
        specialist.append(prompt)
        return (await specialist.call()).content
    return call_specialist

async with Agent("Coordinator") as orchestrator, Agent("You are a Python expert.") as py:
    # Register as a tool and call via invoke
    orchestrator.tools["python_expert"] = wrap_agent_as_tool("python_expert", py)
    orchestrator.append("Ask python_expert to explain contextvars in 1 line")
    await orchestrator.call()
```


## Concurrency: AgentPool
```python
from goodintel_agent.pool import AgentPool
from goodintel_agent import Agent

pool = AgentPool([Agent("You help.") for _ in range(3)])
# Distribute work: pool[i].call(...)
```
