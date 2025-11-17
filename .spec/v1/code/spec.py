# ruff: noqa
import logging
import warnings

import pytest

from good_agent import Agent, AssistantMessage, Message, ToolMessage
from good_agent.core.models import Renderable

logger = logging.getLogger(__name__)

from types import SimpleNamespace


@pytest.fixture
def tools():
    async def get_ip() -> str:
        return "XXX.XXX.XXX.XXX"

    async def get_location(ip: str) -> str:
        return "San Francisco, CA"

    async def get_weather(city: str) -> str:
        return f"In {city}, It's sunny and 75 degrees."

    # Return as namespace for dot notation
    return SimpleNamespace(
        get_ip=get_ip, get_location=get_location, get_weather=get_weather
    )


class TestBasicUsage:
    async def test_basic_use(self):
        async with Agent("You are a helpful assistant.") as agent:
            resp = await agent.call("What is 2+2?")
            logger.info(resp)
            assert "4" in resp.content

            # Typed, role-aware message history
            assert "4" in agent[-1].content

            assert (
                agent[-1] == agent.assistant[-1]
            )  # last assistant message is last message

            assert agent.user[-1].content == "What is 2+2?"  # last user message

    async def test_basic_usage_with_templates(self):
        async with Agent(
            "You are a helpful assistant.",
            context={"name": "Alice"},
        ) as agent:
            resp = await agent.call(
                "Greet user `{{ name }}` using the template 'Hello, [NAME]!'"
            )
            logger.info(resp)
            assert resp.content == "Hello, Alice!"

    async def test_structured_output(self):
        from pydantic import BaseModel

        class Weather(BaseModel):
            temp_c: float
            summary: str

        async with Agent("Return JSON matching the schema.") as agent:
            message = await agent.call(
                "Weather tomorrow in Paris", response_model=Weather
            )

            assert isinstance(message.output, Weather)

            logger.info(f"Received weather: {message.content}")
            logger.info(
                f'Weather: temp_c={message.output.temp_c}, summary="{message.output.summary}"'
            )
            # Can continue longer interactions; structured output just for this turn
            message = await agent.call("Is that warm for Paris at this time of year?")

            logger.info(message)

    async def test_simple_tool_use(self):
        async def calculate(x: int, y: int) -> int:
            """Add two integers together."""
            return x + y

        async with Agent("Use tools when helpful.", tools=[calculate]) as agent:
            agent.append("Add 2 and 3")
            await agent.call()
            assert agent[-1].role == "assistant"
            assert agent[-1].content == "5"  # final response from agent
            # agent.assistant
            assert (
                agent.assistant[-2].tool_calls
                and agent.assistant[-2].tool_calls[0].name == "calculate"
            )  # tool call record
            assert agent.assistant[-2].tool_calls and agent.assistant[-2].tool_calls[
                0
            ].parameters == {"x": 2, "y": 3}
            assert (
                # agent.tools[-1].tool_calls and
                agent.tool[-1].tool_response == 5
            )

    async def test_basic_tool_usage(self, tools):
        from good_agent import Agent, AssistantMessage, ToolMessage

        async with Agent(
            "You are a helpful assistant",
            tools=[tools.get_ip, tools.get_location, tools.get_weather],
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
                        logger.info(f"{i}: Tool {tool_name} output:", message.content)
                    case AssistantMessage(i=i, tool_calls=tool_calls):
                        if tool_calls:
                            for call in tool_calls:
                                logger.info(
                                    f"{i}: Assistant requested tool call:", call.name
                                )
                        else:
                            logger.info(f"{i}: Assistant:", message.content)

    async def test_manipulate_agent_state_iteration(self, tools):
        async with Agent(
            "You are a helpful assistant",
            tools=[tools.get_ip, tools.get_location, tools.get_weather],
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

    async def test_agent_fork(self):
        async with Agent("You are a helpful assistant.") as agent:
            agent.append("What is the capital of France?")
            response1 = await agent.call()
            logger.info("Original agent response:", response1.content)

            # Fork the agent
            forked_agent = agent.context_manager.fork()
            forked_agent.append("What is the capital of Germany?")
            response2 = await forked_agent.call()
            logger.info("Forked agent response:", response2.content)

            assert response1.content == "The capital of France is Paris."
            assert response2.content == "The capital of Germany is Berlin."
            assert len(agent.messages) == 2  # original agent has 2 messages
            assert len(forked_agent.messages) == 4  # forked agent has its

    async def test_agent_copy(self):
        async with Agent("You are a helpful assistant.") as agent:
            agent.append("What is the capital of Italy?")
            response1 = await agent.call()
            logger.info("Original agent response:", response1.content)

            # Copy the agent
            copied_agent = agent.context_manager.copy()

            # agent.context_manager.copy(
            # include_system=True,
            # include_tools=True,
            # components="persist", # initialize
            # ) # just initial config

            copied_agent.append("What is the capital of Spain?")
            response2 = await copied_agent.call()
            logger.info("Copied agent response:", response2.content)

            assert response1.content == "The capital of Italy is Rome."
            assert response2.content == "The capital of Spain is Madrid."
            assert len(agent.messages) == 2  # original agent has 2 messages
            assert len(copied_agent.messages) == 2

    async def test_agent_filtered_messages(self):
        agent = Agent("")

        # last place it can be customized
        await agent.call(
            message_indexer=lambda message, agent: True,
        )

        await agent.call(
            include="message_match_pattern*.", exclude="mesage match pattern"
        )

        async def truncate(message: Message) -> Message:
            return message.copy_with(
                content=message.content[:10] + "..."
                if message.content and len(message.content) > 10
                else message.content
            )

        await agent.call(
            transforms={
                '//message[@role="tool" and rindex>10 ]': lambda message: truncate(
                    message
                )
            }
        )

        # with agent.tranforms(
        #     transforms
        # ):


class SearchResult(Renderable):
    url: str
    title: str | None = None
    content: str | None = None


class SearchResults(Renderable):
    __template__ = """
    {% for item in items %}
    !# section 'item' url=item.url
    {{item.title}}
    ---
    {{item.content}}
    !# end section
    {% endfor %}
    """

    items: list[SearchResult]

    # convenience for dictionary-like access
    def __getitem__(self, url: str) -> SearchResult:
        for item in self.items:
            if item.url == url:
                return item
        raise KeyError(url)


@pytest.fixture
def search_web():
    from fast_depends import Depends

    from good_agent import tool

    class SearchClient:
        async def search(self, query: str, limit: int = 5) -> SearchResults:
            # Dummy implementation
            results = SearchResults(
                items=[
                    SearchResult(
                        url=f"https://example.com/result-{i}",
                        title=f"Result {i} for {query}",
                        content=f"This is the content of result {i}.",
                    )
                    for i in range(1, limit + 1)
                ]
            )
            return results

    class WebFetcher:
        async def fetch_urls(self, urls: list[str]) -> dict[str, str]:
            # Dummy implementation
            return {url: f"Full content of {url}" for url in urls}

    def get_search_client() -> SearchClient:
        return SearchClient()

    def get_web_fetcher() -> WebFetcher:
        return WebFetcher()

    @tool(register=False, name="search_web")
    async def search_web_tool(
        query: str,
        limit: int = 5,
        fetch_pages: bool = False,
        search_client: SearchClient = Depends(
            get_search_client
        ),  # FastAPI-style DI with Fast Depends
        fetcher: WebFetcher = Depends(get_web_fetcher),
    ) -> SearchResults:
        """Search the web and return results."""
        # Dummy implementation
        results: SearchResults = await search_client.search(query, limit=limit)
        if fetch_pages:
            pages: dict[str, str] = await fetcher.fetch_urls(
                [r.url for r in results.items]
            )
            for url, page in pages.items():
                results[url].content = page

        return results

    return search_web_tool


class TestToolAdvancedFeatures:
    async def test_tool_registration_dependency_injection(self, search_web):
        logger.info(search_web)

        async with Agent(
            "You are a research agent. Search for information and write a report based on the results.",
            tools=[search_web],
        ) as agent:
            hits = await agent.tool_calls.invoke(
                search_web, query="python decorators", limit=5, fetch_pages=True
            )

            logger.info(hits)

            assert isinstance(hits.response, SearchResults)

    async def test_agent_driven_tool_calls(self, search_web):
        async with Agent(
            """
            You are a research agent. Search for information and write a report based on the results.
            """,
            tools=[search_web],
        ) as agent:
            agent.append("Research python decorators and summarize.")

            async for message in agent.execute():
                match message:
                    case ToolMessage():
                        if message.tool_response:
                            assert len(message.tool_response.response.items) == 5


class TestComponents:
    async def test_hooks_suites_shared_state(self):
        from good_agent import Agent, CitationManager, TaskManager

        # Components can modify messages/tool calls and maintain shared state
        cites = CitationManager()  # maps URLs -> indices; presents [!CITE_{x}!] to LLM
        tasks = TaskManager()  # exposes todo tools and renders task state into context

        async with Agent(
            "Research with citations and todos.", extensions=[cites, tasks]
        ) as agent:
            # Use component tools directly via invoke
            await agent.tool_calls.invoke(
                "create_list", name="plan", items=["search", "summarize"]
            )
            agent.append("Research Python pattern matching; cite sources.")
            await agent.call()

    async def test_component_tools_method_registration(self):
        from good_agent import AgentComponent, tool

        class Math(AgentComponent):
            @tool
            def mul(self, x: int, y: int) -> int:
                return x * y

        async with Agent("Use mul for multiplication.", extensions=[Math()]) as agent:
            agent.append("Multiply 6 by 7")
            response = await agent.call()
            assert response
            logger.info(response)


class TestEventLifecycle:
    async def test_basic_event_hooks(self):
        from good_agent import Agent, AgentEvents
        from good_agent.events.types import ToolCallAfterParams
        from good_agent.core.event_router import EventContext

        async with Agent("Log tool calls") as agent:
            _on_tool_called_invoked = False

            @agent.on(AgentEvents.TOOL_CALL_AFTER)
            async def on_tool(ctx: EventContext[ToolCallAfterParams, None]) -> None:
                tool = ctx.parameters.get("tool_name")
                success = ctx.parameters.get("success", False)
                nonlocal _on_tool_called_invoked
                _on_tool_called_invoked = True
                print(f"Tool: {tool}, success={success}")

            agent.append("Say hi")
            await agent.call()

            assert _on_tool_called_invoked


class TestAgentStreamingMode:
    async def test_agent_streaming_basic(self):
        warnings.warn("This doesn't properly test streaming behavior yet.", UserWarning)
        async with Agent("Tell me a very short story.") as agent:
            agent.append("Tell a 2-sentence story")
            async for msg in agent.execute(streaming=True):
                match msg:
                    case AssistantMessage(tool_calls=tool_calls) if tool_calls:
                        print(
                            "Assistant requested tools:", [tc.name for tc in tool_calls]
                        )
                    case ToolMessage(content=content):
                        print("Tool result:", content)
                    case AssistantMessage() as a:
                        print("Assistant:", a.content)


class TestMultiAgentConversations:
    async def test_basic_two_agent_conversation(self):
        async with (a := Agent("You are Agent A")) | (
            b := Agent("You are Agent B")
        ) as conversation:
            assert a, b
            a.append("Hello B, please introduce yourself.", role="assistant")
            async for message in conversation.execute():
                match message:
                    case Message(agent=a, content=content):
                        print(f"Agent {a.name} says:", content)
                    case Message(agent=b, content=content):
                        print(f"Agent {b.name} says:", content)


class TestResourceScopedEditing:
    async def test_editable_mdlx(self):
        from good_agent import Agent, EditableMDXL
        from good_agent.core.mdxl import MDXL

        doc = MDXL("<document><summary>draft</summary></document>")
        async with Agent("Use provided tools to edit the doc.") as agent:
            res = EditableMDXL(doc)
            async with res(agent):  # swaps in read/update/insert/delete tools
                await agent.tool_calls.invoke(
                    "update_element", xpath="//summary", new_content="final"
                )
        print(doc.llm_outer_text)


class TestAgentAsTool:
    async def test_agent_as_tool_basic(self):
        from good_agent import Agent

        search_agent = Agent(
            "You are a search agent. Given a query, return a list of relevant URLs."
        )

        async with Agent("You are a research agent.", tools=[search_agent]) as agent:
            response = await agent.call("Find URLs about good agent design.")
            logger.info(response)


class TestAgentPool:
    def test_agent_pool_basic(self):
        from good_agent import Agent
        from good_agent.pool import AgentPool

        pool = AgentPool([Agent("You help.") for _ in range(3)])
        assert len(pool) == 3


class TestAgentPipeline:
    async def test_agent_pipeline_setup(self):
        agent = Agent("You are a helpful assistant")

        @agent.pipeline  # is pipeline the best name?
        async def start_conversation(agent: Agent):
            pass

    async def test_orchestrated_agent(self):
        from typing import Literal
        from pydantic import BaseModel

        agent = Agent()

        class DecisionModel(BaseModel):
            category: Literal["a", "b", "c"]

        @agent.then  # what's our router paradigm here?
        async def inital_research(
            agent: Agent,  # always ready
        ):
            agent[-1]  # message

            agent.append("Add message to context")

            async with (
                agent | (sub_agent := Agent("Search agent"))
                # conversation ensures agents ready
            ) as conversation:
                async for message in conversation.execute():
                    # Note: Message doesn't have a parent attribute in current implementation
                    # This is example/spec code showing desired API
                    match message:
                        case Message():  # type: ignore[misc]
                            pass
                        case Message():  # type: ignore[misc]
                            pass

            message = await agent.call(response_model=DecisionModel)

            if message.output.category == "a":
                # do something

                tool_response = await agent.tool_calls.invoke("tool_name", key="value", test=100)

                async with agent.context_manager.fork(
                    True,  # This API may change - spec/example code
                    system_message="system message",
                    compact_convesation="",
                ) as forked_subagent:
                    await forked_subagent.call()  # Must await async call

                message = await agent.call()

            elif message.output.category == "b":
                # do something else

                message = await agent.call()


class TestAgentRouting:
    async def test_agent_routing_basic(self):
        from good_agent import Agent

        agent = Agent("You are a helpful assistant.")

        # @agent.router

        # Note: This routing API is speculative/example code
        # agent.route() and agent.next() don't exist in current implementation
        
        @agent.route("/init")  # type: ignore[attr-defined]
        async def on_init(agent: Agent):
            agent.append("Hello! How can I assist you today?")

            return agent.next("mode")  # type: ignore[attr-defined]

        @agent.route("/mode")  # type: ignore[attr-defined]
        async def choose_mode(agent: Agent):
            message = await agent.call("Would you like to chat or execute a command?")

            if "chat" in message.content.lower():
                return agent.next("chat_mode")  # type: ignore[attr-defined]
            elif "execute" in message.content.lower():
                return agent.next("exec_mode")  # type: ignore[attr-defined]
            else:
                agent.append("I didn't understand that. Please choose chat or execute.")
                return agent.next("mode")  # type: ignore[attr-defined]


class TestAgentCli:
    async def test_agent_cli_basic(self):
        """
        Usage:

        good-agent chat module.path:agent --config-arg
        -- launches interactive chat session with agent (like claude code)

        good-agent exec module.path:agent "prompt" --config-arg
        -- executes single prompt and returns response (headless)

        good-agent serve module.path:agent --config-arg
        -- launches agent as a openai-compatible web service with REST API

        """
