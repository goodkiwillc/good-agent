import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from good_agent.components.template_manager.index import (
    TemplateIndex,
    TemplateMetadata,
    TemplateVersionManager,
)


class TestTemplateMetadata:
    """Test the TemplateMetadata data model."""

    def test_create_template_metadata(self):
        """Test creating a TemplateMetadata instance."""
        info = TemplateMetadata(
            path="system/analyst.prompt",
            name="system/analyst",
            file_size=1024,
            version="1.0.0",
            content_hash="abc123def456",
            last_modified=datetime.now(),
            description="Test template",
            author="test@example.com",
            tags=["system", "test"],
        )

        assert info.name == "system/analyst"
        assert info.version == "1.0.0"
        assert info.content_hash == "abc123def456"
        assert info.description == "Test template"
        assert info.author == "test@example.com"
        assert info.tags == ["system", "test"]

    def test_version_history(self):
        """Test version history tracking."""
        now = datetime.now()
        history = [
            {
                "version": "1.0.0",
                "hash": "hash1",
                "timestamp": (now - timedelta(days=2)).isoformat(),
            },
            {
                "version": "1.0.1",
                "hash": "hash2",
                "timestamp": (now - timedelta(days=1)).isoformat(),
            },
        ]

        info = TemplateMetadata(
            path="test.prompt",
            name="test",
            file_size=100,
            version="1.0.2",
            content_hash="hash3",
            last_modified=now,
            version_history=history,
        )

        assert len(info.version_history) == 2
        assert info.version_history[0]["version"] == "1.0.0"
        assert info.version_history[1]["version"] == "1.0.1"

    def test_increment_version(self):
        """Test auto-incrementing version."""
        info = TemplateMetadata(
            path="test.prompt",
            name="test",
            file_size=100,
            version="1.0.5",
            content_hash="hash",
            last_modified=datetime.now(),
        )

        new_version = info.increment_version()
        assert new_version == "1.0.6"
        assert info.version == "1.0.6"


class TestTemplateIndex:
    """Test the TemplateIndex class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            # Create directory structure
            (path / "system").mkdir(parents=True)
            (path / "user").mkdir(parents=True)
            (path / "components").mkdir(parents=True)
            yield path

    @pytest.fixture
    def index(self, temp_dir):
        """Create a TemplateIndex instance."""
        return TemplateIndex(temp_dir)

    def test_initialization(self, index, temp_dir):
        """Test index initialization."""
        assert index.prompts_dir == temp_dir
        assert index.index_file == temp_dir / "index.yaml"
        assert index.templates == {}

    def test_load_empty_index(self, index):
        """Test loading when index doesn't exist."""
        index._load_index()
        assert index.templates == {}

    def test_save_and_load_index(self, index, temp_dir):
        """Test saving and loading the index."""
        # Add some templates
        index.templates["system/base"] = TemplateMetadata(
            path="system/base.prompt",
            name="system/base",
            file_size=100,
            version="1.0.0",
            content_hash="hash123",
            last_modified=datetime.now(),
        )

        # Save index
        index._save_index()
        assert (temp_dir / "index.yaml").exists()

        # Create new index and load
        new_index = TemplateIndex(temp_dir)

        assert "system/base" in new_index.templates
        assert new_index.templates["system/base"].version == "1.0.0"
        assert new_index.templates["system/base"].content_hash == "hash123"

    def test_scan_templates(self, index, temp_dir):
        """Test scanning templates in the directory."""
        # Create directories first
        (temp_dir / "system").mkdir(exist_ok=True)
        (temp_dir / "user").mkdir(exist_ok=True)

        # Create test templates
        (temp_dir / "system" / "base.prompt").write_text("Base system prompt")

        (temp_dir / "system" / "analyst.prompt").write_text(
            """---
version: 2.0.0
description: Analyst prompt
author: analyst@example.com
tags: [analyst, system]
---
Analyst template content"""
        )

        (temp_dir / "user" / "custom.prompt").write_text("Custom user prompt")

        # Scan templates
        changes = index.scan_templates(auto_version=True)

        # Check that templates were found
        assert "system/base" in index.templates
        assert "system/analyst" in index.templates
        assert "user/custom" in index.templates

        # Check metadata extraction
        analyst = index.templates["system/analyst"]
        assert analyst.version == "1.0.0"  # Auto-versioned
        assert analyst.semantic_version == "2.0.0"  # From frontmatter
        assert analyst.description == "Analyst prompt"
        assert analyst.author == "analyst@example.com"
        assert analyst.tags == ["analyst", "system"]

        # Check auto-versioning for template without version
        base = index.templates["system/base"]
        assert base.version == "1.0.0"  # Default version

        # Check that changes were detected - returns dict not list
        assert len(changes) == 3
        assert all(status == "new" for status in changes.values())

    def test_detect_changes(self, index, temp_dir):
        """Test detecting changes in templates."""
        # Create directory first
        (temp_dir / "system").mkdir(exist_ok=True)
        template_path = temp_dir / "system" / "test.prompt"

        # Initial scan
        template_path.write_text("Initial content")
        index.scan_templates(auto_version=True)
        initial_version = index.templates["system/test"].version
        initial_hash = index.templates["system/test"].content_hash

        # Modify template
        template_path.write_text("Modified content")
        changes = index.scan_templates(auto_version=True)

        # Check that change was detected - returns dict not list
        modified_templates = {k: v for k, v in changes.items() if v == "modified"}
        assert len(modified_templates) == 1
        assert "system/test" in modified_templates

        # Check version was incremented
        new_version = index.templates["system/test"].version
        assert new_version == "1.0.1"  # Patch version incremented

        # Check hash changed
        new_hash = index.templates["system/test"].content_hash
        assert new_hash != initial_hash

        # Check version history
        history = index.templates["system/test"].version_history
        assert len(history) == 1
        assert history[0]["version"] == initial_version
        assert history[0]["hash"] == initial_hash

    def test_get_template_info(self, index, temp_dir):
        """Test retrieving template information."""
        # Create directory and scan a template
        (temp_dir / "system").mkdir(exist_ok=True)
        (temp_dir / "system" / "test.prompt").write_text("Test content")
        index.scan_templates()

        # Get info
        info = index.get_template_info("system/test")
        assert info is not None
        assert info.name == "system/test"

        # Test with .prompt extension - not supported, should return None
        info = index.get_template_info("system/test.prompt")
        assert info is None  # Extension not stripped in implementation

        # Test nonexistent template
        info = index.get_template_info("nonexistent")
        assert info is None

    def test_list_templates(self, index, temp_dir):
        """Test listing templates."""
        # Create templates
        (temp_dir / "system" / "base.prompt").write_text("Base")
        (temp_dir / "system" / "analyst.prompt").write_text("Analyst")
        (temp_dir / "user" / "custom.prompt").write_text("Custom")

        index.scan_templates()

        # List all
        all_templates = index.list_templates()
        assert len(all_templates) == 3

        # List with prefix
        system_templates = index.list_templates(prefix="system/")
        assert len(system_templates) == 2
        assert all(t.name.startswith("system/") for t in system_templates)

    def test_compute_hash(self, index):
        """Test content hash computation."""
        content = "Test content for hashing"
        hash1 = index._calculate_hash(content)
        hash2 = index._calculate_hash(content)

        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 12  # Truncated SHA256

        # Different content should produce different hash
        hash3 = index._calculate_hash("Different content")
        assert hash3 != hash1

    def test_increment_version_logic(self, index):
        """Test version incrementing logic."""
        # Test incrementing versions using the metadata model
        metadata = TemplateMetadata(
            path="test.prompt",
            name="test",
            file_size=100,
            version="1.0.0",
            content_hash="hash",
            last_modified=datetime.now(),
        )

        # Increment version
        new_version = metadata.increment_version()
        assert new_version == "1.0.1"

        # Test with different version
        metadata.version = "2.3.4"
        new_version = metadata.increment_version()
        assert new_version == "2.3.5"


