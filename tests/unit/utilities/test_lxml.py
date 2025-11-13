"""Tests for utilities/lxml.py module."""

from good_agent.utilities.lxml import extract_first_level_xml


class TestExtractFirstLevelXml:
    """Tests for extract_first_level_xml function."""

    def test_extract_simple_elements(self):
        """Test extraction of simple first-level elements."""
        xml_string = "<root><item>1</item><item>2</item></root>"
        result = extract_first_level_xml(xml_string)

        assert "<item>1</item>" in result
        assert "<item>2</item>" in result
        assert "<root>" not in result

    def test_extract_nested_elements(self):
        """Test extraction preserves nested structure."""
        xml_string = "<root><item><sub>nested</sub></item></root>"
        result = extract_first_level_xml(xml_string)

        assert "<item><sub>nested</sub></item>" in result
        assert "nested" in result

    def test_extract_multiple_types(self):
        """Test extraction with multiple element types."""
        xml_string = "<root><a>first</a><b>second</b><c>third</c></root>"
        result = extract_first_level_xml(xml_string)

        assert "<a>first</a>" in result
        assert "<b>second</b>" in result
        assert "<c>third</c>" in result

    def test_extract_with_attributes(self):
        """Test extraction preserves element attributes."""
        xml_string = '<root><item id="1">value</item></root>'
        result = extract_first_level_xml(xml_string)

        assert 'id="1"' in result
        assert "value" in result

    def test_extract_empty_elements(self):
        """Test extraction of empty elements."""
        xml_string = "<root><item></item></root>"
        result = extract_first_level_xml(xml_string)

        assert "<item></item>" in result

    def test_extract_text_content(self):
        """Test extraction preserves text content."""
        xml_string = "<root><item>Hello World</item></root>"
        result = extract_first_level_xml(xml_string)

        assert "Hello World" in result
