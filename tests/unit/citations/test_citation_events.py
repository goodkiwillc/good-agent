import logging

import pytest

from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.events import AgentEvents
from good_agent.extensions.citations import CitationManager


class TestMessageCreateEvent:
    """Test MESSAGE_CREATE_BEFORE event handling."""

    @pytest.mark.asyncio
    async def test_create_event_extracts_citations(self):
        """MESSAGE_CREATE_BEFORE extracts citations from content."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        # append() triggers MESSAGE_CREATE_BEFORE
        agent.append(
            """
            Text with citation [1].

            [1]: https://example.com/doc
            """
        )

        message = agent.messages[-1]

        # Citations should be extracted during creation
        assert message.citations is not None
        assert len(message.citations) >= 1

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_create_event_provided_citations(self):
        """MESSAGE_CREATE_BEFORE respects provided citations."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        citations = ["https://example.com/doc1", "https://example.com/doc2"]

        # Provide citations explicitly
        agent.append(
            "Text with citation [1] and [2].",
            citations=citations,
        )

        message = agent.messages[-1]

        # Citations should match provided ones
        assert message.citations == citations

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_create_event_normalizes_format(self):
        """MESSAGE_CREATE_BEFORE normalizes citation format."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            Text [1].

            [1]: https://example.com/doc
            """
        )

        message = agent.messages[-1]

        # Content should be normalized to [!CITE_X!] format internally
        # This is the storage format
        content_text = str(message.content_parts[0])

        # Should have citation reference in LLM format
        assert "[!CITE_1!]" in content_text

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_create_event_adds_to_global_index(self):
        """MESSAGE_CREATE_BEFORE adds citations to global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        initial_count = len(manager.index)

        agent.append(
            """
            Text [1].

            [1]: https://example.com/doc
            """
        )

        # Global index should have new citation
        assert len(manager.index) > initial_count

        assert manager.index.lookup("https://example.com/doc") == 1

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_create_xml_tag_content(self):
        """MESSAGE_CREATE_BEFORE handles XML tag content."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            <results>
                <item url="https://example.com/item1" />
                <item url="https://example.com/item2" />
            </results>
            """,
            role="tool",
        )

        message = agent.messages[-1]

        # URLs still extracted from XML attributes
        assert message.citations is not None
        assert "https://example.com/item1" in message.citations
        assert "https://example.com/item2" in message.citations

        # Content stored with normalized local indices
        content_text = str(message.content_parts[0])
        assert "<results>" in content_text

        for idx, _url in enumerate(message.citations, start=1):
            assert f'<item idx="{idx}"' in content_text

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_create_mixed_xml_markdown_content(self):
        """MESSAGE_CREATE_BEFORE handles mixed XML and markdown content."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            <information>
              Here is a block of content with inline citations [1].
              Here's another citation [2].

                [1]: https://example.com/doc
                [2]: https://example.com/otherdoc

              <profiles>
                <profile url="https://example.com/item1" />
                <profile url="https://example.com/item2" />
              </profiles>
            </information>
            """,
            role="tool",
        )

        message = agent.messages[-1]

        # Citations from both XML and markdown should be extracted
        assert message.citations is not None
        assert "https://example.com/item1" in message.citations
        assert "https://example.com/doc" in message.citations

        # Content stored with normalized local indices
        content_text = str(message.content_parts[0])
        assert "<information>" in content_text

        # Citations should include both markdown and XML urls
        assert len(message.citations) == 4

        # Each citation should have an idx attribute or [!CITE_X!] reference
        for idx in range(1, len(message.citations) + 1):
            assert f'idx="{idx}"' in content_text or f"[!CITE_{idx}!]" in content_text

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_create_event_handles_no_citations(self):
        """MESSAGE_CREATE_BEFORE handles messages without citations."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append("This message has no citations.")

        message = agent.messages[-1]

        # Citations should be None or empty
        assert message.citations is None or len(message.citations) == 0

        await agent.events.close()


