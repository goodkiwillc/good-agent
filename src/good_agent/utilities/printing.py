import base64
import json
from typing import TYPE_CHECKING, Literal

try:
    import magic

    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:
    from good_agent.content.parts import RenderMode
    from good_agent.messages import Message


def _format_tool_calls(tool_calls, format: str) -> str:
    """Format tool calls for display.

    Args:
        tool_calls: List of tool calls
        format: Output format ('plain', 'markdown', or 'rich')

    Returns:
        Formatted string representation of tool calls
    """
    if format == "rich" or format == "markdown":
        # Create structured output for tool calls
        content_parts = []
        for i, tool_call in enumerate(tool_calls, 1):
            # Get tool name
            if hasattr(tool_call, "name"):
                name = tool_call.name
            elif hasattr(tool_call, "function"):
                name = tool_call.function.name
            else:
                name = "unknown"

            # Get arguments
            if hasattr(tool_call, "function") and hasattr(tool_call.function, "arguments"):
                args_str = tool_call.function.arguments
            else:
                args_str = "{}"

            # Parse JSON arguments for pretty display
            try:
                args_dict = json.loads(args_str)
                formatted_args = json.dumps(args_dict, indent=2)
            except (json.JSONDecodeError, TypeError):
                formatted_args = args_str

            # Format based on output type
            if format == "markdown":
                if len(tool_calls) > 1:
                    tool_section = f"### Tool {i}: `{name}`\n\n```json\n{formatted_args}\n```"
                else:
                    tool_section = f"### `{name}`\n\n```json\n{formatted_args}\n```"
            else:  # rich format
                if len(tool_calls) > 1:
                    tool_section = f"**Tool {i}: {name}**\n\n```json\n{formatted_args}\n```"
                else:
                    tool_section = f"**Tool: {name}**\n\n```json\n{formatted_args}\n```"

            content_parts.append(tool_section)

        return "\n\n".join(content_parts)
    else:
        # Plain format - simple display
        content_lines = []
        for i, tool_call in enumerate(tool_calls, 1):
            # Get tool name
            if hasattr(tool_call, "name"):
                name = tool_call.name
            elif hasattr(tool_call, "function"):
                name = tool_call.function.name
            else:
                name = "unknown"

            # Get arguments
            if hasattr(tool_call, "function") and hasattr(tool_call.function, "arguments"):
                args_str = tool_call.function.arguments
            else:
                args_str = "{}"

            if len(tool_calls) > 1:
                content_lines.append(f"Tool {i}: {name}\nArguments: {args_str}")
            else:
                content_lines.append(f"Tool: {name}\nArguments: {args_str}")

        return "\n\n".join(content_lines)


