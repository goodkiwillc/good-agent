"""Console output utilities for rich CLI and telemetry outputs.

Provides a unified interface for agent output that can target different backends:
- CLI: Rich console output with panels, spinners, and colors
- Telemetry: Structured logging for REST API and monitoring services

Usage:
    async with Agent("...") as agent:
        agent.console.status("Starting task...")
        agent.console.info("Processing data")
        agent.console.success("Task complete!")

        # Structured outputs
        agent.console.tool_call("search", {"query": "test"})
        agent.console.tool_result("search", "Found 5 results")
        agent.console.mode_enter("research")
        agent.console.mode_exit("research")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal

from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from good_agent.agent.core import Agent


class OutputFormat(StrEnum):
    """Output format modes for the console."""

    RICH = "rich"  # Full Rich formatting with colors, panels, etc.
    PLAIN = "plain"  # Minimal text output, no styling (good for agents/scripts)
    JSON = "json"  # Machine-readable JSON output


class OutputLevel(StrEnum):
    """Output severity/importance levels."""

    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OutputType(StrEnum):
    """Types of console output for categorization."""

    STATUS = "status"
    MESSAGE = "message"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MODE_CHANGE = "mode_change"
    STEP = "step"
    SECTION = "section"
    DATA = "data"
    PROGRESS = "progress"


@dataclass
class OutputRecord:
    """Structured record of a console output for telemetry."""

    timestamp: datetime
    output_type: OutputType
    level: OutputLevel
    title: str | None
    content: Any
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "type": self.output_type,
            "level": self.level,
            "title": self.title,
            "content": str(self.content) if self.content else None,
            "metadata": self.metadata,
        }


class ConsoleBackend(ABC):
    """Abstract base class for console output backends."""

    @abstractmethod
    def write(self, record: OutputRecord) -> None:
        """Write an output record."""
        ...

    @abstractmethod
    def status_context(self, message: str) -> Any:
        """Context manager for status/spinner display."""
        ...

    @abstractmethod
    def progress_context(self, total: int, description: str) -> Any:
        """Context manager for progress bar display."""
        ...


class RichConsoleBackend(ConsoleBackend):
    """Rich library backend for beautiful CLI output."""

    # Style configuration
    LEVEL_STYLES = {
        OutputLevel.DEBUG: ("dim", "dim"),
        OutputLevel.INFO: ("blue", "blue"),
        OutputLevel.SUCCESS: ("bold green", "green"),
        OutputLevel.WARNING: ("bold yellow", "yellow"),
        OutputLevel.ERROR: ("bold red", "red"),
        OutputLevel.CRITICAL: ("bold white on red", "red"),
    }

    LEVEL_ICONS = {
        OutputLevel.DEBUG: "🔍",
        OutputLevel.INFO: "ℹ️ ",
        OutputLevel.SUCCESS: "✓",
        OutputLevel.WARNING: "⚠️ ",
        OutputLevel.ERROR: "✗",
        OutputLevel.CRITICAL: "🚨",
    }

    def __init__(
        self,
        console: Console | None = None,
        show_timestamps: bool = False,
        show_icons: bool = True,
        quiet: bool = False,
    ):
        """Initialize the Rich console backend.

        Args:
            console: Rich Console instance (creates new if None)
            show_timestamps: Include timestamps in output
            show_icons: Show emoji icons for output levels
            quiet: Suppress all output (for testing)
        """
        self.console = console or Console()
        self.show_timestamps = show_timestamps
        self.show_icons = show_icons
        self.quiet = quiet

    def write(self, record: OutputRecord) -> None:
        """Write an output record to the console."""
        if self.quiet:
            return

        method = getattr(self, f"_write_{record.output_type}", self._write_default)
        method(record)

    def _write_default(self, record: OutputRecord) -> None:
        """Default output handler."""
        text_style, _ = self.LEVEL_STYLES.get(record.level, (None, None))
        icon = self.LEVEL_ICONS.get(record.level, "") if self.show_icons else ""

        prefix = ""
        if self.show_timestamps:
            prefix = f"[dim]{record.timestamp.strftime('%H:%M:%S')}[/dim] "

        content = str(record.content) if record.content else ""
        title = record.title or ""

        if title and content:
            self.console.print(f"{prefix}{icon} [{text_style}]{title}:[/{text_style}] {content}")
        elif title:
            self.console.print(f"{prefix}{icon} [{text_style}]{title}[/{text_style}]")
        elif content:
            self.console.print(f"{prefix}{icon} [{text_style}]{content}[/{text_style}]")

    def _write_status(self, record: OutputRecord) -> None:
        """Write a status message."""
        self._write_default(record)

    def _write_message(self, record: OutputRecord) -> None:
        """Write a general message."""
        self._write_default(record)

    def _write_tool_call(self, record: OutputRecord) -> None:
        """Write a tool call notification."""
        tool_name = record.metadata.get("tool_name", "unknown")
        args = record.metadata.get("arguments", {})

        # Format arguments nicely
        if args:
            import json

            try:
                args_str = json.dumps(args, indent=2)
            except (TypeError, ValueError):
                args_str = str(args)
        else:
            args_str = "(no arguments)"

        panel = Panel(
            Text(args_str, style="cyan"),
            title=f"[bold cyan]🔧 Tool Call: {tool_name}[/bold cyan]",
            border_style="cyan",
            expand=False,
            padding=(0, 1),
        )
        self.console.print(panel)

    def _write_tool_result(self, record: OutputRecord) -> None:
        """Write a tool result."""
        tool_name = record.metadata.get("tool_name", "unknown")
        success = record.metadata.get("success", True)

        content = str(record.content) if record.content else "(no output)"
        # Truncate long outputs
        if len(content) > 500:
            content = content[:500] + "... [truncated]"

        border_style = "green" if success else "red"
        icon = "✓" if success else "✗"

        panel = Panel(
            Text(content, style="dim"),
            title=f"[bold {border_style}]{icon} Tool Result: {tool_name}[/bold {border_style}]",
            border_style=border_style,
            expand=False,
            padding=(0, 1),
        )
        self.console.print(panel)

    def _write_mode_change(self, record: OutputRecord) -> None:
        """Write a mode change notification."""
        action = record.metadata.get("action", "change")
        mode_name = record.metadata.get("mode_name", "unknown")
        stack = record.metadata.get("stack", [])

        if action == "enter":
            icon = "→"
            style = "bold magenta"
            title = f"Mode: {mode_name}"
        elif action == "exit":
            icon = "←"
            style = "magenta"
            title = f"Exit: {mode_name}"
        else:
            icon = "⟳"
            style = "magenta"
            title = f"Mode: {mode_name}"

        stack_str = f" [{' > '.join(stack)}]" if stack else ""
        self.console.print(f"[{style}]{icon} {title}{stack_str}[/{style}]")

    def _write_step(self, record: OutputRecord) -> None:
        """Write a step in a sequence."""
        step_num = record.metadata.get("step", None)
        total = record.metadata.get("total", None)

        if step_num and total:
            prefix = f"[bold][{step_num}/{total}][/bold] "
        elif step_num:
            prefix = f"[bold][{step_num}][/bold] "
        else:
            prefix = "• "

        content = str(record.content) if record.content else record.title or ""
        self.console.print(f"{prefix}{content}")

    def _write_section(self, record: OutputRecord) -> None:
        """Write a section header."""
        title = record.title or str(record.content) or "Section"
        style = record.metadata.get("style", "bold blue")
        self.console.print()
        self.console.print(Rule(title, style=style))
        self.console.print()

    def _write_data(self, record: OutputRecord) -> None:
        """Write structured data (dict, list, etc.)."""
        data = record.content
        title = record.title

        if isinstance(data, dict):
            table = Table(title=title, show_header=True, header_style="bold")
            table.add_column("Key", style="cyan")
            table.add_column("Value")
            for key, value in data.items():
                table.add_row(str(key), str(value))
            self.console.print(table)
        elif isinstance(data, list):
            if title:
                self.console.print(f"[bold]{title}[/bold]")
            for item in data:
                self.console.print(f"  • {item}")
        else:
            if title:
                self.console.print(f"[bold]{title}:[/bold] {data}")
            else:
                self.console.print(str(data))

    def _write_progress(self, record: OutputRecord) -> None:
        """Write a progress update (for non-context manager usage)."""
        current = record.metadata.get("current", 0)
        total = record.metadata.get("total", 100)
        description = record.content or ""

        pct = (current / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        self.console.print(f"[cyan]{bar}[/cyan] {pct:.0f}% {description}")

    @contextmanager
    def status_context(self, message: str):
        """Context manager for a spinner/status indicator."""
        if self.quiet:
            yield None
            return

        with self.console.status(f"[bold blue]{message}[/bold blue]") as status:
            yield status

    @contextmanager
    def progress_context(self, total: int, description: str = ""):
        """Context manager for a progress bar."""
        if self.quiet:
            yield None
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        ) as progress:
            task = progress.add_task(description, total=total)
            yield lambda n=1: progress.advance(task, n)


class TelemetryBackend(ConsoleBackend):
    """Telemetry backend for structured logging/monitoring.

    This backend collects outputs as structured records that can be
    sent to external logging services, stored for analysis, or
    streamed via REST API.
    """

    def __init__(self, emit_callback: Any | None = None):
        """Initialize the telemetry backend.

        Args:
            emit_callback: Optional callback(record) for each output
        """
        self.records: list[OutputRecord] = []
        self.emit_callback = emit_callback

    def write(self, record: OutputRecord) -> None:
        """Write an output record to the telemetry store."""
        self.records.append(record)
        if self.emit_callback:
            self.emit_callback(record)

    @contextmanager
    def status_context(self, message: str):
        """No-op context manager for telemetry."""
        # Record the status start
        self.write(
            OutputRecord(
                timestamp=datetime.now(),
                output_type=OutputType.STATUS,
                level=OutputLevel.INFO,
                title=None,
                content=message,
                metadata={"phase": "start"},
            )
        )
        yield None
        # Record the status end
        self.write(
            OutputRecord(
                timestamp=datetime.now(),
                output_type=OutputType.STATUS,
                level=OutputLevel.INFO,
                title=None,
                content=message,
                metadata={"phase": "end"},
            )
        )

    @contextmanager
    def progress_context(self, total: int, description: str = ""):
        """No-op context manager for telemetry."""
        yield lambda n=1: None

    def get_records(self) -> list[dict[str, Any]]:
        """Get all records as dictionaries."""
        return [r.to_dict() for r in self.records]

    def clear(self) -> None:
        """Clear all stored records."""
        self.records.clear()


class PlainConsoleBackend(ConsoleBackend):
    """Plain text backend for minimal output without styling.

    Ideal for:
    - Agent/script consumption via bash tools
    - Log file output
    - Environments without terminal support
    """

    LEVEL_PREFIXES = {
        OutputLevel.DEBUG: "[DEBUG]",
        OutputLevel.INFO: "[INFO]",
        OutputLevel.SUCCESS: "[OK]",
        OutputLevel.WARNING: "[WARN]",
        OutputLevel.ERROR: "[ERROR]",
        OutputLevel.CRITICAL: "[CRITICAL]",
    }

    def __init__(self, show_timestamps: bool = True):
        """Initialize the plain console backend.

        Args:
            show_timestamps: Include timestamps in output
        """
        self.show_timestamps = show_timestamps

    def _format_timestamp(self, dt: datetime) -> str:
        """Format timestamp for output."""
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def write(self, record: OutputRecord) -> None:
        """Write an output record as plain text."""
        prefix = self.LEVEL_PREFIXES.get(record.level, "[INFO]")
        timestamp = f"{self._format_timestamp(record.timestamp)} " if self.show_timestamps else ""

        # Format based on output type
        if record.output_type == OutputType.TOOL_CALL:
            tool_name = record.metadata.get("tool_name", "unknown")
            args = record.metadata.get("arguments", {})
            print(f"{timestamp}{prefix} TOOL_CALL: {tool_name} args={args}")

        elif record.output_type == OutputType.TOOL_RESULT:
            tool_name = record.metadata.get("tool_name", "unknown")
            success = record.metadata.get("success", True)
            status = "success" if success else "failed"
            content = str(record.content)[:200] if record.content else ""
            print(f"{timestamp}{prefix} TOOL_RESULT: {tool_name} ({status}) {content}")

        elif record.output_type == OutputType.MODE_CHANGE:
            action = record.metadata.get("action", "change")
            mode_name = record.metadata.get("mode_name", "unknown")
            stack = record.metadata.get("stack", [])
            print(f"{timestamp}{prefix} MODE_{action.upper()}: {mode_name} stack={stack}")

        elif record.output_type == OutputType.SECTION:
            title = record.title or ""
            print(f"{timestamp}--- {title} ---")

        elif record.output_type == OutputType.STEP:
            step = record.metadata.get("step", "?")
            total = record.metadata.get("total")
            step_str = f"[{step}/{total}]" if total else f"[{step}]"
            print(f"{timestamp}{prefix} {step_str} {record.content}")

        elif record.output_type == OutputType.DATA:
            title = record.title or "DATA"
            print(f"{timestamp}{prefix} {title}: {record.content}")

        else:
            # Default message format
            title = f"{record.title}: " if record.title else ""
            content = str(record.content) if record.content else ""
            print(f"{timestamp}{prefix} {title}{content}")

    @contextmanager
    def status_context(self, message: str):
        """Simple status output for plain mode."""
        print(f"[STATUS] {message}...")
        yield None
        print(f"[STATUS] {message} done")

    @contextmanager
    def progress_context(self, total: int, description: str = ""):
        """Simple progress output for plain mode."""
        current = [0]

        def advance(n: int = 1) -> None:
            current[0] += n
            print(f"[PROGRESS] {description}: {current[0]}/{total}")

        yield advance


class JsonConsoleBackend(ConsoleBackend):
    """JSON backend for machine-readable output.

    Each output is a single JSON line (JSONL format) for easy parsing.
    Ideal for:
    - Machine consumption
    - Log aggregation systems
    - Structured logging pipelines
    """

    def __init__(self, include_metadata: bool = True):
        """Initialize the JSON console backend.

        Args:
            include_metadata: Include full metadata in output
        """
        self.include_metadata = include_metadata

    def write(self, record: OutputRecord) -> None:
        """Write an output record as JSON."""
        import json

        output: dict[str, Any] = {
            "timestamp": record.timestamp.isoformat(),
            "type": record.output_type.value,
            "level": record.level.value,
        }

        if record.title:
            output["title"] = record.title
        if record.content is not None:
            output["content"] = (
                str(record.content)
                if not isinstance(record.content, (dict, list))
                else record.content
            )
        if self.include_metadata and record.metadata:
            output["metadata"] = record.metadata

        print(json.dumps(output))

    @contextmanager
    def status_context(self, message: str):
        """JSON status output."""
        import json

        print(json.dumps({"type": "status", "phase": "start", "message": message}))
        yield None
        print(json.dumps({"type": "status", "phase": "end", "message": message}))

    @contextmanager
    def progress_context(self, total: int, description: str = ""):
        """JSON progress output."""
        import json

        current = [0]

        def advance(n: int = 1) -> None:
            current[0] += n
            print(
                json.dumps(
                    {
                        "type": "progress",
                        "description": description,
                        "current": current[0],
                        "total": total,
                    }
                )
            )

        yield advance


class AgentConsole:
    """High-level console interface for agent outputs.

    Provides a clean API for outputting various types of information
    during agent execution. Supports multiple backends for different
    output targets (CLI, telemetry, etc.).

    Example:
        console = AgentConsole()
        console.info("Processing request")
        console.tool_call("search", {"query": "test"})

        with console.status("Working..."):
            # long operation
            pass
    """

    def __init__(
        self,
        backend: ConsoleBackend | None = None,
        agent: Agent | None = None,
    ):
        """Initialize the agent console.

        Args:
            backend: Output backend (defaults to RichConsoleBackend)
            agent: Optional agent reference for context
        """
        self.backend = backend or RichConsoleBackend()
        self.agent = agent
        self._step_counter = 0

    def _emit(
        self,
        output_type: OutputType,
        level: OutputLevel,
        title: str | None = None,
        content: Any = None,
        **metadata: Any,
    ) -> None:
        """Emit an output record to the backend."""
        record = OutputRecord(
            timestamp=datetime.now(),
            output_type=output_type,
            level=level,
            title=title,
            content=content,
            metadata=metadata,
        )
        self.backend.write(record)

    # ========================================================================
    # Basic Output Methods
    # ========================================================================

    def debug(self, message: str, **metadata: Any) -> None:
        """Output a debug message."""
        self._emit(OutputType.MESSAGE, OutputLevel.DEBUG, content=message, **metadata)

    def info(self, message: str, **metadata: Any) -> None:
        """Output an info message."""
        self._emit(OutputType.MESSAGE, OutputLevel.INFO, content=message, **metadata)

    def success(self, message: str, **metadata: Any) -> None:
        """Output a success message."""
        self._emit(OutputType.MESSAGE, OutputLevel.SUCCESS, content=message, **metadata)

    def warning(self, message: str, **metadata: Any) -> None:
        """Output a warning message."""
        self._emit(OutputType.MESSAGE, OutputLevel.WARNING, content=message, **metadata)

    def error(self, message: str, **metadata: Any) -> None:
        """Output an error message."""
        self._emit(OutputType.MESSAGE, OutputLevel.ERROR, content=message, **metadata)

    def critical(self, message: str, **metadata: Any) -> None:
        """Output a critical error message."""
        self._emit(OutputType.MESSAGE, OutputLevel.CRITICAL, content=message, **metadata)

    # ========================================================================
    # Structured Output Methods
    # ========================================================================

    def status(self, message: str) -> None:
        """Output a status update."""
        self._emit(OutputType.STATUS, OutputLevel.INFO, content=message)

    def section(self, title: str, style: str = "bold blue") -> None:
        """Output a section header/divider."""
        self._emit(OutputType.SECTION, OutputLevel.INFO, title=title, style=style)

    def step(self, message: str, step: int | None = None, total: int | None = None) -> None:
        """Output a numbered step.

        Args:
            message: Step description
            step: Step number (auto-increments if None)
            total: Total number of steps (optional)
        """
        if step is None:
            self._step_counter += 1
            step = self._step_counter
        self._emit(OutputType.STEP, OutputLevel.INFO, content=message, step=step, total=total)

    def reset_steps(self) -> None:
        """Reset the step counter."""
        self._step_counter = 0

    def data(self, data: Any, title: str | None = None) -> None:
        """Output structured data (dict, list, etc.)."""
        self._emit(OutputType.DATA, OutputLevel.INFO, title=title, content=data)

    # ========================================================================
    # Tool Output Methods
    # ========================================================================

    def tool_call(self, tool_name: str, arguments: dict[str, Any] | None = None) -> None:
        """Output a tool call notification."""
        self._emit(
            OutputType.TOOL_CALL,
            OutputLevel.INFO,
            tool_name=tool_name,
            arguments=arguments or {},
        )

    def tool_result(
        self,
        tool_name: str,
        result: Any,
        success: bool = True,
    ) -> None:
        """Output a tool result."""
        self._emit(
            OutputType.TOOL_RESULT,
            OutputLevel.SUCCESS if success else OutputLevel.ERROR,
            content=result,
            tool_name=tool_name,
            success=success,
        )

    # ========================================================================
    # Mode Output Methods
    # ========================================================================

    def mode_enter(self, mode_name: str, stack: list[str] | None = None) -> None:
        """Output a mode entry notification."""
        self._emit(
            OutputType.MODE_CHANGE,
            OutputLevel.INFO,
            action="enter",
            mode_name=mode_name,
            stack=stack or [],
        )

    def mode_exit(self, mode_name: str, stack: list[str] | None = None) -> None:
        """Output a mode exit notification."""
        self._emit(
            OutputType.MODE_CHANGE,
            OutputLevel.INFO,
            action="exit",
            mode_name=mode_name,
            stack=stack or [],
        )

    # ========================================================================
    # Context Managers
    # ========================================================================

    def spinner(self, message: str):
        """Context manager for a spinner/status indicator.

        Example:
            with console.spinner("Processing..."):
                # long operation
                pass
        """
        return self.backend.status_context(message)

    def progress(self, total: int, description: str = ""):
        """Context manager for a progress bar.

        Example:
            with console.progress(100, "Downloading") as advance:
                for i in range(100):
                    advance()
        """
        return self.backend.progress_context(total, description)

    # ========================================================================
    # Rich-Specific Methods (only work with RichConsoleBackend)
    # ========================================================================

    def panel(
        self,
        content: str,
        title: str | None = None,
        style: str = "blue",
        markdown: bool = False,
    ) -> None:
        """Output content in a panel (Rich backend only)."""
        if not isinstance(self.backend, RichConsoleBackend):
            # Fallback for non-Rich backends
            self.info(f"{title}: {content}" if title else content)
            return

        renderable = Markdown(content) if markdown else Text(content)
        panel = Panel(renderable, title=title, border_style=style)
        self.backend.console.print(panel)

    def tree(self, data: dict[str, Any], title: str = "Tree") -> None:
        """Output hierarchical data as a tree (Rich backend only)."""
        if not isinstance(self.backend, RichConsoleBackend):
            self.data(data, title)
            return

        def add_to_tree(tree_node: Tree, data: Any) -> None:
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict | list):
                        branch = tree_node.add(f"[cyan]{key}[/cyan]")
                        add_to_tree(branch, value)
                    else:
                        tree_node.add(f"[cyan]{key}:[/cyan] {value}")
            elif isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict | list):
                        branch = tree_node.add(f"[dim][{i}][/dim]")
                        add_to_tree(branch, item)
                    else:
                        tree_node.add(f"[dim][{i}][/dim] {item}")

        tree = Tree(f"[bold]{title}[/bold]")
        add_to_tree(tree, data)
        self.backend.console.print(tree)

    def markdown(self, content: str) -> None:
        """Output markdown content (Rich backend only)."""
        if not isinstance(self.backend, RichConsoleBackend):
            self.info(content)
            return

        self.backend.console.print(Markdown(content))

    def rule(self, title: str = "", style: str = "dim") -> None:
        """Output a horizontal rule (Rich backend only)."""
        if not isinstance(self.backend, RichConsoleBackend):
            self.info("-" * 40 + (f" {title} " if title else "") + "-" * 40)
            return

        self.backend.console.print(Rule(title, style=style))

    def newline(self, count: int = 1) -> None:
        """Output blank lines."""
        if isinstance(self.backend, RichConsoleBackend):
            for _ in range(count):
                self.backend.console.print()
        else:
            self._emit(OutputType.MESSAGE, OutputLevel.INFO, content="\n" * count)

    # ========================================================================
    # Token Tracking Methods
    # ========================================================================

    def get_model_context_limit(self, model: str | None = None) -> dict[str, int]:
        """Get context window limits for a model from litellm.

        Args:
            model: Model name (uses agent's model if None)

        Returns:
            Dict with 'max_input_tokens' and 'max_output_tokens'
        """
        if model is None and self.agent:
            model = self.agent.config.model
        model = model or "gpt-4o"

        try:
            import litellm

            model_info = litellm.model_cost.get(model, {})
            return {
                "max_input_tokens": model_info.get("max_input_tokens", 128000),
                "max_output_tokens": model_info.get("max_output_tokens", 16384),
            }
        except Exception:
            # Fallback defaults
            return {"max_input_tokens": 128000, "max_output_tokens": 16384}

    def token_usage(
        self,
        show_bar: bool = True,
        compact: bool = False,
    ) -> None:
        """Display current token usage breakdown by message role.

        Args:
            show_bar: Show visual progress bar for context usage
            compact: Use compact single-line format
        """
        if not self.agent:
            self.warning("No agent attached - cannot show token usage")
            return

        # Get token counts by role
        usage_by_role = self.agent.get_token_count_by_role()
        total_tokens = sum(usage_by_role.values())

        # Get context limits
        limits = self.get_model_context_limit()
        max_input = limits["max_input_tokens"]

        # Calculate percentage
        pct_used = (total_tokens / max_input * 100) if max_input > 0 else 0

        if not isinstance(self.backend, RichConsoleBackend):
            # Fallback for non-Rich backends
            parts = [f"{role}: {count:,}" for role, count in usage_by_role.items()]
            self.info(
                f"Tokens: {total_tokens:,}/{max_input:,} ({pct_used:.1f}%) - {', '.join(parts)}"
            )
            return

        if compact:
            # Compact single-line format
            parts = []
            role_colors = {
                "system": "yellow",
                "user": "green",
                "assistant": "blue",
                "tool": "cyan",
            }
            for role, count in usage_by_role.items():
                color = role_colors.get(role, "white")
                parts.append(f"[{color}]{role}:{count:,}[/{color}]")

            bar_color = "green" if pct_used < 70 else "yellow" if pct_used < 90 else "red"
            line = (
                f"[dim]Context:[/dim] {' '.join(parts)} "
                f"[{bar_color}]({total_tokens:,}/{max_input:,} = {pct_used:.1f}%)[/{bar_color}]"
            )
            self.backend.console.print(line)
        else:
            # Full panel format with table and bar
            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
            table.add_column("Role", style="dim")
            table.add_column("Tokens", justify="right")
            table.add_column("", justify="right", width=6)

            role_colors = {
                "system": "yellow",
                "user": "green",
                "assistant": "blue",
                "tool": "cyan",
            }

            for role, count in usage_by_role.items():
                color = role_colors.get(role, "white")
                role_pct = (count / total_tokens * 100) if total_tokens > 0 else 0
                table.add_row(
                    f"[{color}]{role}[/{color}]",
                    f"{count:,}",
                    f"[dim]{role_pct:.0f}%[/dim]",
                )

            # Add total row
            table.add_row("", "", "")
            table.add_row("[bold]Total[/bold]", f"[bold]{total_tokens:,}[/bold]", "")

            # Create progress bar
            bar_color = "green" if pct_used < 70 else "yellow" if pct_used < 90 else "red"

            elements: list[Any] = [table]

            if show_bar:
                # Create progress bar using Unicode blocks
                bar_width = 40
                filled = int(bar_width * pct_used / 100)
                empty = bar_width - filled
                bar = Text()
                bar.append("█" * filled, style=bar_color)
                bar.append("░" * empty, style="grey23")

                bar_text = Text()
                bar_text.append("\n")
                bar_text.append(f"{total_tokens:,}", style="bold")
                bar_text.append(f" / {max_input:,} ", style="dim")
                bar_text.append(f"({pct_used:.1f}%)", style=bar_color)
                elements.append(bar_text)
                elements.append(bar)

            panel = Panel(
                Group(*elements),
                title=f"[bold]Context Usage[/bold] [dim]({self.agent.config.model})[/dim]",
                border_style=bar_color,
                expand=False,
                padding=(0, 1),
            )
            self.backend.console.print(panel)

    def context_bar(self, width: int = 50) -> None:
        """Display a compact context usage bar.

        Args:
            width: Width of the progress bar in characters
        """
        if not self.agent:
            return

        total_tokens = self.agent.get_token_count()
        limits = self.get_model_context_limit()
        max_input = limits["max_input_tokens"]
        pct_used = (total_tokens / max_input * 100) if max_input > 0 else 0

        if not isinstance(self.backend, RichConsoleBackend):
            self.info(f"Context: {total_tokens:,}/{max_input:,} ({pct_used:.1f}%)")
            return

        bar_color = "green" if pct_used < 70 else "yellow" if pct_used < 90 else "red"

        # Create progress bar using Unicode blocks
        filled = int(width * pct_used / 100)
        empty = width - filled
        bar = Text()
        bar.append("█" * filled, style=bar_color)
        bar.append("░" * empty, style="grey23")

        text = Text()
        text.append("Context: ", style="dim")
        text.append(f"{total_tokens:,}", style="bold")
        text.append(f"/{max_input:,} ", style="dim")
        text.append(f"({pct_used:.1f}%)", style=bar_color)

        self.backend.console.print(text)
        self.backend.console.print(bar)


def create_console(
    format: OutputFormat | Literal["rich", "plain", "json", "telemetry"] = "rich",
    agent: Agent | None = None,
    **kwargs: Any,
) -> AgentConsole:
    """Factory function to create an AgentConsole with specified format/backend.

    Args:
        format: Output format - "rich" (default), "plain", "json", or "telemetry"
        agent: Optional agent reference for context-aware output
        **kwargs: Additional arguments passed to the backend

    Returns:
        Configured AgentConsole instance

    Examples:
        # Rich CLI output (default)
        console = create_console()

        # Plain text for scripts/agents
        console = create_console("plain")

        # JSON for machine consumption
        console = create_console("json")
    """
    format_str = format.value if isinstance(format, OutputFormat) else format

    backend: ConsoleBackend
    if format_str == "rich":
        backend = RichConsoleBackend(**kwargs)
    elif format_str == "plain":
        backend = PlainConsoleBackend(**kwargs)
    elif format_str == "json":
        backend = JsonConsoleBackend(**kwargs)
    elif format_str == "telemetry":
        backend = TelemetryBackend(**kwargs)
    else:
        raise ValueError(f"Unknown format: {format}")

    return AgentConsole(backend=backend, agent=agent)