class TestMessageRenderEvent:
    """Test MESSAGE_RENDER_BEFORE event handling."""

    @pytest.mark.asyncio
    async def test_render_event_transforms_for_display(self, recwarn):
        """MESSAGE_RENDER_BEFORE transforms citations for DISPLAY mode."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            Text [1].

            [1]: https://example.com/doc
            """
        )

        message = agent.messages[-1]

        # Render for display should transform to markdown links
        rendered = message.render(RenderMode.DISPLAY)

        assert (
            len(recwarn) == 0
        )  # No warnings - there should be no recursion warning from rendering

        # Should have markdown link format
        assert "[example.com](https://example.com/doc)" in rendered
        # Reference block should be removed
        assert "[1]:" not in rendered

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_render_event_transforms_for_llm(self):
        """MESSAGE_RENDER_BEFORE transforms citations for LLM mode."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            Text [1].

            [1]: https://example.com/doc
            """
        )

        message = agent.messages[-1]
        global_idx = manager.index.lookup("https://example.com/doc")

        # Render for LLM should use global indices
        rendered_llm = message.render(RenderMode.LLM)

        # Should have global index reference
        assert f"[!CITE_{global_idx}!]" in rendered_llm

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_render_event_ensure_global_index(self):
        """MESSAGE_RENDER_BEFORE ensures citations use global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        all_urls = set()

        # Pre-populate global index
        agent.append(
            """
            Some initial text [1][2].
            Some more text[3].
            """,
            citations=[
                "https://example.com/doc",
                "https://example.com/other",
                "https://example.com/more",
            ],
        )

        # Message stored with local indices
        message = agent.messages[-1]

        assert message.citations is not None
        assert len(message.citations) == 3

        all_urls.update(message.citations)

        assert message.content_parts[0].type == "text"
        for i in range(1, 4):
            assert f"[!CITE_{i}!]" in str(message.content_parts[0])

        initial_count = len(manager.index)
        assert initial_count == 3

        # Now append new message referencing same citation
        agent.append(
            """
            First references same doc [1].
            Next references new docs [2] and [3].
            """,
            citations=[
                "https://example.com/doc",  # Existing
                "https://example.com/new1",  # New
                "https://example.com/new2",  # New
            ],
        )

        message = agent.messages[-1]

        assert message.citations is not None
        assert len(message.citations) == 3

        all_urls.update(message.citations)

        assert message.content_parts[0].type == "text"
        # stored with local indicies again
        for i in range(1, 4):
            assert f"[!CITE_{i}!]" in str(message.content_parts[0])

        for message in agent.messages:
            rendered_llm = message.render(RenderMode.LLM)
            for url in message.citations or []:
                # rendered should use global index
                global_idx = manager.index.lookup(url)
                assert f"[!CITE_{global_idx}!]" in rendered_llm

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_render_event_preserves_xml_structure(self):
        """MESSAGE_RENDER_BEFORE preserves XML structure in tool messages."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            <results>
                <item url="https://example.com/item1" />
            </results>
            """,
            role="tool",
        )

        message = agent.messages[-1]

        assert message.citations is not None
        assert "https://example.com/item1" in message.citations
        assert message.content_parts[0].type == "text"
        assert "<results>" in str(message.content_parts[0])
        assert 'idx="1"' in str(message.content_parts[0])

        # Display render should preserve XML and inline citations
        rendered = message.render(RenderMode.DISPLAY)

        assert "<results>" in rendered
        assert 'url="https://example.com/item1"' in rendered

        rendered_llm = message.render(RenderMode.LLM)

        assert "<results>" in rendered_llm
        # Should reference global index (the same in this case)
        assert 'idx="1"' in rendered_llm

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_render_event_mixed_content_global_index(self):
        """MESSAGE_RENDER_BEFORE handles mixed XML/markdown with global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append(
            """
            <information>
              Here is a block of content with inline citations [1].
              Here's another citation [2].

                [1]: https://example.com/doc
                [2]: https://example.com/otherdoc

              <profiles>
                <profile url="https://example.com/item1" />
              </profiles>
            </information>
            """,
            role="tool",
        )

        message = agent.messages[-1]
        assert message.citations is not None
        assert len(message.citations) == 3
        assert "https://example.com/doc" in message.citations
        assert "https://example.com/item1" in message.citations

        agent.append(
            """
            Another message referencing same [1] and new [2].

            <links>
                <link url="https://example.com/item2" />
            </links>
            """,
            citations=[
                "https://example.com/doc",  # Existing
                "https://example.com/newdoc",  # New
            ],  # citations does not include item2 because it was provided directly in XML
        )

        message = agent.messages[-1]
        assert message.citations is not None
        assert len(message.citations) == 3
        assert "https://example.com/doc" in message.citations
        assert "https://example.com/newdoc" in message.citations
        assert "https://example.com/item2" in message.citations  # extracted from XML

        # Render all messages and ensure global indices used
        for msg in agent.messages:
            rendered_llm = msg.render(RenderMode.LLM)
            for url in msg.citations or []:
                global_idx = manager.index.lookup(url)
                assert (
                    f"[!CITE_{global_idx}!]" in rendered_llm
                    or f'idx="{global_idx}"' in rendered_llm
                )

    @pytest.mark.asyncio
    async def test_render_event_inline_citation_no_source_warning(self, caplog):
        """MESSAGE_RENDER_BEFORE handles inline citation without source."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        logger_name = "good_agent.extensions.citations.manager"
        with caplog.at_level(logging.WARNING, logger=logger_name):
            agent.append("Text with inline citation [1] but no source.")

        assert any(
            "Citation [1] has no corresponding source" in record.message
            for record in caplog.records
            if record.name == logger_name
        )

        message = agent.messages[-1]

        # Citations should be None or empty
        assert message.citations is None or len(message.citations) == 0

        # Render for display should leave as-is
        rendered = message.render(RenderMode.DISPLAY)
        assert "[1]" in rendered

        # Render for LLM should also leave as-is
        rendered_llm = message.render(RenderMode.LLM)
        assert "[1]" in rendered_llm

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_render_event_inline_citation_global_index_warning(self, recwarn):
        """MESSAGE_RENDER_BEFORE warns if inline citation not in global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        manager.index.add("https://example.com/otherdoc")  # idx 1
        manager.index.add("https://example.com/moredoc")  # idx 2
        manager.index.add("https://example.com/doc")  # idx 3

        agent.append(
            """
            Text with global citations [2] and [3]
            """,
            # Global indices pre-populated above; manager will resolve automatically at append-time
        )

        message = agent.messages[-1]
        assert message.citations is not None
        assert len(message.citations) == 2  # two provided

        assert "https://example.com/moredoc" in message.citations
        assert "https://example.com/doc" in message.citations

        for i in range(1, 3):
            # local indices created for storage
            assert f"[!CITE_{i}!]" in str(message.content_parts[0])

        assert len(recwarn) == 0  # No warnings as global citations found

        await agent.events.close()