def _preprocess_xml_tags(content: str) -> str:
    """Preprocess content to escape XML-like tags with code blocks.

    Args:
        content: The content to preprocess

    Returns:
        Content with XML tags wrapped in code blocks
    """
    import re

    # Pattern to match XML-like tags (opening, closing, and self-closing)
    # This matches <tag>, </tag>, <tag attr="value">, <tag/>
    xml_pattern = r"</?[a-zA-Z][a-zA-Z0-9_-]*(?:\s+[^>]*)?/?>"

    # Check if content contains XML-like tags
    if not re.search(xml_pattern, content):
        return content

    # Split content by code blocks to avoid processing already formatted code
    code_block_pattern = r"```[^`]*```|`[^`]+`"

    # Find all code blocks first
    code_blocks = re.findall(code_block_pattern, content, re.DOTALL)

    # Replace code blocks with placeholders
    temp_content = content
    placeholders = []
    for i, block in enumerate(code_blocks):
        placeholder = f"__CODE_BLOCK_{i}__"
        placeholders.append(placeholder)
        temp_content = temp_content.replace(block, placeholder, 1)

    # Pattern to find complete XML structures (from opening to closing tag)
    # This will match patterns like <tag>...</tag> including nested content
    complete_xml_pattern = r"(<([a-zA-Z][a-zA-Z0-9_-]*)(?:\s+[^>]*)?>(?:[^<]|<(?!/?\2))*?</\2>|<[a-zA-Z][a-zA-Z0-9_-]*(?:\s+[^>]*)?/>)"

    # Find all complete XML structures
    xml_structures = []
    for match in re.finditer(complete_xml_pattern, temp_content, re.DOTALL):
        xml_structures.append((match.start(), match.end(), match.group(0)))

    # Also find standalone opening/closing tags that might form a block
    standalone_tags = []
    for match in re.finditer(xml_pattern, temp_content):
        # Check if this tag is already part of a complete structure
        is_part_of_structure = False
        for start, end, _ in xml_structures:
            if start <= match.start() < end:
                is_part_of_structure = True
                break

        if not is_part_of_structure:
            standalone_tags.append((match.start(), match.end(), match.group(0)))

    # Group standalone tags that are close together
    if standalone_tags:
        groups = []
        current_group = [standalone_tags[0]]

        for tag in standalone_tags[1:]:
            # If this tag is within 50 chars of the last one, group them
            if tag[0] - current_group[-1][1] <= 50:
                current_group.append(tag)
            else:
                if current_group:
                    groups.append(current_group)
                current_group = [tag]

        if current_group:
            groups.append(current_group)

        # Add grouped standalone tags to structures
        for group in groups:
            start = group[0][0]
            end = group[-1][1]
            # Get all content between first and last tag
            xml_content = temp_content[start:end]
            xml_structures.append((start, end, xml_content))

    # Sort by start position (descending) to process from end to start
    xml_structures.sort(key=lambda x: x[0], reverse=True)

    # Process each XML structure
    for start, end, xml_content in xml_structures:
        # Skip if already in a placeholder area
        if any(placeholder in xml_content for placeholder in placeholders):
            continue

        # Get surrounding context to determine if we should wrap it
        before_context = temp_content[max(0, start - 10) : start].strip()
        after_context = temp_content[end : min(len(temp_content), end + 10)].strip()

        # Don't wrap if it looks like it's already part of formatted content
        if before_context.endswith("```") or after_context.startswith("```"):
            continue

        # Get the complete content including any text between tags
        full_content = temp_content[start:end]

        # Wrap the entire XML content in a code block
        wrapped = f"\n```xml\n{full_content}\n```\n"

        # Replace in the temp content
        temp_content = temp_content[:start] + wrapped + temp_content[end:]

    # Restore code blocks
    for i, block in enumerate(code_blocks):
        placeholder = f"__CODE_BLOCK_{i}__"
        temp_content = temp_content.replace(placeholder, block)

    return temp_content


def _detect_markdown(content: str | None) -> bool:
    """Detect if content contains markdown formatting.

    Args:
        content: Text content to check

    Returns:
        True if markdown formatting is detected
    """
    if not content:
        return False

    # Check for common markdown patterns
    markdown_patterns = [
        "```",  # Code blocks
        "`",  # Inline code
        "**",  # Bold
        "*",  # Italic (but not just bullet points)
        "##",  # Headers
        "###",  # Sub-headers
        "[",  # Links (when paired with ])
        "![",  # Images
        "> ",  # Blockquotes
        "|",  # Tables (when multiple found)
        "___",  # Horizontal rules
        "---",  # Horizontal rules
        "***",  # Horizontal rules
    ]

    for pattern in markdown_patterns:
        if pattern in content:
            # Special handling for asterisks to avoid false positives
            if pattern == "*" and "**" not in content:
                # Check if it's likely italic markdown (not just a bullet)
                if content.count("*") >= 2 and not content.startswith("* "):
                    return True
            else:
                return True

    # Check for numbered lists (1. 2. etc)
    import re

    return bool(re.search(r"^\d+\.\s", content, re.MULTILINE))


