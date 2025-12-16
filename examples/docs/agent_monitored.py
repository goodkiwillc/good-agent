import asyncio

from good_agent import Agent, tool
from good_agent.events import AgentEvents


class MonitoredAgent(Agent):
    def __init__(self, **config):
        super().__init__(**config)
        self._setup_monitoring()

    def _setup_monitoring(self):
        @self.on(AgentEvents.AGENT_INIT_AFTER)
        async def on_init(ctx):
            print(f"Agent {self.name or 'Anonymous'} initialized")

        @self.on(AgentEvents.TOOL_CALL_BEFORE)
        async def on_tool_start(ctx):
            tool_name = ctx.parameters["tool_name"]
            print(f"Starting tool: {tool_name}")

        @self.on(AgentEvents.TOOL_CALL_AFTER)
        async def on_tool_end(ctx):
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            print(f"Tool {tool_name} {'succeeded' if success else 'failed'}")

@tool
async def echo(msg: str) -> str:
    return msg

async def main():
    async with MonitoredAgent(name="Watcher", tools=[echo]) as agent:
        await agent.call("Call echo tool with 'hello'")

if __name__ == "__main__":
    asyncio.run(main())
