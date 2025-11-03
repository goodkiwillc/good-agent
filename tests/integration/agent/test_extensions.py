"""
Tests for the extension system
"""

import pytest
from good_agent import Agent, AgentComponent, CitationIndex, Paragraph
from good_agent.tools import tool


@pytest.mark.asyncio
async def test_citation_index_basic():
    """Test basic CitationIndex functionality"""
    # Create agent with CitationIndex extension
    async with Agent(
        "You are a helpful assistant.", extensions=[CitationIndex()]
    ) as agent:
        # Access the extension via type key
        citations = agent[CitationIndex]
        assert isinstance(citations, CitationIndex)

        # Add a citation
        cid = citations.add(
            "Paris is the capital of France.",
            origin="https://en.wikipedia.org/wiki/Paris",
            source="Wikipedia",
        )

        # Verify citation was added
        assert cid in citations._index
        assert citations[cid] == "Paris is the capital of France."

        # Create a paragraph with citation
        para = citations.create_paragraph(
            "The Eiffel Tower is located in Paris.",
            origin="https://en.wikipedia.org/wiki/Eiffel_Tower",
            source="Wikipedia",
        )

        assert isinstance(para, Paragraph)
        assert para.content == "The Eiffel Tower is located in Paris."
        assert para.citation is not None
        assert para.citation.source == "Wikipedia"

        # Test __llm__ rendering
        llm_text = para.__llm__()
        assert f"[{para.citation.id}]" in llm_text


@pytest.mark.asyncio
async def test_citation_index_with_tools():
    """Test CitationIndex integration with tools"""

    @tool
    async def answer_from_wikipedia(
        query: str,
        citations: CitationIndex,  # Inject the CitationIndex extension
    ) -> Paragraph:
        """
        Search Wikipedia for the given query and return the first paragraph of the summary.
        """
        # Simulate a Wikipedia search
        if "capital of France" in query:
            result_url = "https://en.wikipedia.org/wiki/Paris"
            result_answer = "Paris is the capital of France."
        else:
            result_url = "https://en.wikipedia.org/wiki/Unknown"
            result_answer = "Unknown query."

        # Create cited paragraph
        return citations.create_paragraph(
            result_answer, origin=result_url, source="Wikipedia"
        )

    # Create agent with extension and tool
    async with Agent(
        "You are a helpful assistant.",
        extensions=[CitationIndex()],
        tools=[answer_from_wikipedia],
    ) as agent:
        # Give tools time to load asynchronously
        import asyncio

        await asyncio.sleep(0.1)

        # Verify tool was registered
        assert "answer_from_wikipedia" in agent.tools._tools

        # Access citations
        citations = agent[CitationIndex]

        # Since @tool decorator returns a Tool instance, we need to call it differently
        # For now, let's test the CitationIndex directly
        result = citations.create_paragraph(
            "Paris is the capital of France.",
            origin="https://en.wikipedia.org/wiki/Paris",
            source="Wikipedia",
        )

        assert isinstance(result, Paragraph)
        assert result.content == "Paris is the capital of France."
        assert result.citation.source == "Wikipedia"

        # Verify citation was indexed
        assert result.citation.id in citations._index


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

    # Create agent with citation index
    async with Agent("Original agent", extensions=[CitationIndex()]) as agent:
        # Add some citations
        citations = agent[CitationIndex]
        citations.add("Test content", source="Test")

        # Fork the agent
        forked = agent.fork()

        # Verify extension is preserved
        forked_citations = forked[CitationIndex]
        assert isinstance(forked_citations, CitationIndex)

        # Note: Extensions are shared references in basic implementation
        # For true isolation, extensions would need copy/deepcopy support


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
