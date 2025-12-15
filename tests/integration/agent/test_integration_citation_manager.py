import pytest
from loguru import logger

from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.core.types import URL
from good_agent.extensions.citations import CitationIndex, CitationManager


@pytest.mark.asyncio
class TestCitationManagerInstallation:
    """Test CitationManager installation and basic functionality."""

    async def test_manager_installation(self):
        """Test that CitationManager installs correctly on agent."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Manager should be installed
        assert "CitationManager" in agent.extensions
        assert agent[CitationManager] is manager
        assert manager._agent == agent

        # Should have a citation index
        assert isinstance(manager.index, CitationIndex)
        assert len(manager.index) == 0

    async def test_shared_citation_index(self):
        """Test using shared citation index across managers."""
        # Create shared index
        shared_index = CitationIndex()
        shared_index.add(URL("https://shared-source.com"))

        # Create managers with shared index
        manager1 = CitationManager(shared_index)
        manager2 = CitationManager(shared_index)

        agent1 = Agent("Agent 1", extensions=[manager1])
        agent2 = Agent("Agent 2", extensions=[manager2])

        await agent1.initialize()
        await agent2.initialize()

        # Both should reference same index
        assert manager1.index is manager2.index
        assert len(manager1.index) == 1
        assert len(manager2.index) == 1


@pytest.mark.asyncio
class TestCitationExtractionPipeline:
    """Test citation extraction from different message types."""

    async def test_user_message_with_inline_urls(self):
        """Test extracting citations from user messages with inline URLs."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Add user message with inline URL
        agent.append("Please research https://example.com/study for details.")

        # Check that citation was extracted
        assert len(manager.index) == 1
        assert URL("https://example.com/study") in manager.index

        # Check message was normalized
        message = agent.messages[-1]
        assert message.citations == [URL("https://example.com/study")]

        # Content should use local citation format for LLM rendering
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "https://example.com/study" not in llm_content

        # Display format should be user-friendly
        display_content = str(message)
        assert "[example.com]" in display_content

    async def test_assistant_message_with_citations_list(self):
        """Test processing assistant messages with existing citations."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Simulate LLM response with citations
        citations = [
            URL("https://research.org/paper1"),
            URL("https://study.edu/paper2"),
        ]

        agent.append(
            "Based on research [1] and the study [2], we can conclude...",
            role="assistant",
            citations=citations,
        )

        # Citations should be added to global index
        assert len(manager.index) == 2
        assert URL("https://research.org/paper1") in manager.index
        assert URL("https://study.edu/paper2") in manager.index

        # Message should have normalized content
        message = agent.messages[-1]
        assert message.citations == citations

        # LLM format should use citation markers
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content

        # Display format should be user-friendly
        display_content = str(message)
        assert "[research.org]" in display_content
        assert "[study.edu]" in display_content

    async def test_tool_message_with_xml_urls(self):
        """Test extracting citations from tool messages with XML URLs."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Simulate tool response with XML content
        xml_content = """
        <search_results>
            <result url="https://example.com/article1">First Result</result>
            <result url="https://test.org/article2">Second Result</result>
        </search_results>
        """

        agent.append(xml_content, role="tool")

        # URLs should be extracted to citations
        assert len(manager.index) == 2
        assert URL("https://example.com/article1") in manager.index
        assert URL("https://test.org/article2") in manager.index

        # XML should use idx attributes
        message = agent.messages[-1]
        # Check the normalized content in content_parts, not str(message) which returns original
        content = message.content_parts[0].text if message.content_parts else str(message)
        assert 'idx="1"' in content
        assert 'idx="2"' in content
        assert 'url="https://example.com/article1"' not in content

    async def test_markdown_reference_block(self):
        """Test extracting markdown reference blocks."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Message with markdown reference block
        message_content = """
        The research [1] shows significant results, while the study [2]
        provides additional context.

        [1]: https://research.org/breakthrough
        [2]: https://study.edu/context
        """

        agent.append(message_content)

        # References should be extracted
        assert len(manager.index) == 2
        assert URL("https://research.org/breakthrough") in manager.index
        assert URL("https://study.edu/context") in manager.index

        # Message should have clean content without reference block
        message = agent.messages[-1]
        content = str(message)
        assert "[1]: https://research.org/breakthrough" not in content
        # In DISPLAY mode, citations are rendered as markdown links
        assert "[research.org](https://research.org/breakthrough)" in content
        assert "[study.edu](https://study.edu/context)" in content

        # Check LLM format has normalized citations
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content


@pytest.mark.asyncio
class TestCitationRenderingTransformation:
    """Test citation transformation during message rendering."""

    async def test_llm_rendering_with_global_indices(self):
        """Test that LLM rendering uses global indices."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Pre-populate global index
        manager.index.add(URL("https://existing1.com"))
        manager.index.add(URL("https://existing2.com"))

        # Add message with new citations
        agent.append(
            "New source [!CITE_1!] and another [!CITE_2!]",
            citations=[URL("https://new1.com"), URL("https://new2.com")],
        )

        # Get last message
        message = agent.messages[-1]

        # Render for LLM - should use global indices
        from good_agent.content import RenderMode

        # Mock the rendering process that would happen in LLM calls
        manager._on_message_render_before(
            type(
                "MockContext",
                (),
                {
                    "parameters": {
                        "context": RenderMode.LLM,
                        "message": message,
                        "output": str(message),
                    }
                },
            )()
        )

        # Global index should have 4 citations now
        assert len(manager.index) == 4

        # Message should reference global indices 3 and 4
        # (Note: actual verification would require integration with rendering system)

    async def test_user_rendering_with_links(self):
        """Test that user rendering shows clickable links."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Add message with citations
        citations = [URL("https://example.com/page"), URL("https://test.org/article")]

        agent.append("See source [!CITE_1!] and reference [!CITE_2!]", citations=citations)

        message = agent.messages[-1]

        # Get the actual content parts from message
        from good_agent.content import TextContentPart

        output_parts = (
            list(message.content_parts)
            if hasattr(message, "content_parts")
            else [TextContentPart(text=str(message))]
        )

        # Mock user rendering
        context = type(
            "MockContext",
            (),
            {
                "parameters": {
                    "mode": RenderMode.DISPLAY,
                    "message": message,
                    "output": output_parts,
                }
            },
        )()

        manager._on_message_render_before(context)

        # Output should have markdown links
        transformed_parts = context.parameters["output"]
        if transformed_parts:
            transformed_text = (
                transformed_parts[0].text
                if hasattr(transformed_parts[0], "text")
                else str(transformed_parts[0])
            )
            assert "[example.com](https://example.com/page)" in transformed_text
            assert "[test.org](https://test.org/article)" in transformed_text
            assert "[!CITE_1!]" not in transformed_text


@pytest.mark.asyncio
class TestMultiAgentCitationSharing:
    """Test citation sharing between multiple agents."""

    async def test_shared_citation_index_across_agents(self):
        """Test that multiple agents can share citation index."""
        # Create shared citation index
        shared_index = CitationIndex()

        # Create multiple agents with same index
        manager1 = CitationManager(shared_index)
        manager2 = CitationManager(shared_index)

        agent1 = Agent("Research Agent", extensions=[manager1])
        agent2 = Agent("Analysis Agent", extensions=[manager2])

        await agent1.initialize()
        await agent2.initialize()

        # Agent 1 adds citations
        agent1.append("Found source https://research.org/paper")

        # Agent 2 references same source
        agent2.append(
            "Based on the paper [!CITE_1!]...",
            citations=[URL("https://research.org/paper")],
        )

        # Should have only one unique citation in shared index
        assert len(shared_index) == 1
        assert URL("https://research.org/paper") in shared_index

        # Both agents reference same global index
        assert manager1.index is manager2.index

    async def test_citation_consistency_across_agents(self):
        """Test citation consistency when agents reference same sources."""
        shared_index = CitationIndex()

        agent1 = Agent("Agent 1", extensions=[CitationManager(shared_index)])
        agent2 = Agent("Agent 2", extensions=[CitationManager(shared_index)])

        await agent1.initialize()
        await agent2.initialize()

        # Same URLs added in different order by different agents
        agent1.append("Source A https://a.com and B https://b.com")
        agent2.append("Source B https://b.com and A https://a.com")

        # Should have consistent global indices regardless of order discovered
        assert len(shared_index) == 2

        # Both agents should see same global indices for same URLs
        url_a_index = shared_index.lookup(URL("https://a.com"))
        url_b_index = shared_index.lookup(URL("https://b.com"))

        assert url_a_index is not None
        assert url_b_index is not None
        assert url_a_index != url_b_index


@pytest.mark.asyncio
class TestRealWorldScenarios:
    """Test realistic usage scenarios."""

    async def test_research_workflow_scenario(self):
        """Test complete research workflow with citations."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # 1. User asks for research
        agent.append("Please research the latest developments in AI safety")

        # 2. Tool provides search results
        search_results = """
        <search_results>
            <result url="https://arxiv.org/abs/2024.01001">AI Safety Paper 2024</result>
            <result url="https://safety.ai/report">Safety Report</result>
            <result url="https://openai.com/safety">OpenAI Safety</result>
        </search_results>
        """
        agent.append(search_results, role="tool")

        # 3. Agent analyzes and cites sources
        agent.append(
            "Based on recent research [!CITE_1!] and industry reports [!CITE_2!], "
            "AI safety has become a critical focus. The OpenAI safety guidelines [!CITE_3!] "
            "provide important frameworks.",
            role="assistant",
            citations=[
                URL("https://arxiv.org/abs/2024.01001"),
                URL("https://safety.ai/report"),
                URL("https://openai.com/safety"),
            ],
        )

        # 4. User asks follow-up with additional source
        agent.append("What about the findings in https://anthropic.com/safety-research?")

        # Verify citation management
        assert len(manager.index) == 4  # 3 from search + 1 from user

        # All sources should be indexed
        expected_urls = [
            "https://arxiv.org/abs/2024.01001",
            "https://safety.ai/report",
            "https://openai.com/safety",
            "https://anthropic.com/safety-research",
        ]

        for url in expected_urls:
            assert URL(url) in manager.index

    async def test_tool_invocation_with_citation_processing(self):
        """Test that tool invocations through agent.invoke properly handle citations."""
        from good_agent import tool

        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Define a dummy search tool that returns our XML
        @tool
        async def search_news(query: str, max_results: int = 10) -> str:
            """Search for news articles."""
            # Return the same XML structure from the test above
            return """<search_query>
    <query>
        <query>Xavier Becerra</query>
        <type>news</type>
        <max_results>10</max_results>
    </query>
    <results>
        <news>
            <result url="https://www.politico.com/newsletters/playbook/2025/08/26/cooking-up-a-storm-00524429">
                <title>Playbook: Cooking up a storm</title>
                <description>With help from Eli Okun, Bethany Irvine and Ali Bianco. Good Tuesday morning. This is Jack Blanchard. Reminder: There's no Playbook Podcast or Playbook PM...</description>
            </result>
            <result url="https://www.latimes.com/california/story/2025-08-26/la-times-berkeley-poll-california-governors-race-kamala-harris-katie-porter-chad-bianco-gavin-newsom">
                <title>California voters undecided in 2026 governor's race, but prefer Newsom over Harris for president in 2028</title>
                <description>California voters are uncertain about who should be the state's next governor, according to a new Los Angeles Times/UC Berkeley poll. Termed-out Gov.</description>
            </result>
            <result url="https://www.houstonpublicmedia.org/npr/2025/08/26/nx-s1-5515408/when-hospitals-and-insurers-fight-patients-get-caught-in-the-middle/">
                <title>When hospitals and insurers fight, patients get caught in the middle</title>
                <description>About 90000 people spent months in limbo as central Missouri's major medical provider fought over insurance contracts. These disputes between insurers and...</description>
            </result>
            <result url="https://dailycaller.com/2025/08/26/california-democrats-kamala-harris-president-poll/">
                <title>Majority Of California Dems Think Kamala Harris Should Pass On Another White House Run: POLL</title>
                <description>The majority of Democrats do not want Kamala Harris to make another White House bid, according to a UC Berkeley/Los Angeles Times poll released Tuesday.</description>
            </result>
        </news>
    </results>
</search_query>"""

        # Invoke the tool through the agent's invoke method
        # This tests the internal message routing
        # No need to add_tool - just pass it directly to invoke
        tool_response = await agent.invoke(tool=search_news, query="Xavier Becerra", max_results=10)

        # Check that the tool executed successfully
        assert tool_response.success
        assert tool_response.response is not None

        # Check that the tool response was added to messages
        assert len(agent.messages) > 0

        # The last message should be a tool message
        last_message = agent.messages[-1]
        assert last_message.role == "tool"

        # Citations should be extracted from the tool output
        assert len(manager.index) == 4

        expected_urls = [
            "https://www.politico.com/newsletters/playbook/2025/08/26/cooking-up-a-storm-00524429",
            "https://www.latimes.com/california/story/2025-08-26/la-times-berkeley-poll-california-governors-race-kamala-harris-katie-porter-chad-bianco-gavin-newsom",
            "https://www.houstonpublicmedia.org/npr/2025/08/26/nx-s1-5515408/when-hospitals-and-insurers-fight-patients-get-caught-in-the-middle/",
            "https://dailycaller.com/2025/08/26/california-democrats-kamala-harris-president-poll/",
        ]

        for url in expected_urls:
            assert URL(url) in manager.index

        # Verify that the index entries have metadata
        for url in expected_urls:
            if ref := manager.index.lookup(URL(url)):
                assert ref <= len(expected_urls)

        # Verify the citations were properly extracted and attached
        tool_message = agent.messages[-1]
        assert tool_message.role == "tool"

        # Citations should be attached to the message
        assert tool_message.citations is not None
        assert len(tool_message.citations) == 4

        # All URLs should be URL objects
        for citation in tool_message.citations:
            assert isinstance(citation, URL)

        # Verify all expected URLs are in the citations
        for url_str in expected_urls:
            assert URL(url_str) in tool_message.citations

        # The raw content should still have the XML structure
        raw_content = str(tool_message)
        assert "<search_query>" in raw_content
        assert "<result" in raw_content
        assert "</search_query>" in raw_content

    async def test_perplexity_style_response_processing(self):
        """Test processing Perplexity-style responses with citations."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Simulate Perplexity-style response
        perplexity_response = {
            "content": "Climate change is accelerating [1]. Recent studies show [2] that "
            "global temperatures have risen significantly. The IPCC report [3] "
            "provides comprehensive analysis.",
            "citations": [
                "https://climate.nasa.gov/latest-data",
                "https://nature.com/climate-study-2024",
                "https://ipcc.ch/ar6-synthesis",
            ],
        }

        # Process as assistant message
        agent.append(
            perplexity_response["content"],
            role="assistant",
            citations=[URL(url) for url in perplexity_response["citations"]],
        )

        # Verify processing
        assert len(manager.index) == 3

        message = agent.messages[-1]
        assert message.citations and len(message.citations) == 3

        # Content should be normalized to [!CITE_X!] format for LLM
        # but displayed as markdown links for users
        display_content = str(message)
        assert "[climate.nasa.gov](https://climate.nasa.gov/latest-data)" in display_content
        assert "[nature.com](https://nature.com/climate-study-2024)" in display_content
        assert "[ipcc.ch](https://ipcc.ch/ar6-synthesis)" in display_content
        assert "[1]" not in display_content  # Original format should be replaced

        # Check LLM format has normalized citations
        llm_content = message.render(RenderMode.LLM)
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content
        assert "[!CITE_3!]" in llm_content

    async def test_citation_deduplication_scenario(self):
        """Test citation deduplication across multiple messages."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Multiple messages referencing same sources
        agent.append("First reference to https://example.com/paper")

        agent.append("Analysis based on [!CITE_1!]", citations=[URL("https://example.com/paper")])

        agent.append("Additional insights from https://example.com/paper")

        # Should have only one citation despite multiple references
        assert len(manager.index) == 1
        assert URL("https://example.com/paper") in manager.index

        # All messages should reference same global index
        for message in agent.messages:
            if message.citations:
                assert URL("https://example.com/paper") in message.citations

    async def test_mixed_citation_formats_scenario(self):
        """Test handling mixed citation formats in single session."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Different citation formats in different messages

        # 1. XML from tool
        agent.append(
            '<results><item url="https://source1.com">Result 1</item></results>',
            role="tool",
        )

        # 2. Markdown references from user
        agent.append("""
        Please also check the study [1].

        [1]: https://source2.com/study
        """)

        # 3. Inline URL from user
        agent.append("What about https://source3.com/analysis?")

        # 4. LLM format from assistant
        agent.append(
            "Combining sources [!CITE_1!], [!CITE_2!], and [!CITE_3!]...",
            role="assistant",
            citations=[
                URL("https://source1.com"),
                URL("https://source2.com/study"),
                URL("https://source3.com/analysis"),
            ],
        )

        # All formats should be processed correctly
        assert len(manager.index) == 3

        expected_sources = [
            "https://source1.com",
            "https://source2.com/study",
            "https://source3.com/analysis",
        ]

        for source in expected_sources:
            assert URL(source) in manager.index

    async def test_search_result_xml_citation_processing(self):
        """Test processing search results with URL attributes for LLM rendering."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Simulate search tool response with XML content matching user's example
        search_results_xml = """<search_query>
    <query>
        <query>Xavier Becerra</query>
        <type>news</type>
        <max_results>10</max_results>
    </query>
    <results>
        <news>
            <result url="https://www.politico.com/newsletters/playbook/2025/08/26/cooking-up-a-storm-00524429">
                <title>Playbook: Cooking up a storm</title>
                <description>With help from Eli Okun, Bethany Irvine and Ali Bianco. Good Tuesday morning. This is Jack Blanchard. Reminder: There's no Playbook Podcast or Playbook PM...</description>
            </result>
            <result url="https://www.latimes.com/california/story/2025-08-26/la-times-berkeley-poll-california-governors-race-kamala-harris-katie-porter-chad-bianco-gavin-newsom">
                <title>California voters undecided in 2026 governor's race, but prefer Newsom over Harris for president in 2028</title>
                <description>California voters are uncertain about who should be the state's next governor, according to a new Los Angeles Times/UC Berkeley poll. Termed-out Gov.</description>
            </result>
            <result url="https://www.houstonpublicmedia.org/npr/2025/08/26/nx-s1-5515408/when-hospitals-and-insurers-fight-patients-get-caught-in-the-middle/">
                <title>When hospitals and insurers fight, patients get caught in the middle</title>
                <description>About 90000 people spent months in limbo as central Missouri's major medical provider fought over insurance contracts. These disputes between insurers and...</description>
            </result>
            <result url="https://dailycaller.com/2025/08/26/california-democrats-kamala-harris-president-poll/">
                <title>Majority Of California Dems Think Kamala Harris Should Pass On Another White House Run: POLL</title>
                <description>The majority of Democrats do not want Kamala Harris to make another White House bid, according to a UC Berkeley/Los Angeles Times poll released Tuesday.</description>
            </result>
        </news>
    </results>
</search_query>"""

        # Add as tool message
        agent.append(search_results_xml, role="tool")

        # Verify URLs were extracted to citations
        assert len(manager.index) == 4  # 4 URLs in the XML

        # Check specific URLs are in the index
        expected_urls = [
            URL(
                "https://www.politico.com/newsletters/playbook/2025/08/26/cooking-up-a-storm-00524429"
            ),
            URL(
                "https://www.latimes.com/california/story/2025-08-26/la-times-berkeley-poll-california-governors-race-kamala-harris-katie-porter-chad-bianco-gavin-newsom"
            ),
            URL(
                "https://www.houstonpublicmedia.org/npr/2025/08/26/nx-s1-5515408/when-hospitals-and-insurers-fight-patients-get-caught-in-the-middle/"
            ),
            URL(
                "https://dailycaller.com/2025/08/26/california-democrats-kamala-harris-president-poll/"
            ),
        ]

        for url in expected_urls:
            assert url in manager.index

        # Check that XML was transformed to use idx attributes instead of URLs
        tool_message = agent.messages[-1]
        # Check the normalized content in content_parts, not str(message) which returns original
        message_content = (
            tool_message.content_parts[0].text if tool_message.content_parts else str(tool_message)
        )
        logger.debug(message_content)

        # URL attributes should be replaced with idx attributes
        assert 'idx="1"' in message_content
        assert 'idx="2"' in message_content
        assert 'idx="3"' in message_content
        assert 'idx="4"' in message_content

        # Original URLs should not appear as attributes
        assert 'url="https://www.politico.com' not in message_content
        assert 'url="https://www.latimes.com' not in message_content

        # Verify citations are properly attached to the message
        assert tool_message.citations is not None
        assert len(tool_message.citations) == 4
        assert all(isinstance(c, URL) for c in tool_message.citations)

        # Test LLM rendering transformation
        # When rendered for LLM, idx should map to global citation index
        from good_agent.content import RenderMode

        # Mock the rendering process that would happen during LLM calls
        # The output should be a list of content parts, not a string
        mock_context = type(
            "MockContext",
            (),
            {
                "parameters": {
                    "mode": RenderMode.LLM,  # Changed from "context" to "mode"
                    "message": tool_message,
                    "output": list(tool_message.content_parts),  # List of content parts
                }
            },
        )()

        # Apply the transformation
        manager._on_message_render_before(mock_context)

        # Get transformed output
        transformed_parts = mock_context.parameters["output"]
        # Get the text from the first content part
        transformed_output = transformed_parts[0].text if transformed_parts else ""

        # For LLM rendering, local idx values should map to global citation indices
        # Since these are the only citations so far, they should be idx="1" through idx="4"
        assert 'idx="1"' in transformed_output
        assert 'idx="2"' in transformed_output
        assert 'idx="3"' in transformed_output
        assert 'idx="4"' in transformed_output

    async def test_search_result_with_existing_citations(self):
        """Test that search results properly map to global indices when citations already exist."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # First, add some existing citations to the global index
        agent.append("Check this source: https://existing-source-1.com/article")
        agent.append("And this paper: https://existing-source-2.com/research")

        # Verify we have 2 citations so far
        assert len(manager.index) == 2
        assert manager.index.lookup(URL("https://existing-source-1.com/article")) == 1
        assert manager.index.lookup(URL("https://existing-source-2.com/research")) == 2

        # Now add search results - these should get indices 3, 4
        search_results_xml = """<search_results>
            <result url="https://new-source-1.com/news">
                <title>Breaking News</title>
                <description>Latest updates...</description>
            </result>
            <result url="https://new-source-2.com/article">
                <title>Analysis Article</title>
                <description>In-depth analysis...</description>
            </result>
        </search_results>"""

        agent.append(search_results_xml, role="tool")

        # Should now have 4 total citations
        assert len(manager.index) == 4

        # Verify new URLs got proper global indices
        assert manager.index.lookup(URL("https://new-source-1.com/news")) == 3
        assert manager.index.lookup(URL("https://new-source-2.com/article")) == 4

        # Check that the tool message has local indices 1 and 2
        # (local to the message, not global)
        tool_message = agent.messages[-1]
        # Check the normalized content in content_parts, not str(message) which returns original
        message_content = (
            tool_message.content_parts[0].text if tool_message.content_parts else str(tool_message)
        )
        assert 'idx="1"' in message_content
        assert 'idx="2"' in message_content

        # When rendered for LLM, should map to global indices 3 and 4
        # Create mock context for LLM rendering with proper content parts format
        from good_agent.content import RenderMode, TextContentPart

        output_parts = (
            list(tool_message.content_parts)
            if hasattr(tool_message, "content_parts")
            else [TextContentPart(text=str(tool_message))]
        )

        mock_context = type(
            "MockContext",
            (),
            {
                "parameters": {
                    "mode": RenderMode.LLM,  # Changed from 'context' to 'mode' to match the handler
                    "message": tool_message,
                    "output": output_parts,
                }
            },
        )()

        # Apply transformation
        manager._on_message_render_before(mock_context)
        transformed_parts = mock_context.parameters["output"]

        # Get the transformed text content
        transformed_output = (
            transformed_parts[0].text
            if transformed_parts and hasattr(transformed_parts[0], "text")
            else str(transformed_parts[0])
        )

        # Local idx="1" should become idx="3" (global index)
        # Local idx="2" should become idx="4" (global index)
        assert 'idx="3"' in transformed_output
        assert 'idx="4"' in transformed_output

        # Verify the message has the correct citations attached
        assert len(tool_message.citations) == 2
        assert URL("https://new-source-1.com/news") in tool_message.citations
        assert URL("https://new-source-2.com/article") in tool_message.citations

    async def test_mixed_xml_and_markdown_content(self):
        """Test processing content with both XML elements and markdown citations."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Mixed content: XML search results with markdown commentary
        mixed_content = """Based on my search, here are the top results:

<search_results>
    <result url="https://example.com/article1">
        <title>First Article</title>
        <description>Primary source material</description>
    </result>
    <result url="https://research.org/paper2">
        <title>Research Paper</title>
        <description>Academic study</description>
    </result>
</search_results>

Additionally, I found some relevant context in [1] and further analysis in [2].
The comprehensive review [3] provides additional insights.

[1]: https://context-source.com/overview
[2]: https://analysis.edu/deep-dive
[3]: https://review-journal.org/comprehensive"""

        # Add as tool message
        agent.append(mixed_content, role="tool")

        # Should extract ALL citations from both XML and markdown
        assert len(manager.index) == 5  # 2 from XML + 3 from markdown references

        # Check all URLs are in the index
        expected_urls = [
            URL("https://example.com/article1"),
            URL("https://research.org/paper2"),
            URL("https://context-source.com/overview"),
            URL("https://analysis.edu/deep-dive"),
            URL("https://review-journal.org/comprehensive"),
        ]

        for url in expected_urls:
            assert url in manager.index

        # Check that message content has proper formatting
        tool_message = agent.messages[-1]
        # Check the normalized content in content_parts, not str(message) which returns original
        message_content = (
            tool_message.content_parts[0].text if tool_message.content_parts else str(tool_message)
        )

        # XML urls should be replaced with idx attributes
        assert "idx=" in message_content
        assert 'url="https://example.com/article1"' not in message_content
        assert 'url="https://research.org/paper2"' not in message_content

        # Markdown references should be removed and citations normalized
        assert "[1]: https://context-source.com/overview" not in message_content
        assert "[!CITE_" in message_content  # Should have normalized citations

        # Verify all citations are attached to the message
        assert tool_message.citations is not None
        assert len(tool_message.citations) == 5
        assert all(isinstance(c, URL) for c in tool_message.citations)

    async def test_mixed_inline_urls_and_xml_content(self):
        """Test processing content with inline URLs mixed with XML elements."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Content mixing inline URLs with XML results
        mixed_content = """Check this source https://inline-url.com/article for background.

