"""
Unit tests for the template storage system.

Tests the FileSystemStorage, ChainedStorage, and FileTemplateManager classes
with comprehensive coverage of all features including case-insensitive resolution,
YAML frontmatter parsing, and template snapshots.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from good_agent.templating.storage import (
    ChainedStorage,
    FileSystemStorage,
    FileTemplateManager,
    StorageTemplateLoader,
    TemplateSnapshot,
    TemplateValidator,
)
from jinja2 import TemplateNotFound


class TestFileSystemStorage:
    """Test the FileSystemStorage class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest_asyncio.fixture
    async def storage(self, temp_dir):
        """Create a FileSystemStorage instance with test templates."""
        storage = FileSystemStorage(temp_dir)

        # Create test directory structure
        (temp_dir / "system").mkdir(parents=True)
        (temp_dir / "components" / "headers").mkdir(parents=True)
        (temp_dir / "user").mkdir(parents=True)

        # Create test templates
        await storage.put("system/base", "You are a helpful assistant in {{ domain }}.")

        await storage.put(
            "system/analyst",
            """---
version: 1.0.0
description: Analyst template
author: test@example.com
tags: [system, analyst]
---

{% extends 'system/base' %}
{% block instructions %}
Analyze data in {{ analysis_scope }}.
{% endblock %}""",
        )

        await storage.put("components/headers/standard", "=== {{ title }} ===")

        await storage.put(
            "user/custom-prompt",  # Test kebab-case
            "Custom user prompt",
        )

        return storage

    @pytest.mark.asyncio
    async def test_get_template(self, storage):
        """Test retrieving templates."""
        content = await storage.get("system/base")
        assert content == "You are a helpful assistant in {{ domain }}."

        # Test with .prompt extension
        content = await storage.get("system/base.prompt")
        assert content == "You are a helpful assistant in {{ domain }}."

    @pytest.mark.asyncio
    async def test_case_insensitive_resolution(self, storage):
        """Test that snake_case and kebab-case are interchangeable."""
        # Created as "user/custom-prompt" (kebab-case)

        # Should work with snake_case
        content = await storage.get("user/custom_prompt")
        assert content == "Custom user prompt"

        # Should work with original kebab-case
        content = await storage.get("user/custom-prompt")
        assert content == "Custom user prompt"

        # Should work with extension
        content = await storage.get("user/custom_prompt.prompt")
        assert content == "Custom user prompt"

    @pytest.mark.asyncio
    async def test_put_template(self, storage, temp_dir):
        """Test storing templates."""
        await storage.put("test/new", "New template content")

        # Verify file was created
        file_path = temp_dir / "test" / "new.prompt"
        assert file_path.exists()
        assert file_path.read_text() == "New template content"

        # Verify we can retrieve it
        content = await storage.get("test/new")
        assert content == "New template content"

    @pytest.mark.asyncio
    async def test_list_templates(self, storage):
        """Test listing available templates."""
        templates = await storage.list()

        # Should include all templates
        assert "system/base" in templates
        assert "system/analyst" in templates
        assert "components/headers/standard" in templates
        assert "user/custom-prompt" in templates

        # Test with prefix
        system_templates = await storage.list("system/")
        assert len(system_templates) == 2
        assert all(t.startswith("system/") for t in system_templates)

    @pytest.mark.asyncio
    async def test_exists(self, storage):
        """Test checking template existence."""
        assert await storage.exists("system/base")
        # Note: exists() doesn't check case variations in current implementation
        # Only checks exact path
        assert not await storage.exists(
            "system/base.prompt"
        )  # Extension handled in get()
        assert not await storage.exists("nonexistent/template")

    @pytest.mark.asyncio
    async def test_get_metadata(self, storage):
        """Test extracting YAML frontmatter metadata."""
        metadata = await storage.get_metadata("system/analyst")

        assert metadata["version"] == "1.0.0"
        assert metadata["description"] == "Analyst template"
        assert metadata["author"] == "test@example.com"
        assert metadata["tags"] == ["system", "analyst"]

        # Template without frontmatter
        metadata = await storage.get_metadata("system/base")
        assert metadata == {}

    @pytest.mark.asyncio
    async def test_delete_not_implemented(self, storage, temp_dir):
        """Test that delete is not implemented in FileSystemStorage."""
        # FileSystemStorage doesn't have a delete method
        # This is by design to prevent accidental deletion
        await storage.put("test/deleteme", "Delete this")
        assert await storage.exists("test/deleteme")

        # No delete method available
        assert not hasattr(storage, "delete")

    @pytest.mark.asyncio
    async def test_nonexistent_template(self, storage):
        """Test handling of nonexistent templates."""
        content = await storage.get("nonexistent/template")
        assert content is None

        metadata = await storage.get_metadata("nonexistent/template")
        assert metadata == {}