"""
@TODO: Need to think about these tests / desired behavior
 - When would a user create an AssistantMessage directly?
 - Messages are immutable, so if a message is created with inline citations, how do we handle that?
"""
# class TestMessageAppendEvent:
#     """Test MESSAGE_APPEND_AFTER event handling."""

#     @pytest.mark.asyncio
#     async def test_append_event_processes_assistant_message(self):
#         """MESSAGE_APPEND_AFTER processes pre-created AssistantMessage."""
#         manager = CitationManager()
#         agent = Agent(extensions=[manager])
#         await agent.initialize()

#         # Pre-populate index
#         agent.append("Doc [1]\n\n[1]: https://example.com/doc1")

#         # Create AssistantMessage with reference to existing citation
#         msg = AssistantMessage("According to [1], we see that...")

#         agent.append(msg)

#         # Citation should be resolved from global index
#         appended_msg = agent.messages[-1]

#         # Should have citations populated
#         assert appended_msg.citations is not None

#         await agent.events.close()

#     @pytest.mark.asyncio
#     async def test_append_event_skips_if_citations_present(self):
#         """MESSAGE_APPEND_AFTER skips processing if citations already set."""
#         manager = CitationManager()
#         agent = Agent(extensions=[manager])
#         await agent.initialize()

#         # Create message with explicit citations
#         citations = ["https://example.com/doc1"]
#         msg = UserMessage("Text [1]", citations=citations)

#         agent.append(msg)

#         appended_msg = agent.messages[-1]

#         # Citations should remain unchanged
#         assert appended_msg.citations == citations

#         # Global index should have new citation added
#         assert manager.index.lookup("https://example.com/doc1") == 1

#         await agent.events.close()

#     @pytest.mark.asyncio
#     async def test_append_event_handles_llm_cite_format(self):
#         """MESSAGE_APPEND_AFTER handles [!CITE_X!] references."""
#         manager = CitationManager()
#         agent = Agent(extensions=[manager])
#         await agent.initialize()

#         # Pre-populate index
#         idx = manager.index.add("https://example.com/doc")

#         # Create message with [!CITE_X!] format
#         msg = AssistantMessage(f"According to [!CITE_{idx}!], we see...")

#         agent.append(msg)

#         appended_msg = agent.messages[-1]

#         # Citation should be resolved
#         assert appended_msg.citations is not None
#         assert len(appended_msg.citations) >= 1

#         await agent.events.close()


# class TestEventOrdering:
#     """Test that events fire in correct order."""

