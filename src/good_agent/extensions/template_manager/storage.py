import asyncio
import hashlib
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml  # type: ignore[import-untyped]
from jinja2 import BaseLoader, ChoiceLoader, Environment, TemplateNotFound
from pydantic import BaseModel, Field

from good_agent.core import templating
from good_agent.core.templating import TemplateRegistry

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Storage Protocol and Base Classes
# ------------------------------------------------------------------------------


@runtime_checkable
class TemplateStorage(Protocol):
    """Protocol for template storage backends."""

    async def get(self, key: str) -> str | None:
        """Retrieve template content by key."""
        ...

    async def put(self, key: str, content: str, metadata: dict | None = None) -> None:
        """Store template content with metadata."""
        ...

    async def list(self, prefix: str = "") -> list[str]:
        """List available template keys."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if template exists."""
        ...

    async def get_metadata(self, key: str) -> dict:
        """Get template metadata without content."""
        ...


class TemplateSnapshot(BaseModel):
    """Captures template state for perfect replayability."""

    template_name: str
    content_hash: str
    git_commit: str | None = None
    semantic_version: str | None = None
    timestamp: datetime
    content: str
    metadata: dict = Field(default_factory=dict)

    def to_storage_key(self) -> str:
        """Generate storage key for this snapshot."""
        return f"{self.template_name}@{self.content_hash}"

    @classmethod
    def from_template(
        cls,
        name: str,
        content: str,
        git_commit: str | None = None,
        semantic_version: str | None = None,
        metadata: dict | None = None,
    ) -> TemplateSnapshot:
        """Create snapshot from template content."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return cls(
            template_name=name,
            content_hash=content_hash,
            git_commit=git_commit,
            semantic_version=semantic_version,
            timestamp=datetime.now(),
            content=content,
            metadata=metadata or {},
        )


# ------------------------------------------------------------------------------
# Storage Implementations
# ------------------------------------------------------------------------------


class FileSystemStorage:
    """Local filesystem storage for templates."""

    def __init__(self, base_path: Path | str, extension: str = ".prompt"):
        self.base_path = Path(base_path)
        self.extension = extension
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _normalize_key(self, key: str) -> str:
        """Normalize template key to handle case variations."""
        # Remove extension if present
        if key.endswith(self.extension):
            key = key[: -len(self.extension)]
        return key

    def _get_case_variations(self, key: str) -> list[str]:
        """Generate case variations for a template key.

        Returns variations in order of preference:
        1. Original (kebab-case if present)
        2. Snake_case version
        3. Original with underscores converted to hyphens
        """
        variations = [key]

        # Add snake_case version if key has hyphens
        if "-" in key:
            variations.append(key.replace("-", "_"))

        # Add kebab-case version if key has underscores
        if "_" in key:
            variations.append(key.replace("_", "-"))

        return variations

    async def get(self, key: str) -> str | None:
        """Retrieve template content by key, trying case variations."""
        key = self._normalize_key(key)

        # Try each case variation
        for variant in self._get_case_variations(key):
            # Try with extension
            path = self.base_path / f"{variant}{self.extension}"
            if path.exists():
                content = path.read_text()
                return self._strip_frontmatter(content)

            # Try without extension (for full paths)
            path = self.base_path / variant
            if path.exists() and path.is_file():
                content = path.read_text()
                return self._strip_frontmatter(content)

        return None

    def _strip_frontmatter(self, content: str) -> str:
        """Strip YAML frontmatter from template content if present."""
        if content.startswith("---\n"):
            # Find the closing ---
            parts = content.split("---\n", 2)
            if len(parts) >= 3:
                # Return everything after the frontmatter
                return parts[2]
        return content

    async def put(self, key: str, content: str, metadata: dict | None = None) -> None:
        """Store template content with metadata."""
        path = self.base_path / f"{key}{self.extension}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        # Store metadata separately if provided
        if metadata:
            meta_path = path.with_suffix(".meta.json")
            meta_path.write_text(json.dumps(metadata, indent=2, default=str))

    async def list(self, prefix: str = "") -> list[str]:
        """List available template keys."""
        search_path = self.base_path / prefix if prefix else self.base_path
        if not search_path.exists():
            return []

        templates = []
        for path in search_path.rglob(f"*{self.extension}"):
            relative = path.relative_to(self.base_path)
            # Remove extension from key
            key = str(relative)[: -len(self.extension)]
            templates.append(key)

        return sorted(templates)

    async def exists(self, key: str) -> bool:
        """Check if template exists."""
        path = self.base_path / f"{key}{self.extension}"
        return path.exists()

    async def get_metadata(self, key: str) -> dict[Any, Any]:
        """Get template metadata without content."""
        meta_path = self.base_path / f"{key}.meta.json"
        if meta_path.exists():
            data: dict[Any, Any] = json.loads(meta_path.read_text())
            return data

        # Extract frontmatter if present - read raw content, not via get()
        key = self._normalize_key(key)

        # Try each case variation to find the file
        for variant in self._get_case_variations(key):
            # Try with extension
            path = self.base_path / f"{variant}{self.extension}"
            if path.exists():
                raw_content = path.read_text()
                break

            # Try without extension (for full paths)
            path = self.base_path / variant
            if path.exists() and path.is_file():
                raw_content = path.read_text()
                break
        else:
            # No file found
            return {}

        # Extract frontmatter from raw content
        if raw_content.startswith("---\n"):
            try:
                parts = raw_content.split("---\n", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    return yaml.safe_load(frontmatter) or {}
            except Exception:
                pass

        return {}


class GitVersionProvider:
    """Provides git version information for templates."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def get_commit_hash(self, file_path: Path | None = None) -> str | None:
        """Get current git commit hash."""
        try:
            cmd = ["git", "rev-parse", "HEAD"]
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.repo_path, check=True
            )
            return result.stdout.strip()[:12]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def get_file_history(self, file_path: Path, limit: int = 10) -> list[dict]:
        """Get git history for a specific file."""
        try:
            relative_path = file_path.relative_to(self.repo_path)
            cmd = [
                "git",
                "log",
                f"--max-count={limit}",
                "--pretty=format:%H|%ai|%s",
                str(relative_path),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=self.repo_path, check=True
            )

            history = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    commit, date, message = line.split("|", 2)
                    history.append({"commit": commit[:12], "date": date, "message": message})
            return history
        except (subprocess.CalledProcessError, FileNotFoundError):
            return []


