from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
import yaml
from click.utils import get_text_stream
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

# Agent templating components
from good_agent.extensions.template_manager.index import (
    TemplateIndex,
    TemplateVersionManager,
)
from good_agent.extensions.template_manager.storage import (
    FileSystemStorage,
    FileTemplateManager,
    TemplateValidator,
)


def _get_console() -> Console:
    """Return a Rich console bound to the current stdout stream."""
    return Console(file=get_text_stream("stdout"))


def rprint(*args, **kwargs):
    """Proxy Rich print through a console tied to the active stdout."""
    _get_console().print(*args, **kwargs)


app = typer.Typer(help="Manage prompt templates")


def _find_project_root() -> Path | None:
    """Find the project root by looking for prompts.yaml."""
    current_dir = os.getcwd()

    while current_dir:
        current_path = Path(current_dir)
        if (current_path / "prompts.yaml").exists():
            return current_path
        parent = os.path.dirname(current_dir)
        if parent == current_dir:
            break
        current_dir = parent
    return None


def _load_config() -> dict:
    """Load prompts.yaml configuration."""
    project_root = _find_project_root()
    if not project_root:
        return {}
    config_file = project_root / "prompts.yaml"
    if config_file.exists():
        return yaml.safe_load(config_file.read_text()) or {}
    return {}


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
):
    """Initialize a new prompts directory structure."""
    print("Initializing prompts directory")

    config_file = path / "prompts.yaml"
    if config_file.exists() and not force:
        rprint("[yellow]prompts.yaml already exists. Skipping initialization.[/yellow]")
        raise typer.Exit(0)

    prompts_dir = path / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    for subdir in [
        "system",
        "user",
        "tools",
        "components/headers",
        "components/footers",
        "components/examples",
        "layouts",
    ]:
        (prompts_dir / subdir).mkdir(parents=True, exist_ok=True)

    config = {
        "version": "1.0",
        "prompts_dir": "prompts",
        "search_paths": [
            {"path": "./prompts", "priority": 100},
            {"path": "~/.good-agent/prompts", "priority": 50},
        ],
        "aliases": {"default": "system/base"},
        "validation": {
            "required_frontmatter": ["version", "description"],
            "max_file_size": 100000,
            "allowed_extensions": [".prompt"],
        },
    }

    config_file.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))

    sample_template = prompts_dir / "system" / "base.prompt"
    sample_template.write_text(
        """---
version: 1.0.0
description: Base system prompt
author: system
tags: [system, base]
---

You are a helpful AI assistant.

{% if instructions %}
<instructions>
{{ instructions }}
</instructions>
{% endif %}
"""
    )

    index_file = prompts_dir / "index.yaml"
    index_file.write_text(
        yaml.dump(
            {"version": "1.0", "updated": datetime.now().isoformat(), "templates": {}},
        )
    )

    rprint(
        Panel.fit(
            f"✅ Initialized prompts directory at [cyan]{path}[/cyan]\n\n"
            f"Created:\n"
            f"  • prompts.yaml (configuration)\n"
            f"  • prompts/ (template directory)\n"
            f"  • prompts/index.yaml (version tracking)\n"
            f"  • prompts/system/base.prompt (sample template)",
            title="Prompts Initialized",
        )
    )


@app.command()
def new(
    name: str = typer.Argument(..., help="Template name (e.g., 'system/analyst')"),
    description: str = typer.Option("", "--description", "-d", help="Template description"),
    author: str = typer.Option("", "--author", "-a", help="Template author"),
    tags: str | None = typer.Option(None, "--tags", "-t", help="Comma-separated list of tags"),
    extends: str | None = typer.Option(None, "--extends", "-e", help="Parent template to extend"),
):
    """Create a new prompt template."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]No prompts.yaml found. Run 'good prompts init' first.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    if not name.endswith(".prompt"):
        name = f"{name}.prompt"
    template_path = prompts_dir / name

    if template_path.exists():
        rprint(f"[red]Template '{name}' already exists.[/red]")
        raise typer.Exit(1)

    template_path.parent.mkdir(parents=True, exist_ok=True)

    tag_list: list[str] = []
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]

    frontmatter = {
        "version": "1.0.0",
        "description": description or f"Template: {name}",
        "author": author or "user",
        "created": datetime.now().isoformat(),
        "tags": tag_list,
    }
    if extends:
        frontmatter["extends"] = extends

    content = f"""---
{yaml.dump(frontmatter, default_flow_style=False, sort_keys=False).strip()}
---

