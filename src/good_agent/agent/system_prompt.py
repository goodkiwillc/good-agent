"""System prompt management for Agent modes.

Provides dynamic system prompt composition with mode-scoped changes
and auto-restore on mode exit.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from good_agent.agent.core import Agent


@dataclass
class PromptSegment:
    """A segment of content to add to the system prompt."""

    content: str
    persist: bool = False


@dataclass
class SystemPromptSnapshot:
    """Snapshot of system prompt state for mode restore."""

    prepends: list[PromptSegment] = field(default_factory=list)
    appends: list[PromptSegment] = field(default_factory=list)
    sections: dict[str, PromptSegment] = field(default_factory=dict)


class SectionsView(MutableMapping[str, str]):
    """Dict-like view for managing system prompt sections."""

    def __init__(self, manager: SystemPromptManager):
        self._manager = manager

    def __getitem__(self, key: str) -> str:
        segment = self._manager._sections.get(key)
        if segment is None:
            raise KeyError(key)
        return segment.content

    def __setitem__(self, key: str, value: str) -> None:
        self._manager.set_section(key, value)

    def __delitem__(self, key: str) -> None:
        if key not in self._manager._sections:
            raise KeyError(key)
        del self._manager._sections[key]

    def __iter__(self):
        return iter(self._manager._sections)

    def __len__(self) -> int:
        return len(self._manager._sections)

    def __repr__(self) -> str:
        return f"SectionsView({dict(self)})"


class SystemPromptManager:
    """Manages dynamic system prompt composition with mode-scoped changes.

    This manager allows mode handlers to modify the system prompt with
    automatic restore on mode exit. Changes can be marked as persistent
    to survive mode exits.

    Example:
        @agent.modes('research')
        async def research_mode(agent: Agent):
            # These changes are restored when mode exits
            agent.prompt.append("Focus on citations.")
            agent.prompt.sections['mode'] = "RESEARCH MODE"

            # This change persists after mode exit
            agent.prompt.append("Always be thorough.", persist=True)

            yield agent
    """

    def __init__(self, agent: Agent, *, modes_awareness: bool = True):
        """Initialize system prompt manager.

        Args:
            agent: The agent instance this manager belongs to
            modes_awareness: If True (default), automatically inject mode awareness
                into the system prompt when invokable modes are registered
        """
        self._agent = agent
        self._prepends: list[PromptSegment] = []
        self._appends: list[PromptSegment] = []
        self._sections: dict[str, PromptSegment] = {}
        self._snapshot_stack: list[SystemPromptSnapshot] = []
        self._sections_view = SectionsView(self)
        self._modes_awareness = modes_awareness

    @property
    def sections(self) -> SectionsView:
        """Get mutable dict-like view for named sections.

        Sections are rendered in alphabetical order between prepends and appends.

        Example:
            agent.prompt.sections['mode'] = "You are in research mode."
            agent.prompt.sections['constraints'] = "Be concise."
        """
        return self._sections_view

    def append(self, content: str, *, persist: bool = False) -> None:
        """Append content to end of system prompt.

        Args:
            content: Text to append
            persist: If True, change survives mode exit (default False)
        """
        self._appends.append(PromptSegment(content=content, persist=persist))

    def prepend(self, content: str, *, persist: bool = False) -> None:
        """Prepend content to start of system prompt.

        Args:
            content: Text to prepend
            persist: If True, change survives mode exit (default False)
        """
        self._prepends.append(PromptSegment(content=content, persist=persist))

    def set_section(self, name: str, content: str, *, persist: bool = False) -> None:
        """Set a named section in the system prompt.

        Sections are rendered between prepends and appends in alphabetical order.

        Args:
            name: Section name (e.g., 'mode', 'context', 'constraints')
            content: Section content
            persist: If True, change survives mode exit (default False)
        """
        self._sections[name] = PromptSegment(content=content, persist=persist)

    def remove_section(self, name: str) -> bool:
        """Remove a named section.

        Args:
            name: Section name to remove

        Returns:
            True if section existed and was removed
        """
        if name in self._sections:
            del self._sections[name]
            return True
        return False

    def clear(self, *, include_persistent: bool = False) -> None:
        """Clear all dynamic content.

        Args:
            include_persistent: If True, also clear persistent changes
        """
        if include_persistent:
            self._prepends.clear()
            self._appends.clear()
            self._sections.clear()
        else:
            self._prepends = [s for s in self._prepends if s.persist]
            self._appends = [s for s in self._appends if s.persist]
            self._sections = {k: v for k, v in self._sections.items() if v.persist}

    def render(self, base_prompt: str | None = None) -> str:
        """Render the complete system prompt.

        Combines: prepends + base + sections + modes_awareness + appends

        Args:
            base_prompt: Override base prompt (defaults to agent's system message)

        Returns:
            Fully composed system prompt string
        """
        parts: list[str] = []

        # Prepends (in order added)
        for segment in self._prepends:
            parts.append(segment.content)

        # Base prompt
        if base_prompt is not None:
            parts.append(base_prompt)
        elif self._agent._messages:
            from good_agent.messages import SystemMessage

            first_msg = self._agent._messages[0]
            if isinstance(first_msg, SystemMessage):
                parts.append(first_msg.content)

        # Sections (alphabetical order)
        for name in sorted(self._sections.keys()):
            segment = self._sections[name]
            parts.append(segment.content)

        # Mode awareness section (auto-injected when invokable modes exist)
        if self._modes_awareness:
            modes_section = self._render_modes_section()
            if modes_section:
                parts.append(modes_section)

        # Appends (in order added)
        for segment in self._appends:
            parts.append(segment.content)

        return "\n\n".join(filter(None, parts))

    def _render_modes_section(self) -> str | None:
        """Render the modes awareness section for the system prompt.

        Only renders if there are invokable modes registered.

        Returns:
            Modes section string, or None if no invokable modes
        """
        mode_manager = self._agent._mode_manager
        invokable_modes = [
            (name, mode_manager.get_info(name))
            for name in mode_manager.list_modes()
            if mode_manager.get_info(name).get("invokable", False)
        ]

        if not invokable_modes:
            return None

        # Build mode list
        mode_lines = []
        for name, info in invokable_modes:
            description = info.get("description", "").split("\n")[0].strip()
            tool_name = info.get("tool_name", f"enter_{name}_mode")
            is_active = mode_manager.in_mode(name)
            status = " (ACTIVE)" if is_active else ""
            mode_lines.append(f"- {name}{status}: {description} [tool: {tool_name}]")

        current_mode = mode_manager.current_mode or "none"
        mode_stack = mode_manager.mode_stack or []
        stack_str = " > ".join(mode_stack) if mode_stack else "none"

        return f"""## Operational Modes

You have access to operational modes that change your capabilities and focus.
Modes are persistent states - once entered, you remain in a mode until explicitly exiting.

Current mode: {current_mode}
Mode stack: {stack_str}

Available modes:
{chr(10).join(mode_lines)}

To switch modes, use the appropriate mode entry tool."""

    def take_snapshot(self) -> None:
        """Take a snapshot of current state for later restore.

        Called automatically when entering a mode.
        """
        snapshot = SystemPromptSnapshot(
            prepends=self._prepends.copy(),
            appends=self._appends.copy(),
            sections=self._sections.copy(),
        )
        self._snapshot_stack.append(snapshot)

    def restore_snapshot(self) -> None:
        """Restore to most recent snapshot, keeping persistent changes.

        Called automatically when exiting a mode.
        """
        if not self._snapshot_stack:
            return

        snapshot = self._snapshot_stack.pop()

        # Get persistent items added since snapshot
        persistent_prepends = [s for s in self._prepends[len(snapshot.prepends) :] if s.persist]
        persistent_appends = [s for s in self._appends[len(snapshot.appends) :] if s.persist]
        persistent_sections = {
            k: v for k, v in self._sections.items() if k not in snapshot.sections and v.persist
        }

        # Restore to snapshot state
        self._prepends = snapshot.prepends + persistent_prepends
        self._appends = snapshot.appends + persistent_appends
        self._sections = {**snapshot.sections, **persistent_sections}

    @property
    def has_modifications(self) -> bool:
        """Check if there are any dynamic modifications."""
        return bool(self._prepends or self._appends or self._sections)

    def __repr__(self) -> str:
        return (
            f"SystemPromptManager("
            f"prepends={len(self._prepends)}, "
            f"appends={len(self._appends)}, "
            f"sections={list(self._sections.keys())})"
        )
