import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TemplateMetadata(BaseModel):
    """Metadata for a single template file."""

    path: str
    name: str
    content_hash: str
    file_size: int
    last_modified: datetime
    version: str
    semantic_version: str | None = None
    description: str | None = None
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    frontmatter: dict[str, Any] = Field(default_factory=dict)

    # Version history tracking
    previous_hash: str | None = None
    version_history: list[dict] = Field(default_factory=list)

    def increment_version(self) -> str:
        """Auto-increment version based on change detection."""
        if not self.version:
            self.version = "1.0.0"
            return self.version

        # Parse current version
        parts = self.version.split(".")
        if len(parts) == 3:
            major, minor, patch = parts
            # Auto-increment patch version for content changes
            self.version = f"{major}.{minor}.{int(patch) + 1}"
        else:
            # Fallback to simple increment
            self.version = "1.0.0"

        return self.version


class TemplateIndex:
    """Manages the template index file and tracks changes."""

    def __init__(self, prompts_dir: Path, index_file: str = "index.yaml"):
        self.prompts_dir = Path(prompts_dir)
        self.index_file = self.prompts_dir / index_file
        self.templates: dict[str, TemplateMetadata] = {}
        self._load_index()

    @staticmethod
    def _normalize_name(value: str) -> str:
        """Normalize template keys to a consistent POSIX-style format."""
        return value.replace("\\", "/")

    def _load_index(self) -> None:
        """Load existing index from file."""
        if self.index_file.exists():
            try:
                data = yaml.safe_load(self.index_file.read_text())
                if data and "templates" in data:
                    for name, meta in data["templates"].items():
                        meta_name = meta.get("name", name)
                        meta["name"] = self._normalize_name(meta_name)
                        if "path" in meta:
                            meta["path"] = self._normalize_name(str(meta["path"]))
                        # Convert datetime strings back to datetime objects
                        if "last_modified" in meta:
                            meta["last_modified"] = datetime.fromisoformat(meta["last_modified"])
                        if meta.get("version_history"):
                            for entry in meta["version_history"]:
                                timestamp = entry.get("timestamp")
                                if isinstance(timestamp, str):
                                    try:
                                        entry["timestamp"] = datetime.fromisoformat(timestamp)
                                    except ValueError:
                                        # Leave as string if parsing fails
                                        entry["timestamp"] = timestamp
                        normalized_name = meta["name"]
                        self.templates[normalized_name] = TemplateMetadata(**meta)
            except Exception as e:
                logger.error(f"Failed to load index: {e}")
                self.templates = {}

    def _save_index(self) -> None:
        """Save index to file."""
        try:
            # Convert to serializable format
            data: dict[str, Any] = {
                "version": "1.0",
                "updated": datetime.now().isoformat(),
                "templates": {},
            }

            for name, meta in self.templates.items():
                meta_dict = meta.model_dump()
                # Convert datetime to ISO format
                meta_dict["last_modified"] = meta_dict["last_modified"].isoformat()
                if meta_dict.get("version_history"):
                    for entry in meta_dict["version_history"]:
                        if "timestamp" in entry:
                            entry["timestamp"] = entry["timestamp"].isoformat()
                data["templates"][name] = meta_dict

            self.index_file.parent.mkdir(parents=True, exist_ok=True)
            self.index_file.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    def _calculate_hash(self, content: str) -> str:
        """Calculate content hash for a template."""
        return hashlib.sha256(content.encode()).hexdigest()[:12]

    def _extract_frontmatter(self, content: str) -> tuple[dict, str]:
        """Extract YAML frontmatter from template content."""
        if content.startswith("---"):
            try:
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    content = parts[2].strip()
                    return frontmatter, content
            except Exception:
                pass
        return {}, content

    def scan_templates(self, auto_version: bool = True) -> dict[str, str]:
        """Scan for template files and detect changes.

        Returns:
            Dict mapping template names to their change status
            ('new', 'modified', 'unchanged', 'deleted')
        """
        changes = {}
        found_templates = set()

        # Scan all .prompt files (excluding .versions directory)
        for prompt_file in self.prompts_dir.rglob("*.prompt"):
            # Skip files in the .versions directory
            if ".versions" in str(prompt_file):
                continue
            relative_path = prompt_file.relative_to(self.prompts_dir)
            relative_path_posix = relative_path.as_posix()
            template_name = relative_path.with_suffix("").as_posix()
            template_name = self._normalize_name(template_name)
            found_templates.add(template_name)

            # Read file content
            content = prompt_file.read_text()
            content_hash = self._calculate_hash(content)

            # Extract frontmatter
            frontmatter, _ = self._extract_frontmatter(content)

            # Get file stats
            stats = prompt_file.stat()

            # Check if template exists in index
            if template_name in self.templates:
                existing = self.templates[template_name]
                existing.path = relative_path_posix
                existing.name = template_name

                # Check for modifications
                if existing.content_hash != content_hash:
                    changes[template_name] = "modified"

                    if auto_version:
                        # Store version history
                        existing.version_history.append(
                            {
                                "version": existing.version,
                                "hash": existing.content_hash,
                                "timestamp": existing.last_modified,
                            }
                        )

                        # Update metadata
                        existing.previous_hash = existing.content_hash
                        existing.content_hash = content_hash
                        existing.file_size = stats.st_size
                        existing.last_modified = datetime.fromtimestamp(stats.st_mtime)
                        existing.increment_version()

                        # Update from frontmatter
                        if "version" in frontmatter:
                            existing.semantic_version = frontmatter["version"]
                        if "description" in frontmatter:
                            existing.description = frontmatter["description"]
                        if "author" in frontmatter:
                            existing.author = frontmatter["author"]
                        if "tags" in frontmatter:
                            existing.tags = frontmatter.get("tags", [])
                        existing.frontmatter = frontmatter

                    logger.info(f"Template '{template_name}' modified (v{existing.version})")
                else:
                    changes[template_name] = "unchanged"
            else:
                # New template
                changes[template_name] = "new"

                metadata = TemplateMetadata(
                    path=relative_path_posix,
                    name=template_name,
                    content_hash=content_hash,
                    file_size=stats.st_size,
                    last_modified=datetime.fromtimestamp(stats.st_mtime),
                    version="1.0.0",
                    semantic_version=frontmatter.get("version"),
                    description=frontmatter.get("description"),
                    author=frontmatter.get("author"),
                    tags=frontmatter.get("tags", []),
                    frontmatter=frontmatter,
                )

                self.templates[template_name] = metadata
                logger.info(f"New template '{template_name}' added (v1.0.0)")

        # Check for deleted templates
        for template_name in list(self.templates.keys()):
            if template_name not in found_templates:
                changes[template_name] = "deleted"
                if auto_version:
                    # Mark as deleted but keep in history
                    self.templates[template_name].tags.append("deleted")
                    logger.warning(f"Template '{template_name}' deleted")

        # Save updated index
        if auto_version and changes:
            self._save_index()

        return changes

    def get_template_info(self, name: str) -> TemplateMetadata | None:
        """Get metadata for a specific template."""
        # Try exact match first
        normalized = self._normalize_name(name)
        if normalized in self.templates:
            return self.templates[normalized]

        # Try case variations
        for variant in [normalized.replace("-", "_"), normalized.replace("_", "-")]:
            if variant in self.templates:
                return self.templates[variant]

        return None

    def list_templates(
        self, tags: list[str] | None = None, prefix: str | None = None
    ) -> list[TemplateMetadata]:
        """List all templates, optionally filtered by tags or name prefix."""
        templates = list(self.templates.values())

        # Filter by prefix if provided
        if prefix:
            normalized_prefix = self._normalize_name(prefix)
            templates = [t for t in templates if t.name.startswith(normalized_prefix)]

        # Filter by tags if provided
        if tags:
            templates = [t for t in templates if any(tag in t.tags for tag in tags)]

        # Sort by name
        return sorted(templates, key=lambda t: t.name)

    def get_version_history(self, name: str) -> list[dict]:
        """Get version history for a template."""
        template = self.get_template_info(name)
        if template:
            return template.version_history
        return []

    def export_manifest(self) -> dict:
        """Export a manifest of all templates for distribution."""
        manifest: dict[str, Any] = {
            "version": "1.0",
            "generated": datetime.now().isoformat(),
            "templates": {},
        }

        for name, meta in self.templates.items():
            manifest["templates"][name] = {
                "version": meta.version,
                "semantic_version": meta.semantic_version,
                "hash": meta.content_hash,
                "description": meta.description,
                "author": meta.author,
                "tags": meta.tags,
            }

        return manifest