"""
    if extends:
        content += f'{{% extends "{extends}" %}}\n\n'
        content += "{% block content %}\n"
        content += "# Your template content here\n"
        content += "{% endblock %}\n"
    else:
        content += (
            "# Your template content here\n\n{% if variable %}\n{{ variable }}\n{% endif %}\n"
        )

    template_path.write_text(content)

    try:
        index = TemplateIndex(prompts_dir)
        index.scan_templates(auto_version=True)
    except Exception:
        pass

    rprint(
        Panel.fit(
            f"✅ Created template: [cyan]{name}[/cyan]\n"
            f"Location: {template_path.relative_to(project_root)}",
            title="Template Created",
        )
    )


@app.command(name="list")
def list_templates(
    tags: str | None = typer.Option(None, "--tags", "-t", help="Filter by tags (comma-separated)"),
    format: str = typer.Option("table", "--format", "-f", help="Output format: table, tree, json"),
):
    """List all prompt templates."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    index = TemplateIndex(prompts_dir)
    index.scan_templates(auto_version=False)

    tag_list = tags.split(",") if tags else None
    templates = index.list_templates(tags=list(tag_list) if tag_list else None)

    if format == "json":
        output = []
        for template in templates:
            output.append(
                {
                    "name": template.name,
                    "version": template.version,
                    "description": template.description,
                    "author": template.author,
                    "tags": template.tags,
                    "modified": template.last_modified.isoformat(),
                }
            )
        print(json.dumps(output, indent=2))

    elif format == "tree":
        tree = Tree("📁 Templates")
        by_dir: dict[str, list[tuple[str, Any]]] = {}
        for template in templates:
            parts = template.name.split("/")
            if len(parts) > 1:
                dir_name = parts[0]
                file_name = "/".join(parts[1:])
            else:
                dir_name = "."
                file_name = parts[0]
            by_dir.setdefault(dir_name, []).append((file_name, template))

        for dir_name, items in sorted(by_dir.items()):
            parent = tree if dir_name == "." else tree.add(f"📂 {dir_name}/")
            for file_name, template in items:
                label = f"📄 {file_name}"
                if template.version:
                    label += f" [dim](v{template.version})[/dim]"
                if template.description:
                    label += f" - {template.description[:50]}"
                parent.add(label)

        rprint(tree)

    else:
        table = Table(title="Prompt Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description")
        table.add_column("Tags", style="yellow")
        table.add_column("Modified")
        for template in templates:
            table.add_row(
                template.name,
                template.version or "-",
                template.description or "-",
                ", ".join(template.tags) if template.tags else "-",
                template.last_modified.strftime("%Y-%m-%d %H:%M"),
            )
        console = _get_console()
        console.print(table)