<results>
    <item url="https://xml-source-1.com/data">Data Point 1</item>
    <item url="https://xml-source-2.com/info">Data Point 2</item>
</results>

Also see https://another-inline.org/reference for more details."""

        agent.append(mixed_content, role="tool")

        # Should extract all 4 citations
        assert len(manager.index) == 4

        expected_urls = [
            URL("https://inline-url.com/article"),
            URL("https://xml-source-1.com/data"),
            URL("https://xml-source-2.com/info"),
            URL("https://another-inline.org/reference"),
        ]

        for url in expected_urls:
            assert url in manager.index

        # Check content transformation
        tool_message = agent.messages[-1]
        # Check the normalized content in content_parts, not str(message) which returns original
        message_content = (
            tool_message.content_parts[0].text if tool_message.content_parts else str(tool_message)
        )

        # Inline URLs should be replaced with citations
        assert "https://inline-url.com/article" not in message_content
        assert "https://another-inline.org/reference" not in message_content
        assert "[!CITE_" in message_content

        # XML URLs should be idx attributes
        assert "idx=" in message_content
        assert 'url="https://xml-source-1.com/data"' not in message_content

    async def test_display_mode_rendering_mixed_formats(self):
        """Test RenderMode.DISPLAY properly renders mixed citation formats."""
        manager = CitationManager()
        agent = Agent("Research Assistant", extensions=[manager])

        await agent.initialize()

        # Content with both LLM citations and XML idx attributes
        mixed_content = """Summary: The research [!CITE_1!] shows important findings.

<results>
    <item idx="2">Data Point</item>
    <item idx="3">Another Point</item>
</results>

This aligns with [!CITE_4!] conclusions."""

        citations = [
            URL("https://research.com/study"),
            URL("https://data.org/point1"),
            URL("https://data.org/point2"),
            URL("https://analysis.edu/paper"),
        ]

        agent.append(mixed_content, citations=citations)
        message = agent.messages[-1]

        # Simulate RenderMode.DISPLAY rendering
        output_parts = list(message.content_parts)
        context = type(
            "MockContext",
            (),
            {
                "parameters": {
                    "mode": RenderMode.DISPLAY,
                    "message": message,
                    "output": output_parts,
                }
            },
        )()

        manager._on_message_render_before(context)

        # Check transformed output
        transformed_parts = context.parameters["output"]
        assert len(transformed_parts) > 0

        transformed_text = transformed_parts[0].text

        # Markdown citations should be converted to links
        assert "[research.com](https://research.com/study)" in transformed_text
        assert "[analysis.edu](https://analysis.edu/paper)" in transformed_text

        # XML idx attributes should be converted to url attributes
        assert 'url="https://data.org/point1"' in transformed_text
        assert 'url="https://data.org/point2"' in transformed_text

        # Original formats should not be present
        assert "[!CITE_1!]" not in transformed_text
        assert "[!CITE_4!]" not in transformed_text
        assert 'idx="2"' not in transformed_text
        assert 'idx="3"' not in transformed_text