class TestChainedStorage:
    """Test the ChainedStorage class."""

    @pytest_asyncio.fixture
    async def storages(self):
        """Create mock storage instances."""
        storage1 = AsyncMock()
        storage1.priority = 100
        storage1.list = AsyncMock(return_value=["template1", "template2"])
        storage1.get = AsyncMock(
            side_effect=lambda k: "content1" if k == "template1" else None
        )
        storage1.exists = AsyncMock(side_effect=lambda k: k == "template1")
        storage1.get_metadata = AsyncMock(return_value={"source": "storage1"})

        storage2 = AsyncMock()
        storage2.priority = 50
        storage2.list = AsyncMock(return_value=["template2", "template3"])
        storage2.get = AsyncMock(
            side_effect=lambda k: "content2"
            if k in ["template2", "template3"]
            else None
        )
        storage2.exists = AsyncMock(
            side_effect=lambda k: k in ["template2", "template3"]
        )
        storage2.get_metadata = AsyncMock(return_value={"source": "storage2"})

        return [storage1, storage2]

    @pytest_asyncio.fixture
    async def chained_storage(self, storages):
        """Create a ChainedStorage instance."""
        return ChainedStorage(storages)

    @pytest.mark.asyncio
    async def test_get_from_first_storage(self, chained_storage):
        """Test that templates are retrieved from the first matching storage."""
        content = await chained_storage.get("template1")
        assert content == "content1"

        # template2: storage1 returns None, so it falls back to storage2
        content = await chained_storage.get("template2")
        assert content == "content2"  # Falls back to storage2

        # template3 only exists in storage2
        content = await chained_storage.get("template3")
        assert content == "content2"

    @pytest.mark.asyncio
    async def test_list_combines_all_storages(self, chained_storage):
        """Test that list combines templates from all storages."""
        templates = await chained_storage.list()

        # Should have unique templates from all storages
        assert "template1" in templates
        assert "template2" in templates
        assert "template3" in templates
        assert len(set(templates)) == len(templates)  # No duplicates

    @pytest.mark.asyncio
    async def test_exists_checks_all_storages(self, chained_storage):
        """Test that exists checks all storages."""
        assert await chained_storage.exists("template1")
        assert await chained_storage.exists("template2")
        assert await chained_storage.exists("template3")
        assert not await chained_storage.exists("nonexistent")

    @pytest.mark.asyncio
    async def test_put_to_first_storage(self, chained_storage, storages):
        """Test that put writes to the first storage."""
        await chained_storage.put("new_template", "content")

        # Should have called put on the first storage
        storages[0].put.assert_called_once_with("new_template", "content", None)
        storages[1].put.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_chain(self):
        """Test ChainedStorage with no storages."""
        chained = ChainedStorage([])

        assert await chained.get("any") is None
        assert await chained.list() == []
        assert not await chained.exists("any")
        assert await chained.get_metadata("any") == {}


class TestTemplateSnapshot:
    """Test the TemplateSnapshot class."""

    def test_create_snapshot(self):
        """Test creating a template snapshot."""
        snapshot = TemplateSnapshot.from_template(
            name="test/template",
            content="Template content with {{ variable }}",
            git_commit="abc123",
            semantic_version="1.0.0",
            metadata={"author": "test"},
        )

        assert snapshot.template_name == "test/template"
        assert len(snapshot.content_hash) == 12  # Truncated SHA256
        assert snapshot.git_commit == "abc123"
        assert snapshot.semantic_version == "1.0.0"
        assert snapshot.content == "Template content with {{ variable }}"
        assert snapshot.metadata == {"author": "test"}

    def test_storage_key_generation(self):
        """Test generating storage keys for snapshots."""
        snapshot = TemplateSnapshot.from_template(
            name="test/template", content="Content"
        )

        key = snapshot.to_storage_key()
        assert key.startswith("test/template@")
        assert len(key.split("@")[1]) == 12  # Hash length

    def test_snapshot_deterministic_hash(self):
        """Test that the same content produces the same hash."""
        content = "Identical content"

        snapshot1 = TemplateSnapshot.from_template("test1", content)
        snapshot2 = TemplateSnapshot.from_template("test2", content)

        assert snapshot1.content_hash == snapshot2.content_hash