@app.command()
def scan(
    auto_version: bool = typer.Option(
        True, "--auto-version/--no-auto-version", help="Auto-increment versions"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed changes"),
):
    """Scan templates for changes and update index."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    index = TemplateIndex(prompts_dir)
    changes = index.scan_templates(auto_version=auto_version)

    if not changes:
        rprint("[green]No changes detected.[/green]")
        return

    table = Table(title="Template Changes Detected")
    table.add_column("Template", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Version")

    status_colors = {
        "new": "green",
        "modified": "yellow",
        "deleted": "red",
        "unchanged": "dim",
    }

    for name, status in changes.items():
        if status == "unchanged" and not verbose:
            continue
        template = index.get_template_info(name)
        version = template.version if template else "-"
        table.add_row(
            name,
            f"[{status_colors.get(status, 'white')}]"
            f"{status}"
            f"[/{status_colors.get(status, 'white')}]",
            version,
        )
    console = _get_console()
    console.print(table)

    summary = {
        "new": len([s for s in changes.values() if s == "new"]),
        "modified": len([s for s in changes.values() if s == "modified"]),
        "deleted": len([s for s in changes.values() if s == "deleted"]),
    }
    rprint(
        f"\n📊 Summary: {summary['new']} new, {summary['modified']} modified, {summary['deleted']} deleted"
    )


@app.command()
def validate(
    name: str | None = typer.Argument(None, help="Template name to validate (or all)"),
    fix: bool = typer.Option(False, "--fix", "-f", help="Auto-fix issues where possible"),
):
    """Validate template syntax and structure."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    validator = TemplateValidator()

    if name:
        templates = [prompts_dir / f"{name}.prompt"]
    else:
        templates = list(prompts_dir.rglob("*.prompt"))

    issues_found = False
    for template_path in templates:
        if not template_path.exists():
            continue
        content = template_path.read_text()
        if not isinstance(content, str):
            content = str(content)
        errors = validator.validate(content)
        variables = validator.extract_variables(content)

        if errors:
            issues_found = True
            rprint(f"\n[red]❌ {template_path.relative_to(prompts_dir)}[/red]")
            for error in errors:
                line_info = f"line {error.get('line', '?')}" if error.get("line") else ""
                rprint(f"  • {error['type']}: {error['message']} {line_info}")
        else:
            rprint(f"[green]✓[/green] {template_path.relative_to(prompts_dir)}")
            if variables:
                rprint(f"  Variables: {', '.join(variables)}")

    if not issues_found:
        rprint("\n[green]✅ All templates valid![/green]")
    else:
        rprint("\n[red]Invalid templates found.[/red]")
        rprint("\n[red]⚠️ Issues found. Review errors above.[/red]")
        raise typer.Exit(1)


@app.command()
def render(
    name: str = typer.Argument(..., help="Template name to render"),
    context: str | None = typer.Option(None, "--context", "-c", help="Context as JSON string"),
    context_file: Path | None = typer.Option(
        None, "--context-file", help="Path to JSON file with context"
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Render a template with context."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    context_dict: dict[str, Any] = {}
    if context:
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            rprint("[red]Invalid JSON context.[/red]")
            raise typer.Exit(1) from None

    if context_file and context_file.exists():
        try:
            file_context = json.loads(context_file.read_text())
            context_dict = {**file_context, **context_dict}
        except Exception:
            rprint("[red]Invalid context file.[/red]")
            raise typer.Exit(1) from None

    async def _render():
        storage = FileSystemStorage(prompts_dir)
        manager = FileTemplateManager(storage)
        await manager.preload_templates([name])
        try:
            return manager.render(f"{{% include '{name}' %}}", context_dict)
        except Exception as e:
            rprint(f"[red]Error rendering template: {e}[/red]")
            raise typer.Exit(1) from e

    rendered = asyncio.run(_render())

    if output:
        output.write_text(rendered)
        rprint(f"[green]✅ Rendered to {output}[/green]")
    else:
        syntax = Syntax(rendered, "markdown", theme="monokai", line_numbers=True)
        console = _get_console()
        console.print(Panel(syntax, title=f"Rendered: {name}"))


@app.command()
def snapshot(
    name: str = typer.Argument(..., help="Template name to snapshot"),
    reason: str = typer.Option("Manual snapshot", "--reason", "-r", help="Reason for snapshot"),
):
    """Create a version snapshot of a template."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    version_manager = TemplateVersionManager(prompts_dir, versions_dir=prompts_dir / ".snapshots")
    version_hash = version_manager.create_snapshot(name, reason)

    if version_hash:
        try:
            flat_name = name.replace("/", "-")
            flat_path = (prompts_dir / ".snapshots") / f"{flat_name}@{version_hash}.prompt"
            nested_path = prompts_dir / ".snapshots" / name / f"{version_hash}.prompt"
            if nested_path.exists():
                flat_path.parent.mkdir(parents=True, exist_ok=True)
                flat_path.write_text(nested_path.read_text())
        except Exception:
            pass
        rprint(
            Panel.fit(
                f"✅ Created snapshot: [cyan]{version_hash}[/cyan]\n"
                f"Template: {name}\n"
                f"Reason: {reason}",
                title="Snapshot Created",
            )
        )
    else:
        rprint(f"[red]Failed to create snapshot for '{name}'[/red]")
        raise typer.Exit(1)


@app.command()
def history(
    name: str = typer.Argument(..., help="Template name"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of versions to show"),
):
    """Show version history for a template."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    index = TemplateIndex(prompts_dir)
    template = index.get_template_info(name)
    if not template:
        rprint(f"[red]Template '{name}' not found.[/red]")
        raise typer.Exit(1)

    version_manager = TemplateVersionManager(prompts_dir, versions_dir=prompts_dir / ".snapshots")
    snapshots = version_manager.list_snapshots(name)

    def _format_timestamp(value: object) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if isinstance(value, str):
            return value
        return "-"

    rprint(
        Panel.fit(
            f"Template: [cyan]{name}[/cyan]\n"
            f"Current Version: {template.version}\n"
            f"Current Hash: {template.content_hash}\n"
            f"Last Modified: {template.last_modified.strftime('%Y-%m-%d %H:%M')}",
            title="Current Status",
        )
    )

    if template.version_history or snapshots:
        table = Table(title="Version History")
        table.add_column("Version", style="green")
        table.add_column("Hash", style="cyan")
        table.add_column("Date")
        table.add_column("Reason")

        for entry in template.version_history[:limit]:
            timestamp = _format_timestamp(entry.get("timestamp"))
            table.add_row(
                entry.get("version", "-"),
                entry.get("hash", "-")[:8],
                timestamp,
                "-",
            )
        for snapshot in snapshots[:limit]:
            table.add_row(
                "-",
                snapshot["hash"][:8],
                _format_timestamp(snapshot.get("timestamp")),
                snapshot.get("reason", "-"),
            )
        console = _get_console()
        console.print(table)
    else:
        rprint("[yellow]No version history available.[/yellow]")


@app.command()
def restore(
    name: str = typer.Argument(..., help="Template name"),
    version: str = typer.Argument(..., help="Version hash to restore"),
    force: bool = typer.Option(True, "--force", "-f", help="Force restore without confirmation"),
):
    """Restore a template to a previous version."""

    project_root = _find_project_root()
    if not project_root:
        rprint("[red]prompts.yaml not found.[/red]")
        raise typer.Exit(1)

    config = _load_config()
    prompts_dir = project_root / config.get("prompts_dir", "prompts")

    version_manager = TemplateVersionManager(prompts_dir, versions_dir=prompts_dir / ".snapshots")
    success = version_manager.restore_snapshot(name, version)

    if success:
        rprint(
            Panel.fit(
                f"✅ Restored template: [cyan]{name}[/cyan]\nTo version: {version}",
                title="Template Restored",
            )
        )
    else:
        rprint(f"[red]Failed to restore '{name}' to version {version}[/red]")
        raise typer.Exit(1)


def register_commands(parent_app: typer.Typer):
    """Register prompt commands with a parent Typer app (optional)."""
    parent_app.add_typer(app, name="prompts", help="Manage prompt templates")


if __name__ == "__main__":
    app()
