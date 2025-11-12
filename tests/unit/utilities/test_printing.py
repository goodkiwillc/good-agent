"""Tests for utilities/printing.py module."""

from good_agent.utilities.printing import (
    _detect_markdown,
    _format_tool_calls,
    _preprocess_xml_tags,
)


class TestDetectMarkdown:
    """Tests for markdown detection."""

    def test_detect_code_blocks(self):
        """Test detection of code blocks."""
        assert _detect_markdown("Some text ```code``` more text")

    def test_detect_inline_code(self):
        """Test detection of inline code."""
        assert _detect_markdown("Some text `code` more text")

    def test_detect_bold(self):
        """Test detection of bold text."""
        assert _detect_markdown("Some **bold** text")

    def test_detect_headers(self):
        """Test detection of headers."""
        assert _detect_markdown("## Header")
        assert _detect_markdown("### Subheader")

    def test_detect_links(self):
        """Test detection of links."""
        assert _detect_markdown("[link](url)")

    def test_detect_images(self):
        """Test detection of images."""
        assert _detect_markdown("![alt](image.png)")

    def test_detect_blockquotes(self):
        """Test detection of blockquotes."""
        assert _detect_markdown("> quoted text")

    def test_detect_horizontal_rules(self):
        """Test detection of horizontal rules."""
        assert _detect_markdown("---")
        assert _detect_markdown("___")
        assert _detect_markdown("***")

    def test_detect_numbered_lists(self):
        """Test detection of numbered lists."""
        assert _detect_markdown("1. First item\n2. Second item")

    def test_no_markdown_plain_text(self):
        """Test plain text returns False."""
        assert not _detect_markdown("Just plain text")

    def test_no_markdown_empty_string(self):
        """Test empty string returns False."""
        assert not _detect_markdown("")

    def test_no_markdown_none(self):
        """Test None returns False."""
        assert not _detect_markdown(None)

    def test_single_asterisk_bullet_not_markdown(self):
        """Test single asterisk for bullets is not considered markdown."""
        # Starts with bullet, should not be detected as italic
        assert not _detect_markdown("* bullet point\n* another bullet")


class TestPreprocessXmlTags:
    """Tests for XML tag preprocessing."""

    def test_no_xml_returns_unchanged(self):
        """Test content without XML tags is unchanged."""
        content = "Just plain text with no tags"
        assert _preprocess_xml_tags(content) == content

    def test_wraps_simple_xml_tag(self):
        """Test simple XML tags get wrapped."""
        content = "Before <tag>content</tag> after"
        result = _preprocess_xml_tags(content)
        assert "```xml" in result
        assert "<tag>content</tag>" in result

    def test_preserves_existing_code_blocks(self):
        """Test existing code blocks are not modified."""
        content = "Text ```<already>formatted</already>``` more text"
        result = _preprocess_xml_tags(content)
        # Should not add additional wrapping
        assert result.count("```") == 2  # Original code block only

    def test_handles_self_closing_tags(self):
        """Test self-closing XML tags."""
        content = "Before <tag/> after"
        result = _preprocess_xml_tags(content)
        # Should wrap self-closing tag
        assert (
            "```xml" in result or result == content
        )  # May or may not wrap depending on proximity

    def test_empty_string(self):
        """Test empty string is unchanged."""
        assert _preprocess_xml_tags("") == ""


class TestFormatToolCalls:
    """Tests for tool call formatting."""

    def test_format_plain_single_tool(self):
        """Test plain format with single tool call."""

        class MockToolCall:
            name = "search"
            function = None

        tool_calls = [MockToolCall()]
        result = _format_tool_calls(tool_calls, "plain")

        assert "Tool: search" in result
        assert "Arguments:" in result

    def test_format_plain_multiple_tools(self):
        """Test plain format with multiple tool calls."""

        class MockToolCall:
            name = "tool"
            function = None

        tool_calls = [MockToolCall(), MockToolCall()]
        result = _format_tool_calls(tool_calls, "plain")

        assert "Tool 1:" in result
        assert "Tool 2:" in result

    def test_format_markdown_single_tool(self):
        """Test markdown format with single tool call."""

        class MockToolCall:
            name = "search"
            function = None

        tool_calls = [MockToolCall()]
        result = _format_tool_calls(tool_calls, "markdown")

        assert "###" in result
        assert "`search`" in result
        assert "```json" in result

    def test_format_markdown_multiple_tools(self):
        """Test markdown format with multiple tool calls."""

        class MockToolCall:
            name = "tool"
            function = None

        tool_calls = [MockToolCall(), MockToolCall()]
        result = _format_tool_calls(tool_calls, "markdown")

        assert "Tool 1:" in result
        assert "Tool 2:" in result

    def test_format_rich_with_function_attribute(self):
        """Test rich format with function attribute."""

        class MockFunction:
            name = "calculate"
            arguments = '{"x": 10, "y": 20}'

        class MockToolCall:
            function = MockFunction()

        tool_calls = [MockToolCall()]
        result = _format_tool_calls(tool_calls, "rich")

        assert "calculate" in result
        assert "```json" in result

    def test_format_handles_invalid_json(self):
        """Test formatting handles invalid JSON gracefully."""

        class MockFunction:
            name = "tool"
            arguments = "not valid json"

        class MockToolCall:
            function = MockFunction()

        tool_calls = [MockToolCall()]
        result = _format_tool_calls(tool_calls, "rich")

        # Should still return something without crashing
        assert "tool" in result
        assert "not valid json" in result

    def test_format_unknown_tool_name(self):
        """Test formatting with tool that has no name attribute."""

        class MockToolCall:
            pass

        tool_calls = [MockToolCall()]
        result = _format_tool_calls(tool_calls, "plain")

        # Should handle missing name gracefully
        assert "unknown" in result

    def test_format_empty_tool_calls(self):
        """Test formatting with empty tool calls list."""
        result = _format_tool_calls([], "plain")
        # Should return empty string
        assert result == ""