class ChainedStorage:
    """Combines multiple storage backends with fallback."""

    def __init__(self, storages: list[TemplateStorage]):
        self.storages = storages

    async def get(self, key: str) -> str | None:
        """Try each storage in order until template is found."""
        for storage in self.storages:
            try:
                content = await storage.get(key)
                if content is not None:
                    return content
            except Exception as e:
                logger.warning(f"Error accessing {storage.__class__.__name__} for '{key}': {e}")
        return None

    async def put(self, key: str, content: str, metadata: dict | None = None) -> None:
        """Store in the first writable storage."""
        for storage in self.storages:
            try:
                await storage.put(key, content, metadata)
                return
            except Exception as e:
                logger.warning(f"Could not store in {storage.__class__.__name__}: {e}")
        raise RuntimeError(f"Could not store template '{key}' in any storage backend")

    async def list(self, prefix: str = "") -> list[str]:
        """List templates from all storages."""
        all_templates = set()
        for storage in self.storages:
            try:
                templates = await storage.list(prefix)
                all_templates.update(templates)
            except Exception as e:
                logger.warning(f"Error listing from {storage.__class__.__name__}: {e}")
        return sorted(all_templates)

    async def exists(self, key: str) -> bool:
        """Check if template exists in any storage."""
        for storage in self.storages:
            try:
                if await storage.exists(key):
                    return True
            except Exception:
                continue
        return False

    async def get_metadata(self, key: str) -> dict:
        """Get metadata from the first storage that has the template."""
        for storage in self.storages:
            try:
                if await storage.exists(key):
                    return await storage.get_metadata(key)
            except Exception:
                continue
        return {}


# ------------------------------------------------------------------------------
# Template Path Resolution
# ------------------------------------------------------------------------------


