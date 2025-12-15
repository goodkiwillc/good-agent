from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Literal, cast

from good_agent.content import RenderMode
from good_agent.core.components import AgentComponent
from good_agent.core.event_router import EventContext, on
from good_agent.events import (
    AgentEvents,
    MessageAppendParams,
    MessageCreateParams,
    MessageRenderParams,
    ToolsGenerateSignature,
)
from good_agent.extensions.citations.citation_adapter import CitationAdapter
from good_agent.extensions.citations.formats import (
    CitationExtractor,
    CitationFormat,
    CitationPatterns,
    CitationTransformer,
)
from good_agent.extensions.citations.index import CitationIndex

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from good_agent import Agent
    from good_agent.messages import Message
    from good_agent.tools import ToolSignature


class CitationManager(AgentComponent):
    """Normalizes citations on message create/render and keeps a shared index.

    Hooks into AgentEvents so appended/created messages automatically reuse
    global numbering. See ``examples/extensions/citations_basic.py`` for a quick
    integration demo.
    """

    def __init__(
        self,
        citation_index: CitationIndex | None = None,
        use_tool_adapter: bool = True,
        debug: bool = False,
    ):
        """
        Initialize CitationManager with optional existing index.

        Args:
            citation_index: Existing CitationIndex to use, or create new one
            use_tool_adapter: Whether to use the CitationAdapter for tool transformation
        """
        # Store the index before calling parent
        self._provided_index = citation_index

        # Don't pass citation_index to parent class
        super().__init__()

        # Set the index after parent initialization
        if self._provided_index is not None:
            self.index = self._provided_index
        else:
            self.index = CitationIndex()

        self._agent = None
        self._use_tool_adapter = use_tool_adapter
        self._citation_adapter: CitationAdapter | None = None
        self._debug = debug

    async def install(self, agent: Agent) -> None:
        """
        Install the citation manager on an agent.

        Registers event handlers for message creation and rendering.
        Also registers the CitationAdapter if enabled.

        Args:
            agent: Agent instance to install on
        """
        await super().install(agent)

        # Register event handlers using enum constants (not string literals)
        # agent.on(AgentEvents.MESSAGE_CREATE_BEFORE, priority=150)(
        #     self._on_message_create_before
        # )
        # agent.on(AgentEvents.MESSAGE_RENDER_BEFORE, priority=150)(
        #     self._on_message_render_before
        # )
        # # Also handle messages that are directly appended (not created via create_message)
        # agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=150)(
        #     self._on_message_append_after
        # )

        # Register CitationAdapter if enabled
        if self._use_tool_adapter:
            self._citation_adapter = CitationAdapter(self)
            self.register_tool_adapter(self._citation_adapter)
            if self._debug:
                logger.debug(f"CitationAdapter registered for agent {agent.id}")
        else:
            pass
            # Keep the legacy TOOLS_GENERATE_SIGNATURE handler for backward compatibility
            # agent.on(AgentEvents.TOOLS_GENERATE_SIGNATURE, priority=150)(
            #     self._on_tools_generate_signature
            # )

        if self._debug:
            logger.debug(f"CitationManager installed on agent {agent.id}")

    def _on_tools_generate_signature(
        self, ctx: EventContext[ToolsGenerateSignature, ToolSignature]
    ):
        ctx.parameters["tool"]
        signature = ctx.output

        return signature

    @on(AgentEvents.MESSAGE_APPEND_AFTER, priority=150)
    def _on_message_append_after(self, ctx: EventContext[MessageAppendParams, None]) -> None:
        """
        Process citations for messages that are directly appended.

        This handles the case where a pre-created Message object is appended
        directly to the agent (e.g., AssistantMessage with citation references).

        Args:
            ctx: Event context containing the appended message
        """
        try:
            message = ctx.parameters.get("message")
            if not message:
                return

            # Skip if message already has citations populated
            if hasattr(message, "citations") and message.citations:
                # Add citations to global index
                for citation in message.citations:
                    self.index.add(citation)
                return

            # Check if message content has citation references
            content_text = ""
            if hasattr(message, "content_parts") and message.content_parts:
                for part in message.content_parts:
                    if hasattr(part, "text"):
                        content_text += part.text
                    elif hasattr(part, "template"):
                        content_text += part.template
                    else:
                        content_text += str(part)

            # Check for citation patterns
            if CitationPatterns.LLM_CITE.search(content_text) or CitationPatterns.MARKDOWN.search(
                content_text
            ):
                # Process content to extract and resolve citations
                processed_content, resolved_citations = self._lookup_and_resolve_citations(
                    content_text
                )

                if resolved_citations:
                    # Update message citations (make mutable if needed)
                    if hasattr(message, "__dict__"):
                        message.__dict__["citations"] = resolved_citations

                    # Add to global index
                    for citation in resolved_citations:
                        self.index.add(citation)

                    # Update content if it was transformed
                    if processed_content != content_text:
                        from good_agent.content import TextContentPart

                        # Replace first text content part with processed content
                        for i, part in enumerate(message.content_parts):
                            if hasattr(part, "text"):
                                message.content_parts[i] = TextContentPart(text=processed_content)
                                break

                    if self._debug:
                        logger.debug(
                            f"Resolved {len(resolved_citations)} citations for appended message"
                        )

        except Exception as e:
            logger.error(f"Error in _on_message_append_after: {e}", exc_info=True)

    @on(AgentEvents.MESSAGE_CREATE_BEFORE, priority=150)
    def _on_message_create_before(self, ctx: EventContext[MessageCreateParams, Message]) -> None:
        """
        Extract citations during message creation using default render mode.

        This method extracts citations during creation to maintain backward compatibility
        while using a sensible default render mode. Fine-grained transformation
        happens later during rendering with the proper render mode context.

        Args:
            ctx: Event context containing role, content (content_parts),
                 citations, and extra_kwargs parameters
        """
        try:
            # Extract parameters from event context
            role = ctx.parameters.get("role")
            content_parts: list[Any] = ctx.parameters.get("content", [])
            citations = ctx.parameters.get("citations")

            # Convert content parts to strings using default render mode (DISPLAY)
            # This provides a reasonable default for citation extraction during creation
            converted_content = []
            for part in content_parts:
                if hasattr(part, "render"):
                    # Use DISPLAY mode as a sensible default for creation-time extraction
                    converted_content.append(part.render(RenderMode.DISPLAY))
                else:
                    # Fall back to str() for non-content parts
                    converted_content.append(str(part))

            # Process content parts to extract and normalize citations
            processed_parts, extracted_citations = self._process_content_parts(
                converted_content,
                citations,
                role or "",
                RenderMode.DISPLAY,  # type: ignore[arg-type]
            )

            # Always update content with processed parts
            # The processed parts contain the normalized citations
            ctx.parameters["content"] = processed_parts

            if extracted_citations:
                # Add citations to global index
                for citation in extracted_citations:
                    self.index.add(citation)

                # Update citations in parameters AND extra_kwargs
                ctx.parameters["citations"] = extracted_citations

                # Also update extra_kwargs to ensure citations are passed to message
                # Note: extra_kwargs is not a standard TypedDict key, but we use it dynamically
                if (
                    "extra_kwargs" in ctx.parameters  # type: ignore[typeddict-item, typeddict-unknown-key]
                    and ctx.parameters["extra_kwargs"] is not None  # type: ignore[typeddict-item, typeddict-unknown-key]
                ):
                    ctx.parameters["extra_kwargs"]["citations"] = extracted_citations  # type: ignore[typeddict-item, typeddict-unknown-key]
                else:
                    ctx.parameters["extra_kwargs"] = {"citations": extracted_citations}  # type: ignore[typeddict-item, typeddict-unknown-key]

        except Exception as e:
            logger.error(f"Error in _on_message_create_before: {e}", exc_info=True)

    @on(AgentEvents.MESSAGE_RENDER_BEFORE)
    def _on_message_render_before(self, ctx: EventContext[MessageRenderParams, None]) -> None:
        """
        Transform citations based on render mode.

        This method runs before messages are rendered and transforms citation
        references based on the target audience (LLM vs user display). Citation
        extraction primarily happens during message creation, but this method
        can also extract citations if they weren't found during creation.

        For LLM rendering:
        -ult Map local indices to global indices via CitationIndex
        - Use [!CITE_X!] format or idx="X" attributes for high visibility

        For user display:
        - Replace with inline markdown links [text](url)
        - Or preserve URL attributes for XML elements

        Args:
            ctx: Event context containing message, mode, and output
        """
        try:
            # Extract parameters
            mode = ctx.parameters.get("mode")
            message = ctx.parameters.get("message")
            output_param = ctx.parameters.get("output")  # List of content parts

            if not isinstance(output_param, list):
                return

            output = cast(list[Any], output_param)

            if not message or not mode or not output:
                return

            # If no citations yet, attempt render-time extraction and normalization
            if not hasattr(message, "citations") or not message.citations:
                try:
                    processed_parts, extracted_citations = self._process_content_parts(
                        output,
                        None,
                        getattr(message, "role", "user"),
                        mode,  # type: ignore[arg-type]
                    )
                    if extracted_citations:
                        if hasattr(message, "__dict__"):
                            message.__dict__["citations"] = extracted_citations
                        for citation in extracted_citations:
                            self.index.add(citation)
                        # Use normalized parts (with local indices) for downstream transforms
                        ctx.output = processed_parts  # type: ignore[assignment]
                        ctx.parameters["output"] = processed_parts
                        output = processed_parts
                except Exception as e:
                    logger.error(
                        f"Error extracting citations during render fallback: {e}",
                        exc_info=True,
                    )

            # Only transform if message now has citations
            if not hasattr(message, "citations") or not message.citations:
                return

            # Import here to avoid circular dependency
            from good_agent.content import TextContentPart

            # Process each content part for transformation
            transformed_parts = []
            was_transformed = False

            for part in output:  # type: ignore[attr-defined]
                if isinstance(part, TextContentPart):
                    original_text = part.text

                    # Transform based on render mode
                    if mode == RenderMode.LLM:
                        transformed_text = self._transform_for_llm(original_text, message.citations)
                    elif mode == RenderMode.DISPLAY:
                        # Pass message role to determine transformation behavior
                        message_role = getattr(message, "role", "user")
                        transformed_text = self._transform_for_user(
                            original_text, message.citations, message_role
                        )
                    else:
                        transformed_text = original_text

                    # If transformed, create a new TextContentPart
                    if transformed_text != original_text:
                        was_transformed = True
                        transformed_parts.append(TextContentPart(text=transformed_text))
                    else:
                        transformed_parts.append(part)
                else:
                    # Keep non-text parts as-is (templates, images, etc.)
                    transformed_parts.append(part)

            # Update the output if transformation was applied
            if was_transformed:
                ctx.output = transformed_parts  # type: ignore[assignment]
                ctx.parameters["output"] = transformed_parts

        except Exception as e:
            logger.error(f"Error in _on_message_render_before: {e}", exc_info=True)

    def _extract_citations_from_parts(
        self, content_parts: list, mode: RenderMode, role: str
    ) -> list | None:
        """
        Extract citations from content parts using the provided render mode.

        Args:
            content_parts: List of content parts to process
            mode: Render mode to use for content part rendering
            role: Message role for context

        Returns:
            List of extracted citations or None if none found
        """
        try:
            # Convert content parts to strings using proper rendering with the specified mode
            converted_content = []
            for part in content_parts:
                if hasattr(part, "render"):
                    # Use the provided render mode for citation extraction
                    converted_content.append(part.render(mode))
                else:
                    # Fall back to str() for non-content parts
                    converted_content.append(str(part))

            # Process content parts to extract citations
            processed_parts, extracted_citations = self._process_content_parts(
                converted_content, None, role, mode
            )

            return extracted_citations

        except Exception as e:
            logger.error(f"Error in _extract_citations_from_parts: {e}", exc_info=True)
            return None

    def _process_content_parts(
        self,
        content_parts: list,
        citations: list | None,
        role: str,
        mode: RenderMode | None = None,
    ) -> tuple[list, list | None]:
        """
        Process content parts to extract and normalize citations.

        Three-phase approach:
        1. Extract ALL citations from content (URLs, references, etc.)
        2. Build deduplicated message.citations list
        3. Normalize content to use consistent local indices

        Args:
            content_parts: List of content parts (strings or ContentPart objects)
            citations: Existing citations list if provided
            role: Message role (user, assistant, tool, etc.)
            mode: Render mode to use for content part rendering (defaults to DISPLAY)

        Returns:
            Tuple of (processed_content_parts, extracted_citations)
        """
        # logger.debug(
        #     f"CitationManager: _process_content_parts called for role={role}, citations={citations is not None}"
        # )
        # logger.debug(f"CitationManager: Content preview: {str(content_parts)[:100]}...")

        from good_agent.content import TemplateContentPart, TextContentPart, is_template
        from good_agent.core.types import URL

        # Default to DISPLAY mode if not provided (for backward compatibility)
        if mode is None:
            mode = RenderMode.DISPLAY

        def safe_render(part: Any, render_mode: RenderMode) -> str:
            """Safely render a content part, falling back to str() on error."""
            if not hasattr(part, "render"):
                return str(part)
            try:
                return part.render(render_mode)
            except Exception:
                # Template may reference undefined variables - fall back to str()
                return str(part)

        # If we already have citations and proper format, AND there are no XML URLs to extract,
        # return as-is. Messages with XML may have additional URLs to extract even when citations are provided.
        # Use the specified render mode to check for citation patterns
        has_cite_format = any("[!CITE_" in safe_render(part, mode) for part in content_parts)
        has_xml_urls = any('url="' in safe_render(part, mode) for part in content_parts)

        if citations and has_cite_format and not has_xml_urls:
            return content_parts, citations

        processed_parts = []

        # Phase 1: Extract ALL citations from all parts
        all_found_citations = []
        content_texts = []  # Track original content for each part

        for part in content_parts:
            # Convert strings to ContentPart objects
            if isinstance(part, str):
                if is_template(part):
                    part = TemplateContentPart(
                        template=part,
                        context_requirements=[],
                    )
                else:
                    part = TextContentPart(text=part)

            if isinstance(part, TextContentPart):
                content = part.text
                part_citations = []
                markdown_ref_mapping = {}  # original_idx -> URL

                # Extract markdown reference blocks [X]: URL first and remove them
                if CitationPatterns.MARKDOWN_REF_BLOCK.search(content):
                    refs = CitationExtractor.extract_markdown_references(content)
                    # Store mapping of original indices to URLs
                    for original_idx, url in refs.items():
                        markdown_ref_mapping[original_idx] = url
                        part_citations.append(url)
                    # Remove reference blocks from content completely
                    # First pass: remove the exact matches
                    content = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", content)

                    # Second pass: clean up multiple blank lines and trailing whitespace
                    content = re.sub(
                        r"\n\s*\n\s*\n+", "\n\n", content
                    )  # Multiple blank lines -> double blank
                    content = content.strip()

                    logger.debug(f"Removed {len(refs)} reference blocks from content")

                # Also remove already-processed reference blocks like [!CITE_X!]: [!CITE_Y!]
                if CitationPatterns.PROCESSED_REF_BLOCK.search(content):
                    # Count before removing
                    removed_count = len(CitationPatterns.PROCESSED_REF_BLOCK.findall(content))
                    content = CitationPatterns.PROCESSED_REF_BLOCK.sub("", content)

                    # Clean up multiple blank lines and trailing whitespace after removal
                    content = re.sub(
                        r"\n\s*\n\s*\n+", "\n\n", content
                    )  # Multiple blank lines -> double blank
                    content = content.strip()

                    logger.debug(
                        f"Removed {removed_count} already-processed reference blocks from content"
                    )

                # Keep track of XML URLs separately to avoid double-processing
                xml_urls_extracted = []
                markdown_urls_extracted = []

                # Extract XML url attributes from any message (not just tool messages)
                # This allows citations in user messages that contain XML-like content
                if 'url="' in content:
                    url_matches = list(CitationPatterns.XML_URL_ATTR.finditer(content))
                    for match in url_matches:
                        url = URL(match.group(1))
                        part_citations.append(url)
                        xml_urls_extracted.append(url)

                # Extract markdown inline links: [text](https://example.com)
                try:
                    markdown_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
                    for m in markdown_link_pattern.finditer(content):
                        url = URL(m.group(2))
                        if url not in part_citations:
                            part_citations.append(url)
                        markdown_urls_extracted.append(url)
                except Exception:
                    pass

                # Extract inline URLs (but not those already extracted from XML)
                url_pattern = re.compile(r'(?<!["\'>])(https?://[^\s<>"\']+)(?!["\'>])')
                for match in url_pattern.finditer(content):
                    url = URL(match.group(1))
                    # Skip if this URL was already extracted
                    if (
                        url not in xml_urls_extracted
                        and url not in markdown_urls_extracted
                        and url not in part_citations
                    ):
                        part_citations.append(url)

                all_found_citations.extend(part_citations)
                content_texts.append((content, part, part_citations, markdown_ref_mapping))
            else:
                # Non-text parts pass through unchanged
                content_texts.append((None, part, [], {}))  # type: ignore[arg-type]

        # Phase 2: Build deduplicated citations list
        # We need to handle sparse indices from markdown references
        # Build a complete mapping of all referenced indices to URLs
        all_referenced_mappings = {}  # original_idx -> URL

        # Collect all markdown reference mappings
        for content_text, _, _, markdown_mapping in content_texts:
            if markdown_mapping:
                all_referenced_mappings.update(markdown_mapping)

            if content_text:
                # Also check for [!CITE_X!] references to global index
                for match in CitationPatterns.LLM_CITE.finditer(content_text):
                    idx = int(match.group(1))
                    # Look up in global index if not in markdown mappings
                    if idx not in all_referenced_mappings and idx in self.index.as_dict():
                        url = self.index.as_dict()[idx]
                        all_referenced_mappings[idx] = url

        # Build sequential citations list from all found citations
        final_citations = []

        # Create a reindex mapping: original_idx -> new_local_idx (1-based)
        reindex_mapping = {}

        # First add all URLs from sparse indices in order
        for original_idx in sorted(all_referenced_mappings.keys()):
            url = all_referenced_mappings[original_idx]
            if url not in final_citations:
                final_citations.append(url)
            # Map original index to new sequential index (1-based)
            reindex_mapping[original_idx] = final_citations.index(url) + 1

        # Add provided citations if any
        if citations:
            for citation in citations:
                if citation not in final_citations:
                    final_citations.append(citation)

        # Add other found citations (from inline URLs, etc.)
        for citation in all_found_citations:
            if citation not in final_citations:
                final_citations.append(citation)

        # Phase 3: Normalize content to use local indices
        for content, part, _part_citations, _markdown_mapping in content_texts:
            if content is None:
                # Non-text part, pass through
                processed_parts.append(part)
                continue

            # Now normalize all references to use local indices from final_citations
            normalized_content = content

            # FIRST: Reindex sparse [!CITE_X!] references using our mapping
            if CitationPatterns.LLM_CITE.search(normalized_content):
                for match in reversed(list(CitationPatterns.LLM_CITE.finditer(normalized_content))):
                    original_idx = int(match.group(1))
                    logger.info(f"CitationManager: Processing LLM citation [!CITE_{original_idx}!]")
                    # Use reindex mapping if available
                    if original_idx in reindex_mapping:
                        new_idx = reindex_mapping[original_idx]
                        if new_idx != original_idx:
                            replacement = f"[!CITE_{new_idx}!]"
                            logger.info(
                                f"CitationManager: Reindexing using mapping: [!CITE_{original_idx}!] -> [!CITE_{new_idx}!]"
                            )
                            normalized_content = (
                                normalized_content[: match.start()]
                                + replacement
                                + normalized_content[match.end() :]
                            )
                    elif original_idx in self.index.as_dict():
                        # Try global index lookup
                        url = self.index.as_dict()[original_idx]
                        logger.info(f"CitationManager: Found global index {original_idx} -> {url}")
                        if url in final_citations:
                            local_idx = final_citations.index(url) + 1
                            if local_idx != original_idx:
                                replacement = f"[!CITE_{local_idx}!]"
                                logger.info(
                                    f"CitationManager: Reindexing using global lookup: [!CITE_{original_idx}!] -> [!CITE_{local_idx}!]"
                                )
                                normalized_content = (
                                    normalized_content[: match.start()]
                                    + replacement
                                    + normalized_content[match.end() :]
                                )
                            else:
                                logger.info(
                                    f"CitationManager: Index {original_idx} already matches local index {local_idx}"
                                )
                        else:
                            logger.warning(
                                f"CitationManager: URL {url} not found in final_citations"
                            )
                    else:
                        logger.warning(
                            f"CitationManager: Index {original_idx} not found in reindex_mapping or global index"
                        )

            # SECOND: Handle XML url attributes -> idx attributes
            # Support XML URLs in any message type (not just tool messages)
            if 'url="' in normalized_content:
                url_matches = list(CitationPatterns.XML_URL_ATTR.finditer(normalized_content))

                # First, collect all URLs in order to add to final_citations
                for match in url_matches:
                    url = URL(match.group(1))
                    if url not in final_citations:
                        final_citations.append(url)
                        # logger.debug(
                        #     f"Added URL {url} to citations during normalization"
                        # )

                # Then process replacements in reverse to maintain string positions
                for match in reversed(url_matches):
                    url = URL(match.group(1))
                    # URL should now be in final_citations
                    local_idx = final_citations.index(url) + 1
                    replacement = f'idx="{local_idx}"'
                    logger.info(
                        f"CitationManager: Normalizing XML URL to index: {url} -> idx={local_idx}"
                    )
                    normalized_content = (
                        normalized_content[: match.start()]
                        + replacement
                        + normalized_content[match.end() :]
                    )

            # THIRD: Handle inline URLs -> [!CITE_X!]
            url_pattern = re.compile(r'(?<!["\'>])(https?://[^\s<>"\']+)(?!["\'>])')
            for match in reversed(list(url_pattern.finditer(normalized_content))):
                url = URL(match.group(1))
                if url in final_citations:
                    local_idx = final_citations.index(url) + 1
                    replacement = f"[!CITE_{local_idx}!]"
                    logger.info(
                        f"CitationManager: Converting inline URL to citation: {url} -> [!CITE_{local_idx}!]"
                    )
                    normalized_content = (
                        normalized_content[: match.start()]
                        + replacement
                        + normalized_content[match.end() :]
                    )
                else:
                    # URL not found - add it dynamically
                    final_citations.append(url)
                    local_idx = len(final_citations)
                    replacement = f"[!CITE_{local_idx}!]"
                    logger.info(
                        f"CitationManager: Adding and converting inline URL to citation: {url} -> [!CITE_{local_idx}!]"
                    )
                    normalized_content = (
                        normalized_content[: match.start()]
                        + replacement
                        + normalized_content[match.end() :]
                    )
                    # logger.debug(
                    #     f"Added inline URL {url} to citations during normalization"
                    # )

            # THIRD-B: Convert markdown links [text](url) -> 'text [!CITE_X!]'
            markdown_link_pattern = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
            for match in reversed(list(markdown_link_pattern.finditer(normalized_content))):
                link_text = match.group(1)
                url = URL(match.group(2))
                if url not in final_citations:
                    final_citations.append(url)
                local_idx = final_citations.index(url) + 1
                replacement = f"{link_text} [!CITE_{local_idx}!]"
                logger.info(
                    f"CitationManager: Converting markdown link to citation: {url} -> [!CITE_{local_idx}!]"
                )
                normalized_content = (
                    normalized_content[: match.start()]
                    + replacement
                    + normalized_content[match.end() :]
                )

            # FOURTH: Handle [X] markdown references -> [!CITE_X!] with reindexing
            if CitationPatterns.MARKDOWN.search(normalized_content):
                for match in reversed(list(CitationPatterns.MARKDOWN.finditer(normalized_content))):
                    original_idx = int(match.group(1))
                    # Check if this needs reindexing (sparse reference)
                    if original_idx in reindex_mapping:
                        new_idx = reindex_mapping[original_idx]
                        replacement = f"[!CITE_{new_idx}!]"
                    elif 1 <= original_idx <= len(final_citations):
                        # Valid sequential index, just normalize format
                        replacement = f"[!CITE_{original_idx}!]"
                    else:
                        # Invalid index - check if it exists in global index before warning
                        if original_idx not in self.index.as_dict():
                            logger.warning(
                                "Citation [%s] has no corresponding source",
                                original_idx,
                            )
                        # Leave as-is for now - may be resolved from global index later
                        continue

                    normalized_content = (
                        normalized_content[: match.start()]
                        + replacement
                        + normalized_content[match.end() :]
                    )

            processed_parts.append(TextContentPart(text=normalized_content))

        return (
            processed_parts,
            final_citations if final_citations else None,
        )

    def _extract_and_normalize_xml_urls(self, content: str) -> tuple[str, list]:
        """
        Extract URLs from XML attributes and normalize to idx format.

        Args:
            content: XML content with url="..." attributes

        Returns:
            Tuple of (normalized_content, extracted_citations)
        """
        from good_agent.core.types import URL

        # First collect all URLs in order
        url_matches = list(CitationPatterns.XML_URL_ATTR.finditer(content))
        citations = [URL(match.group(1)) for match in url_matches]

        transformed_content = content

        # Process in reverse to maintain string positions
        for i, match in enumerate(reversed(url_matches)):
            # Calculate the correct index (1-based) from the original position
            local_idx = len(url_matches) - i  # This gives us n, n-1, ..., 2, 1
            url = match.group(1)
            replacement = f'idx="{local_idx}"'
            logger.info(
                f"CitationManager: Converting XML URL to index (extract_and_normalize): {url} -> idx={local_idx}"
            )
            transformed_content = (
                transformed_content[: match.start()]
                + replacement
                + transformed_content[match.end() :]
            )

        return transformed_content, citations

    def _extract_and_normalize_markdown_refs(self, content: str) -> tuple[str, list]:
        """
        Extract citations from markdown reference blocks and normalize.

        Args:
            content: Content with markdown reference blocks

        Returns:
            Tuple of (normalized_content, extracted_citations)
        """
        # Extract reference mappings
        references = CitationExtractor.extract_markdown_references(content)

        if not references:
            return content, []

        # Build citations list in index order
        max_index = max(references.keys()) if references else 0
        citations: list[str | None] = [None] * max_index

        for index, url in references.items():
            citations[index - 1] = str(url)  # Convert to 0-based

        # Remove None entries (gaps in indexing)
        citations = [c for c in citations if c is not None]

        # Remove reference blocks from content and normalize
        clean_content = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", content).strip()

        # Transform markdown citations to LLM format
        normalized_content = CitationTransformer.transform_to_llm_format(
            clean_content, source_format=CitationFormat.MARKDOWN
        )

        return normalized_content, citations

    def _normalize_markdown_citations(self, content: str, citations: list) -> str:
        """
        Normalize markdown citations when citation list is provided.

        Args:
            content: Content with markdown [N] citations
            citations: List of citation URLs

        Returns:
            Normalized content with [!CITE_X!] format
        """
        # Transform markdown citations to LLM format
        return CitationTransformer.transform_to_llm_format(
            content, source_format=CitationFormat.MARKDOWN
        )

    def _lookup_and_resolve_citations(self, content: str) -> tuple[str, list]:
        """
        Look up citation references in the global index.

        This handles the case where an LLM response contains citation references
        ([!CITE_X!] or [X] format) but no explicit URLs - we look them up from
        the global citation index.

        Args:
            content: Content with citation references like [!CITE_1!] or [1]

        Returns:
            Tuple of (normalized_content, resolved_citations)
        """
        logger.info(
            f"CitationManager: _lookup_and_resolve_citations called with content: {content[:100]}..."
        )
        logger.debug(f"Current index contents: {dict(self.index.items())}")

        # Detect which format is being used
        current_format = CitationPatterns.detect_format(content)
        logger.debug(f"Detected format: {current_format}")

        # Extract all citation references from the content
        citation_refs = CitationExtractor.extract_citations(content, current_format)
        logger.debug(f"Extracted citation refs: {[ref.citation_index for ref in citation_refs]}")

        if not citation_refs:
            logger.debug("No citation refs found")
            return content, []

        # Build list of resolved citations from global index
        # IMPORTANT: We need to preserve the relationship between citation indices
        # and URLs. The citations list should map local indices (1-based position
        # in THIS message) to the actual URLs.

        # First, collect all unique citation indices referenced in the content
        referenced_indices = []
        seen_indices = set()

        for ref in citation_refs:
            if ref.citation_index and ref.citation_index not in seen_indices:
                referenced_indices.append(ref.citation_index)
                seen_indices.add(ref.citation_index)

        # Now resolve each referenced index to its URL
        index_dict = self.index.as_dict()
        resolved_citations = []

        for idx in referenced_indices:
            logger.debug(f"Checking ref: index={idx}, in index={idx in index_dict}")
            if idx in index_dict:
                url = index_dict[idx]
                resolved_citations.append(url)
                logger.debug(f"Added citation {idx} -> {url}")

        logger.debug(f"Resolved citations: {resolved_citations}")

        # If we found any citations, reindex them to sequential local indices
        if resolved_citations:
            # Create mapping from original global indices to new local sequential indices
            global_to_local_mapping = {}
            for i, idx in enumerate(referenced_indices):
                if idx in index_dict:  # Only map indices that were found
                    url = index_dict[idx]
                    local_idx = i + 1  # 1-based local index
                    global_to_local_mapping[idx] = local_idx
                    logger.info(
                        f"CitationManager: Reindexing global citation: global_idx={idx} -> local_idx={local_idx} for URL={url}"
                    )

            logger.debug(f"Reindexing mapping: {global_to_local_mapping}")

            # Transform content to use sequential local indices, regardless of input format
            normalized_content = CitationTransformer.transform_to_llm_format(
                content,
                index_mapping=global_to_local_mapping,
                source_format=current_format,
            )
            logger.debug(
                f"Reindexed content to sequential local indices: {normalized_content[:100]}..."
            )
            return normalized_content, resolved_citations

        # No citations found in index - preserve existing format
        logger.debug("No citations found in index")
        return content, []

    def _process_message_citations(self, message: Message) -> None:
        """
        Process a message to extract and normalize citations.

        Handles different message types and citation sources:
        - AssistantMessage: From LLMs like Perplexity/Claude with existing citations
        - ToolMessage: XML content with url="..." attributes
        - UserMessage: Markdown citations or reference blocks
        - Any message: Inline URLs that should become citations

        Args:
            message: Message to process for citations
        """
        content = message.render(RenderMode.DISPLAY) if hasattr(message, "render") else str(message)
        message_type = type(message).__name__

        logger.debug(f"Processing citations for {message_type}")

        # Handle different processing paths based on message type and content
        if hasattr(message, "citations") and message.citations:
            # Message already has citations list - normalize content format
            self._normalize_existing_citations(message, content)

        elif 'url="' in content:
            # XML content with URL attributes (typically ToolMessage)
            self._extract_xml_url_citations(message, content)

        elif CitationPatterns.MARKDOWN_REF_BLOCK.search(content):
            # Markdown reference block format
            self._extract_markdown_references(message, content)

        elif CitationPatterns.MARKDOWN.search(content):
            # Markdown citations without URLs - might need external citation list
            self._handle_markdown_citations(message, content)

        else:
            # Check for inline URLs to convert to citations
            self._extract_inline_urls(message, content)

    def _normalize_existing_citations(self, message: Message, content: str) -> None:
        """
        Normalize message that already has citations list.

        Ensures content uses local indices in [!CITE_X!] format.

        Args:
            message: Message with existing citations
            content: Message content to normalize
        """
        if not message.citations:
            return

        # Detect current format in content
        current_format = CitationPatterns.detect_format(content)

        if current_format == CitationFormat.LLM:
            # Already in correct format
            return

        # Create mapping from detected indices to local indices (1-based)
        local_mapping: dict[int, int] = {}

        if current_format == CitationFormat.MARKDOWN:
            # Map [1], [2] to local indices
            matches = CitationExtractor.extract_citations(content, CitationFormat.MARKDOWN)
            for i, match in enumerate(matches, 1):
                if match.citation_index is None:
                    continue
                local_mapping[int(match.citation_index)] = i

        # Transform to LLM format with local indices
        normalized_content = CitationTransformer.transform_to_llm_format(
            content,
            local_mapping,
            current_format,
        )

        # Update message content through content_parts
        if hasattr(message, "content_parts") and message.content_parts:
            # Update the first text content part
            from good_agent.content import TextContentPart

            for part in message.content_parts:
                if isinstance(part, TextContentPart):
                    # Create new part with normalized content (Pydantic immutable)
                    new_part = TextContentPart(text=normalized_content)
                    message.content_parts[message.content_parts.index(part)] = new_part
                    break

    def _extract_xml_url_citations(self, message: Message, content: str) -> None:
        """
        Extract citations from XML url="..." attributes.

        Converts <item url="https://..."> to <item idx="1"> with citations list.

        Args:
            message: Message to update
            content: XML content with URL attributes
        """
        from good_agent.core.types import URL

        # Find all url="..." attributes
        url_matches = list(CitationPatterns.XML_URL_ATTR.finditer(content))
        if not url_matches:
            return

        # First collect all URLs in order
        citations = [URL(match.group(1)) for match in url_matches]

        transformed_content = content

        # Process in reverse order to maintain string positions
        for i, match in enumerate(reversed(url_matches)):
            # Calculate the correct index (1-based) from the original position
            local_idx = len(url_matches) - i  # This gives us n, n-1, ..., 2, 1
            url = match.group(1)
            replacement = f'idx="{local_idx}"'
            logger.info(f"CitationManager: Converting URL to index: {url} -> idx={local_idx}")
            transformed_content = (
                transformed_content[: match.start()]
                + replacement
                + transformed_content[match.end() :]
            )

        # Update message
        self._update_message_citations(message, transformed_content, citations)

    def _extract_markdown_references(self, message: Message, content: str) -> None:
        """
        Extract citations from markdown reference blocks.

        Handles formats like:
        [1]: https://example.com
        [2]: https://other.com
        [3]: <https://example.com/with/angle/brackets>

        Args:
            message: Message to update
            content: Content with reference blocks
        """
        # Extract reference mappings
        references = CitationExtractor.extract_markdown_references(content)

        if not references:
            return

        # Build citations list in index order
        max_index = max(references.keys()) if references else 0
        citations: list[str | None] = [None] * max_index

        for index, url in references.items():
            citations[index - 1] = str(url)  # Convert to 0-based

        # Remove None entries (gaps in indexing)
        citations = [c for c in citations if c is not None]

        # Remove reference blocks from content and normalize citations
        clean_content = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", content).strip()

        # Transform markdown citations to local format
        normalized_content = CitationTransformer.transform_to_llm_format(
            clean_content, source_format=CitationFormat.MARKDOWN
        )

        # Update message
        self._update_message_citations(message, normalized_content, citations)

    def _handle_markdown_citations(self, message: Message, content: str) -> None:
        """
        Handle markdown citations that may reference external citation list.

        For now, preserve as-is since we don't have external context.
        Future enhancement could look up citations from context.

        Args:
            message: Message to potentially update
            content: Content with markdown citations
        """
        # For now, just convert format without changing indices
        # This handles cases where citations reference external lists
        normalized_content = CitationTransformer.transform_to_llm_format(
            content, source_format=CitationFormat.MARKDOWN
        )

        if normalized_content != content:
            self._update_message_content(message, normalized_content)

    def _extract_inline_urls(self, message: Message, content: str) -> None:
        """
        Extract inline URLs and convert to citations.

        Finds URLs like https://example.com and converts to [!CITE_1!] format.

        Args:
            message: Message to update
            content: Content with potential inline URLs
        """
        normalized_content, citations = CitationTransformer.extract_and_normalize_citations(content)

        if citations:
            self._update_message_citations(message, normalized_content, citations)

    def _transform_for_llm(self, content: str, citations: list) -> str:
        """
        Transform content for LLM rendering with global indices.

        Maps local citation indices to global indices for canonical referencing.
        This allows the LLM to reference the same content consistently across
        different messages and use global indices with tools like WebFetcher.

        Args:
            content: Content with local citation references
            citations: Local citations list

        Returns:
            Content with global citation indices
        """
        # Pre-clean reference blocks that shouldn't be sent to the LLM
        # Remove markdown reference blocks and already-processed blocks like
        # "[!CITE_1!]: [!CITE_1!]" that can appear after migrations.
        import re

        cleaned = content
        if CitationPatterns.MARKDOWN_REF_BLOCK.search(cleaned):
            cleaned = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", cleaned)
        if CitationPatterns.PROCESSED_REF_BLOCK.search(cleaned):
            cleaned = CitationPatterns.PROCESSED_REF_BLOCK.sub("", cleaned)
        # Normalize excessive blank lines
        cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned).strip()

        # Get mapping from local to global indices
        index_mapping = self.index.merge(citations)

        # Log the mapping from local to global indices
        for local_idx, global_idx in index_mapping.items():
            if local_idx <= len(citations):
                url = citations[local_idx - 1]  # Convert to 0-based
                if self._debug:
                    logger.debug(
                        f"CitationManager: Mapping local to global index: local_idx={local_idx} -> global_idx={global_idx} for URL={url}"
                    )
            else:
                logger.warning(
                    f"CitationManager: Invalid local index {local_idx} for mapping to global index {global_idx}"
                )

        # Convert any XML url attributes directly to global idx for LLM consumption
        # This covers cases where creation-time normalization didn't run
        try:
            from good_agent.core.types import URL
            from good_agent.extensions.citations.formats import CitationPatterns as _CP

            if 'url="' in cleaned:

                def _url_to_idx(m):
                    u = URL(m.group(1))
                    g = self.index.lookup(u)
                    return f'idx="{g}"' if g else m.group(0)

                cleaned = _CP.XML_URL_ATTR.sub(_url_to_idx, cleaned)
        except Exception:
            pass

        # Auto-detect the format in the cleaned content (could be LLM or XML_IDX)
        current_format = CitationPatterns.detect_format(cleaned)

        # Transform to global indices, preserving the detected format
        return CitationTransformer.transform_to_llm_format(
            cleaned,
            index_mapping,
            source_format=current_format,  # Use the detected format, not assume LLM
        )

    def _transform_for_user(self, content: str, citations: list, role: str = "user") -> str:
        """
        Transform content for user display with clickable links.

        Converts [!CITE_X!] references to [domain](url) format using the global index.
        For tool messages: converts idx="X" attributes to url="..." format for display.
        For other messages: converts idx="X" references to url="..." format.

        Args:
            content: Content with citation references
            citations: Local citations list (used for idx to URL mapping)
            role: Message role

        Returns:
            Content with clickable markdown links or XML with URLs
        """
        # For [!CITE_X!] format, we need to use the global index
        import re

        from good_agent.extensions.citations.formats import CitationPatterns

        result = content

        # Remove any reference blocks that shouldn't appear in user display
        # Remove markdown reference blocks [X]: URL
        if CitationPatterns.MARKDOWN_REF_BLOCK.search(result):
            result = CitationPatterns.MARKDOWN_REF_BLOCK.sub("", result)
            # Clean up blank lines
            result = re.sub(r"\n\s*\n\s*\n+", "\n\n", result)
            result = result.strip()
            logger.debug("Removed markdown reference blocks from user display content")

        # Remove already-processed reference blocks [!CITE_X!]: [!CITE_Y!]
        if CitationPatterns.PROCESSED_REF_BLOCK.search(result):
            processed_count = len(CitationPatterns.PROCESSED_REF_BLOCK.findall(result))
            result = CitationPatterns.PROCESSED_REF_BLOCK.sub("", result)
            # Clean up blank lines
            result = re.sub(r"\n\s*\n\s*\n+", "\n\n", result)
            result = result.strip()
            logger.debug(
                f"Removed {processed_count} processed reference blocks from user display content"
            )

        # Transform idx attributes to url attributes for user display
        # This applies to all messages with XML content, including tool messages
        if 'idx="' in result and citations:

            def replace_idx_with_url(match):
                idx = int(match.group(1))
                # idx is 1-based, list is 0-based
                if 1 <= idx <= len(citations):
                    url = citations[idx - 1]
                    logger.info(
                        f"CitationManager: Converting index to URL for display: idx={idx} -> {url}"
                    )
                    return f'url="{url}"'
                else:
                    # Leave unchanged if index out of bounds
                    logger.warning(
                        f"CitationManager: Index {idx} out of bounds for citations list (length={len(citations)})"
                    )
                    return match.group(0)

            result = re.sub(r'idx="(\d+)"', replace_idx_with_url, result)

        # Transform [!CITE_X!] using local citations first, then global index
        if CitationPatterns.LLM_CITE.search(result):

            def replace_with_citation_url(match):
                index = int(match.group(1))

                # First check local citations (1-based index)
                if citations and 1 <= index <= len(citations):
                    url = citations[index - 1]  # Convert to 0-based
                    logger.info(
                        f"CitationManager: Converting [!CITE_{index}!] to markdown link using local citations: {url}"
                    )
                else:
                    # Fall back to global index
                    index_dict = self.index.as_dict()
                    if index in index_dict:
                        url = index_dict[index]
                        logger.info(
                            f"CitationManager: Converting [!CITE_{index}!] to markdown link using global index: {url}"
                        )
                    else:
                        # Leave unchanged if not found anywhere
                        logger.warning(
                            f"CitationManager: Citation index {index} not found in local citations or global index"
                        )
                        return match.group(0)

                # Format as markdown link
                from urllib.parse import urlparse

                parsed = urlparse(str(url))
                domain = parsed.netloc or parsed.path
                return f"[{domain}]({url})"

            result = CitationPatterns.LLM_CITE.sub(replace_with_citation_url, result)

        # For regular markdown citations [X], use the provided citations list
        # (for backward compatibility with messages that have local citations)
        if CitationPatterns.MARKDOWN.search(result) and citations:
            result = CitationTransformer.transform_to_user_format(
                result, citations, source_format=CitationFormat.MARKDOWN
            )

        return result

    def _update_message_citations(self, message: Message, content: str, citations: list) -> None:
        """
        Update message with new content and citations list.

        Args:
            message: Message to update
            content: New content string
            citations: Citations list to set
        """
        # Set citations (message should be mutable for this field)
        if hasattr(message, "__dict__"):
            message.__dict__["citations"] = citations

        # Update content
        self._update_message_content(message, content)

        logger.debug(f"Updated message with {len(citations)} citations")

    def _update_message_content(self, message: Message, content: str) -> None:
        """
        Update message content through content_parts.

        Args:
            message: Message to update
            content: New content string
        """
        if not hasattr(message, "content_parts") or not message.content_parts:
            return

        # Update the first text content part
        from good_agent.content.parts import TextContentPart

        for i, part in enumerate(message.content_parts):
            if isinstance(part, TextContentPart):
                # Create new part with updated content (Pydantic immutable)
                new_part = TextContentPart(text=content)
                message.content_parts[i] = new_part
                break

    # Public API methods

    def parse(
        self, content: str, content_format: Literal["llm", "markdown"] = "markdown"
    ) -> tuple[str, list[str]]:
        """
        Parse content and extract citations.

        Args:
            content: Content to parse (may contain citations)
            content_format: Format to parse as ("markdown" or "llm")

        Returns:
            Tuple of (parsed_content, extracted_citations)

        Example:
            >>> manager = CitationManager()
            >>> content = '''
            ... Text with citation [1].
            ...
            ... [1]: https://example.com
            ... '''
            >>> parsed, citations = manager.parse(content)
            >>> print(parsed)
            Text with citation [1].
            >>> print(citations)
            ['https://example.com']
        """
        from good_agent.core.types import URL

        # Extract citations from content
        extracted_citations = []

        # Patterns for reference blocks (with and without colons)
        # Standard format: [1]: https://...
        ref_block_pattern = re.compile(
            r"^\s*\[(\d+|[a-zA-Z]\w*)\]:\s*(?:<(.+?)>|(.+))$", re.MULTILINE
        )
        # Malformed format: [1] https://... (missing colon) - captures entire line
        malformed_ref_pattern = re.compile(
            r"^\s*\[(\d+|[a-zA-Z]\w*)\]\s+(https?://\S+).*$", re.MULTILINE
        )

        # Check for any reference blocks (well-formed or malformed)
        has_refs = ref_block_pattern.search(content) or malformed_ref_pattern.search(content)

        if has_refs:
            # Extract well-formed references
            refs: dict[int, str] = {}
            for match in ref_block_pattern.finditer(content):
                idx_str = match.group(1)
                # Try to convert to int if it's numeric, otherwise use as-is
                try:
                    idx = int(idx_str)
                except ValueError:
                    # For non-numeric refs like [cite1], we'll use them in order found
                    idx = len(refs) + 1
                # Group 2 is angle-bracket URL, group 3 is plain URL
                url_text = match.group(2) if match.group(2) else match.group(3)
                refs[idx] = URL(url_text)

            # Also extract URLs from malformed references (for citations list)
            for match in malformed_ref_pattern.finditer(content):
                url_text = match.group(2)
                # Add to citations if not already there
                if URL(url_text) not in refs.values():
                    idx = len(refs) + 1
                    refs[idx] = URL(url_text)

            # Build citations list from references in sorted order
            # Also build index mapping for sparse indices
            index_mapping = {}  # original_idx -> sequential_idx
            sequential_idx = 1
            for original_idx in sorted(refs.keys()):
                url = refs[original_idx]
                extracted_citations.append(str(URL(url)))
                index_mapping[original_idx] = sequential_idx
                sequential_idx += 1

            # Remove both well-formed and malformed reference blocks from content
            parsed_content = ref_block_pattern.sub("", content)
            parsed_content = malformed_ref_pattern.sub("", parsed_content)

            # Clean up multiple blank lines (but preserve leading/trailing whitespace)
            parsed_content = re.sub(r"\n\s*\n\s*\n+", "\n\n", parsed_content)
            # Remove trailing blank lines that may have been left after reference block removal
            parsed_content = parsed_content.rstrip("\n")

            # Transform based on output format
            if content_format == "llm":
                # Convert [X] references to [!CITE_X!] format with index remapping
                parsed_content = CitationTransformer.transform_to_llm_format(
                    parsed_content,
                    index_mapping=index_mapping,
                    source_format=CitationFormat.MARKDOWN,
                )

                # Also handle XML url/href attributes if present
                # Check for both url="..." and href="..." patterns
                xml_url_pattern = re.compile(r'(url|href)="([^"]+)"')
                if xml_url_pattern.search(parsed_content):
                    # Extract XML URLs and add to citations
                    xml_matches = list(xml_url_pattern.finditer(parsed_content))
                    for match in xml_matches:
                        url = URL(match.group(2))  # Group 2 is the URL value
                        if str(url) not in extracted_citations:
                            extracted_citations.append(str(url))

                    # Transform url/href attributes to idx attributes
                    for match in reversed(xml_matches):
                        url = URL(match.group(2))
                        idx = extracted_citations.index(str(url)) + 1
                        # Replace the entire match (attribute name + value) with idx
                        replacement = f'idx="{idx}"'
                        parsed_content = (
                            parsed_content[: match.start()]
                            + replacement
                            + parsed_content[match.end() :]
                        )
        else:
            # No reference blocks, just extract inline URLs and XML attributes
            parsed_content = content

            # Extract inline URLs (excluding trailing punctuation)
            url_pattern = re.compile(
                r'(?<!["\'>])(https?://[^\s<>"\']+?)(?:[).,;!?]+)?(?=[\s<>"\']|$)'
            )
            for match in url_pattern.finditer(parsed_content):
                url_str = match.group(1).rstrip(").,;!?")  # Strip trailing punctuation
                url = URL(url_str)
                if str(url) not in extracted_citations:
                    extracted_citations.append(str(url))

            # Handle XML url/href attributes even when there are no reference blocks
            if content_format == "llm":
                xml_url_pattern = re.compile(r'(?:url|href)="([^"]+)"')
                if xml_url_pattern.search(parsed_content):
                    # Extract XML URLs and add to citations
                    xml_matches = list(xml_url_pattern.finditer(parsed_content))
                    for match in xml_matches:
                        url = URL(match.group(1))
                        if str(url) not in extracted_citations:
                            extracted_citations.append(str(url))

                    # Transform url/href attributes to idx attributes
                    for match in reversed(xml_matches):
                        url = URL(match.group(1))
                        idx = extracted_citations.index(str(url)) + 1
                        # Replace the entire match (attribute name + value) with idx
                        replacement = f'idx="{idx}"'
                        parsed_content = (
                            parsed_content[: match.start()]
                            + replacement
                            + parsed_content[match.end() :]
                        )

        return parsed_content, extracted_citations

    def get_citations_count(self) -> int:
        """Get total number of citations in global index."""
        return len(self.index)

    def get_citations_summary(self) -> str:
        """
        Get a formatted summary of all citations in the index.

        Returns:
            Human-readable summary of citations

        Example:
            >>> manager = CitationManager()
            >>> # ... add some citations through messages ...
            >>> print(manager.get_citations_summary())
            Citations (3 total):
            [1] https://example.com/article
            [2] https://research.org/paper
            [3] https://news.com/story
        """
        if len(self.index) == 0:
            return "No citations available."

        lines = [f"Citations ({len(self.index)} total):"]

        for index, url in self.index.items():
            lines.append(f"[{index}] {url}")

        return "\n".join(lines)

    def find_citations_by_tag(self, tag: str) -> list[tuple[int, str]]:
        """
        Find citations by tag.

        Args:
            tag: Tag to search for

        Returns:
            List of (index, url) tuples
        """
        # Index protocol now returns list[int], need to look up URLs
        indices = self.index.find_by_tag(tag)
        return [(idx, str(self.index[idx])) for idx in indices]

    def export_citations(self, format: str = "json") -> str:
        """
        Export citations in specified format.

        Args:
            format: Export format ("json", "markdown", "csv")

        Returns:
            Formatted citation data
        """
        if format == "json":
            import json

            data = {
                "total_citations": len(self.index),
                "citations": {
                    str(index): {
                        "url": str(url),
                        "metadata": self.index.get_metadata(index),  # Use index, not URL
                        "tags": list(self.index.get_tags(index)),  # Use index, not URL
                    }
                    for index, url in self.index.items()
                },
            }
            return json.dumps(data, indent=2)

        elif format == "markdown":
            lines = ["# Citations", ""]
            for index, url in self.index.items():
                tags = self.index.get_tags(index)  # Use index, not URL
                tag_str = f" `{', '.join(tags)}`" if tags else ""
                lines.append(f"{index}. [{url}]({url}){tag_str}")
            return "\n".join(lines)

        elif format == "csv":
            lines = ["Index,URL,Tags"]
            for index, url in self.index.items():
                tags_str: str = "; ".join(self.index.get_tags(index))  # Use index, not URL
                lines.append(f'{index},{url},"{tags_str}"')
            return "\n".join(lines)

        else:
            raise ValueError(f"Unknown export format: {format}")