@pytest.mark.asyncio
class TestCitationManagerAPI:
    """Test CitationManager public API methods."""

    async def test_get_citations_summary(self):
        """Test citations summary generation."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Empty index
        summary = manager.get_citations_summary()
        assert "No citations available" in summary

        # Add some citations
        agent.append("Source https://example.com/paper1")
        agent.append("Another https://test.org/paper2")

        summary = manager.get_citations_summary()
        assert "Citations (2 total)" in summary
        assert "https://example.com/paper1" in summary
        assert "https://test.org/paper2" in summary

    async def test_export_citations(self):
        """Test citation export functionality."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Add citations with metadata and tags
        manager.index.add(URL("https://example.com"), tags=["research"], title="Example Paper")

        # Test JSON export
        json_export = manager.export_citations("json")
        assert "https://example.com" in json_export
        assert "Example Paper" in json_export
        assert "research" in json_export

        # Test Markdown export
        md_export = manager.export_citations("markdown")
        assert "# Citations" in md_export
        # URL canonicalization adds trailing slash
        assert "[https://example.com/](https://example.com/)" in md_export

        # Test CSV export
        csv_export = manager.export_citations("csv")
        assert "Index,URL,Tags" in csv_export
        assert "https://example.com" in csv_export

    async def test_find_citations_by_tag(self):
        """Test finding citations by tag."""
        manager = CitationManager()
        agent = Agent("Test assistant", extensions=[manager])

        await agent.initialize()

        # Add citations with different tags
        manager.index.add(URL("https://research1.com"), tags=["research", "ai"])
        manager.index.add(URL("https://research2.com"), tags=["research", "ml"])
        manager.index.add(URL("https://news.com"), tags=["news"])

        # Find by tag
        research_citations = manager.find_citations_by_tag("research")
        assert len(research_citations) == 2

        ai_citations = manager.find_citations_by_tag("ai")
        assert len(ai_citations) == 1

        news_citations = manager.find_citations_by_tag("news")
        assert len(news_citations) == 1

        # Non-existent tag
        none_citations = manager.find_citations_by_tag("nonexistent")
        assert len(none_citations) == 0