#     @pytest.mark.asyncio
#     async def test_create_before_happens_before_append(self):
#         """MESSAGE_CREATE_BEFORE fires before MESSAGE_APPEND_AFTER."""
#         manager = CitationManager()
#         agent = Agent(extensions=[manager])
#         await agent.initialize()

#         event_order = []

#         def track_create(ctx):
#             event_order.append("create")

#         def track_append(ctx):
#             event_order.append("append")

#         # Register tracking handlers
#         agent.on(AgentEvents.MESSAGE_CREATE_BEFORE)(track_create)
#         agent.on(AgentEvents.MESSAGE_APPEND_AFTER)(track_append)

#         agent.append("Test message")

#         # Create should fire before append
#         assert event_order == ["create", "append"]

#         await agent.events.close()

#     @pytest.mark.asyncio
#     async def test_render_event_fires_on_each_render(self):
#         """MESSAGE_RENDER_BEFORE fires each time message is rendered."""
#         manager = CitationManager()
#         agent = Agent(extensions=[manager])
#         await agent.initialize()

#         agent.append("Test message")
#         message = agent.messages[-1]

#         render_count = [0]

#         def track_render(ctx):
#             render_count[0] += 1

#         agent.on(AgentEvents.MESSAGE_RENDER_BEFORE)(track_render)

#         # Render multiple times
#         message.render(RenderMode.DISPLAY)
#         message.render(RenderMode.LLM)
#         message.render(RenderMode.DISPLAY)

#         # Should fire for each render
#         assert render_count[0] == 3

#         await agent.events.close()


class TestEventPriorities:
    """Test that CitationManager handlers run at correct priority."""

    @pytest.mark.asyncio
    async def test_citation_handler_priority(self):
        """CitationManager handlers run at priority 150."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        execution_order = []

        # Register handlers at different priorities
        @agent.on(AgentEvents.MESSAGE_CREATE_BEFORE, priority=100)
        def early_handler(ctx):
            execution_order.append("early")

        @agent.on(AgentEvents.MESSAGE_CREATE_BEFORE, priority=200)
        def late_handler(ctx):
            execution_order.append("late")

        agent.append("Test")

        # Citation manager (priority 150) should run between these
        # Order should be: late (200), citation_manager (150), early (100)
        assert execution_order == ["late", "early"]

        await agent.events.close()


class TestErrorHandling:
    """Test error handling in event handlers."""

    @pytest.mark.asyncio
    async def test_malformed_content_doesnt_break_agent(self):
        """Malformed citation content doesn't crash agent."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        # Malformed citations
        agent.append("Text [1] without references")
        agent.append("Text with [xyz] non-numeric reference")

        # Should not crash
        assert len(agent.messages) == 2

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_missing_citation_reference_handled(self):
        """Missing citation references are handled gracefully."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        # Reference [2] but only provide [1]
        agent.append(
            """
            Text [1] and [2].

            [1]: https://example.com/doc1
            """
        )

        message = agent.messages[-1]

        # Should not crash, message created successfully
        assert message is not None

        await agent.events.close()


class TestMultipleMessages:
    """Test citation handling across multiple messages."""

    @pytest.mark.asyncio
    async def test_citations_accumulate_in_global_index(self):
        """Citations from multiple messages accumulate in global index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        agent.append("First [1]\n\n[1]: https://example.com/doc1")
        agent.append("Second [1]\n\n[1]: https://example.com/doc2")
        agent.append("Third [1]\n\n[1]: https://example.com/doc3")

        # Global index should have all three
        assert len(manager.index) == 3

        await agent.events.close()

    @pytest.mark.asyncio
    async def test_cross_message_citation_consistency(self):
        """Same URL referenced in multiple messages has consistent index."""
        manager = CitationManager()
        agent = Agent(extensions=[manager])
        await agent.initialize()

        url = "https://example.com/doc"

        agent.append(f"First [1]\n\n[1]: {url}")
        agent.append(f"Second [1]\n\n[1]: {url}")

        # Both messages reference same global index
        idx1 = manager.index.lookup(url)

        # Render both for LLM
        msg1_llm = agent.messages[-2].render(RenderMode.LLM)
        msg2_llm = agent.messages[-1].render(RenderMode.LLM)

        # Both should reference same global index
        assert f"[!CITE_{idx1}!]" in msg1_llm or "[1]" in msg1_llm
        assert f"[!CITE_{idx1}!]" in msg2_llm or "[1]" in msg2_llm

        await agent.events.close()
