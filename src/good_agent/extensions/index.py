from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypedDict

from good_agent.core.types import URL
from good_agent.core.event_router import EventContext
from ulid import ULID

from ..base import Index
from ..components import AgentComponent
from ..events import AgentEvents


@dataclass
class Citation:
    """Represents a citation reference"""

    id: str = field(default_factory=lambda: str(ULID()))
    text: str = ""
    origin: str = ""  # URL or reference
    source: str = ""  # Source name (e.g., "Wikipedia")
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)


class Paragraph:
    """
    A paragraph that can contain cited text.
    Implements __llm__ for rendering within LLM context.
    """

    def __init__(self, content: str, citation: Citation | None = None):
        self.content = content
        self.citation = citation

    def __llm__(self) -> str:
        """Render paragraph for LLM context"""
        if self.citation:
            # Include citation reference in LLM rendering
            return f"{self.content} [{self.citation.id}]"
        return self.content

    def __str__(self) -> str:
        """String representation"""
        return self.content

    def __repr__(self) -> str:
        """Debug representation"""
        return f"Paragraph(content={self.content!r}, citation={self.citation})"


# Event parameter types for type safety
class MessageAppendParams(TypedDict):
    """Parameters for message:append event"""

    message: Any  # Message type
    agent: Any  # Agent type


class ToolResponseParams(TypedDict):
    """Parameters for tool:response event"""

    response: Any
    tool: str


if TYPE_CHECKING:
    # Type hint for protocol implementation
    _CitationIndexBase = Index[URL, str, Citation]
else:
    _CitationIndexBase = object


