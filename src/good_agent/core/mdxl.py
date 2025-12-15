from __future__ import annotations

import copy
import datetime
import re
import textwrap
from typing import Any, Literal, overload

import lxml.etree as etree
import yaml
from box import Box
from good_common.utilities import try_chain

_DATA_ATTRIBUTE_FLAG = "yaml"

_LLM_FILTER_XPATHS = [
    "//*[@private]",  # Any element with private attribute (flag or true)
    '//*[@private="true"]',  # Explicit private="true"
    ".//citations",  # Remove citations block
    ".//references",  # Remove references block
]


class MDXL:
    """Minimal MDXL implementation - XML-flavored markdown container.

    MDXL wraps an lxml Element and provides convenient methods for:
    - XPath navigation
    - YAML data block support
    - Text rendering with filtering
    - Immutable operations

    This is a minimal implementation that focuses on being a container
    for XML-flavored markdown. Complex operations like citations and
    editing are handled externally.
    """

    # Cache for text rendering to avoid repeated serialization
    _text_cache: dict[int, str] = {}

    def __init__(
        self,
        content: str | etree._Element,
        parent: MDXL | None = None,
        convert_legacy: bool = True,
    ):
        """Initialize MDXL from string or element.

        Args:
            content: XML/MDXL string or lxml Element
            parent: Parent MDXL instance if this is a child element
            convert_legacy: Whether to auto-convert legacy v1 MDXL to v2 format (default: True)
        """
        self._version: str | None = None  # Store detected version
        if isinstance(content, str):
            # Check if we need to convert legacy v1 content
            if convert_legacy and self._should_convert_legacy(content):
                with open("truth.v1.mdxl", "w") as f:
                    f.write(content)
                from good_agent.core.migration import MDXLMigrator  # type: ignore[import-not-found]

                content = MDXLMigrator.migrate_to_v2(content, citation_urls=None)
                with open("truth.v2.mdxl", "w") as f:
                    f.write(content)  # type: ignore[arg-type]
            self._root = self._parse(content)  # type: ignore[arg-type]
        else:
            self._root = content

        self._parent = parent
        self._init_caches()

    def _should_convert_legacy(self, content: str) -> bool:
        """Check if content should be converted from legacy v1 to v2 format.

        Args:
            content: MDXL content string

        Returns:
            True if content appears to be legacy v1 that needs conversion
        """
        import re

        # Check for explicit version declaration. If present, do NOT auto-convert.
        # Auto-conversion should only occur for legacy content without an explicit header.
        version_match = re.search(r'<\?mdxl\s+version=["\']?(\d+)["\']?\?>', content)
        if version_match:
            # Respect the declared version and avoid implicit migration during parse.
            return False

        # Heuristic: Check for [X] citations without corresponding [X]: URL definitions
        # This is the main indicator of legacy v1 content needing reference conversion
        citation_pattern = r"\[(\d+)\](?!:)"  # [X] but not [X]:
        definition_pattern = r"^\s*\[(\d+)\]:\s*(.+?)$"  # [X]: URL

        citations = set(re.findall(citation_pattern, content))
        # Extract only the numeric index from definitions
        definition_matches = re.findall(definition_pattern, content, re.MULTILINE)
        defined_indices = {idx for idx, _ in definition_matches}

        # If we have citations but some are missing definitions, consider it legacy
        missing_definitions = citations - defined_indices
        return bool(citations) and len(missing_definitions) > 0

    def _init_caches(self):
        """Initialize cache attributes after object creation."""
        self._cached_children = {}
        self._cached_data_box = None  # Cache for Box data property

    @classmethod
    def with_version(cls, content: str, version: str) -> MDXL:
        """Create an MDXL instance with a specific version.

        Args:
            content: XML/MDXL content (without version header)
            version: Version string to set (e.g., "1", "2")

        Returns:
            MDXL instance with the specified version
        """
        instance = cls(content)
        instance._version = version
        return instance

    def _parse(self, content: str) -> etree._Element:
        """Parse MDXL string into XML tree.

        Handles:
        - <?mdxl version="X"?> declarations (detects version and strips them)
        - Auto-wrapping in <root> if not present
        - Preserving whitespace and formatting
        - Attributes without values (e.g., `yaml` -> `yaml="true"`)
        """
        # Detect and strip <?mdxl version="X"?> declaration if present
        version_match = re.search(r'<\?mdxl\s+version=["\']?(\d+)["\']?\?>', content)
        if version_match:
            self._version = version_match.group(1)
            content = re.sub(r'<\?mdxl\s+version=["\']?\d+["\']?\?>\s*', "", content)

        # Also strip <mdxl version="X"/> self-closing tags
        content = re.sub(r'<mdxl\s+version=["\']?\d+["\']?\s*/>', "", content)

        # Remove any standalone backslashes (legacy MDXL artifact)
        content = re.sub(r"^\\\s*\n", "", content)

        # Handle empty content
        if not content.strip():
            return etree.Element("root")

        # Fix attributes without values (e.g., `yaml` -> `yaml="true"`)
        # This is more complex because we need to handle various formats
        def fix_tag_attributes(content: str) -> str:
            """Fix valueless attributes in XML tags."""
            import re

            # Pattern to match tags with potential valueless attributes
            # This handles: <tag attr1 attr2="value" attr3>
            def process_tag(match):
                full_tag = match.group(0)
                tag_name = match.group(1)
                attrs_str = match.group(2) if match.group(2) else ""
                closing = match.group(3)

                if not attrs_str:
                    return full_tag

                # Parse attributes more carefully
                # Split on whitespace but preserve quoted values
                attrs = []
                current_attr = []
                in_quotes = False
                quote_char = None

                for char in attrs_str + " ":
                    if char in "\"'":
                        if not in_quotes:
                            in_quotes = True
                            quote_char = char
                        elif char == quote_char:
                            in_quotes = False
                            quote_char = None
                        current_attr.append(char)
                    elif char.isspace() and not in_quotes:
                        if current_attr:
                            attr = "".join(current_attr).strip()
                            if attr:
                                # Check if this attribute has a value
                                if "=" not in attr:
                                    # Valueless attribute (flag) - set value to attribute name
                                    # This matches legacy MDXL behavior
                                    attrs.append(f'{attr}="{attr}"')
                                else:
                                    attrs.append(attr)
                            current_attr = []
                    else:
                        current_attr.append(char)

                if attrs:
                    return f"<{tag_name} {' '.join(attrs)}{closing}"
                else:
                    return f"<{tag_name}{closing}"

            # Match opening tags and self-closing tags
            content = re.sub(r"<(\w+)((?:\s+[^>]+?)?)(\s*/?>)", process_tag, content)
            return content

        content = fix_tag_attributes(content)

        # Escape special characters in text content
        # We need to be careful to only escape in text, not in actual tags
        # First protect existing entities
        import uuid

        entity_placeholder = f"__ENTITY_{uuid.uuid4().hex}__"
        entities = {
            "&lt;": f"{entity_placeholder}lt",
            "&gt;": f"{entity_placeholder}gt",
            "&amp;": f"{entity_placeholder}amp",
            "&quot;": f"{entity_placeholder}quot",
            "&apos;": f"{entity_placeholder}apos",
        }

        # Protect existing entities
        for entity, placeholder in entities.items():
            content = content.replace(entity, placeholder)

        # Now escape bare ampersands
        content = content.replace("&", "&amp;")

        # Restore protected entities
        for entity, placeholder in entities.items():
            content = content.replace(placeholder, entity)

        # Escape template placeholders that look like XML tags
        # These are used in MDXL templates but aren't actual XML
        content = content.replace("<|", "&lt;|").replace("|>", "|&gt;")

        # Wrap in root if not already wrapped
        content = content.strip()
        if not content.startswith("<root>"):
            content = f"<root>{content}</root>"

        # Parse with whitespace preservation
        parser = etree.XMLParser(remove_blank_text=False, resolve_entities=True)
        try:
            return etree.fromstring(content.encode("utf-8"), parser)
        except etree.XMLSyntaxError as e:
            # Provide more helpful error message
            raise ValueError(f"Invalid MDXL/XML syntax: {e}") from e

    # ===== Core Navigation Methods =====

    @overload
    def select(self, xpath: str, raise_if_none: Literal[True] = True) -> MDXL: ...

    @overload
    def select(self, xpath: str, raise_if_none: Literal[False]) -> MDXL | None: ...

    def select(self, xpath: str, raise_if_none: bool = True) -> MDXL | None:
        """Select first matching element using XPath.

        Args:
            xpath: XPath expression
            raise_if_none: If True, raise ValueError when no element found

        Returns:
            MDXL wrapper for first matching element, or None
        """
        elements = self._root.xpath(xpath)
        if not elements:
            if raise_if_none:
                raise ValueError(f"No elements match XPath: {xpath}")
            return None

        # Cache child MDXL instances to avoid re-wrapping
        cache_key = (xpath, id(elements[0]))
        if cache_key not in self._cached_children:
            self._cached_children[cache_key] = MDXL(elements[0], parent=self)

        return self._cached_children[cache_key]

    def select_all(self, xpath: str) -> list[MDXL]:
        """Select all matching elements using XPath.

        Args:
            xpath: XPath expression

        Returns:
            List of MDXL wrappers for matching elements
        """
        elements = self._root.xpath(xpath)
        return [MDXL(el, parent=self) for el in elements]

    @property
    def attributes(self) -> dict[str, Any]:
        """Get all attributes of this element as a dictionary.

        Returns:
            Dictionary of attribute names to values
        """
        from good_agent.core.types import URL

        attributes: dict[str, Any] = dict(self._root.attrib)
        for k, v in attributes.items():
            if v == k:
                attributes[k] = True  # Convert flag attributes back to boolean True
            if v.lower() == "true":
                attributes[k] = True
            if v.startswith("http"):
                attributes[k] = URL(v)
        return attributes

    def update_attributes(self, **attrs: Any):
        """Update multiple attributes at once.

        Args:
            **attrs: Attribute names and values to set
        """
        for k, v in attrs.items():
            if v is True:
                self.set(k, k)  # Set flag attribute
            elif v is False or v is None:
                if k in self._root.attrib:
                    del self._root.attrib[k]  # Remove attribute
            else:
                self.set(k, str(v))
        self._clear_cache()

    def set_attributes(self, attrs: dict[str, Any]):
        """Set multiple attributes from a dictionary.

        Args:
            attrs: Dictionary of attribute names and values
        """
        for k, v in attrs.items():
            if v is True:
                self.set(k, k)  # Set flag attribute
            elif v is False or v is None:
                if k in self._root.attrib:
                    del self._root.attrib[k]  # Remove attribute
            else:
                self.set(k, str(v))
        self._clear_cache()

    def sort_children(self, key: str):
        """Sort child elements by attribute key.

        Args:
            key: Attribute name to sort by
        """

        # def _convert(value: str) -> Any:
        #     """Convert attribute value to int/float if possible for sorting."""

        #     return

        #     try:
        #         return int(value)
        #     except ValueError:
        #         try:
        #             return float(value)
        #         except ValueError:
        # return value.lower()  # Case-insensitive string sort

        _convert = try_chain(  # type: ignore[misc]
            [
                lambda v: datetime.date.fromisoformat(v),  # type: ignore[arg-type, return-value, list-item]
                lambda v: datetime.datetime.fromisoformat(v),  # type: ignore[arg-type, return-value, list-item]
                int,
                float,  # type: ignore[list-item]
                lambda v: v.lower(),  # Case-insensitive string sort
            ],
            default_value=0,
        )

        self._root[:] = sorted(
            self._root,
            key=lambda el: _convert(el.get(key, "")),  # type: ignore
        )
        self._clear_cache()

    # ===== Convenience Properties =====
    # These provide easy access to common elements without XPath

    @property
    def references(self) -> list[str]:
        """Extract all references (URLs) from markdown reference-style links and link elements.

        This extracts references from:
        - Markdown reference-style links: [1]: https://example.com
        - Link elements with url attribute: <link url="https://example.com"/>

        Returns:
            List of URLs in order they appear (0-indexed)
        """
        import re

        references = []
        seen_urls = set()
        # Pattern for markdown reference links: [1]: https://example.com
        ref_pattern = r"^\s*\[(\d+)\]:\s*(.+?)\s*$"

        def process_text(text: str):
            """Extract references from text content."""
            if not text:
                return
            for line in text.split("\n"):
                match = re.match(ref_pattern, line)
                if match:
                    index = int(match.group(1))
                    url = match.group(2).strip()
                    # Store with 1-based index for sorting
                    references.append((index, url))

        def extract_from_element(elem):
            """Recursively extract references from an element and its children."""
            # Use lxml element directly for better text extraction
            element = elem._root if hasattr(elem, "_root") else elem

            # Extract from element's text
            if element.text:
                process_text(element.text)

            # Process all children and their tails
            for child in element:
                # Process child recursively
                extract_from_element(child)
                # Process tail text (text after the child element)
                if child.tail:
                    process_text(child.tail)

            # Extract from link elements with url attribute
            if element.tag == "link" and "url" in element.attrib:
                url = element.attrib["url"]
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    # Use high index for link elements to append after markdown refs
                    references.append((9999, url))

        # Extract from this element
        extract_from_element(self._root)

        # Sort by index and deduplicate while preserving order
        sorted_refs = sorted(references, key=lambda x: x[0])
        result = []
        seen = set()

        for _, url in sorted_refs:
            if url not in seen:
                seen.add(url)
                result.append(url)

        return result

    @property
    def project(self) -> MDXL:
        """Get project element if it exists."""
        return self.select("./project")

    @property
    def ground_truth(self) -> MDXL:
        """Get ground-truth element (note the hyphen)."""
        return self.select("./ground-truth")

    @property
    def entities(self) -> MDXL:
        """Get entities container element."""
        return self.select("./entities")

    @property
    def templates(self) -> dict[str, str]:
        """Extract all templates as a dictionary.

        Looks for: <templates><template name="...">content</template></templates>

        Returns:
            Dict mapping template names to their text content
        """
        result = {}
        for elem in self.select_all(".//templates/template[@name]"):
            name = elem.get("name")
            if name and elem.text:
                result[name] = elem.text
        return result

    # ===== Array-like Access =====

    def __getitem__(self, index: int) -> MDXL:
        """Get child element by index.

        Optimized to create MDXL instances on-demand rather than
        creating all children at once.

        Args:
            index: Index of child element

        Returns:
            MDXL wrapper for child element

        Raises:
            IndexError: If index is out of range
        """
        if not isinstance(index, int):
            raise TypeError(f"indices must be integers, not {type(index).__name__}")

        # Work directly with lxml elements for efficiency
        num_children = len(self._root)

        if index < 0:
            index = num_children + index

        if index < 0 or index >= num_children:
            raise IndexError("list index out of range")

        # Use cache key based on element id to reuse instances
        element = self._root[index]
        cache_key = ("child", id(element))

        if cache_key not in self._cached_children:
            self._cached_children[cache_key] = MDXL(element, parent=self)

        return self._cached_children[cache_key]

    def __len__(self) -> int:
        """Get number of child elements.

        Returns:
            Number of direct child elements
        """
        return len(self.children)

    # ===== Element Properties =====

    @property
    def version(self) -> str | None:
        """Get MDXL version detected from header.

        Returns:
            Version string (e.g., "1", "2") if version header was present, None otherwise
        """
        return self._version

    @version.setter
    def version(self, value: str | None):
        """Set MDXL version.

        Args:
            value: Version string (e.g., "1", "2") or None to clear version
        """
        self._version = value

    @property
    def tag(self) -> str:
        """Get element tag name."""
        return str(self._root.tag)

    @property
    def text(self) -> str | None:
        """Get element text content (not including children)."""
        return self._root.text

    @text.setter
    def text(self, value: str | None):
        """Set element text content."""
        self._root.text = value
        # Clear text cache when content changes
        self._clear_cache()

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get attribute value.

        Args:
            key: Attribute name
            default: Default value if attribute not found

        Returns:
            Attribute value or default
        """
        return self._root.get(key, default)

    def set(self, key: str, value: str):
        """Set attribute value.

        Args:
            key: Attribute name
            value: Attribute value
        """
        self._root.set(key, value)
        self._clear_cache()

    # ===== YAML Data Block Support =====

    @property
    def data(self) -> Box:
        """Parse YAML data if this element has yaml attribute (flag).

        Elements with yaml flag are treated as YAML data blocks.
        Their text content is parsed as YAML.

        Returns:
            Parsed YAML data as dict, or empty dict if not a yaml data block

        Raises:
            yaml.YAMLError: If YAML parsing fails
        """
        # Return cached Box if available
        if self._cached_data_box is not None:
            return self._cached_data_box

        def _on_change(obj, key, value, action, is_root):
            """Callback when Box data changes - sync back to YAML text."""
            # Update the YAML text with the modified Box data
            self.text = yaml.dump(obj.to_dict(), default_flow_style=False, sort_keys=False)
            # Clear the text cache since content changed
            self._clear_cache()

        data_attr = self.get(_DATA_ATTRIBUTE_FLAG)
        # Check for yaml flag attribute (yaml="yaml")
        if data_attr == _DATA_ATTRIBUTE_FLAG and self.text:
            yaml_data = yaml.safe_load(self.text)
            # Handle empty YAML (returns None) as empty dict
            if yaml_data is None:
                yaml_data = {}
            self._cached_data_box = Box(yaml_data, on_change=_on_change)
        else:
            self._cached_data_box = Box({}, on_change=_on_change)

        return self._cached_data_box

    # def _on_data_change(
    #     self,
    #     key, value, action, is_root
    # ):
    #     print(f"Data changed: {action} {key} = {value}", is_root)

    @data.setter
    def data(self, value: dict[str, Any]):
        """Set element content as YAML data.

        Sets yaml="yaml" attribute (flag) and serializes dict as YAML text.

        Args:
            value: Dictionary to serialize as YAML
        """
        self.set(_DATA_ATTRIBUTE_FLAG, _DATA_ATTRIBUTE_FLAG)
        self.text = yaml.dump(value, default_flow_style=False, sort_keys=False)
        # Clear cached Box since we're setting new data
        self._cached_data_box = None

    # ===== Filtering Operations =====

    def without(self, *xpaths: str) -> MDXL:
        """Create copy without elements matching given XPath expressions.

        This is an immutable operation - returns a new MDXL instance
        with specified elements removed.

        Args:
            *xpaths: XPath expressions for elements to remove

        Returns:
            New MDXL instance with elements removed
        """
        # Deep copy the tree
        tree = copy.deepcopy(self._root)

        # Remove matching elements
        for xpath in xpaths:
            for elem in tree.xpath(xpath):
                parent = elem.getparent()
                if parent is not None:
                    parent.remove(elem)

        return MDXL(tree)

    def copy(self) -> MDXL:
        """Create a deep copy of this MDXL instance.

        Returns:
            New independent MDXL instance
        """
        return MDXL(copy.deepcopy(self._root))

    @property
    def children(self) -> list[MDXL]:
        """Get list of child elements as MDXL instances.

        Uses caching to avoid recreating MDXL instances on repeated access.
        Cache is invalidated when the document structure changes.
        """
        # Use a special cache key for the children list
        cache_key = ("_children_list",)

        if cache_key not in self._cached_children:
            # Build the children list, reusing cached instances where possible
            children = []
            for child in self._root:
                child_cache_key = ("child", id(child))
                if child_cache_key not in self._cached_children:
                    self._cached_children[child_cache_key] = MDXL(child, parent=self)
                children.append(self._cached_children[child_cache_key])

            self._cached_children[cache_key] = children

        return self._cached_children[cache_key]

    # ===== Text Rendering =====

    @property
    def outer(self) -> str:
        """Render element as XML string including the element itself.

        For root elements, strips the <root> wrapper to return
        the actual content. Citations are automatically reindexed.

        Returns:
            Pretty-printed XML string with proper indentation and reindexed citations
        """
        # Include version header only when rendering the top-level document root
        include_ver = self.tag == "root" and self._parent is None

        # Use to_string for consistent formatting and reindexing
        return self.to_string(
            pretty=True,
            include_root=False,
            mdxl_format=True,
            include_version=include_ver,
            reindex_citations=True,
        )

    @property
    def inner(self) -> str:
        """Get inner content (text and child elements).

        Returns:
            Combined text content and serialized child elements
        """
        parts = []

        # Add initial text if present
        if self._root.text:
            parts.append(self._root.text)

        # Add child elements and their tails
        for child in self._root:
            child_xml = etree.tostring(child, encoding="unicode", pretty_print=False)  # type: ignore[arg-type]
            parts.append(child_xml)
            if child.tail:
                parts.append(child.tail)

        return textwrap.dedent("".join(parts))

    @property
    def outer_text(self) -> str:
        """Alias for outer property for compatibility.

        Returns:
            Full element as XML string
        """
        return self.outer

    @property
    def inner_text(self) -> str:
        """Alias for inner property for compatibility.

        Returns:
            Inner content of element
        """
        return self.inner

    @property
    def llm_outer_text(self) -> str:
        """Get outer text filtered for LLM consumption.

        Removes:
        - Elements with private
        - <citations> elements
        - <references> elements

        Returns:
            Filtered XML string for LLM
        """
        filtered = self.without(*_LLM_FILTER_XPATHS)
        return filtered.outer

    @property
    def llm_inner_text(self) -> str:
        """Get inner text filtered for LLM consumption.

        Returns:
            Filtered inner content for LLM
        """
        filtered = self.without(*_LLM_FILTER_XPATHS)
        return filtered.inner

    # ===== Serialization =====

    def to_renumbered_references(self) -> str:
        """Serialize element with renumbered references starting from 1.

        This is useful when extracting a section that had higher-numbered
        references in the original document.

        Returns:
            XML string with references renumbered from 1
        """
        import re

        # Get the current outer text
        content = self.outer

        # Find all reference-style links and their indices
        ref_pattern = r"^\s*\[(\d+)\]:\s*(.+?)\s*$"
        citation_pattern = r"\[(\d+)\](?!\:)"

        # Build mapping of old to new indices
        old_to_new: dict[str, str] = {}
        new_refs = []

        for line in content.split("\n"):
            match = re.match(ref_pattern, line)
            if match:
                old_idx = match.group(1)
                url = match.group(2).strip()
                if old_idx not in old_to_new:
                    new_idx = len(old_to_new) + 1
                    old_to_new[old_idx] = str(new_idx)
                    new_refs.append((new_idx, url))

        # Replace all reference definitions
        lines = []
        for line in content.split("\n"):
            match = re.match(ref_pattern, line)
            if match:
                old_idx_str = match.group(1)
                url = match.group(2).strip()
                if old_idx_str in old_to_new:
                    new_idx_str = old_to_new[old_idx_str]
                    lines.append(f"[{new_idx_str}]: {url}")
                else:
                    lines.append(line)
            else:
                lines.append(line)

        content = "\n".join(lines)

        # Replace all citation references
        def replace_citation(match):
            old_idx = match.group(1)
            if old_idx in old_to_new:
                return f"[{old_to_new[old_idx]}]"
            return match.group(0)

        content = re.sub(citation_pattern, replace_citation, content)

        return content

    def to_string(
        self,
        pretty: bool = True,
        include_root: bool = False,
        mdxl_format: bool = True,
        include_version: bool = False,
        reindex_citations: bool = True,
    ) -> str:
        """Serialize to XML string.

        Args:
            pretty: Whether to pretty-print with indentation
            include_root: Whether to include <root> wrapper (default: False for root elements)
            mdxl_format: Whether to use MDXL formatting rules (text on separate lines)
            include_version: Whether to include <?mdxl version="X"?> header if version is set
            reindex_citations: Whether to reindex citations to sequential numbers

        Returns:
            XML string representation
        """
        if mdxl_format and pretty:
            # Use custom MDXL formatting
            text = self._format_element(self._root, indent=0)

            # Reindex citations if requested
            if reindex_citations:
                text = self._reindex_citations(text)

            # Unescape template placeholders
            text = text.replace("&lt;|", "<|").replace("|&gt;", "|>")

            # Minimize flag attributes back to their bare form
            text = self._minimize_flag_attributes(text)

            # Strip <root> wrapper if this is the root element
            if not include_root and self.tag == "root" and not self._parent:
                lines = text.strip().split("\n")
                if lines[0].startswith("<root") and lines[-1] == "</root>":
                    # Remove first and last lines, dedent the content
                    inner_lines = lines[1:-1]
                    # Remove one level of indentation
                    dedented = []
                    for line in inner_lines:
                        if line.startswith("  "):
                            dedented.append(line[2:])
                        else:
                            dedented.append(line)
                    text = "\n".join(dedented)
        else:
            # Use standard lxml formatting
            text = str(
                etree.tostring(
                    self._root,
                    encoding="unicode",
                    pretty_print=pretty,
                    xml_declaration=False,
                )
            )  # type: ignore[arg-type]

            # Strip <root> wrapper by default for root elements
            if not include_root and self.tag == "root" and not self._parent:
                text = text.strip()
                if text.startswith("<root>"):
                    text = text[6:]
                if text.endswith("</root>"):
                    text = text[:-7]
                text = text.strip()

        # Unescape template placeholders
        text = text.replace("&lt;|", "<|").replace("|&gt;", "|>")

        # Minimize flag attributes back to their bare form
        text = self._minimize_flag_attributes(text)

        # Add version header if requested and version is set
        if include_version and self._version is not None:
            text = f'<?mdxl version="{self._version}"?>\n{text}'

        return text

    # ===== Edit Operations =====
    # These are kept minimal - complex editing should be external

    # def to_editable(self) -> MDXL:
    #     """Convert to numbered format for editing.

    #     This is a placeholder - the actual implementation should be
    #     in a separate edit module for better separation of concerns.

    #     Returns:
    #         New MDXL with numbered lines for editing
    #     """
    #     # Import here to avoid circular dependency
    #     from .edit import to_editable_xml

    #     editable_content = to_editable_xml(self.inner_text)
    #     return MDXL(f"<editable>{editable_content}</editable>")

    # def from_editable(self, editable: MDXL):
    #     """Apply edits from editable format.

    #     This is a placeholder - actual implementation in edit module.

    #     Args:
    #         editable: MDXL in editable format with changes
    #     """
    #     from .edit import from_editable_xml

    #     new_content = from_editable_xml(editable.inner_text)
    #     self._root = self._parse(new_content)
    #     self._clear_cache()

    # ===== Structure Modification Methods =====

    def append(self, element: str | MDXL | Any, text: str | None = None, **attributes) -> MDXL:
        """Append child element to this element.

        Args:
            element: Can be:
                - XML string to parse (e.g., "<item>text</item>")
                - MDXL instance (will be deep copied)
                - Tag name string (when used with text/attributes)
                - lxml Element (will be deep copied)
            text: Optional text content (only when element is a tag name)
            **attributes: Optional attributes (only when element is a tag name)

        Returns:
            The newly appended child as MDXL instance

        Examples:
            doc.append("<item>3</item>")
            doc.append("item", text="3", id="three")
            doc.append(other_mdxl_element)
        """
        new_element = self._prepare_element(element, text, attributes)
        self._root.append(new_element)
        self._clear_cache()
        return MDXL(new_element, parent=self)

    def insert(
        self,
        index: int,
        element: str | MDXL | Any,
        text: str | None = None,
        **attributes,
    ) -> MDXL:
        """Insert child element at specific position.

        Args:
            index: Position to insert at (supports negative indexing)
            element: Same as append()
            text: Optional text content
            **attributes: Optional attributes

        Returns:
            The newly inserted child as MDXL instance
        """
        new_element = self._prepare_element(element, text, attributes)

        # Handle negative indexing
        if index < 0:
            index = len(self._root) + index + 1

        self._root.insert(index, new_element)
        self._clear_cache()
        return MDXL(new_element, parent=self)

    def remove(self, index: int) -> None:
        """Remove child element by index.

        Args:
            index: Index of child to remove (supports negative indexing)

        Raises:
            IndexError: If index is out of range
        """
        if not isinstance(index, int):
            raise TypeError(f"indices must be integers, not {type(index).__name__}")

        num_children = len(self._root)
        if index < 0:
            index = num_children + index

        if index < 0 or index >= num_children:
            raise IndexError("list index out of range")

        del self._root[index]
        self._clear_cache()

    def remove_child(self, child: MDXL) -> None:
        """Remove specific child element.

        Args:
            child: MDXL instance to remove (must be a direct child)

        Raises:
            ValueError: If child is not a direct child of this element
        """
        # Find the child's underlying element
        for i, elem in enumerate(self._root):
            if elem is child._root:
                del self._root[i]
                self._clear_cache()
                return

        raise ValueError("Element is not a direct child of this element")

    def remove_all(self, xpath: str) -> int:
        """Remove all elements matching XPath expression.

        Args:
            xpath: XPath expression to match elements

        Returns:
            Number of elements removed
        """
        elements = self._root.xpath(xpath)
        count = 0
        for elem in elements:
            parent = elem.getparent()
            if parent is self._root:  # Only remove direct children
                parent.remove(elem)
                count += 1

        if count > 0:
            self._clear_cache()

        return count

    def clear(self) -> None:
        """Remove all child elements."""
        # Clear all children but preserve text and tail
        for child in list(self._root):
            self._root.remove(child)
        self._clear_cache()

    def replace(
        self,
        index: int,
        element: str | MDXL | Any,
        text: str | None = None,
        **attributes,
    ) -> MDXL:
        """Replace child element at index.

        Args:
            index: Index of child to replace
            element: Replacement element (same as append)
            text: Optional text content
            **attributes: Optional attributes

        Returns:
            The new child element
        """
        if not isinstance(index, int):
            raise TypeError(f"indices must be integers, not {type(index).__name__}")

        num_children = len(self._root)
        if index < 0:
            index = num_children + index

        if index < 0 or index >= num_children:
            raise IndexError("list index out of range")

        new_element = self._prepare_element(element, text, attributes)
        old_element = self._root[index]
        self._root.replace(old_element, new_element)
        self._clear_cache()
        return MDXL(new_element, parent=self)

    def create_child(self, tag: str, text: str | None = None, **attributes) -> MDXL:
        """Create and append a new child element.

        Args:
            tag: Element tag name
            text: Optional text content
            **attributes: Optional attributes (including flags like 'yaml')

        Returns:
            The newly created child element

        Example:
            config = doc.create_child("config", yaml=True)
            config.data = {"key": "value"}
        """
        return self.append(tag, text=text, **attributes)

    def extend(self, elements: list[str | MDXL | Any]) -> None:
        """Append multiple child elements.

        Args:
            elements: List of elements to append (same format as append())
        """
        for element in elements:
            self.append(element)

    def _prepare_element(
        self, element: str | MDXL | Any, text: str | None, attributes: dict
    ) -> Any:
        """Prepare an element for insertion into the tree.

        Args:
            element: Element to prepare
            text: Optional text content
            attributes: Optional attributes

        Returns:
            lxml Element ready for insertion
        """
        from lxml import etree

        if isinstance(element, str):
            if text is None and not attributes:
                # Try to determine if it's XML or just a tag name
                # Simple heuristic: if it starts with < and ends with >, try parsing
                if element.strip().startswith("<") and element.strip().endswith(">"):
                    try:
                        parsed = self._parse(element)
                        # If it's a root wrapper, extract the actual element
                        if parsed.tag == "root" and len(parsed) == 1:
                            # Single child in root wrapper - use the child
                            return copy.deepcopy(parsed[0])
                        elif parsed.tag == "root" and len(parsed) == 0 and parsed.text:
                            # Root with just text - create a text node?
                            # This is an edge case, just return the root
                            return copy.deepcopy(parsed)
                        else:
                            # Use as-is (might be a proper element or a root with multiple children)
                            return copy.deepcopy(parsed)
                    except Exception:
                        # If parsing fails, treat it as a tag name
                        pass

            # It's a tag name - create new element
            new_elem = etree.Element(element)
            if text is not None:
                new_elem.text = text
            for key, value in attributes.items():
                # Handle flag attributes
                if isinstance(value, bool) and value:
                    new_elem.set(key, key)
                elif value is not None and value is not False:
                    new_elem.set(key, str(value))
            return new_elem

        elif isinstance(element, MDXL):
            # For MDXL, use the root element directly if not wrapped
            if element._root.tag == "root" and element._parent is None and len(element._root) == 1:
                # It's a standalone MDXL with single child - use the child
                return copy.deepcopy(element._root[0])
            else:
                # Use the element as-is
                return copy.deepcopy(element._root)

        else:
            # Assume it's an lxml Element
            return copy.deepcopy(element)

    # ===== Private Helper Methods =====

    def _cleanup_markdown_text(self, text: str) -> str:
        """Clean up markdown text formatting with proper header spacing.

        Args:
            text: Raw markdown text

        Returns:
            Cleaned up markdown text with proper spacing
        """
        if not text or not text.strip():
            return text

        lines = text.split("\n")
        cleaned = []

        for i, line in enumerate(lines):
            # Check if this line is a header or bold-as-header
            is_header = False
            is_bold_header = False

            stripped = line.strip()

            # Check for markdown headers
            if stripped.startswith("#"):
                is_header = True

            # Check for bold text that appears to be a header
            # (starts and ends with ** and is the only thing on the line)
            elif stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
                # Make sure it's not inline bold (check if it's the whole line)
                if stripped == line.strip():
                    is_bold_header = True

            # Add spacing before headers (but not at the start)
            if i > 0 and (is_header or is_bold_header):
                # Check if previous line is empty
                prev_line = lines[i - 1].strip() if i > 0 else ""
                if prev_line:  # Only add blank line if previous line isn't empty
                    cleaned.append("")

            cleaned.append(line)

        return "\n".join(cleaned)

    def _format_element(self, element: Any, indent: int = 0) -> str:
        """Format an element with proper indentation for text and children.

        Args:
            element: lxml Element to format
            indent: Current indentation level

        Returns:
            Formatted XML string
        """

        indent_str = "  " * indent
        text_indent_str = "  " * (indent + 1)  # Base text indent

        # Build opening tag
        tag = element.tag
        attrs = []
        for key, value in element.attrib.items():
            attrs.append(f'{key}="{value}"')

        if attrs:
            opening = f"{indent_str}<{tag} {' '.join(attrs)}>"
        else:
            opening = f"{indent_str}<{tag}>"

        # Check if element has children or text
        has_children = len(element) > 0
        has_text = element.text is not None and element.text.strip()  # Ignore whitespace-only

        # Handle self-closing empty elements
        if not has_children and not has_text:
            if attrs:
                return f"{indent_str}<{tag} {' '.join(attrs)}/>"
            else:
                return f"{indent_str}<{tag}/>"

        # Build content
        lines = []
        lines.append(opening)

        # Add text content with proper indentation
        if has_text:
            original_text = element.text

            # Special handling for YAML-flagged blocks: preserve internal indentation
            is_yaml_block = "yaml" in element.attrib
            if is_yaml_block and original_text is not None:
                # Remove common leading indentation only, keep per-line indentation
                preserved = textwrap.dedent(original_text)
                # Drop a single leading newline if present (common in pretty XML)
                if preserved.startswith("\n"):
                    preserved = preserved[1:]

                # Emit lines with only the base indent added
                for line in preserved.split("\n"):
                    if line:
                        lines.append(text_indent_str + line)
                    else:
                        lines.append("")
            else:
                # For non-YAML text, normalize and indent properly
                dedented_text = textwrap.dedent(original_text)

                # Check if original has trailing blank lines (2+ newlines)
                # A single trailing newline is just the line ending, not a blank line
                has_trailing_blank_line = dedented_text.rstrip("\n") != dedented_text.rstrip()

                # Strip surrounding whitespace/newlines
                dedented_text = dedented_text.strip()

                # Remove any remaining leading whitespace from all lines
                # The dedent doesn't always remove all indentation evenly
                text_lines_temp = dedented_text.split("\n")
                normalized_lines = []
                for line in text_lines_temp:
                    # Strip all leading spaces - we'll re-add proper indentation later
                    normalized_lines.append(line.lstrip())
                dedented_text = "\n".join(normalized_lines)

                # Apply markdown formatting standardization if needed
                # Don't apply to "doc" - it has its own special formatting
                if tag in [
                    "ground-truth",
                    "section",
                    "subsection",
                    "document",
                    "project",
                    "position",
                    "person",
                ]:
                    dedented_text = self._apply_markdown_formatting(dedented_text)
                elif tag == "doc":
                    # For doc tags, add blank lines between header sections but not after headers
                    dedented_text = self._format_doc_content(dedented_text)

                text_lines = dedented_text.split("\n")

                # Add base indentation for all content
                for text_line in text_lines:
                    if text_line:
                        lines.append(text_indent_str + text_line)
                    else:
                        lines.append("")  # Keep blank lines

                # Add trailing blank line if original had trailing blank lines
                # and it wasn't already added by markdown formatting
                if has_trailing_blank_line and not has_children:
                    # Check if we already have a trailing blank line
                    if not lines or lines[-1] != "":
                        lines.append("")

        # Add child elements
        if has_children:
            # Add a single blank line before children if there was text content
            if has_text:
                lines.append("")

            for _i, child in enumerate(element):
                # Format child recursively
                child_str = self._format_element(child, indent + 1)
                lines.append(child_str)

                # Handle tail text after child element (text between child elements)
                if child.tail and child.tail.strip():
                    tail_text = child.tail.strip()
                    # Apply markdown formatting if needed
                    if tag in ["positions", "profiles", "entities"]:
                        tail_text = self._apply_markdown_formatting(tail_text)

                    tail_lines = tail_text.split("\n")
                    for tail_line in tail_lines:
                        if tail_line:
                            lines.append(text_indent_str + tail_line)

        # Add closing tag
        lines.append(f"{indent_str}</{tag}>")

        return "\n".join(lines)

    def _reindex_citations(self, text: str) -> str:
        """Reindex citations to sequential numbers starting from 1.

        Ensures globally unique indices across all sections/blocks.
        Each unique URL gets a unique index based on order of first use.
        References are collected and output in numeric order at the end of each section.

        Args:
            text: The serialized XML text with citations

        Returns:
            Text with reindexed citations and references in numeric order
        """
        import re

        if not text:
            return text

        # Patterns
        citation_pattern = r"\[(\d+)\](?!:)"  # [X] but not [X]:
        definition_pattern = r"^\s*\[(\d+)\]:\s*(.+?)$"  # [X]: URL

        lines = text.split("\n")

        # First pass: collect all citations and assign new indices
        seen_urls = {}  # url -> new_idx
        next_new_idx = 1
        current_scope_defs: dict[str, str] = {}

        for i, line in enumerate(lines):
            # Check if this is a section boundary (closing tag)
            if line.strip().startswith("</"):
                current_scope_defs = {}
                continue

            # Check for definitions - they update the current scope
            def_match = re.match(definition_pattern, line)
            if def_match:
                idx = def_match.group(1)
                url = def_match.group(2).strip()
                current_scope_defs[idx] = url
                continue

            # Process citation uses
            for match in re.finditer(citation_pattern, line):
                idx = match.group(1)
                url = None

                # First check current scope
                if idx in current_scope_defs:
                    url = current_scope_defs[idx]
                else:
                    # Look ahead in this section for the definition
                    for j in range(i + 1, len(lines)):
                        future_line = lines[j]
                        if future_line.strip().startswith("</"):
                            break
                        future_def = re.match(definition_pattern, future_line)
                        if future_def and future_def.group(1) == idx:
                            url = future_def.group(2).strip()
                            break

                # Track this citation if we found its URL
                if url and url not in seen_urls:
                    seen_urls[url] = str(next_new_idx)
                    next_new_idx += 1

        # Second pass: rewrite with new indices and collect references per section
        result_lines = []
        current_scope_defs_2: dict[str, str] = {}
        section_refs: dict[str, str] = {}  # new_idx -> url for current section
        base_indent = 0
        blank_line_buffer: list[
            str
        ] = []  # Buffer to hold blank lines until we know if they precede references

        for i, line in enumerate(lines):
            # Track indentation of content lines for reference formatting
            if (
                line.strip()
                and not line.strip().startswith("<")
                and not re.match(definition_pattern, line)
            ):
                base_indent = len(line) - len(line.lstrip())

            # Check if this is a section boundary (closing tag)
            if line.strip().startswith("</"):
                # Before adding the closing tag, add collected references in order
                if section_refs:
                    # Trim excessive blank lines from buffer (keep at most 1)
                    while len(blank_line_buffer) > 1:
                        blank_line_buffer.pop(0)

                    # Output any remaining blank line
                    result_lines.extend(blank_line_buffer)
                    blank_line_buffer = []

                    # Add a blank line before references if there isn't one
                    if result_lines and result_lines[-1].strip():
                        result_lines.append("")

                    # Add references in numeric order with blank lines between them
                    sorted_refs = sorted(section_refs.keys(), key=int)
                    for j, idx in enumerate(sorted_refs):
                        url = section_refs[idx]
                        result_lines.append(" " * base_indent + f"[{idx}]: {url}")
                        # Add blank line after each reference except the last
                        if j < len(sorted_refs) - 1:
                            result_lines.append("")

                # Clear section state
                current_scope_defs_2 = {}
                section_refs = {}
                result_lines.append(line)
                blank_line_buffer = []
                continue

            # Skip definition lines - we'll add them in order at the end of sections
            def_match = re.match(definition_pattern, line)
            if def_match:
                idx = def_match.group(1)
                url = def_match.group(2).strip()
                current_scope_defs_2[idx] = url
                # Track which references are used in this section
                if url in seen_urls:
                    new_idx = seen_urls[url]
                    section_refs[new_idx] = url
                # Clear blank line buffer since we're skipping this definition
                blank_line_buffer = []
                continue

            # Handle blank lines - buffer them to see if they precede references
            if not line.strip():
                blank_line_buffer.append(line)
                continue

            # Non-blank, non-definition line - output buffered blank lines first
            if blank_line_buffer:
                result_lines.extend(blank_line_buffer)
                blank_line_buffer = []

            # Replace citations in regular lines
            def replace_citation(
                match,
                current_scope_defs=current_scope_defs,
                section_refs=section_refs,
                i=i,
                current_scope_defs_2=current_scope_defs_2,
            ):
                idx = match.group(1)
                url = None
                if idx in current_scope_defs_2:
                    url = current_scope_defs_2[idx]
                else:
                    # Look ahead for definition
                    for j in range(i + 1, len(lines)):
                        future_line = lines[j]
                        if future_line.strip().startswith("</"):
                            break
                        future_def = re.match(definition_pattern, future_line)
                        if future_def and future_def.group(1) == idx:
                            url = future_def.group(2).strip()
                            break

                # Replace with new index and track reference
                if url and url in seen_urls:
                    new_idx = seen_urls[url]
                    section_refs[new_idx] = url
                    return f"[{new_idx}]"
                return match.group(0)

            new_line = re.sub(citation_pattern, replace_citation, line)
            result_lines.append(new_line)

        # Handle any remaining references if document doesn't end with closing tag
        if section_refs:
            # Handle any buffered blank lines
            while len(blank_line_buffer) > 1:
                blank_line_buffer.pop(0)
            result_lines.extend(blank_line_buffer)

            if result_lines and result_lines[-1].strip():
                result_lines.append("")
            sorted_refs = sorted(section_refs.keys(), key=int)
            for i, idx in enumerate(sorted_refs):
                url = section_refs[idx]
                result_lines.append(" " * base_indent + f"[{idx}]: {url}")
                # Add blank line after each reference except the last
                if i < len(sorted_refs) - 1:
                    result_lines.append("")

        return "\n".join(result_lines)

    def _reindex_citations_old(self, text: str) -> str:
        """Reindex citations to sequential numbers starting from 1.

        Ensures globally unique indices across all sections/blocks.
        Each unique URL gets a unique index, even if referenced
        multiple times with different indices in different sections.

        Args:
            text: The serialized XML text with citations

        Returns:
            Text with reindexed citations
        """
        import re
        from collections import OrderedDict

        if not text:
            return text

        # Find all citation uses and definitions
        citation_pattern = r"\[(\d+)\](?!:)"  # [X] but not [X]:
        definition_pattern = r"^\s*\[(\d+)\]:\s*(.+?)$"  # [X]: URL

        lines = text.split("\n")

        # First pass: Build complete index->URL mapping from all definitions
        idx_to_url = {}  # Map old index to URL (within each section context)
        section_contexts = []  # Track which indices are defined in each "section"
        current_section_defs = {}

        for line in lines:
            def_match = re.match(definition_pattern, line)
            if def_match:
                old_idx = def_match.group(1)
                url = def_match.group(2).strip()
                idx_to_url[old_idx] = url
                current_section_defs[old_idx] = url
            # Detect section boundaries (empty line or XML tag)
            elif not line.strip() or line.strip().startswith("<"):
                if current_section_defs:
                    section_contexts.append(current_section_defs.copy())
                    current_section_defs = {}
        # Don't forget the last section
        if current_section_defs:
            section_contexts.append(current_section_defs)

        # Second pass: Find order of first use for each unique URL
        url_first_use = OrderedDict()
        active_context = {}

        for line in lines:
            # Update context when we hit definitions
            def_match = re.match(definition_pattern, line)
            if def_match:
                old_idx = def_match.group(1)
                url = def_match.group(2).strip()
                active_context[old_idx] = url
                continue

            # Track citation uses
            for match in re.finditer(citation_pattern, line):
                old_idx = match.group(1)
                # Look for URL in active context or global map
                url = None
                if old_idx in active_context:
                    url = active_context[old_idx]
                elif old_idx in idx_to_url:
                    url = idx_to_url[old_idx]

                if url and url not in url_first_use:
                    url_first_use[url] = True

        # Assign new indices based on order of first use
        url_to_new_idx = {}
        for new_idx, url in enumerate(url_first_use.keys(), 1):
            url_to_new_idx[url] = str(new_idx)

        # Third pass: Rewrite the text with new indices
        result_lines = []
        active_context = {}
        seen_definitions = set()

        for line in lines:
            # Check if this is a definition
            def_match = re.match(definition_pattern, line)
            if def_match:
                old_idx = def_match.group(1)
                url = def_match.group(2).strip()
                active_context[old_idx] = url

                # Only output each unique URL once with its new index
                if url in url_to_new_idx and url not in seen_definitions:
                    new_idx_str = url_to_new_idx[url]
                    # Preserve original indentation
                    indent_len = len(line) - len(line.lstrip())
                    result_lines.append(" " * indent_len + f"[{new_idx_str}]: {url}")
                    seen_definitions.add(url)
                # Skip duplicate or unmapped definitions
                continue
            else:
                # Replace citation uses
                def replace_citation(match):
                    old_idx = match.group(1)
                    # Look for URL in active context or global map
                    url = None
                    if old_idx in active_context:
                        url = active_context[old_idx]
                    elif old_idx in idx_to_url:
                        url = idx_to_url[old_idx]

                    if url and url in url_to_new_idx:
                        return f"[{url_to_new_idx[url]}]"
                    return match.group(0)

                new_line = re.sub(citation_pattern, replace_citation, line)
                result_lines.append(new_line)

        return "\n".join(result_lines)

    def _format_doc_content(self, text: str) -> str:
        """Format doc content with blank lines between header sections.

        For doc tags, we keep headers and their content together,
        but add blank lines between different header sections.

        Args:
            text: The doc content to format

        Returns:
            Formatted doc content
        """
        if not text:
            return text

        lines = text.split("\n")
        result = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if this line is a header
            is_header = stripped.startswith("#")

            # Check if previous line exists and was also a header or content
            if i > 0:
                prev_line = lines[i - 1].strip() if i > 0 else ""
                prev_is_header = prev_line.startswith("#") if prev_line else False

                # Add blank line before new header sections (but not between header and its content)
                if is_header and i > 1 and not prev_is_header:
                    # This is a new header section, add blank line before it
                    result.append("")

            result.append(line)

        return "\n".join(result)

    def _apply_markdown_formatting(self, text: str) -> str:
        """Apply markdown formatting standardization.

        Ensures proper spacing before and after headers and bold-only lines.

        Args:
            text: The markdown text to format

        Returns:
            Formatted markdown text
        """

        if not text:
            return text

        # Check if original text ends with blank line(s)
        original_has_trailing_blank = text.rstrip() != text

        lines = text.split("\n")
        result: list[str] = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Check if this line is a header or bold-only line
            is_header = stripped.startswith("#")
            is_bold_only = (
                stripped.startswith("**")
                and stripped.endswith("**")
                and len(stripped) > 4
                and not any(c in stripped[2:-2] for c in ["#", "*", "_"])
            )

            # Add blank line BEFORE headers and bold-only lines if not already present
            if (is_header or is_bold_only) and i > 0:
                # Check if we just added a line to result
                if result and result[-1].strip():  # Previous line is not blank
                    result.append("")

            result.append(line)

            # Add blank line AFTER headers only (not bold-only) if not already present
            if is_header and i < len(lines) - 1:
                next_line = lines[i + 1] if i + 1 < len(lines) else ""
                if next_line.strip():  # Next line is not blank
                    result.append("")

        # Clean up multiple consecutive blank lines
        cleaned = []
        blank_count = 0
        for line in result:
            is_blank = not line.strip()
            if is_blank:
                blank_count += 1
                if blank_count <= 1:  # Allow max 1 blank line
                    cleaned.append(line)
            else:
                blank_count = 0
                cleaned.append(line)

        # Preserve trailing blank line if original had one
        if original_has_trailing_blank:
            # Ensure exactly one trailing blank line
            while cleaned and not cleaned[-1].strip():
                cleaned.pop()
            cleaned.append("")
        else:
            # Remove all trailing blank lines
            while cleaned and not cleaned[-1].strip():
                cleaned.pop()

        return "\n".join(cleaned)

    def _minimize_flag_attributes(self, text: str) -> str:
        """Convert flag attributes from expanded to minimized form.

        E.g., yaml="yaml" -> yaml, private="private" -> private
        This matches legacy MDXL serialization behavior.
        """
        import re

        # Pattern to match attribute="attribute" (flag attributes)
        # This will convert yaml="yaml" back to yaml
        pattern1 = r'(\s+)([a-zA-Z][-a-zA-Z0-9:_]*)="(\2)"'
        text = re.sub(pattern1, r"\1\2", text)

        # Also handle empty attributes if needed
        # pattern2 = r'(\s+)([a-zA-Z][-a-zA-Z0-9:_]*)=""'
        # text = re.sub(pattern2, r"\1\2", text)

        return text

    def _clear_cache(self):
        """Clear cached data when content changes."""
        self._cached_children.clear()
        self._cached_data_box = None
        # Remove from text cache if present
        cache_key = id(self._root)
        if cache_key in MDXL._text_cache:
            del MDXL._text_cache[cache_key]

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"MDXL(tag='{self.tag}', children={len(list(self._root))})"
