from typing import Any

from good_agent.resources.base import StatefulResource


class EditableResource(StatefulResource[str]):
    """Resource for editing text/document content.

    Provides basic editing operations without complex state management.
    """

    def __init__(self, content: str, name: str = "document"):
        super().__init__(name)
        self._initial_content = content
        self._modified = False

    async def initialize(self) -> None:
        """Set initial content."""
        self.state = self._initial_content

    async def persist(self) -> None:
        """Mark as saved (subclasses can override for actual persistence)."""
        self._modified = False

    def get_tools(self) -> dict[str, Any]:  # type: ignore[override]
        """Return editing tools as a dict (backwards compatibility)."""
        from good_agent import tool

        @tool(name="read", description="Read the current content")  # type: ignore[arg-type,misc]
        async def read(start_line: int | None = None, num_lines: int | None = None) -> str:
            """Read document content."""
            lines = self.state.split("\n")

            if start_line is not None:
                start_idx = max(0, start_line - 1)
                if num_lines is not None:
                    end_idx = min(len(lines), start_idx + num_lines)
                    lines = lines[start_idx:end_idx]
                else:
                    lines = lines[start_idx:]

            # Return with line numbers
            # Fix: enumerate's start affects the iteration count, not the line number display
            actual_start = start_line or 1
            return "\n".join(f"{actual_start + i:4}: {line}" for i, line in enumerate(lines))

        @tool(name="replace", description="Replace text in document")  # type: ignore[arg-type,misc]
        async def replace(old_text: str, new_text: str, all_occurrences: bool = False) -> str:
            """Replace text in document."""
            content = self.state

            if all_occurrences:
                new_content = content.replace(old_text, new_text)
                count = content.count(old_text)
            else:
                new_content = content.replace(old_text, new_text, 1)
                count = 1 if old_text in content else 0

            if count > 0:
                self.state = new_content
                self._modified = True
                return f"Replaced {count} occurrence(s)"
            return "No matches found"

        @tool(name="edit_line", description="Edit a specific line")  # type: ignore[arg-type,misc]
        async def edit_line(line_number: int, new_content: str) -> str:
            """Edit a specific line."""
            lines = self.state.split("\n")

            if not (1 <= line_number <= len(lines)):
                return f"Invalid line number: {line_number}"

            lines[line_number - 1] = new_content
            self.state = "\n".join(lines)
            self._modified = True

            return f"Updated line {line_number}"

        @tool(name="insert", description="Insert text after a line")  # type: ignore[arg-type,misc]
        async def insert(after_line: int, content: str) -> str:
            """Insert content after specified line."""
            lines = self.state.split("\n")

            if not (0 <= after_line <= len(lines)):
                return f"Invalid line number: {after_line}"

            new_lines = content.split("\n")
            # Insert all new lines after the specified line
            # after_line is 1-based, so after_line=1 means after the first line
            # which is index 1 in 0-based indexing
            for i, line in enumerate(new_lines):
                lines.insert(after_line + i, line)

            self.state = "\n".join(lines)
            self._modified = True

            return f"Inserted {len(new_lines)} line(s)"

        @tool(name="save", description="Save changes")  # type: ignore[arg-type,misc]
        async def save() -> str:
            """Save the document and exit editing mode."""
            await self.persist()
            # Signal to exit by disabling further tool calls
            # This is handled by the resource context manager
            return f"Saved {self.name}"

        return {
            "read": read,
            "replace": replace,
            "edit_line": edit_line,
            "insert": insert,
            "save": save,
        }
