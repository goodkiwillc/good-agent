import re
from typing import Any

from jinja2 import Environment, TemplateSyntaxError, nodes
from jinja2.ext import Extension

__all__ = [
    "SectionExtension",
    "MultiLineInclude",
]


class SectionExtension(Extension):
    """Extension that implements an indent-aware section tag with customizable type and attributes."""

    tags = {"section"}

    def __init__(self, environment: Environment):
        super().__init__(environment)

        # Store all state as instance variables
        self.section_indents: dict[int, dict[str, Any]] = {}
        self.template_source: list[str] | None = None
        self.section_counter: int = 0

        # Register the filter
        environment.filters["section"] = self.section_filter

    def preprocess(self, source: str, name: str | None = None, filename: str | None = None) -> str:
        """Preprocess the template source to extract indentation information"""
        _ = name, filename  # Mark as intentionally unused
        # Store source for later indentation analysis
        self.template_source = source.splitlines()
        return source

    def parse(self, parser):
        # Get current token information
        token = parser.stream.current
        lineno = token.lineno

        # Generate a unique ID for this section
        section_id = self.section_counter
        self.section_counter += 1

        # Parse the section tag
        parser.stream.expect("name:section")

        # Parse optional name argument (string or identifier)
        # This allows: {% section "instructions" %} or {% section goals %}
        # The name becomes the HTML tag name
        tag_name = None
        tag_name_value = None  # Store the actual value for validation

        # Try to catch common errors early
        try:
            if parser.stream.current.type in (
                "string",
                "name",
            ) and not parser.stream.look().test("assign"):
                # It's a positional name argument, not a keyword argument
                tag_name_value = parser.stream.current.value
                current_type = parser.stream.current.type

                # Validate the name if it's provided as an identifier (not a string)
                if current_type == "name" and not self._is_valid_identifier(tag_name_value):
                    # Check what makes it invalid
                    invalid_chars = self._get_invalid_identifier_chars(tag_name_value)
                    raise TemplateSyntaxError(
                        f"Section name '{tag_name_value}' is not a valid identifier. "
                        f"It contains invalid characters: {invalid_chars}. "
                        f"Please quote the name: {{% section '{tag_name_value}' %}}",
                        lineno,
                        parser.name,
                        parser.filename,
                    )

                tag_name = nodes.Const(tag_name_value)
                parser.stream.skip()
        except TemplateSyntaxError as e:
            # Check if this is the generic parsing error we want to improve
            if "expected token" in str(e) and parser.stream.current.type == "name":
                # Try to build a better error message
                # Look ahead to see what's causing the issue
                tokens = []
                temp_stream = parser.stream
                pos = temp_stream.current_idx

                # Collect tokens until we hit a block end or error
                while temp_stream.current.type not in ("block_end", "eof"):
                    tokens.append(temp_stream.current.value)
                    if not temp_stream.eos:
                        temp_stream.skip()
                    else:
                        break

                # Reset stream position
                temp_stream.current_idx = pos

                # Build the problematic name
                problematic_name = " ".join(str(t) for t in tokens[:3])  # Get first few tokens
                if "-" in problematic_name or "@" in problematic_name or "." in problematic_name:
                    raise TemplateSyntaxError(
                        f"Section name contains invalid characters. "
                        f"Names with special characters must be quoted: "
                        f"{{% section '{problematic_name.split()[0]}' %}}",
                        lineno,
                        parser.name,
                        parser.filename,
                    ) from None
            # Re-raise the original error if we can't improve it
            raise

        # Default tag name is 'section' if not provided
        if tag_name is None:
            tag_name = nodes.Const("section")

        # Store all attributes in kwargs (type is just another attribute now)
        kwargs = []

        # Parse attributes until we reach the end of the block
        while parser.stream.current.type != "block_end":
            if parser.stream.current.type == "name":
                key = parser.stream.current.value
                parser.stream.skip()
                parser.stream.expect("assign")
                value = parser.parse_expression()
                kwargs.append(nodes.Keyword(key, value))
            else:
                parser.stream.skip()

        # If we have access to the template source, extract indentation
        tag_indent = 0
        if self.template_source and lineno <= len(self.template_source):
            # Get the line where the section tag appears (adjust for 0-based indexing)
            line = self.template_source[lineno - 1]
            # Find the indentation of the section tag
            match = re.match(r"^(\s*){%\s*section", line)
            if match:
                tag_indent = len(match.group(1))

        # Store indentation information for this section
        self.section_indents[section_id] = {"tag_indent": tag_indent}

        # Parse the body content until {% end section %}
        body = parser.parse_statements(("name:endsection", "name:end"), drop_needle=True)

        # Support both `{% end section %}` and `{% endsection %}`
        if parser.stream.current.test("name:section"):
            parser.stream.skip()

        # Build a dictionary from all keyword arguments
        # Convert Keyword nodes to Pair nodes for the Dict
        pairs = [nodes.Pair(nodes.Const(kw.key), kw.value) for kw in kwargs]
        kwargs_dict = nodes.Dict(pairs)

        # Return the call block
        return nodes.CallBlock(
            self.call_method("_render_section", [tag_name, kwargs_dict, nodes.Const(section_id)]),
            [],
            [],
            body,
        ).set_lineno(lineno)

    def _render_section(
        self, tag_name: str, attributes: dict[str, Any], section_id: int, caller: Any
    ) -> str:
        # Get the indentation level for this section
        section_info = self.section_indents.get(section_id, {"tag_indent": 0})
        tag_indent = section_info["tag_indent"]

        # Convert attributes to HTML attribute string
        attrs_str = " ".join(f'{key}="{value}"' for key, value in attributes.items())
        if attrs_str:
            attrs_str = " " + attrs_str

        content = caller()

        if content.startswith("\r\n"):
            content = content[2:]
        elif content.startswith("\n"):
            content = content[1:]

        if content.endswith("\n"):
            content = content[:-1]

        # Process content lines
        lines = content.split("\n")

        processed_lines = []

        # If no content, just return wrapped empty content
        if not content.strip():
            opening_tag = " " * tag_indent + f"<{tag_name}{attrs_str}>"
            closing_tag = " " * tag_indent + f"</{tag_name}>"
            return opening_tag + "\n" + closing_tag

        # Process each line of content
        for line in lines:
            if not line.strip():
                # Keep empty lines as-is
                processed_lines.append(line)
                continue
            # We want to preserve the exact indentation relative to the tag
            # So we prefix with tag's indentation
            new_line = " " * tag_indent + line
            processed_lines.append(new_line)

        # Create tags with the exact indentation of the tag in the template
        opening_tag = " " * tag_indent + f"<{tag_name}{attrs_str}>"
        closing_tag = " " * tag_indent + f"</{tag_name}>"

        # Combine all parts
        result = [opening_tag]
        if processed_lines:
            result.extend(processed_lines)
        result.append(closing_tag)
        result.append("")

        return "\n".join(result)

    def section_filter(self, value: Any, tag_name: str = "section", **kwargs: Any) -> str:
        """Filter that wraps content in a section tag."""
        # Get current indentation context for the template
        # This is tricky with filters since we don't have lineno information
        # So we'll use a default indentation of 4 spaces for content
        content_indent = 4

        # Convert attributes to HTML attribute string
        attrs_str = " ".join(f'{key}="{value}"' for key, value in kwargs.items())
        if attrs_str:
            attrs_str = " " + attrs_str

        # Process content lines
        content = str(value)
        lines = content.split("\n")
        processed_lines = []

        # Process each line of content
        for line in lines:
            if not line.strip():
                # Keep empty lines as-is
                processed_lines.append(line)
                continue
            # Indent the content
            processed_lines.append(" " * content_indent + line)

        # Create opening and closing tags
        opening_tag = f"<{tag_name}{attrs_str}>"
        closing_tag = f"</{tag_name}>"

        # Combine all parts
        result = [opening_tag]
        if processed_lines:
            result.extend(processed_lines)
        result.append(closing_tag)

        return "\n".join(result)

    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a name is a valid Python identifier."""
        import keyword

        if not name:
            return False
        if keyword.iskeyword(name):
            return False
        # Check if it's a valid identifier
        import re

        return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name))

    def _get_invalid_identifier_chars(self, name: str) -> str:
        """Get the invalid characters in an identifier."""
        import re

        invalid_chars = set()
        for char in name:
            if not re.match(r"[a-zA-Z0-9_]", char):
                invalid_chars.add(char)
        return ", ".join(repr(c) for c in sorted(invalid_chars))


def _improved_include_statement(block_start, block_end):
    return re.compile(
        rf"""
        (^ .*)  # first group: greedy tokens at the beginning of the line (can be empty)
        (?= # second group: positive lookahead of pattern
            (
                {re.escape(block_start)}
                (?P<block_start_modifier> [\+|-]?)
                (?P<statement>
                    \s* include \b   # include keyword
                    \s*? .*?  # fluff
                    indent \s content  # new 'with indentation' option
                    \s*? .*? # fluff
                )
                (?P<block_end_modifier> [\+|-]?)
                {re.escape(block_end)}
            )
        )
        .* $ # rest of the line, required to also include the lookahead in the match
        """,
        flags=re.MULTILINE | re.VERBOSE,
    )


class MultiLineInclude(Extension):
    def preprocess(self, source: str, name: str | None = None, filename: str | None = None) -> str:
        _ = name, filename  # Mark as intentionally unused
        env: Environment = self.environment

        block_start: str = env.block_start_string
        block_end: str = env.block_end_string
        pattern = _improved_include_statement(block_start=block_start, block_end=block_end)
        re_newline = re.compile("\n")

        def add_indentation_filter(match):
            line_content_before_statement = match.group(1)
            statement = match.group("statement").replace(
                "indent content", ""
            )  # strip 'with indentation' directive

            # guard against invalid use of improved include statement
            if line_content_before_statement is not None:
                # line before include statement must be indentation only (empty string is valid)
                if line_content_before_statement and not line_content_before_statement.isspace():
                    start_position = match.start(0)
                    lineno = len(re_newline.findall(source, 0, start_position)) + 1
                    raise TemplateSyntaxError(
                        "line contains non-whitespace characters before include statement",
                        lineno,
                        name,
                        filename,
                    )

            indentation = line_content_before_statement or ""
            block_start_modifier = match.group("block_start_modifier") or ""
            block_end_modifier = match.group("block_end_modifier") or ""
            indent_width = len(indentation)

            start_filter = f"{block_start + block_start_modifier} filter indent({indent_width}, True) -{block_end}"
            include_statement = f"{block_start} {statement.strip()} {block_end}"
            end_filter = f"{block_start}- endfilter {block_end_modifier + block_end}"
            return "\n".join([start_filter, include_statement, end_filter])

        return pattern.sub(add_indentation_filter, source)
