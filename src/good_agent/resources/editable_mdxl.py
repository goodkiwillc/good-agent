import logging
import re
from typing import Any

from pydantic import Field

from good_agent import tool
from good_agent.core.mdxl import MDXL
from good_agent.extensions.citations.formats import CitationPatterns
from good_agent.extensions.citations.manager import CitationManager
from good_agent.resources.base import StatefulResource

logger = logging.getLogger(__name__)


class EditableMDXL(StatefulResource[MDXL]):
    """Resource wrapper that exposes read/update/append helpers for MDXL trees."""

    def __init__(self, mdxl: MDXL, name: str = "mdxl_document"):
        # Don't call super().__init__ with content - we'll store MDXL directly
        self.name = name
        self._initial_content = mdxl
        self._modified = False
        self._initialized = False
        self._changelog: list[str] = []

    async def initialize(self) -> None:
        """Initialize from MDXL."""
        self.state = self._initial_content

    async def persist(self) -> None:
        """Mark as saved."""
        self._modified = False

    def _clean_xpath(self, xpath: str) -> str:
        """Clean up common XPath mistakes and handle namespaces."""
        # Remove /text() suffix if present
        if xpath.endswith("/text()"):
            logger.debug(f"Removing /text() suffix from XPath: {xpath}")
            xpath = xpath[:-7]

        # Handle namespace issues first - convert local-name() to simpler form
        # e.g., /*[local-name()='tag'] -> //tag (ensure descendant search semantics)
        if "local-name()" in xpath:
            logger.debug(f"Simplifying local-name() in XPath: {xpath}")
            # Match segments like /*[local-name()='tagname'] and replace with //tagname
            xpath = re.sub(r"/\*\[local-name\(\)='([^']+)'\]", r"//\1", xpath)

        # Convert leading absolute path to descendant search for robustness
        if xpath.startswith("/") and not xpath.startswith("//"):
            logger.debug(f"Converting absolute XPath to relative: {xpath}")
            xpath = "//" + xpath[1:]

        return xpath

    @tool
    async def read(self) -> str:
        """Read the full document content (filtered for LLM).

        Shows the entire document using llm_outer_text which:
        - Filters out private elements
        - Removes citations and references
        - Provides clean content for LLM understanding
        """
        logger.debug("Read called - returning filtered document content")
        # State is already an MDXL object
        # Apply proper LLM filtering (add missing //private filter)
        filtered = self.state.without(
            "//private",  # Elements named "private"
            "//*[@private]",  # Elements with private attribute
            '//*[@private="true"]',  # Elements with private="true"
            ".//citations",  # Citation elements
            ".//references",  # Reference elements
        )
        content = filtered.llm_outer_text
        # Strip markdown/processed reference blocks that can remain after migration
        if CitationPatterns.MARKDOWN_REF_BLOCK.search(content):
            content = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", content)
        if CitationPatterns.PROCESSED_REF_BLOCK.search(content):
            content = CitationPatterns.PROCESSED_REF_BLOCK.sub("", content)
        # Normalize excessive blank lines
        content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content).strip()
        logger.debug(f"Read returning {len(content)} chars of filtered content")
        return content

    @tool
    async def update(
        self,
        xpath: str = Field(
            ...,
            description="XPath selector for EXISTING element(s) to update. Element MUST already exist. Use // for descendant search. To add new child elements, use append_child instead.",
        ),
        text_content: str | None = Field(
            None,
            description="New text content for the EXISTING element (None = no change)",
        ),
        attributes: dict[str, str | None] | None = Field(
            None,
            description="Dict of attribute updates for EXISTING element. Value of None removes the attribute. Example: {'role': 'former-candidate', 'status': None}",
        ),
        data: dict[str, Any] | None = Field(
            None, description="New YAML data content (None = no change)"
        ),
        cm: CitationManager | None = None,
    ) -> str:
        """Update EXISTING element content or attributes using XPath.

        ⚠️ IMPORTANT: The element MUST already exist! This tool only updates existing elements.

        ❌ WRONG: xpath='//person[@name="John"]/details' (if details doesn't exist)
        ✅ RIGHT: First use append_child to add details, then update it

        To add new child elements:
        1. Use append_child with parent_xpath='//person[@name="John"]', element_tag='details'
        2. Then update the new element if needed

        Examples:
            - Update person's role: xpath='//person[@name="John"]', attributes={'role': 'candidate'}
            - Update EXISTING text: xpath='//summary', text_content='New summary text'
            - Remove attribute: xpath='//item[@id="123"]', attributes={'obsolete': None}

        Returns:
            Description of what was updated
        """
        # Clean up the XPath
        xpath = self._clean_xpath(xpath)

        logger.debug(
            f"Update called with xpath={xpath}, text={text_content is not None}, "
            f"attributes={attributes}, data={data is not None}"
        )

        # Find matching elements in current MDXL state
        elements = self.state.select_all(xpath)

        if not elements:
            logger.warning(f"No elements found for XPath: {xpath}")
            # Provide helpful guidance for hierarchical paths
            if "/" in xpath:
                segments = [s for s in xpath.split("/") if s and s != ""]
                if len(segments) >= 2:
                    # Try to extract parent path and child element
                    parts = xpath.rsplit("/", 1)
                    parent_path = parts[0] if parts[0] else "/"
                    child_name = parts[1].split("[")[0] if len(parts) > 1 else ""

                    if child_name:
                        return (
                            f"No elements found for XPath: {xpath}\n"
                            f"💡 The element doesn't exist. Please reformulate your edit:\n"
                            f"  1. Use append_child with parent_xpath='{parent_path}', element_tag='{child_name}'\n"
                            f"  2. Then update the new element if needed\n"
                            f"🔄 Please try again with the correct tool."
                        )
            return (
                f"No elements found for XPath: {xpath}. Element must exist before updating.\n"
                f"🔄 Please reformulate using either:\n"
                f"  - append_child to add new elements\n"
                f"  - A different xpath selector for existing elements\n"
                f"Try again with the appropriate approach."
            )

        # Update first matching element only
        element = elements[0]
        updates = []

        # Update text content (only if not updating data - data takes precedence)
        if text_content is not None and data is None:
            logger.debug(f"Updating text content for element at {xpath}")
            # Convert global [!CITE_X!] markers to section-level markdown references
            try:
                transformed = self._convert_llm_citations_to_markdown_refs(text_content, cm)
            except Exception:
                transformed = text_content
            element._root.text = transformed
            updates.append("text content")

        # Update attributes
        if attributes:
            logger.debug(f"Updating attributes: {attributes}")
            for key, value in attributes.items():
                if value is None:
                    # Remove attribute
                    if key in element._root.attrib:
                        logger.debug(f"Removing attribute '{key}'")
                        del element._root.attrib[key]
                        updates.append(f"removed '{key}'")
                else:
                    # Set/update attribute
                    logger.debug(f"Setting attribute '{key}' = '{value}'")
                    element._root.set(key, value)
                    updates.append(f"set {key}='{value}'")

        # Update data
        if data is not None:
            logger.debug(f"Updating YAML data: {data}")
            element.data = data
            updates.append("YAML data")

        # Mark as modified
        self._modified = True

        update_desc = ", ".join(updates)
        if len(elements) > 1:
            result = (
                f"Updated {update_desc} on first of {len(elements)} matching elements at {xpath}"
            )
        else:
            result = f"Updated {update_desc} at {xpath}"

        logger.info(f"Update successful: {result}")
        return result

    def _convert_llm_citations_to_markdown_refs(
        self, content: str, cm: CitationManager | None
    ) -> str:
        """Convert [!CITE_X!] (global indices) into section-level [N] with a reference block.

        - Removes any existing reference blocks in the incoming content
        - Preserves url/href attributes and other URLs as-is
        - Renumbers citations in order of first appearance per section
        - Appends a markdown reference list mapping [N]: URL at the end
        """
        if not content:
            return content

        text = content

        # Extract any existing reference mappings first
        existing_refs = {}
        try:
            from good_agent.extensions.citations.formats import CitationExtractor

            existing_refs = CitationExtractor.extract_markdown_references(text) or {}
        except Exception:
            existing_refs = {}

        # Strip existing reference blocks and processed blocks to avoid duplication
        if CitationPatterns.MARKDOWN_REF_BLOCK.search(text):
            text = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", text)
        if CitationPatterns.PROCESSED_REF_BLOCK.search(text):
            text = CitationPatterns.PROCESSED_REF_BLOCK.sub("", text)
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()

        # Determine current highest numeric citation used in the text
        present_numeric = [int(m.group(1)) for m in CitationPatterns.MARKDOWN.finditer(text)]
        next_idx = max(present_numeric) if present_numeric else 0

        # Replace [!CITE_X!] with sequential numeric indices continuing after existing ones
        llm_matches = list(CitationPatterns.LLM_CITE.finditer(text))
        assigned: dict[int, int] = {}  # global_idx -> local_idx
        new_idx_to_url: dict[int, str] = {}

        if llm_matches:
            # Assign in order of appearance
            for m in llm_matches:
                gidx = int(m.group(1))
                if gidx not in assigned:
                    next_idx += 1
                    assigned[gidx] = next_idx
                    if cm is not None and getattr(cm, "index", None) is not None:
                        url_obj = cm.index.get_url(gidx)
                        if url_obj is not None:
                            new_idx_to_url[next_idx] = str(url_obj)

            # Apply replacements in reverse order to keep positions stable
            for m in reversed(llm_matches):
                gidx = int(m.group(1))
                lidx = assigned.get(gidx)
                if lidx is not None:
                    text = text[: m.start()] + f"[{lidx}]" + text[m.end() :]

        # Build final reference list for indices present in text (in appearance order)
        ref_lines: list[str] = []
        seen_indices: set[int] = set()
        for m in CitationPatterns.MARKDOWN.finditer(text):
            idx = int(m.group(1))
            if idx in seen_indices:
                continue
            seen_indices.add(idx)
            url: str | None = None
            # Prefer existing refs for existing indices
            if idx in existing_refs and existing_refs[idx] is not None:
                url = str(existing_refs[idx])
            elif idx in new_idx_to_url:
                url = new_idx_to_url[idx]
            if url:
                ref_lines.append(f"[{idx}]: {url}")

        # If we have any references to add, append them after a blank line
        if ref_lines:
            text = text.rstrip() + "\n\n" + "\n".join(ref_lines)

        return text

    @tool
    async def replace_text(
        self,
        xpath: str = Field(
            ...,
            description="XPath selector for the element. Use // for descendant search.",
        ),
        old_text: str = Field(..., description="Text to find and replace"),
        new_text: str = Field(..., description="Replacement text"),
        all_occurrences: bool = Field(
            False, description="Replace all occurrences (default: first only)"
        ),
        cm: CitationManager | None = None,
    ) -> str:
        """Replace specific text within an element.

        Examples:
            - Replace single word: xpath='//summary', old_text='draft', new_text='final'
            - Replace all occurrences: xpath='//document', old_text='2023', new_text='2024', all_occurrences=True

        Returns:
            Description of what was replaced
        """
        xpath = self._clean_xpath(xpath)
        logger.debug(f"Replace text in {xpath}: '{old_text[:50]}...' -> '{new_text[:50]}...'")

        elements = self.state.select_all(xpath)
        if not elements:
            logger.warning(f"No elements found for XPath: {xpath}")
            # Provide helpful guidance for hierarchical paths
            if "/" in xpath:
                # Count the segments to determine if this looks like a child element path
                segments = [s for s in xpath.split("/") if s and s != ""]
                if len(segments) >= 2:
                    # Try to extract parent path and child element
                    parts = xpath.rsplit("/", 1)
                    parent_path = parts[0] if parts[0] else "/"
                    child_name = parts[1].split("[")[0] if len(parts) > 1 else ""

                    if child_name:
                        return (
                            f"No elements found for XPath: {xpath}\n"
                            f"💡 Hint: The element doesn't exist. To add a new <{child_name}> element:\n"
                            f"  1. Use append_child with parent_xpath='{parent_path}', element_tag='{child_name}'\n"
                            f"  2. Then update it if needed"
                        )
            return f"No elements found for XPath: {xpath}. Element must exist before updating."

        element = elements[0]
        current_text = element._root.text or ""

        if old_text not in current_text:
            return f"Text '{old_text[:50]}' not found in element at {xpath}"

        if all_occurrences:
            replaced_text = current_text.replace(old_text, new_text)
            count = current_text.count(old_text)
        else:
            replaced_text = current_text.replace(old_text, new_text, 1)
            count = 1

        # Normalize citations within the resulting content for self-contained markdown
        new_content = self._convert_llm_citations_to_markdown_refs(replaced_text, cm)

        element._root.text = new_content
        self._modified = True

        result = f"Replaced {count} occurrence(s) of text in {xpath}"
        logger.info(result)
        return result

    @tool
    async def insert(
        self,
        reference_xpath: str = Field(
            ...,
            description="XPath to EXISTING reference element. New element will be inserted as its SIBLING. Reference must exist.",
        ),
        element_tag: str = Field(..., description="Tag name for the new SIBLING element"),
        position: str = Field(
            "after",
            description="Where to insert relative to reference: 'before' or 'after' (default: 'after')",
        ),
        text_content: str | None = Field(None, description="Text content for the new element"),
        attributes: dict[str, str] | None = Field(
            None, description="Attributes for the new element"
        ),
        cm: CitationManager | None = None,
    ) -> str:
        """Insert a sibling element relative to ``reference_xpath``.

        Keeps citation markers consistent and returns a short description; prefer
        ``append_child`` when targeting the parent's end. Demonstrated in
        ``examples/resources/editable_mdxl.py``.
        """
        reference_xpath = self._clean_xpath(reference_xpath)
        logger.debug(f"Insert {position} {reference_xpath}: <{element_tag}>")

        elements = self.state.select_all(reference_xpath)
        if not elements:
            logger.warning(f"No reference element found for XPath: {reference_xpath}")

            # Extract parent suggestion for append_child
            parent_suggestion = ""
            if "/" in reference_xpath:
                parts = reference_xpath.rsplit("/", 1)
                if parts[0]:
                    parent_suggestion = parts[0]

            return (
                f"No reference element found for XPath: {reference_xpath}\n"
                f"🔄 Please reformulate your insertion:\n"
                f"  Option 1: Use read() to find an existing element as reference\n"
                f"  Option 2: If adding to end of parent, use append_child instead\n"
                f"           parent_xpath='{parent_suggestion or '//parent'}', element_tag='{element_tag}'\n"
                f"  Option 3: Check your xpath syntax and element names\n"
                f"Try again with a valid reference element or different approach."
            )

        reference = elements[0]
        parent = reference._root.getparent()

        if parent is None:
            return f"Cannot insert {position} root element"

        # Build element string
        elem_str = f"<{element_tag}"
        if attributes:
            for key, value in attributes.items():
                elem_str += f' {key}="{value}"'

        if text_content:
            # Normalize citations to self-contained markdown with refs
            normalized_text = self._convert_llm_citations_to_markdown_refs(text_content, cm)
            elem_str += f">{normalized_text}</{element_tag}>"
        else:
            elem_str += "/>"

        # Find position and insert
        index = list(parent).index(reference._root)

        # Parse and insert new element
        from lxml import etree

        new_elem = etree.fromstring(elem_str)

        # Insert based on position parameter
        if position == "before":
            parent.insert(index, new_elem)
        elif position == "after":
            parent.insert(index + 1, new_elem)
        else:
            return f"Invalid position: {position}. Must be 'before' or 'after'"

        self._modified = True
        result = f"Inserted <{element_tag}> {position} {reference_xpath}"
        logger.info(result)
        return result

    # Deprecated: use insert() with position='before' instead
    # @tool
    # async def insert_before(
    #     self,
    #     reference_xpath: str = Field(...,
    #         description="XPath to reference element before which to insert. Use // for descendant search."),
    #     element_tag: str = Field(...,
    #         description="Tag name for the new element"),
    #     text_content: str | None = Field(None,
    #         description="Text content for the new element"),
    #     attributes: dict[str, str] | None = Field(None,
    #         description="Attributes for the new element"),
    # ) -> str:
    #     """Insert a new element before an existing element as a sibling.
    #
    #     Timeline Example:
    #         To insert an event before an existing date:
    #         - reference_xpath='//timeline/day[@date="2024-01-20"]'
    #         - element_tag='day'
    #         - attributes={'date': '2024-01-19'}
    #         - text_content='Day before inauguration'
    #
    #     Returns:
    #         Description of what was inserted
    #     """
    #     reference_xpath = self._clean_xpath(reference_xpath)
    #     logger.debug(f"Insert before {reference_xpath}: <{element_tag}>")
    #
    #     elements = self.state.select_all(reference_xpath)
    #     if not elements:
    #         logger.warning(f"No reference element found for XPath: {reference_xpath}")
    #         return f"No reference element found for XPath: {reference_xpath}"
    #
    #     reference = elements[0]
    #     parent = reference._root.getparent()
    #
    #     if parent is None:
    #         return "Cannot insert before root element"
    #
    #     # Build element string
    #     elem_str = f"<{element_tag}"
    #     if attributes:
    #         for key, value in attributes.items():
    #             elem_str += f' {key}="{value}"'
    #
    #     if text_content:
    #         elem_str += f">{text_content}</{element_tag}>"
    #     else:
    #         elem_str += "/>"
    #
    #     # Find position and insert
    #     index = list(parent).index(reference._root)
    #
    #     # Parse and insert new element
    #     from lxml import etree
    #
    #     new_elem = etree.fromstring(elem_str)
    #     parent.insert(index, new_elem)
    #
    #     self._modified = True
    #     result = f"Inserted <{element_tag}> before {reference_xpath}"
    #     logger.info(result)
    #     return result

    @tool
    async def append_child(
        self,
        parent_xpath: str = Field(
            ...,
            description="XPath to EXISTING parent element where new child will be added. Parent must exist. (e.g., '//person[@name=\"John\"]' to add child to John)",
        ),
        element_tag: str = Field(
            ...,
            description="Tag name for the NEW element to create (e.g., 'details', 'description', 'notes')",
        ),
        text_content: str | None = Field(None, description="Text content for the new element"),
        attributes: dict[str, str] | None = Field(
            None,
            description="Attributes for the new element (e.g., {'type': 'personal', 'visibility': 'public'})",
        ),
        cm: CitationManager | None = None,
    ) -> str:
        """Append a new child element beneath ``parent_xpath``.

        Use when the parent already exists but the child does not. Normalizes
        citation markers in ``text_content`` and returns a short status string.
        See ``examples/resources/editable_mdxl.py`` for a runnable workflow.
        """
        parent_xpath = self._clean_xpath(parent_xpath)
        logger.debug(f"Append child to {parent_xpath}: <{element_tag}>")

        parents = self.state.select_all(parent_xpath)
        if not parents:
            logger.warning(f"No parent element found for XPath: {parent_xpath}")
            return (
                f"No parent element found for XPath: {parent_xpath}\n"
                f"🔄 Please reformulate:\n"
                f"  1. Use read() to see the document structure\n"
                f"  2. Ensure the parent element exists (e.g., '//entities', '//timeline', '//document')\n"
                f"  3. Check xpath syntax - use // for descendant search\n"
                f"  4. For persons, use: '//person[@name=\"exact-name\"]'\n"
                f"Try again with a valid parent element path."
            )

        parent = parents[0]

        # Build element string
        elem_str = f"<{element_tag}"
        if attributes:
            for key, value in attributes.items():
                elem_str += f' {key}="{value}"'

        if text_content:
            # Normalize citations to self-contained markdown with refs
            normalized_text = self._convert_llm_citations_to_markdown_refs(text_content, cm)
            elem_str += f">{normalized_text}</{element_tag}>"
        else:
            elem_str += "/>"

        # Parse and append new element
        from lxml import etree

        new_elem = etree.fromstring(elem_str)
        parent._root.append(new_elem)

        self._modified = True
        result = f"Appended <{element_tag}> as child of {parent_xpath}"
        logger.info(result)
        return result

    @tool(name="delete")  # type: ignore[arg-type,misc]
    async def delete(
        self,
        xpath: str = Field(
            ...,
            description="XPath selector for element(s) to delete. Use // for descendant search.",
        ),
        limit: int = Field(
            1,
            description="Maximum number of elements to delete (default 1, use -1 for all)",
        ),
    ) -> str:
        """Delete elements matching an XPath selector.

        Examples:
            - Delete specific person: xpath='//person[@name="John"]'
            - Delete all former candidates: xpath='//person[@role="former-candidate"]', limit=-1
            - Delete old timeline entry: xpath='//timeline/day[@date="2023-01-01"]'

        Returns:
            Description of what was deleted
        """
        xpath = self._clean_xpath(xpath)
        logger.debug(f"Delete called with xpath={xpath}, limit={limit}")
        elements = self.state.select_all(xpath)

        if not elements:
            logger.warning(f"No elements found for XPath: {xpath}")
            return (
                f"No elements found for XPath: {xpath}\n"
                f"🔄 Please check your xpath selector and try again.\n"
                f"Tip: Use read() to see the document structure first."
            )

        count = 0
        for element in elements:
            if limit != -1 and count >= limit:
                break

            # Remove the element from its parent
            parent = element._root.getparent()
            if parent is not None:
                parent.remove(element._root)
                count += 1

        self._modified = True
        result = f"Deleted {count} element(s) matching {xpath}"
        logger.info(result)
        return result

    # @tool(name="move")
    # async def move(
    #     self,
    #     source_xpath: str = Field(...,
    #         description="XPath selector for element(s) to move. Use // for descendant search."),
    #     target_xpath: str = Field(...,
    #         description="XPath selector for target parent element"),
    #     position: str = Field("append",
    #         description="Where to insert - 'append' (end) or 'prepend' (beginning)"),
    # ) -> str:
    #     """Move content between elements.

    #     Examples:
    #         - Move person to different section:
    #           source='//inactive/person[@id="123"]', target='//active'
    #         - Reorder timeline entries:
    #           source='//timeline/day[@date="2024-01-15"]', target='//timeline', position='prepend'

    #     Returns:
    #         Description of what was moved
    #     """
    #     source_xpath = self._clean_xpath(source_xpath)
    #     target_xpath = self._clean_xpath(target_xpath)
    #     logger.debug(
    #         f"Move called: source={source_xpath}, target={target_xpath}, position={position}"
    #     )
    #     source_elements = self.state.select_all(source_xpath)
    #     if not source_elements:
    #         logger.warning(f"No source elements found for XPath: {source_xpath}")
    #         return f"No source elements found for XPath: {source_xpath}"

    #     target_elements = self.state.select_all(target_xpath)
    #     if not target_elements:
    #         logger.warning(f"No target element found for XPath: {target_xpath}")
    #         return f"No target element found for XPath: {target_xpath}"

    #     target = target_elements[0]
    #     moved_count = 0

    #     for element in source_elements:
    #         # Remove from current parent
    #         parent = element._root.getparent()
    #         if parent is not None:
    #             parent.remove(element._root)

    #             # Add to target
    #             if position == "append":
    #                 target._root.append(element._root)
    #             elif position == "prepend":
    #                 target._root.insert(0, element._root)
    #             else:
    #                 return f"Invalid position: {position}"

    #             moved_count += 1

    #     self._modified = True
    #     result = f"Moved {moved_count} element(s) from {source_xpath} to {target_xpath}"
    #     logger.info(result)
    #     return result