def print_message(
    message: Message,
    console: Console | None = None,
    format: Literal["plain", "markdown", "rich"] = "rich",
    title: str | None = None,
    include_reasoning: bool = False,
    include_citations: bool = False,
    include_tool_calls: bool = True,
    truncate: bool = False,
    max_length: int = 500,
    render_mode: RenderMode | str | None = None,
    force_markdown: bool | None = None,
) -> None:
    """Print a message with Rich formatting support.

    Args:
        message: The message to print
        console: Rich console instance (creates new if None)
        format: Output format - 'plain', 'markdown', or 'rich'
        title: Custom title (auto-generated if None)
        include_reasoning: Show reasoning field for assistant messages
        include_citations: Show citations for assistant messages
        include_tool_calls: Show tool calls for assistant messages
        truncate: Truncate long content
        max_length: Maximum content length when truncating
        render_mode: Optional render mode for message content (DISPLAY, LLM, RAW, etc.)
                    Can be RenderMode enum or string literal
        force_markdown: Force markdown rendering regardless of content detection
    """
    console = console or Console()

    # Import here to avoid circular imports
    from good_agent.content import RenderMode
    from good_agent.messages import AssistantMessage, ToolMessage

    content = None

    # Convert string render mode to enum if needed
    if render_mode is not None and isinstance(render_mode, str):
        try:
            render_mode = RenderMode(render_mode.lower())
        except ValueError:
            # If invalid string, default to None
            console.print(
                f"[yellow]Warning: Invalid render mode '{render_mode}', using default[/yellow]"
            )
            render_mode = None

    # Generate title if not provided
    if title is None:
        title = f"@{message.role}"

        # Add tool name for tool messages
        if isinstance(message, ToolMessage) and hasattr(message, "tool_name"):
            title += f" ({message.tool_name})"

        # Add agent name if available
        agent = message._agent_ref() if message._agent_ref else None
        if agent and hasattr(agent, "name") and agent.name:
            title += f" [{agent.name}]"

    # Get message content based on render mode
    if render_mode is not None:
        # Use specified render mode
        if hasattr(message, "render"):
            content = message.render(render_mode)
        else:
            content = str(message)

        # Handle tool calls for AssistantMessage even with render_mode
        if isinstance(message, AssistantMessage) and message.tool_calls and include_tool_calls:
            tool_content = _format_tool_calls(message.tool_calls, format)

            # Combine content and tool calls
            if content:
                # Both content and tool calls present
                if format == "markdown":
                    content = f"{content}\n\n---\n\n## 🔧 Tool Calls\n\n{tool_content}\n"
                elif format == "rich":
                    content = f"{content}\n\n**───── Tool Calls ─────**\n\n{tool_content}"
                else:  # plain
                    content = f"{content}\n\n--- Tool Calls ---\n{tool_content}"
            else:
                # Only tool calls, no content
                content = tool_content
    elif isinstance(message, AssistantMessage):
        # Use the display rendering for main content
        content = message.__display__()

        # Add tool calls if present and requested
        if message.tool_calls and include_tool_calls:
            tool_content = _format_tool_calls(message.tool_calls, format)

            # Combine content and tool calls
            if content:
                # Both content and tool calls present
                if format == "markdown":
                    content = f"{content}\n\n---\n\n## 🔧 Tool Calls\n\n{tool_content}"
                elif format == "rich":
                    content = f"{content}\n\n**───── Tool Calls ─────**\n\n{tool_content}"
                else:  # plain
                    content = f"{content}\n\n--- Tool Calls ---\n{tool_content}"
            else:
                # Only tool calls, no content
                content = tool_content
    elif not render_mode:  # Only apply default logic if render_mode wasn't already handled
        # Use display rendering for all other message types
        content = message.__display__()

    # Add reasoning if requested (for assistant messages)
    if include_reasoning and isinstance(message, AssistantMessage) and message.reasoning:
        if format == "markdown":
            content = f"💭 **Reasoning:**\n```\n{message.reasoning}\n```\n\n---\n\n{content}"
        else:
            content = f"<reasoning>\n{message.reasoning}\n</reasoning>\n\n{content}"

    # Add citations if requested (for assistant messages)
    if include_citations and isinstance(message, AssistantMessage):
        citations = getattr(message, "citations", None) or getattr(message, "citation_urls", None)
        if citations and content:
            citation_text = "\n\n---\n📚 **Citations:**\n"
            for idx, citation in enumerate(citations, 1):
                citation_text += f"[{idx}] {citation}\n"
            content += citation_text

    if not content:
        content = ""

    # Truncate if requested
    if truncate and len(content) > max_length:
        content = content[:max_length] + "..."

    # Preprocess XML tags before markdown rendering
    if format == "rich" or format == "markdown":
        content = _preprocess_xml_tags(content)

    # Strip leading/trailing whitespace
    content = content.strip()

    # Only show "(empty message)" if we truly have no content
    # Tool-only messages should show their tool calls, not "(empty message)"
    if not content:
        # Check if this is a tool-only assistant message that we already handled
        if not (
            isinstance(message, AssistantMessage) and message.tool_calls and include_tool_calls
        ):
            content = "(empty message)"

    # Format and print based on format type
    if format == "plain":
        # Plain text output
        print(f"--- {title} ---")
        print(content)
        print()

    elif format == "markdown":
        # Markdown with Rich rendering
        console.print(
            Panel(
                Markdown(content),
                title=title,
                border_style="blue"
                if message.role == "assistant"
                else "green"
                if message.role == "user"
                else "yellow",
                padding=(1, 2),
            )
        )

    elif format == "rich":
        # Rich formatted output with color coding
        # Determine style based on role
        role_styles = {
            "user": ("bold green", "green"),
            "assistant": ("bold blue", "blue"),
            "system": ("bold yellow", "yellow"),
            "tool": ("bold magenta", "magenta"),
        }

        title_style, border_style = role_styles.get(message.role, ("bold", "white"))

        # Create a styled text object for better control
        renderable: Markdown | Text

        # Determine if we should use markdown rendering
        use_markdown = (
            force_markdown is True
            or format == "markdown"
            or (force_markdown is not False and _detect_markdown(content))
        )

        if use_markdown:
            # Use Markdown rendering for content with markdown formatting
            renderable = Markdown(content)
        else:
            # Plain text with style
            renderable = Text(content)

        console.print(
            Panel(
                renderable,
                title=f"[{title_style}]{title}[/{title_style}]",
                border_style=border_style,
                padding=(1, 2),
            )
        )