class TemplatePathResolver:
    """Resolves template names to file paths with priority-based search."""

    def __init__(self, config_path: Path | None = None):
        self.config = self._load_config(config_path)
        self.search_paths = self._build_search_paths()

    def _load_config(self, config_path: Path | None) -> dict[Any, Any]:
        """Load prompts.yaml configuration."""
        if config_path and config_path.exists():
            data: dict[Any, Any] = yaml.safe_load(config_path.read_text())
            return data

        # Default configuration
        return {
            "version": "1.0",
            "search_paths": [
                {"path": "./prompts", "priority": 100},
                {"path": "~/.good-agent/prompts", "priority": 50},
            ],
        }

    def _build_search_paths(self) -> list[tuple[int, Path]]:
        """Build prioritized search paths."""
        paths = []
        for entry in self.config.get("search_paths", []):
            path = Path(entry["path"]).expanduser().resolve()
            priority = entry.get("priority", 0)
            if path.exists():
                paths.append((priority, path))

        # Sort by priority (higher first)
        paths.sort(key=lambda x: x[0], reverse=True)
        return paths

    def resolve(self, template_name: str) -> Path | None:
        """Resolve template name to file path."""
        for _, search_path in self.search_paths:
            # Try with .prompt extension
            candidate = search_path / f"{template_name}.prompt"
            if candidate.exists():
                return candidate

            # Try as direct path
            candidate = search_path / template_name
            if candidate.exists() and candidate.is_file():
                return candidate

        return None


# ------------------------------------------------------------------------------
# Jinja2 Integration
# ------------------------------------------------------------------------------


class StorageTemplateLoader(BaseLoader):
    """Jinja2 loader for storage backends."""

    def __init__(self, storage: TemplateStorage):
        self.storage = storage
        self._cache: dict[str, str] = {}

    def get_source(self, environment: Environment, template: str) -> tuple[str, str | None, Any]:
        """Get template source for Jinja2."""
        # Check cache first
        content: str | None
        if template in self._cache:
            content = self._cache[template]
        else:
            # We need to run async code in a sync context
            # Use asyncio.run_coroutine_threadsafe for running loops
            try:
                asyncio.get_running_loop()
                # We're in an async context, but Jinja2 called us synchronously
                # Use a thread to fetch the template
                import threading

                result: str | None = None
                exception: Exception | None = None

                def fetch_in_thread():
                    nonlocal result, exception
                    try:
                        # Create a new event loop for this thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result = new_loop.run_until_complete(self.storage.get(template))
                        finally:
                            new_loop.close()
                    except Exception as e:
                        exception = e

                thread = threading.Thread(target=fetch_in_thread)
                thread.start()
                thread.join(timeout=5.0)  # 5 second timeout

                if exception:
                    raise exception
                content = result

            except RuntimeError:
                # No running loop, we can use asyncio.run directly
                content = asyncio.run(self.storage.get(template))

            if content is None:
                raise TemplateNotFound(template)

            # Cache the content
            self._cache[template] = content

        # Strip frontmatter if present
        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            except Exception:
                pass

        # Return source, filename (None for non-file), uptodate check
        return content, None, lambda: True


class FileTemplateManager:
    """Extended TemplateManager with file-based template support."""

    def __init__(
        self,
        storage: TemplateStorage,
        registry: TemplateRegistry | None = None,
        cache_ttl: int = 300,
        enable_hot_reload: bool = False,
        snapshot_templates: bool = True,
    ):
        self.storage = storage
        self.registry = registry or TemplateRegistry()
        self.cache_ttl = cache_ttl
        self.enable_hot_reload = enable_hot_reload
        self.snapshot_templates = snapshot_templates
        self.snapshots: dict[str, TemplateSnapshot] = {}
        self._template_cache: dict[str, str] = {}

        # Create combined Jinja2 environment
        self.file_loader = StorageTemplateLoader(storage)
        self.env = templating.create_environment(
            loader=ChoiceLoader(
                [
                    self.file_loader,  # Check files first
                    self.registry,  # Fall back to registry
                ]
            )
        )

    async def get_template(self, name: str) -> str:
        """Get template content by name."""
        content = await self.storage.get(name)
        if content is None:
            # Try registry
            try:
                content = self.registry.get_template(name)
            except TemplateNotFound:
                raise TemplateNotFound(f"Template '{name}' not found") from None

        # Create snapshot if enabled
        if self.snapshot_templates and content:
            snapshot = TemplateSnapshot.from_template(name, content)
            self.snapshots[name] = snapshot

        return content

    async def preload_templates(self, template_names: list[str]) -> None:
        """Pre-load templates into cache for sync access."""
        for name in template_names:
            content = await self.storage.get(name)
            if content:
                self.file_loader._cache[name] = content
                self._template_cache[name] = content

    def render(self, template_str: str, context: dict[str, Any] | None = None) -> str:
        """Render a template string with context.

        Note: Templates referenced via include/extends must be pre-loaded
        using preload_templates() or they must exist in the registry.
        """
        template = self.env.from_string(template_str)
        rendered: str = template.render(context or {})
        return rendered

    async def load_template_snapshot(self, snapshot: TemplateSnapshot) -> str:
        """Load a specific template snapshot for replayability."""
        # First check if we have the exact content hash
        storage_key = snapshot.to_storage_key()
        content = await self.storage.get(storage_key)

        if content is None:
            # Fall back to using the embedded content
            content = snapshot.content
            # Optionally store it for future use
            await self.storage.put(
                storage_key,
                content,
                {"snapshot": True, "original_name": snapshot.template_name},
            )

        return content


