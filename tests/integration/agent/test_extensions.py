import pytest

from good_agent import Agent, AgentComponent


@pytest.mark.asyncio
async def test_extension_access_methods():
    """Test different ways to access extensions"""

    # Custom extension
    class CustomExtension(AgentComponent):
        def __init__(self):
            super().__init__()
            self.name = "custom"
            self.data = []

        async def install(self, target):
            await super().install(target)
            # Custom installation logic
            self.data.append("installed")

    ext = CustomExtension()
    async with Agent("Test agent", extensions=[ext]) as agent:
        # Access by type
        assert agent[CustomExtension] is ext

        # Access by name
        assert agent.extensions["custom"] is ext

        # Verify installation
        assert ext.data == ["installed"]


@pytest.mark.asyncio
async def test_extension_forking():
    """Test that extensions are preserved when forking agents"""

    # Custom extension for testing
    class DataExtension(AgentComponent):
        def __init__(self):
            super().__init__()
            self.name = "data"
            self.data = []

        def add(self, item):
            self.data.append(item)

    # Create agent with extension
    async with Agent("Original agent", extensions=[DataExtension()]) as agent:
        # Add some data
        ext = agent[DataExtension]
        ext.add("Test content")

        # Fork the agent
        forked = agent.fork()

        # Verify extension is preserved
        forked_ext = forked[DataExtension]
        assert isinstance(forked_ext, DataExtension)

        # Check that data is shared (since it's a reference)
        assert "Test content" in forked_ext.data


@pytest.mark.asyncio
async def test_extension_event_handlers():
    """Test that extensions can register event handlers"""

    class EventTrackingExtension(AgentComponent):
        def __init__(self):
            super().__init__()
            self.name = "event_tracker"
            self.events = []

        def setup(self, target):
            """Use setup for synchronous event handler registration."""
            super().setup(target)

            # Register event handler
            @target.on("message:append:after")
            async def track_message(ctx):
                message = ctx.parameters["message"]
                self.events.append(f"message_appended: {message.role}")

        async def install(self, target):
            await super().install(target)

    ext = EventTrackingExtension()
    async with Agent("Test agent", extensions=[ext]) as agent:
        # Append a message
        agent.append("Hello world")

        # Give async event handler time to process
        import asyncio

        await asyncio.sleep(0.01)

        # Verify event was tracked
        assert "message_appended: user" in ext.events


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