def _detect_mime_type_from_bytes(image_bytes: bytes) -> str:
    """Detect MIME type from image byte headers.

    Args:
        image_bytes: Image file bytes

    Returns:
        Detected MIME type string
    """
    # Check common image format signatures
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    elif image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    elif image_bytes[8:12] == b"WEBP":
        return "image/webp"
    elif image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
        return "image/gif"
    else:
        # Default to JPEG for unknown types
        return "image/jpeg"


def url_to_base64(image_bytes):
    """
    Fetches an image from a URL and returns it as a base64 encoded data URL.
    Works with PNG, JPEG/JPG, WEBP, and non-animated GIF formats.

    Args:
        image_url (str): URL of the image to fetch

    Returns:
        str: Base64 encoded data URL of the image
    """

    # Determine MIME type
    if HAS_MAGIC:
        # Use python-magic if available
        mime_type = magic.Magic(mime=True).from_buffer(image_bytes)

        # Check if the detected type is one of our supported types
        if mime_type not in ["image/jpeg", "image/png", "image/webp", "image/gif"]:
            # Default to JPEG for unsupported types
            mime_type = "image/jpeg"
    else:
        # Fallback to byte header detection
        mime_type = _detect_mime_type_from_bytes(image_bytes)

    # Encode the image data to base64
    base64_encoded = base64.b64encode(image_bytes).decode("utf-8")

    # Return the complete data URL
    return f"data:{mime_type};base64,{base64_encoded}"
