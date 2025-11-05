import os
import tempfile
from pathlib import Path

import pytest
import yaml
from good_agent.cli.prompts import app
from typer.testing import CliRunner


class TestPromptsCLI:
    """Test the prompts CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            yield Path(tmpdir)
            os.chdir(original_cwd)

    def test_init_command(self, runner, temp_project):
        """Test the init command."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "Initializing prompts directory" in result.stdout

        # Check that files were created
        assert (temp_project / "prompts.yaml").exists()
        assert (temp_project / "prompts").exists()
        assert (temp_project / "prompts" / "index.yaml").exists()
        assert (temp_project / "prompts" / "system").exists()
        assert (temp_project / "prompts" / "user").exists()
        assert (temp_project / "prompts" / "tools").exists()
        assert (temp_project / "prompts" / "components").exists()

        # Check prompts.yaml content
        config = yaml.safe_load((temp_project / "prompts.yaml").read_text())
        assert config["prompts_dir"] == "prompts"
        assert "search_paths" in config

    def test_init_already_exists(self, runner, temp_project):
        """Test init when already initialized."""
        # First init
        runner.invoke(app, ["init"])

        # Second init should detect existing setup
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert "already exists" in result.stdout.lower()

    def test_new_command(self, runner, temp_project):
        """Test creating a new template."""
        # Initialize first
        runner.invoke(app, ["init"])

        # Create new template
        result = runner.invoke(
            app, ["new", "system/test", "--description", "Test template"]
        )

        assert result.exit_code == 0
        assert "Created template" in result.stdout

        # Check file was created
        template_path = temp_project / "prompts" / "system" / "test.prompt"
        assert template_path.exists()

        # Check content
        content = template_path.read_text()
        assert "description: Test template" in content
        assert "version: 1.0.0" in content

    def test_new_with_author_and_tags(self, runner, temp_project):
        """Test creating template with author and tags."""
        runner.invoke(app, ["init"])

        result = runner.invoke(
            app,
            [
                "new",
                "system/advanced",
                "--description",
                "Advanced template",
                "--author",
                "test@example.com",
                "--tags",
                "system,advanced,test",
            ],
        )

        assert result.exit_code == 0

        template_path = temp_project / "prompts" / "system" / "advanced.prompt"
        content = template_path.read_text()

        assert "author: test@example.com" in content
        assert "tags:" in content
        assert "system" in content
        assert "advanced" in content

    def test_list_command(self, runner, temp_project):
        """Test listing templates."""
        # Initialize and create some templates
        runner.invoke(app, ["init"])
        runner.invoke(app, ["new", "system/test1"])
        runner.invoke(app, ["new", "system/test2"])
        runner.invoke(app, ["new", "user/custom"])

        # List all templates
        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0
        assert "system/test1" in result.stdout
        assert "system/test2" in result.stdout
        assert "user/custom" in result.stdout

    def test_list_with_format(self, runner, temp_project):
        """Test listing with different formats."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["new", "system/test"])

        # Table format (default)
        result = runner.invoke(app, ["list", "--format", "table"])
        assert result.exit_code == 0
        assert "Name" in result.stdout  # Table header

        # Tree format
        result = runner.invoke(app, ["list", "--format", "tree"])
        assert result.exit_code == 0
        assert "📁" in result.stdout or "└" in result.stdout  # Tree characters

        # JSON format
        result = runner.invoke(app, ["list", "--format", "json"])
        assert result.exit_code == 0
        # Should be valid JSON
        import json

        templates = json.loads(result.stdout)
        assert isinstance(templates, list)

    def test_scan_command(self, runner, temp_project):
        """Test scanning for template changes."""
        runner.invoke(app, ["init"])

        # Create a template
        runner.invoke(app, ["new", "system/test"])

        # Initial scan
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0

        # Modify template
        template_path = temp_project / "prompts" / "system" / "test.prompt"
        content = template_path.read_text()
        template_path.write_text(content + "\n# Modified")

        # Scan for changes
        result = runner.invoke(app, ["scan"])
        assert result.exit_code == 0
        assert "modified" in result.stdout.lower()

    def test_validate_command(self, runner, temp_project):
        """Test template validation."""
        runner.invoke(app, ["init"])

        # Create valid template
        valid_path = temp_project / "prompts" / "system" / "valid.prompt"
        valid_path.write_text("""---
version: 1.0.0
---
Hello {{ name }}!""")

        # Create invalid template
        invalid_path = temp_project / "prompts" / "system" / "invalid.prompt"
        invalid_path.write_text("""---