class CitationIndex(AgentComponent, _CitationIndexBase):
    """
    Extension for managing citations and references in agent conversations.

    This allows tools to register sources and create properly cited content.
    """

    def __init__(self, name: str = "citations"):
        super().__init__()
        self.name = name
        self._index: dict[str, Citation] = {}  # citation_id -> Citation
        self._content_map: dict[str, str] = {}  # citation_id -> content
        self._aliases: dict[str, URL] = {}  # alias -> primary_id
        self._target = None  # Will be set by install()

    async def install(self, agent):
        """Install the citation index on the agent"""
        await super().install(agent)
        # Store reference to the agent
        self._agent = agent

        # Register our event handlers with the agent
        # The super().install() already called target.broadcast_to(self)
        # which means our @on decorated methods will receive events

        # We can also manually register handlers if needed
        self.agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=150)(
            self.on_message_append
        )
        self.agent.on(AgentEvents.TOOL_CALL_AFTER, priority=150)(self.on_tool_response)

    def on_message_append(self, ctx: EventContext) -> None:
        """Extract and index citations from appended messages

        Fired when a message is added to the agent.
        Extracts citation references like [1], [2] from the message content.
        """
        message = ctx.parameters.get("message")
        if not message:
            return

        # Extract citations from message content if it has citation_urls
        if hasattr(message, "citation_urls") and message.citation_urls:
            content = str(message)  # Get the rendered content
            for i, url in enumerate(message.citation_urls, 1):
                # Create citation for each URL
                citation = Citation(
                    text=f"[{i}]",
                    origin=url,
                    source=self._extract_domain(url),
                    metadata={"message_id": getattr(message, "id", None)},
                )
                self.add(content, citation)

    def on_tool_response(self, ctx: EventContext) -> None:
        """Track citations from tool responses

        Fired after a tool returns a response.
        If the response is a Paragraph with a citation, indexes it.
        """
        response = ctx.parameters.get("response")
        if isinstance(response, Paragraph) and response.citation:
            self.add(response.content, response.citation)

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL for source field"""
        if "://" in url:
            parts = url.split("://", 1)[1].split("/", 1)
            return parts[0]
        return url

    # Index Protocol Implementation

    def __getitem__(self, ref: str) -> URL:
        """Get content by citation ID"""
        if ref in self._content_map:
            return self._content_map[ref]

        # Check aliases
        primary = self._resolve_aliases(ref)
        if primary in self._content_map:
            return self._content_map[primary]

        raise KeyError(f"Citation {ref} not found")

    def __contains__(self, key: str) -> bool:
        """Check if content exists in index"""
        return any(content == key for content in self._content_map.values())

    def add(
        self,
        key: str,  # The content/text
        value: Citation | None = None,
        *,
        tags: str | list[str] | None = None,
        **metadata,
    ) -> str:  # Returns citation ID
        """Add a citation to the index"""
        # Create citation if not provided
        if value is None:
            value = Citation(text=key, metadata=metadata)

        # Update citation with additional metadata
        if metadata:
            value.metadata.update(metadata)

        # Add tags
        if tags:
            if isinstance(tags, str):
                value.tags.add(tags)
            else:
                value.tags.update(tags)

        # Store in index
        citation_id = value.id
        self._index[citation_id] = value
        self._content_map[citation_id] = key

        return citation_id

    def create_paragraph(
        self, content: str, *, origin: str = "", source: str = "", **metadata
    ) -> Paragraph:
        """Create a paragraph with citation"""
        citation = Citation(
            text=content, origin=origin, source=source, metadata=metadata
        )

        # Add to index
        self.add(content, citation)

        return Paragraph(content, citation)

    def lookup(self, key: str) -> str:
        """Look up citation ID by content"""
        for cid, content in self._content_map.items():
            if content == key:
                return cid
        raise KeyError(f"No citation found for content: {key}")

    def add_alias(self, key: str, alias: str) -> str:
        """Add an alias for a citation ID"""
        primary = self._resolve_aliases(key)
        self._aliases[alias] = primary
        return primary

    def _resolve_aliases(self, key: str) -> str:
        """Resolve aliases to primary citation ID"""
        while key in self._aliases:
            key = self._aliases[key]
        return key

    def _get_aliases(self, key: str) -> set[str]:
        """Get all aliases for a citation ID"""
        primary = self._resolve_aliases(key)
        return {alias for alias, pid in self._aliases.items() if pid == primary}

    def items(self) -> Iterator[tuple[str, str]]:
        """Iterate over (citation_id, content) pairs"""
        return iter(self._content_map.items())

    def as_dict(self) -> dict[str, str]:
        """Get index as dictionary"""
        return self._content_map.copy()

    def contents(self) -> Iterator[tuple[str, Citation | None]]:
        """Iterate over (content, citation) pairs"""
        for cid, content in self._content_map.items():
            yield content, self._index.get(cid)

    def contents_as_dict(self) -> dict[str, Citation | None]:
        """Get contents as dictionary"""
        return {
            content: self._index.get(cid) for cid, content in self._content_map.items()
        }

    # Tag Management

    def add_tag(self, ref: str, tag: str | list[str]) -> None:
        """Add tags to a citation"""
        citation = self._index.get(ref)
        if citation:
            if isinstance(tag, str):
                citation.tags.add(tag)
            else:
                citation.tags.update(tag)

    def remove_tag(self, ref: str, tag: str | list[str]) -> None:
        """Remove tags from a citation"""
        citation = self._index.get(ref)
        if citation:
            if isinstance(tag, str):
                citation.tags.discard(tag)
            else:
                for t in tag:
                    citation.tags.discard(t)

    def get_tags(self, ref: str) -> set[str]:
        """Get tags for a citation"""
        citation = self._index.get(ref)
        return citation.tags if citation else set()

    def find_by_tag(self, tag: str) -> list[str]:
        """Find citations by tag"""
        return [cid for cid, citation in self._index.items() if tag in citation.tags]

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[str]:
        """Find citations by multiple tags"""
        results = []
        for cid, citation in self._index.items():
            if match_all:
                if all(tag in citation.tags for tag in tags):
                    results.append(cid)
            else:
                if any(tag in citation.tags for tag in tags):
                    results.append(cid)
        return results

    # Metadata Management

    def get_metadata(self, ref: str) -> dict[str, Any]:
        """Get metadata for a citation"""
        citation = self._index.get(ref)
        return citation.metadata if citation else {}

    def set_metadata(self, ref: str, **metadata) -> None:
        """Set metadata for a citation"""
        citation = self._index.get(ref)
        if citation:
            citation.metadata = metadata

    def update_metadata(self, ref: str, **metadata) -> None:
        """Update metadata for a citation"""
        citation = self._index.get(ref)
        if citation:
            citation.metadata.update(metadata)

    def find_by_metadata(self, **criteria) -> list[str]:
        """Find citations by metadata criteria"""
        results = []
        for cid, citation in self._index.items():
            if all(citation.metadata.get(k) == v for k, v in criteria.items()):
                results.append(cid)
        return results

    # Combined Retrieval

    def get_entry(self, ref: str) -> tuple[str, Citation | None, dict[str, Any]]:
        """Get complete entry information"""
        content = self._content_map.get(ref, "")
        citation = self._index.get(ref)
        metadata = citation.metadata if citation else {}
        return content, citation, metadata

    def get_value(self, ref: str) -> Citation | None:
        """Get citation by ID"""
        return self._index.get(ref)

    def get_entries_by_tag(
        self, tag: str
    ) -> Iterator[tuple[str, str, Citation | None, dict[str, Any]]]:
        """Get all entries with a specific tag"""
        for cid in self.find_by_tag(tag):
            content = self._content_map.get(cid, "")
            citation = self._index.get(cid)
            metadata = citation.metadata if citation else {}
            yield cid, content, citation, metadata

    def get_citations_summary(self) -> str:
        """Get a formatted summary of all citations"""
        if not self._index:
            return "No citations available."

        lines = ["Citations:"]
        for cid, citation in self._index.items():
            source_info = f" - {citation.source}" if citation.source else ""
            origin_info = f" ({citation.origin})" if citation.origin else ""
            lines.append(f"[{cid}]{source_info}{origin_info}")

        return "\n".join(lines)