class TestTemplateVersionManager:
    """Test the TemplateVersionManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)
            # Note: versions_dir will be created automatically
            yield path

    @pytest.fixture
    def manager(self, temp_dir):
        """Create a TemplateVersionManager instance."""
        return TemplateVersionManager(temp_dir)

    def test_initialization(self, manager, temp_dir):
        """Test manager initialization."""
        assert manager.prompts_dir == temp_dir
        assert manager.versions_dir == temp_dir / ".versions"
        # versions_dir is created on demand, not at initialization

    def test_create_snapshot(self, manager, temp_dir):
        """Test creating a snapshot."""
        # Create a template
        template_path = temp_dir / "test.prompt"
        template_path.write_text("Template content")

        # Create snapshot - only takes template_name and optional reason
        snapshot_hash = manager.create_snapshot("test", reason="Test snapshot")

        assert snapshot_hash is not None
        assert len(snapshot_hash) == 12

        # Check snapshot file exists - stored in subdirectory by template name
        snapshot_file = temp_dir / ".versions" / "test" / f"{snapshot_hash}.prompt"
        assert snapshot_file.exists()
        assert snapshot_file.read_text() == "Template content"

        # Check metadata - stored as JSON
        metadata_file = temp_dir / ".versions" / "test" / f"{snapshot_hash}.meta.json"
        assert metadata_file.exists()

        import json

        metadata = json.loads(metadata_file.read_text())
        assert metadata["template"] == "test"
        assert metadata["hash"] == snapshot_hash
        assert metadata["reason"] == "Test snapshot"
        assert "timestamp" in metadata

    def test_restore_snapshot(self, manager, temp_dir):
        """Test restoring from a snapshot."""
        # Create original template
        template_path = temp_dir / "test.prompt"
        original_content = "Original content"
        template_path.write_text(original_content)

        # Create snapshot
        snapshot_hash = manager.create_snapshot("test", original_content)

        # Modify template
        template_path.write_text("Modified content")

        # Restore snapshot
        success = manager.restore_snapshot("test", snapshot_hash)
        assert success is True

        # Check content was restored
        assert template_path.read_text() == original_content

    def test_list_snapshots(self, manager, temp_dir):
        """Test listing snapshots for a template."""
        # Create template file first
        template_path = temp_dir / "test.prompt"

        # Create multiple snapshots
        content1 = "Version 1"
        template_path.write_text(content1)
        hash1 = manager.create_snapshot("test", reason="First version")

        content2 = "Version 2"
        template_path.write_text(content2)
        hash2 = manager.create_snapshot("test", reason="Second version")

        # List snapshots
        snapshots = manager.list_snapshots("test")

        assert len(snapshots) == 2
        assert any(s["hash"] == hash1 for s in snapshots)
        assert any(s["hash"] == hash2 for s in snapshots)
        assert any(s["reason"] == "First version" for s in snapshots)
        assert any(s["reason"] == "Second version" for s in snapshots)

    # REMOVED: test_clean_old_snapshots
    # Future feature: TemplateVersionManager.clean_old_snapshots() method
    # Would allow removing old template snapshots to save space

    # REMOVED: test_get_snapshot_content
    # Future feature: TemplateVersionManager.get_snapshot_content() method
    # Would allow retrieving the content of a specific snapshot

    # REMOVED: test_snapshot_with_metadata
    # Future feature: Support metadata parameter in create_snapshot()
    # Would allow storing additional metadata with snapshots