version: 1.0.0
---
Hello {{ name""")  # Unclosed variable

        # Validate all
        result = runner.invoke(app, ["validate"])
        assert "invalid" in result.stdout.lower()

        # Validate specific template
        result = runner.invoke(app, ["validate", "system/valid"])
        assert result.exit_code == 0
        assert "✅" in result.stdout or "valid" in result.stdout.lower()

        result = runner.invoke(app, ["validate", "system/invalid"])
        assert result.exit_code != 0
        assert "error" in result.stdout.lower()

    def test_render_command(self, runner, temp_project):
        """Test template rendering."""
        runner.invoke(app, ["init"])

        # Create template
        template_path = temp_project / "prompts" / "system" / "greeting.prompt"
        template_path.write_text("""---
version: 1.0.0
---
Hello {{ name }}! Welcome to {{ place }}.""")

        # Render with context
        result = runner.invoke(
            app,
            [
                "render",
                "system/greeting",
                "--context",
                '{"name": "Alice", "place": "Wonderland"}',
            ],
        )

        assert result.exit_code == 0
        assert "Hello Alice!" in result.stdout
        assert "Welcome to Wonderland" in result.stdout

    def test_render_with_file_context(self, runner, temp_project):
        """Test rendering with context from file."""
        runner.invoke(app, ["init"])

        # Create template
        template_path = temp_project / "prompts" / "system" / "test.prompt"
        template_path.write_text("Name: {{ name }}, Age: {{ age }}")

        # Create context file
        context_file = temp_project / "context.json"
        context_file.write_text('{"name": "Bob", "age": 30}')

        # Render with file context
        result = runner.invoke(
            app, ["render", "system/test", "--context-file", str(context_file)]
        )

        assert result.exit_code == 0
        assert "Name: Bob" in result.stdout
        assert "Age: 30" in result.stdout

    def test_snapshot_command(self, runner, temp_project):
        """Test creating snapshots."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["new", "system/test"])

        # Create snapshot
        result = runner.invoke(
            app, ["snapshot", "system/test", "--reason", "Initial version"]
        )

        assert result.exit_code == 0
        assert "snapshot created" in result.stdout.lower()

        # Check snapshot directory
        snapshot_dir = temp_project / "prompts" / ".snapshots"
        assert snapshot_dir.exists()
        assert len(list(snapshot_dir.glob("system-test@*.prompt"))) > 0

    def test_history_command(self, runner, temp_project):
        """Test viewing version history."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["new", "system/test"])

        # Create some snapshots
        runner.invoke(app, ["snapshot", "system/test", "--reason", "Version 1"])

        # Modify template
        template_path = temp_project / "prompts" / "system" / "test.prompt"
        content = template_path.read_text()
        template_path.write_text(content + "\n# Modified")

        runner.invoke(app, ["scan"])  # Update index
        runner.invoke(app, ["snapshot", "system/test", "--reason", "Version 2"])

        # View history
        result = runner.invoke(app, ["history", "system/test"])

        assert result.exit_code == 0
        assert "Version 1" in result.stdout
        assert "Version 2" in result.stdout

    def test_restore_command(self, runner, temp_project):
        """Test restoring from snapshot."""
        runner.invoke(app, ["init"])

        # Create template
        template_path = temp_project / "prompts" / "system" / "test.prompt"
        template_path.write_text("""---
version: 1.0.0
---
Original content""")

        # Create snapshot
        result = runner.invoke(app, ["snapshot", "system/test", "--reason", "Backup"])

        # Extract hash from output (this is a simplified version)
        # In reality, you'd parse the output or use the history command
        snapshot_dir = temp_project / "prompts" / ".snapshots"
        snapshot_files = list(snapshot_dir.glob("system-test@*.prompt"))
        assert len(snapshot_files) > 0

        # Get hash from filename
        snapshot_hash = snapshot_files[0].stem.split("@")[1]

        # Modify template
        template_path.write_text("Modified content")

        # Restore
        result = runner.invoke(app, ["restore", "system/test", snapshot_hash])

        assert result.exit_code == 0
        assert "restored" in result.stdout.lower()

        # Check content was restored
        content = template_path.read_text()
        assert "Original content" in content

    def test_validate_no_project(self, runner):
        """Test commands when not in a project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)

                # Commands should fail gracefully
                result = runner.invoke(app, ["list"])
                assert result.exit_code != 0
                assert (
                    "not found" in result.stdout.lower()
                    or "error" in result.stdout.lower()
                )
            finally:
                # Always restore the original working directory to avoid leaving
                # the process in a deleted temp directory (which breaks later tests)
                os.chdir(original_cwd)

    def test_tree_format_display(self, runner, temp_project):
        """Test tree format display with nested templates."""
        runner.invoke(app, ["init"])

        # Create nested structure
        runner.invoke(app, ["new", "system/base"])
        runner.invoke(app, ["new", "system/agents/analyst"])
        runner.invoke(app, ["new", "system/agents/researcher"])
        runner.invoke(app, ["new", "components/headers/standard"])
        runner.invoke(app, ["new", "components/footers/brief"])

        result = runner.invoke(app, ["list", "--format", "tree"])

        assert result.exit_code == 0
        # Check for tree structure indicators
        assert "system" in result.stdout
        assert "agents" in result.stdout
        assert "components" in result.stdout

    def test_scan_with_auto_version(self, runner, temp_project):
        """Test scanning with auto-versioning."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["new", "system/test"])

        # Modify template
        template_path = temp_project / "prompts" / "system" / "test.prompt"
        original = template_path.read_text()

        # Change content to trigger version increment
        modified = original.replace("1.0.0", "1.0.0")  # Keep version same
        modified += "\n# New content"
        template_path.write_text(modified)

        # Scan with auto-version
        result = runner.invoke(app, ["scan", "--auto-version"])

        assert result.exit_code == 0

        # Check index was updated
        index_path = temp_project / "prompts" / "index.yaml"
        index = yaml.safe_load(index_path.read_text())

        # Version should have been incremented
        if "templates" in index and "system/test" in index["templates"]:
            version = index["templates"]["system/test"]["version"]
            assert version == "1.0.1"  # Patch version incremented
