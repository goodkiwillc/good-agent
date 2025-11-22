"""Handle component lifecycle and error events."""

import asyncio

from good_agent import Agent, AgentComponent
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, ExtensionErrorParams, ExtensionInstallParams


class SampleComponent(AgentComponent):
    """Sample component for demonstration."""

    async def install(self, agent):
        """Install the component."""
        await super().install(agent)
        print("SampleComponent installing...")


async def main():
    """Demonstrate extension lifecycle events."""
    component = SampleComponent()

    async with Agent("Assistant", extensions=[component]) as agent:

        @agent.on(AgentEvents.EXTENSION_INSTALL_AFTER)
        def on_extension_installed(ctx: EventContext[ExtensionInstallParams, None]):
            extension = ctx.parameters["extension"]
            print(f"📦 Installed extension: {type(extension).__name__}")

        @agent.on(AgentEvents.EXTENSION_ERROR)
        def on_extension_error(ctx: EventContext[ExtensionErrorParams, None]):
            extension = ctx.parameters["extension"]
            error = ctx.parameters["error"]
            context = ctx.parameters["context"]

            print(
                f"⚠️ Extension {type(extension).__name__} error in {context}: {error}"
            )

        print("Agent with extension is ready")


if __name__ == "__main__":
    asyncio.run(main())
