"""
Test citation reference priority when both global index and local references exist.
"""

import pytest
from good_agent import Agent
from good_agent.content import RenderMode
from good_agent.extensions.citations import CitationManager


@pytest.mark.asyncio
async def test_markdown_reference_block_takes_precedence():
    """Test that markdown reference blocks take precedence over global index."""
    # Pre-populate global index
    citation_manager = CitationManager()

    # Add some citations to global index - these should NOT be used for [1], [2], [3]
    citation_manager.index.add("https://global1.com/doc.pdf")  # CITE_1
    citation_manager.index.add("https://global2.com/doc.pdf")  # CITE_2
    citation_manager.index.add("https://global3.com/doc.pdf")  # CITE_3

    # Content with markdown citations AND a reference block
    content_with_refs = """
    This document cites [1] and [2] and [3].
    
    [1]: https://local1.com/paper.pdf
    [2]: https://local2.com/paper.pdf
    [3]: https://local3.com/paper.pdf
    """

    agent = Agent("Test", extensions=[citation_manager])
    await agent.ready()

    agent.append(content_with_refs)

    message = agent.messages[-1]

    # Check citations were extracted from reference block
    assert message.citations is not None
    print(f"\nExtracted citations: {message.citations}\n")
    assert len(message.citations) == 3

    # The citations should be from the reference block, NOT the global index
    assert "https://local1.com/paper.pdf" in str(message.citations[0])
    assert "https://local2.com/paper.pdf" in str(message.citations[1])
    assert "https://local3.com/paper.pdf" in str(message.citations[2])

    # NOT the global ones
    assert "https://global1.com" not in str(message.citations)
    assert "https://global2.com" not in str(message.citations)
    assert "https://global3.com" not in str(message.citations)

    # Display render should show local URLs
    display_content = message.render(RenderMode.DISPLAY)
    print("\n=== DISPLAY RENDER ===")
    print(display_content)
    print("=== END ===\n")

    # Should have local URLs in links
    assert "local1.com" in display_content
    assert "local2.com" in display_content
    assert "local3.com" in display_content

    # Should NOT have global URLs
    assert "global1.com" not in display_content
    assert "global2.com" not in display_content
    assert "global3.com" not in display_content

    # Reference block should be removed
    assert "[1]: https://local1.com/paper.pdf" not in display_content
    assert "[2]: https://local2.com/paper.pdf" not in display_content
    assert "[3]: https://local3.com/paper.pdf" not in display_content
