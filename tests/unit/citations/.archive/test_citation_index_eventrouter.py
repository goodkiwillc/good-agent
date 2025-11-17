import pytest
from good_agent import Agent
from good_agent.extensions.index import Citation, CitationIndex, Paragraph


@pytest.mark.asyncio
async def test_citation_index_receives_message_append_event():
    """Test that CitationIndex receives and processes message:append events."""
    # Create agent with CitationIndex extension
    citation_index = CitationIndex()
    agent = Agent("You are a helpful assistant", extensions=[citation_index])

    # Wait for agent to be ready
    await agent.initialize()

    # Append a message with citations
    agent.append(
        "This is from source [1] and also [2].",
        citations=["https://example.com/source1", "https://example.org/source2"],
    )

    # Verify citations were indexed
    assert len(citation_index._index) == 2

    # Check that citations were properly extracted
    citations_list = list(citation_index._index.values())
    assert any(c.origin == "https://example.com/source1" for c in citations_list)
    assert any(c.origin == "https://example.org/source2" for c in citations_list)

    # Check that source domains were extracted
    assert any(c.source == "example.com" for c in citations_list)
    assert any(c.source == "example.org" for c in citations_list)


@pytest.mark.asyncio
async def test_citation_index_receives_tool_response_event():
    """Test that CitationIndex receives and processes tool:response events."""
    # Create agent with CitationIndex extension
    citation_index = CitationIndex()
    agent = Agent("You are a helpful assistant", extensions=[citation_index])

    # Wait for agent to be ready
    await agent.initialize()

    # Create a Paragraph with citation
    citation = Citation(
        text="Example text",
        origin="https://example.com/article",
        source="Example Source",
    )
    paragraph = Paragraph("This is cited content", citation)

    # Simulate a tool response event
    agent.do("tool:call:after", response=paragraph, tool="test_tool")

    # Verify citation was indexed
    assert len(citation_index._index) == 1
    assert citation.id in citation_index._index

    # Verify content mapping
    assert citation_index._content_map[citation.id] == "This is cited content"


def test_citation_index_paragraph_llm_rendering():
    """Test that Paragraph properly renders citations for LLM context."""
    citation = Citation(id="abc123", text="Example text", origin="https://example.com")
    paragraph = Paragraph("This is the content", citation)

    # Test __llm__ rendering includes citation ID
    llm_output = paragraph.__llm__()
    assert llm_output == "This is the content [abc123]"

    # Test regular string representation doesn't include citation
    str_output = str(paragraph)
    assert str_output == "This is the content"


def test_citation_index_lookup_operations():
    """Test CitationIndex lookup and alias operations."""
    index = CitationIndex()

    # Add a citation
    citation = Citation(
        text="Test citation",
        origin="https://example.com",
        source="Example",
        metadata={"type": "article"},
    )

    citation_id = index.add("Test content", citation, tags=["test", "example"])

    # Test lookup by content
    found_id = index.lookup("Test content")
    assert found_id == citation_id

    # Test __getitem__ retrieval
    content = index[citation_id]
    assert content == "Test content"

    # Test alias functionality
    alias_id = index.add_alias(citation_id, "short-ref")
    assert alias_id == citation_id

    # Retrieve via alias
    content_via_alias = index["short-ref"]
    assert content_via_alias == "Test content"


def test_citation_index_tag_management():
    """Test CitationIndex tag operations."""
    index = CitationIndex()

    # Add citations with tags
    citation1 = Citation(text="First", origin="https://example1.com")
    id1 = index.add("Content 1", citation1, tags=["science", "research"])

    citation2 = Citation(text="Second", origin="https://example2.com")
    id2 = index.add("Content 2", citation2, tags=["science", "news"])

    # Find by single tag
    science_ids = index.find_by_tag("science")
    assert len(science_ids) == 2
    assert id1 in science_ids
    assert id2 in science_ids

    # Find by multiple tags (match any)
    found_ids = index.find_by_tags(["research", "news"], match_all=False)
    assert len(found_ids) == 2

    # Find by multiple tags (match all)
    found_ids = index.find_by_tags(["science", "research"], match_all=True)
    assert len(found_ids) == 1
    assert id1 in found_ids

    # Add and remove tags
    index.add_tag(id2, "important")
    assert "important" in index.get_tags(id2)

    index.remove_tag(id2, "important")
    assert "important" not in index.get_tags(id2)


def test_citation_index_metadata_operations():
    """Test CitationIndex metadata management."""
    index = CitationIndex()

    # Add citation with metadata
    citation = Citation(
        text="Test",
        origin="https://example.com",
        metadata={"author": "John Doe", "year": 2024},
    )
    cid = index.add("Test content", citation)

    # Get metadata
    metadata = index.get_metadata(cid)
    assert metadata["author"] == "John Doe"
    assert metadata["year"] == 2024

    # Update metadata
    index.update_metadata(cid, category="research", reviewed=True)
    metadata = index.get_metadata(cid)
    assert metadata["category"] == "research"
    assert metadata["reviewed"] is True
    assert metadata["author"] == "John Doe"  # Original still there

    # Set (replace) metadata
    index.set_metadata(cid, type="article", status="published")
    metadata = index.get_metadata(cid)
    assert metadata["type"] == "article"
    assert metadata["status"] == "published"
    assert "author" not in metadata  # Original replaced

    # Find by metadata
    found_ids = index.find_by_metadata(type="article", status="published")
    assert len(found_ids) == 1
    assert cid in found_ids


def test_citation_index_summary():
    """Test CitationIndex summary generation."""
    index = CitationIndex()

    # Empty index
    summary = index.get_citations_summary()
    assert summary == "No citations available."

    # Add some citations
    c1 = Citation(
        id="ref1",
        text="First citation",
        origin="https://example.com/article1",
        source="Example News",
    )
    index.add("Content 1", c1)

    c2 = Citation(
        id="ref2",
        text="Second citation",
        origin="https://research.org/paper",
        source="Research Journal",
    )
    index.add("Content 2", c2)

    # Get summary
    summary = index.get_citations_summary()
    assert "Citations:" in summary
    assert "[ref1] - Example News (https://example.com/article1)" in summary
    assert "[ref2] - Research Journal (https://research.org/paper)" in summary


@pytest.mark.asyncio
async def test_citation_index_with_agent_context_manager():
    """Test CitationIndex works with Agent async context manager."""
    citation_index = CitationIndex()
    async with Agent("Test assistant", extensions=[citation_index]) as agent:
        # Agent should be ready in context manager
        assert agent._state.value >= 1  # READY state

        # Add message with citations
        agent.append("Information from [1]", citations=["https://source.com"])

        # Verify citation was indexed
        assert len(citation_index._index) == 1
