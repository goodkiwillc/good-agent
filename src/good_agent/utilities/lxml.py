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