# ------------------------------------------------------------------------------
# Template Validation
# ------------------------------------------------------------------------------


class TemplateValidator:
    """Validates template syntax and structure."""

    def __init__(self, use_sandbox: bool = True):
        self.env = templating.create_environment(use_sandbox=use_sandbox)

    def validate(self, content: str) -> list[dict]:
        """Validate template content."""
        errors = []

        # Check Jinja2 syntax
        try:
            self.env.parse(content)
        except Exception as e:
            errors.append(
                {
                    "type": "syntax",
                    "message": str(e),
                    "line": getattr(e, "lineno", None),
                }
            )

        # Check for common issues
        if "{{" in content and "}}" not in content:
            errors.append({"type": "syntax", "message": "Unclosed variable tag"})

        if "{%" in content and "%}" not in content:
            errors.append({"type": "syntax", "message": "Unclosed block tag"})

        return errors

    def extract_variables(self, content: str) -> set[str]:
        """Extract all variables used in template."""
        from jinja2 import meta

        try:
            ast = self.env.parse(content)
            return meta.find_undeclared_variables(ast)
        except Exception:
            return set()


# ------------------------------------------------------------------------------
# Development Tools
# ------------------------------------------------------------------------------


class TemplatePreviewServer:
    """Development server for template preview and testing."""

    def __init__(self, storage: TemplateStorage, port: int = 8000):
        self.storage = storage
        self.port = port
        self.manager = FileTemplateManager(storage, enable_hot_reload=True)

    async def preview_template(self, name: str, context: dict | None = None) -> dict:
        """Preview a template with given context."""
        try:
            content = await self.manager.get_template(name)
            rendered = self.manager.render(content, context or {})

            # Extract variables for UI
            validator = TemplateValidator()
            variables = validator.extract_variables(content)

            return {
                "name": name,
                "raw": content,
                "rendered": rendered,
                "variables": list(variables),
                "context": context or {},
            }
        except Exception as e:
            return {"error": str(e), "name": name}


# ------------------------------------------------------------------------------
# Example Usage
# ------------------------------------------------------------------------------


async def example_usage():
    """Example of using the template storage system."""

    # Set up storage chain
    storage = ChainedStorage(
        [
            FileSystemStorage("./prompts"),  # Project templates
            FileSystemStorage("~/.good-agent/prompts"),  # User templates
        ]
    )

    # Create some example templates
    await storage.put(
        "system/analyst",
        """---
version: 1.0.0
description: Analyst system prompt
---

You are an expert analyst focused on {{ domain }}.

Your responsibilities:
{% for resp in responsibilities %}
- {{ resp }}
{% endfor %}

{% if include_examples %}
{% include 'components/examples' %}
{% endif %}
""",
    )

    await storage.put(
        "components/examples",
        """
## Examples

Here are some example analyses:
- Example 1: {{ example1 }}
- Example 2: {{ example2 }}
""",
    )

    # Use templates
    manager = FileTemplateManager(storage)

    # Get and render template
    await manager.get_template("system/analyst")
    rendered = manager.render(
        "{% include 'system/analyst' %}",
        {
            "domain": "political campaigns",
            "responsibilities": [
                "Track spending",
                "Analyze trends",
                "Generate reports",
            ],
            "include_examples": True,
            "example1": "Campaign finance analysis",
            "example2": "Voter demographic study",
        },
    )

    print("Rendered template:")
    print(rendered)
    print("\nSnapshots created:", list(manager.snapshots.keys()))


if __name__ == "__main__":
    # Run example
    asyncio.run(example_usage())
