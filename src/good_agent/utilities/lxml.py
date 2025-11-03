"""
CONTEXT: XML and HTML processing utilities using lxml.
ROLE: Provide utilities for parsing and extracting structured content from XML/HTML
      documents, particularly first-level element extraction for model processing.
DEPENDENCIES: lxml.html for HTML/XML parsing and serialization.
ARCHITECTURE: Simple utility functions for common XML/HTML processing patterns.
KEY EXPORTS: extract_first_level_xml
USAGE PATTERNS:
  1) Extract first-level XML content from HTML documents
  2) Parse structured content for model initialization
  3) Process XML templates and dynamic content
RELATED MODULES:
  - goodintel_core.models.renderable: XML content extraction for templates
  - goodintel_core.models.application: Application model XML processing
"""

import lxml.html


def extract_first_level_xml(xml_string: str) -> str:
    """
    Extract the inner content of first-level XML-like tags from a string.

    PURPOSE: Parse XML/HTML content and extract direct children of the root element,
    preserving their structure and content for further processing.

    ARGS:
        xml_string: A string containing XML-like content with proper structure

    RETURNS:
        str: The concatenated first-level XML elements with their content,
             preserving original formatting and structure

    NOTES:
        - Uses lxml.html.fromstring() for robust parsing
        - Extracts only direct children of the root element
        - Preserves original XML structure and content
        - Commonly used for processing structured content in models

    EXAMPLE:
        Input: "<root><item>1</item><item>2</item></root>"
        Output: "<item>1</item><item>2</item>"
    """
    tree = lxml.html.fromstring(xml_string)

    return "".join([lxml.html.tostring(child).decode() for child in tree])
