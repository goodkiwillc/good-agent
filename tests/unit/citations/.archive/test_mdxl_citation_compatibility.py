import pytest
from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.extensions.citations import CitationManager


class TestMDXLCitationCompatibility:
    """Test suite for MDXL + CitationManager integration."""

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Citation display rendering not fully implemented")
    async def test_markdown_reference_block_not_duplicated(self):
        """Test that markdown reference blocks are extracted but not re-added as content."""
        # MDXL content with markdown reference block at the end
        mdxl_content = """
        <document>
            <title>Test Document</title>
            <content>
                This is a document with citations [1] and [2] in the text.
                The research [3] shows important findings.
            </content>
        </document>
        
        [1]: https://example.com/paper1.pdf
        [2]: https://example.com/paper2.pdf  
        [3]: https://example.com/research.pdf
        """

        # Create agent with citation manager
        citation_manager = CitationManager()
        agent = Agent("Test agent", extensions=[citation_manager])
        await agent.initialize()

        # Add the MDXL content as a message
        agent.append(mdxl_content)

        # Get the last message
        last_message = agent.messages[-1]

        # Check that citations were extracted
        assert hasattr(last_message, "citations")
        assert last_message.citations is not None
        assert len(last_message.citations) == 3
        assert "https://example.com/paper1.pdf" in str(last_message.citations[0])
        assert "https://example.com/paper2.pdf" in str(last_message.citations[1])
        assert "https://example.com/research.pdf" in str(last_message.citations[2])

        # Render the message for display
        from good_agent.content import RenderMode

        display_content = last_message.render(RenderMode.DISPLAY)

        # The reference block should be removed, not duplicated
        assert "[1]: https://example.com/paper1.pdf" not in display_content
        assert "[2]: https://example.com/paper2.pdf" not in display_content
        assert "[3]: https://example.com/research.pdf" not in display_content

        # The display should not have duplicate citation indices at the end
        # like "[!CITE_1!]: [!CITE_178!]"
        assert "[!CITE_1!]: [!CITE_" not in display_content
        assert "[!CITE_2!]: [!CITE_" not in display_content
        assert "[!CITE_3!]: [!CITE_" not in display_content

        # Print for debugging
        print("\n=== DISPLAY CONTENT ===")
        print(display_content)
        print("=== END DISPLAY ===\n")

        # The content should have proper citation links
        assert "[example.com](https://example.com/paper1.pdf)" in display_content

        # Render for LLM
        llm_content = last_message.render(RenderMode.LLM)

        # Should have [!CITE_X!] format for LLM
        assert "[!CITE_1!]" in llm_content
        assert "[!CITE_2!]" in llm_content
        assert "[!CITE_3!]" in llm_content

        # Should not have the reference block in LLM format either
        assert "[1]: https://example.com" not in llm_content
        assert "[2]: https://example.com" not in llm_content
        assert "[3]: https://example.com" not in llm_content

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Citation display rendering not fully implemented")
    async def test_mdxl_with_inline_citations_only(self):
        """Test MDXL content with citations already in [!CITE_X!] format."""
        mdxl_content = """
        <document>
            <content>
                The study [!CITE_1!] shows that results [!CITE_2!] are significant.
            </content>
        </document>
        """

        # Add citations to global index first
        citation_manager = CitationManager()
        citation_manager.index.add("https://study.com/paper.pdf")  # Will be CITE_1
        citation_manager.index.add("https://results.com/data.pdf")  # Will be CITE_2

        agent = Agent("Test agent", extensions=[citation_manager])
        await agent.initialize()

        # Add the content
        agent.append(mdxl_content)

        last_message = agent.messages[-1]

        # Render for display
        from good_agent.content import RenderMode

        display_content = last_message.render(RenderMode.DISPLAY)

        # Should convert to markdown links
        assert (
            "[study.com/paper.pdf](https://study.com/paper.pdf)" in display_content
            or "study.com" in display_content
        )
        assert (
            "[results.com/data.pdf](https://results.com/data.pdf)" in display_content
            or "results.com" in display_content
        )

        # Should not have duplicate citation blocks at the end
        assert "[!CITE_1!]: [!CITE_" not in display_content
        assert "[!CITE_2!]: [!CITE_" not in display_content

    @pytest.mark.asyncio
    async def test_mixed_citation_formats(self):
        """Test MDXL with both markdown references and inline citations."""
        mdxl_content = """
        <document>
            <content>
                Some citations use markdown format [1] while others 
                use the LLM format [!CITE_10!] in the same document.
            </content>
        </document>
        
        [1]: https://markdown.com/ref.pdf
        """

        # Pre-populate global index with CITE_10
        citation_manager = CitationManager()
        for i in range(10):
            citation_manager.index.add(f"https://example.com/doc{i}.pdf")

        agent = Agent("Test agent", extensions=[citation_manager])
        await agent.initialize()

        agent.append(mdxl_content)

        last_message = agent.messages[-1]

        # Check citations were extracted properly
        assert hasattr(last_message, "citations")
        assert last_message.citations is not None
        # Should have extracted the markdown reference
        assert any("markdown.com/ref.pdf" in str(c) for c in last_message.citations)

        from good_agent.content import RenderMode

        # Display rendering
        display_content = last_message.render(RenderMode.DISPLAY)

        # Should not have the reference block
        assert "[1]: https://markdown.com/ref.pdf" not in display_content

        # Should not have duplicate indices at the end
        assert "[!CITE_1!]: [!CITE_" not in display_content

        # LLM rendering
        llm_content = last_message.render(RenderMode.LLM)

        # Should normalize both to [!CITE_X!] format
        assert "[!CITE_" in llm_content
        # Original markdown [1] should be converted
        assert "[1]" not in llm_content or "[!CITE_1!]" in llm_content
        # Should preserve or renumber [!CITE_10!]
        assert "[!CITE_10!]" in llm_content or "[!CITE_" in llm_content

    @pytest.mark.asyncio
    async def test_reference_block_with_existing_citations_in_global_index(self):
        """Test the specific issue where citations appear as [!CITE_1!]: [!CITE_178!]."""
        # Pre-populate global index with many citations
        citation_manager = CitationManager()

        # Add 177 citations to the global index
        for i in range(1, 178):
            citation_manager.index.add(f"https://previous.com/doc{i}.pdf")

        # Now we have a document with its own reference block
        mdxl_content = """
        <document>
            <content>
                New document with citations [1], [2], [3].
            </content>
        </document>
        
        [1]: https://new.com/ref1.pdf
        [2]: https://new.com/ref2.pdf
        [3]: https://new.com/ref3.pdf
        """

        agent = Agent("Test agent", extensions=[citation_manager])
        await agent.initialize()

        agent.append(mdxl_content)

        last_message = agent.messages[-1]

        # Render for display
        display_content = last_message.render(RenderMode.DISPLAY)

        print("\n=== DISPLAY CONTENT WITH EXISTING INDEX ===")
        print(display_content)
        print("=== END ===\n")

        # Check for the problematic pattern
        assert "[!CITE_1!]: [!CITE_178!]" not in display_content
        assert "[!CITE_2!]: [!CITE_177!]" not in display_content
        assert "[!CITE_3!]: [!CITE_176!]" not in display_content

        # Should not have ANY [!CITE_X!]: [!CITE_Y!] patterns
        import re

        problematic_pattern = re.compile(r"\[!CITE_\d+!\]:\s*\[!CITE_\d+!\]")
        assert not problematic_pattern.search(display_content), (
            "Found problematic citation pattern in display content"
        )

        # The reference block should be properly removed
        assert "[1]: https://new.com/ref1.pdf" not in display_content
        assert "[2]: https://new.com/ref2.pdf" not in display_content
        assert "[3]: https://new.com/ref3.pdf" not in display_content