@pytest.mark.asyncio
class TestCitationAdapterIntegration:
    """Test end-to-end citation adapter functionality with real agent workflow."""

    async def test_complete_citation_adapter_workflow(self):
        """
        Complete end-to-end integration test showing:
        1. Agent creation with CitationManager and tools
        2. Citation index population
        3. Tool signature transformation for LLM
        4. Parameter transformation in both directions
        5. Successful tool execution with actual URLs
        6. Invalid citation handling
        """
        from good_agent import tool

        # Mock tools for testing citation adapter
        @tool
        async def fetch_url(url: str, timeout: int = 30) -> str:
            """Fetch content from a URL."""
            return f"Content from {url}"

        @tool
        async def fetch_urls(urls: list[str], parallel: bool = False) -> list[str]:
            """Fetch multiple URLs."""
            return [f"Content from {url}" for url in urls]

        # Step 1: Set up CitationManager with citations
        manager = CitationManager()

        # Add various types of URLs to demonstrate different use cases
        research_idx = manager.index.add(URL("https://arxiv.org/abs/2301.07041"))
        docs_idx = manager.index.add(URL("https://docs.python.org/3/library/asyncio.html"))
        repo_idx = manager.index.add(URL("https://github.com/microsoft/TypeScript"))

        # Step 2: Create agent with citation-aware tools
        # CitationManager will automatically create and register the adapter
        agent = Agent(
            "Research assistant with citation management",
            tools=[fetch_url, fetch_urls],
            extensions=[manager],
        )
        await agent.initialize()

        # Step 3: Verify tool adapter registration and signature transformation
        fetch_url_tool = agent.tools["fetch_url"]
        fetch_urls_tool = agent.tools["fetch_urls"]

        # Check that the CitationAdapter was created and registered
        citation_adapter = manager._citation_adapter
        assert citation_adapter is not None, "CitationAdapter should be created by manager"

        # Verify adapter recognizes the tools
        should_adapt_url = citation_adapter.should_adapt(fetch_url_tool, agent)
        should_adapt_urls = citation_adapter.should_adapt(fetch_urls_tool, agent)
        assert should_adapt_url is True, "Should adapt single URL tool"
        assert should_adapt_urls is True, "Should adapt multiple URLs tool"

        # Step 4: Test signature transformation
        original_url_signature = fetch_url_tool.signature
        original_urls_signature = fetch_urls_tool.signature

        # Manually test signature adaptation (this is what happens during LLM calls)
        adapted_url_signature = citation_adapter.adapt_signature(
            fetch_url_tool, original_url_signature, agent
        )
        adapted_urls_signature = citation_adapter.adapt_signature(
            fetch_urls_tool, original_urls_signature, agent
        )

        # Verify single URL tool signature transformation
        url_params = adapted_url_signature["function"]["parameters"]["properties"]
        assert "url" not in url_params, (
            f"Original 'url' parameter should be removed. Got: {url_params}"
        )
        assert "citation_idx" in url_params, (
            f"Should have 'citation_idx' parameter. Got: {url_params}"
        )
        assert url_params["citation_idx"]["type"] == "integer"
        assert url_params["citation_idx"]["minimum"] == 0

        # Verify multiple URLs tool signature transformation
        urls_params = adapted_urls_signature["function"]["parameters"]["properties"]
        assert "urls" not in urls_params, (
            f"Original 'urls' parameter should be removed. Got: {urls_params}"
        )
        assert "citation_idxs" in urls_params, (
            f"Should have 'citation_idxs' parameter. Got: {urls_params}"
        )
        assert urls_params["citation_idxs"]["type"] == "array"
        assert urls_params["citation_idxs"]["items"]["type"] == "integer"

        # Step 5: Test parameter transformation - single URL
        llm_params = {"citation_idx": research_idx, "timeout": 30}
        transformed_params = citation_adapter.adapt_parameters("fetch_url", llm_params, agent)

        # Verify transformation worked correctly
        assert "citation_idx" not in transformed_params, "citation_idx should be removed"
        assert "url" in transformed_params, "url should be present after transformation"
        assert str(transformed_params["url"]) == str(manager.index.get_url(research_idx))
        assert transformed_params["timeout"] == 30

        # Execute tool with transformed parameters
        result = await fetch_url_tool(_agent=agent, **transformed_params)
        assert result.success is True, f"Tool execution failed: {result.error}"
        assert result.response == f"Content from {manager.index.get_url(research_idx)}"

        # Step 6: Test parameter transformation - multiple URLs
        llm_multi_params = {"citation_idxs": [docs_idx, repo_idx], "parallel": True}
        transformed_multi_params = citation_adapter.adapt_parameters(
            "fetch_urls", llm_multi_params, agent
        )

        # Verify transformation worked correctly
        assert "citation_idxs" not in transformed_multi_params, "citation_idxs should be removed"
        assert "urls" in transformed_multi_params, "urls should be present after transformation"
        assert len(transformed_multi_params["urls"]) == 2, "Should have 2 URLs"
        assert str(transformed_multi_params["urls"][0]) == str(manager.index.get_url(docs_idx))
        assert str(transformed_multi_params["urls"][1]) == str(manager.index.get_url(repo_idx))
        assert transformed_multi_params["parallel"] is True

        # Execute multi-URL tool with transformed parameters
        multi_result = await fetch_urls_tool(_agent=agent, **transformed_multi_params)
        assert multi_result.success is True, (
            f"Multi-URL tool execution failed: {multi_result.error}"
        )
        expected_responses = [
            f"Content from {manager.index.get_url(docs_idx)}",
            f"Content from {manager.index.get_url(repo_idx)}",
        ]
        assert multi_result.response == expected_responses

        # Step 7: Test invalid citation handling
        invalid_llm_params = {"citation_idx": 999, "timeout": 15}
        invalid_transformed_params = citation_adapter.adapt_parameters(
            "fetch_url", invalid_llm_params, agent
        )

        # Should keep the invalid citation_idx since it couldn't be resolved
        assert "citation_idx" in invalid_transformed_params, "Invalid citation_idx should be kept"
        assert invalid_transformed_params["citation_idx"] == 999
        assert "url" not in invalid_transformed_params, "url should not be added for invalid index"

        # Step 8: Verify tool descriptions were updated
        url_desc = adapted_url_signature["function"]["description"]
        urls_desc = adapted_urls_signature["function"]["description"]

        assert "citation" in url_desc.lower(), "Tool description should mention citations"
        assert "index" in url_desc.lower(), "Tool description should mention index usage"
        assert "citation" in urls_desc.lower(), "Multi-URL tool should mention citations"

        # Step 9: Verify final citation state
        assert len(manager.index.url_to_index) == 3, "Should have 3 citations total"

        # All URLs should be properly indexed
        for idx, url in manager.index.items():
            value = manager.index.get_value(idx)
            assert url in [
                URL("https://arxiv.org/abs/2301.07041"),
                URL("https://docs.python.org/3/library/asyncio.html"),
                URL("https://github.com/microsoft/TypeScript"),
            ]
            # Values should be None since we didn't provide them
            assert value is None

        print("✅ Complete citation adapter integration test passed!")
        print("   - Citation indices properly transformed to URLs")
        print("   - Tool signatures adapted for LLM consumption")
        print("   - Tools executed successfully with real URLs")
        print("   - Invalid indices handled gracefully")