class TemplateVersionManager:
    """Manages template versions and snapshots."""

    def __init__(self, prompts_dir: Path, versions_dir: Path | None = None):
        self.prompts_dir = Path(prompts_dir)
        self.versions_dir = versions_dir or (self.prompts_dir / ".versions")
        self.index = TemplateIndex(prompts_dir)

    def create_snapshot(self, template_name: str, reason: str = "") -> str | None:
        """Create a versioned snapshot of a template.

        Returns:
            Version identifier (hash) of the snapshot
        """
        template_path = None
        for ext in [".prompt", ""]:
            candidate = self.prompts_dir / f"{template_name}{ext}"
            if candidate.exists():
                template_path = candidate
                break

        if not template_path:
            logger.error(f"Template '{template_name}' not found")
            return None

        content = template_path.read_text()
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]

        # Create version directory
        version_dir = self.versions_dir / template_name
        version_dir.mkdir(parents=True, exist_ok=True)

        # Save snapshot
        snapshot_file = version_dir / f"{content_hash}.prompt"
        snapshot_file.write_text(content)

        # Save metadata
        metadata = {
            "template": template_name,
            "hash": content_hash,
            "timestamp": datetime.now().isoformat(),
            "reason": reason,
            "original_path": str(template_path.relative_to(self.prompts_dir)),
        }

        meta_file = version_dir / f"{content_hash}.meta.json"
        meta_file.write_text(json.dumps(metadata, indent=2))

        logger.info(f"Created snapshot {content_hash} for '{template_name}'")
        return content_hash

    def restore_snapshot(self, template_name: str, version_hash: str) -> bool:
        """Restore a template from a snapshot."""
        snapshot_file = self.versions_dir / template_name / f"{version_hash}.prompt"

        if not snapshot_file.exists():
            logger.error(f"Snapshot {version_hash} not found for '{template_name}'")
            return False

        # Backup current version first
        self.create_snapshot(template_name, f"Before restore to {version_hash}")

        # Restore snapshot
        target_path = self.prompts_dir / f"{template_name}.prompt"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(snapshot_file.read_text())

        logger.info(f"Restored '{template_name}' to version {version_hash}")
        return True

    def list_snapshots(self, template_name: str) -> list[dict]:
        """List all snapshots for a template."""
        version_dir = self.versions_dir / template_name

        if not version_dir.exists():
            return []

        snapshots = []
        for meta_file in version_dir.glob("*.meta.json"):
            metadata = json.loads(meta_file.read_text())
            snapshots.append(metadata)

        # Sort by timestamp (newest first)
        snapshots.sort(key=lambda x: x["timestamp"], reverse=True)
        return snapshots