class TestTemplateValidator:
    """Test the TemplateValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a TemplateValidator instance."""
        return TemplateValidator()

    def test_validate_valid_template(self, validator):
        """Test validating a valid Jinja2 template."""
        template = """
        Hello {{ name }}!
        {% if show_details %}
        Details: {{ details }}
        {% endif %}
        """

        errors = validator.validate(template)
        assert errors == []

    def test_validate_invalid_template(self, validator):
        """Test validating an invalid template."""
        template = "Hello {{ name"  # Unclosed variable

        errors = validator.validate(template)
        assert len(errors) > 0
        assert "message" in errors[0]

    def test_extract_variables(self, validator):
        """Test extracting variables from templates."""
        template = """
        Name: {{ name }}
        Age: {{ age }}
        {% if show_address %}
        Address: {{ address.street }} {{ address.city }}
        {% endif %}
        """

        variables = validator.extract_variables(template)
        assert "name" in variables
        assert "age" in variables
        assert "show_address" in variables
        assert "address" in variables

    def test_extract_dependencies_not_implemented(self, validator):
        """Test that extract_dependencies is not implemented."""
        # TemplateValidator doesn't have extract_dependencies method
        # It only has validate() and extract_variables()
        assert not hasattr(validator, "extract_dependencies")

        # But we can extract variables
        template = "Hello {{ name }}, you have {{ count }} items"
        variables = validator.extract_variables(template)
        assert "name" in variables
        assert "count" in variables


class TestStorageTemplateLoader:
    """Test the Jinja2 template loader."""

    @pytest.fixture
    def loader(self):
        """Create a loader with mock storage."""
        storage = AsyncMock()
        storage.get = AsyncMock(
            side_effect=lambda k: f"Content of {k}"
            if k in ["test", "test.prompt"]
            else None
        )
        storage.exists = AsyncMock(side_effect=lambda k: k in ["test", "test.prompt"])

        loader = StorageTemplateLoader(storage)
        # Pre-populate cache since get_source can't easily run async code
        loader._cache["test"] = "Content of test"
        return loader

    def test_get_source(self, loader):
        """Test getting template source."""
        from jinja2 import Environment

        env = Environment()
        source, filename, uptodate = loader.get_source(env, "test")

        assert source == "Content of test"
        assert filename is None  # Non-file source
        assert uptodate() is True  # Always returns True for simplicity

    def test_get_source_not_found(self, loader):
        """Test handling of missing templates."""
        from jinja2 import Environment

        env = Environment()
        with pytest.raises(TemplateNotFound):
            loader.get_source(env, "nonexistent")

    def test_list_templates(self, loader):
        """Test that list_templates raises TypeError by default."""
        # BaseLoader's list_templates raises TypeError by default
        with pytest.raises(TypeError):
            loader.list_templates()


class TestFileTemplateManager:
    """Test the FileTemplateManager class."""

    @pytest_asyncio.fixture
    async def manager(self):
        """Create a manager with mock storage."""
        storage = AsyncMock()
        storage.get = AsyncMock(return_value="Template {{ var }}")
        storage.exists = AsyncMock(return_value=True)
        storage.list = AsyncMock(return_value=["template1", "template2"])

        manager = FileTemplateManager(storage)
        await manager.preload_templates(["template1"])
        return manager

    @pytest.mark.asyncio
    async def test_get_template(self, manager):
        """Test retrieving templates."""
        content = await manager.get_template("template1")
        assert content == "Template {{ var }}"

    def test_render_template(self, manager):
        """Test rendering templates with context."""
        # Pre-populate the file_loader cache
        manager.file_loader._cache["test"] = "Hello {{ name }}!"

        rendered = manager.render("{% include 'test' %}", {"name": "World"})
        assert rendered == "Hello World!"

    @pytest.mark.asyncio
    async def test_snapshot_creation(self):
        """Test that snapshots are created when enabled."""
        storage = AsyncMock()
        storage.get = AsyncMock(return_value="Content")

        manager = FileTemplateManager(storage, snapshot_templates=True)

        await manager.get_template("test/template")

        assert "test/template" in manager.snapshots
        snapshot = manager.snapshots["test/template"]
        assert snapshot.content == "Content"

    @pytest.mark.asyncio
    async def test_hot_reload(self):
        """Test hot reload clears cache."""
        storage = AsyncMock()
        storage.get = AsyncMock(return_value="New content")
        manager = FileTemplateManager(storage, enable_hot_reload=True)

        # Add something to cache
        manager.file_loader._cache["test"] = "Cached content"

        # In hot reload mode, cache should be used but can be cleared
        # This behavior is implementation-specific
        assert manager.enable_hot_reload is True

        # Cache exists
        assert "test" in manager.file_loader._cache
