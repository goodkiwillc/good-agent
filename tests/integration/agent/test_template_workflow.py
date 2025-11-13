import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
import yaml
from good_agent import Agent
from good_agent.templating.index import TemplateIndex, TemplateVersionManager
from good_agent.templating.storage import (
    ChainedStorage,
    FileSystemStorage,
    FileTemplateManager,
    TemplateSnapshot,
)


class TestTemplateWorkflowIntegration:
    """Test the complete template workflow."""

    @pytest_asyncio.fixture
    async def project_dir(self):
        """Create a project directory with template structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create prompts.yaml in project root
            config = {
                "prompts_dir": "prompts",
                "search_paths": [
                    {"path": "./prompts", "priority": 100},
                    {"path": "~/.good-agent/prompts", "priority": 50},
                ],
                "default_extension": ".prompt",
                "enable_hot_reload": False,
                "auto_versioning": True,
            }
            (project / "prompts.yaml").write_text(yaml.dump(config))

            # Create prompts directory structure
            prompts = project / "prompts"
            (prompts / "system").mkdir(parents=True)
            (prompts / "user").mkdir(parents=True)
            (prompts / "tools").mkdir(parents=True)
            (prompts / "components" / "headers").mkdir(parents=True)
            (prompts / "components" / "footers").mkdir(parents=True)
            (prompts / "components" / "examples").mkdir(parents=True)

            # Create base templates
            (prompts / "system" / "base.prompt").write_text("""---
version: 1.0.0
description: Base system prompt
author: system@example.com
tags: [system, base]
---

You are a helpful AI assistant specializing in {{ domain }}.

{% block instructions %}
Follow these general guidelines:
- Be helpful and accurate
- Provide detailed explanations
- Stay within your area of expertise
{% endblock %}

{% block footer %}
Remember to be respectful and professional.
{% endblock %}""")

            # Create analyst template that extends base
            (prompts / "system" / "analyst.prompt").write_text("""---
version: 1.0.0
description: Data analyst prompt
author: analyst@example.com
tags: [system, analyst, data]
extends: system/base
---

{% extends 'system/base' %}

{% block instructions %}
{{ super() }}

As a data analyst, you should:
- Analyze data in {{ analysis_scope }}
- Focus on {{ time_period }} timeframe
- Use available tools: {{ tools | join(', ') }}
{% include 'components/headers/analysis-framework' %}
{% endblock %}

{% block footer %}
{% include 'components/footers/standard' %}
{% endblock %}""")

            # Create component templates with kebab-case names
            (
                prompts / "components" / "headers" / "analysis-framework.prompt"
            ).write_text("""
## Analysis Framework
- Data Collection
- Statistical Analysis
- Visualization
- Reporting""")

            (prompts / "components" / "footers" / "standard.prompt").write_text("""
---
End of response. Please let me know if you need clarification.
---""")

            # Create user template
            (prompts / "user" / "research-request.prompt").write_text("""---
version: 1.0.0
description: Research request template
---

Please research {{ topic }} and provide:
{% for item in requirements %}
- {{ item }}
{% endfor %}""")

            # Create tool template
            (prompts / "tools" / "search_tool.prompt").write_text("""---
version: 1.0.0
description: Search tool prompt
---

Use the search tool to find information about {{ query }}.
Limit results to {{ limit | default(10) }} items.""")

            yield project

    @pytest_asyncio.fixture
    async def template_system(self, project_dir):
        """Create a complete template system."""
        # Set up storage
        prompts_dir = project_dir / "prompts"
        storage = FileSystemStorage(prompts_dir)

        # Set up index
        index = TemplateIndex(prompts_dir)
        index.scan_templates(auto_version=True)

        # Set up version manager
        version_manager = TemplateVersionManager(prompts_dir)

        # Set up template manager
        manager = FileTemplateManager(
            storage=storage, enable_hot_reload=False, snapshot_templates=True
        )

        # Preload all templates
        templates = await storage.list()
        await manager.preload_templates(templates)

        return {
            "storage": storage,
            "index": index,
            "version_manager": version_manager,
            "manager": manager,
            "project_dir": project_dir,
        }

    @pytest.mark.asyncio
    async def test_complete_workflow(self, template_system):
        """Test the complete template workflow from creation to rendering."""
        storage = template_system["storage"]
        template_system["index"]
        manager = template_system["manager"]

        # 1. Verify templates were created and indexed
        templates = await storage.list()
        assert len(templates) > 0
        assert "system/base" in templates
        assert "system/analyst" in templates
        assert "components/headers/analysis-framework" in templates

        # 2. Test case-insensitive resolution
        # Template created with kebab-case should work with snake_case
        content = await storage.get("components/headers/analysis_framework")
        assert content is not None
        assert "Analysis Framework" in content

        # 3. Test template inheritance and rendering
        context = {
            "domain": "financial analysis",
            "analysis_scope": "stock market trends",
            "time_period": "Q1 2024",
            "tools": ["search", "calculate", "visualize"],
        }

        rendered = manager.render("{% include 'system/analyst' %}", context)

        # Check that base template content is included
        assert "helpful AI assistant specializing in financial analysis" in rendered

        # Check that analyst-specific content is included
        assert "Analyze data in stock market trends" in rendered
        assert "Focus on Q1 2024 timeframe" in rendered
        assert "search, calculate, visualize" in rendered

        # Check that components are included
        assert "Analysis Framework" in rendered
        assert "End of response" in rendered

    @pytest.mark.asyncio
    async def test_versioning_workflow(self, template_system):
        """Test the versioning workflow."""
        index = template_system["index"]
        version_manager = template_system["version_manager"]
        project_dir = template_system["project_dir"]

        # 1. Check initial versions
        info = index.get_template_info("system/base")
        assert info.version == "1.0.0"

        # 2. Modify template
        template_path = project_dir / "prompts" / "system" / "base.prompt"
        original_content = template_path.read_text()

        # Create snapshot before modification
        snapshot_hash = version_manager.create_snapshot(
            "system/base", reason="Before modification"
        )

        # Modify the template
        modified_content = original_content.replace(
            "helpful AI assistant", "knowledgeable AI assistant"
        )
        template_path.write_text(modified_content)

        # 3. Scan for changes
        changes = index.scan_templates(auto_version=True)

        # Check that change was detected (filter for modified only)
        modified_templates = {k: v for k, v in changes.items() if v == "modified"}
        assert len(modified_templates) == 1
        assert "system/base" in modified_templates
        assert modified_templates["system/base"] == "modified"

        # Check version was incremented
        info = index.get_template_info("system/base")
        assert info.version == "1.0.1"

        # 4. Restore from snapshot
        success = version_manager.restore_snapshot("system/base", snapshot_hash)
        assert success is True

        # Verify content was restored
        restored_content = template_path.read_text()
        assert "helpful AI assistant" in restored_content

    @pytest.mark.asyncio
    async def test_agent_integration(self, template_system):
        """Test integration with the Agent class."""
        manager = template_system["manager"]

        # Mock the LLM's complete method instead of the whole class
        from good_agent.model.llm import LanguageModel

        # Create a real LanguageModel with mocked complete method
        mock_lm = LanguageModel(config={"model": "gpt-4o-mini"})
        mock_lm.complete = AsyncMock(return_value="Test response")

        # Create agent with template-based system prompt
        context = {
            "domain": "Python programming",
            "analysis_scope": "code optimization",
            "time_period": "current best practices",
            "tools": ["linter", "profiler", "debugger"],
        }

        # Render the system prompt
        system_prompt = manager.render("{% include 'system/analyst' %}", context)

        # Debug: check what was rendered
        assert system_prompt, f"System prompt is empty! Got: {repr(system_prompt)}"
        assert len(system_prompt) > 0, "System prompt has zero length"

        # Pass system_prompt as positional argument, not keyword
        agent = Agent(
            system_prompt,  # Positional argument
            context=context,
            language_model=mock_lm,  # Provide the mocked language model
        )

        await agent.ready()

        # Verify system prompt was properly rendered
        assert len(agent.messages) == 1
        system_msg = agent.messages[0]
        assert "Python programming" in str(system_msg.content)
        assert "code optimization" in str(system_msg.content)

    @pytest.mark.asyncio
    async def test_chained_storage(self, template_system):
        """Test chained storage with multiple search paths."""
        project_dir = template_system["project_dir"]

        # Create user directory
        user_dir = Path.home() / ".good-agent" / "prompts"
        user_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create user-specific template
            (user_dir / "user" / "personal.prompt").parent.mkdir(
                parents=True, exist_ok=True
            )
            (user_dir / "user" / "personal.prompt").write_text("""---
version: 1.0.0
description: Personal template
---
This is my personal template for {{ task }}.""")

            # Create chained storage
            chained = ChainedStorage(
                [
                    FileSystemStorage(project_dir / "prompts"),  # Priority 100
                    FileSystemStorage(user_dir),  # Priority 50
                ]
            )

            # Test that both storages are accessible
            templates = await chained.list()
            assert "system/base" in templates  # From project
            assert "user/personal" in templates  # From user dir

            # Test priority (project templates override user templates)
            # Create same template in both locations
            (user_dir / "system" / "base.prompt").parent.mkdir(
                parents=True, exist_ok=True
            )
            (user_dir / "system" / "base.prompt").write_text("User version")

            content = await chained.get("system/base")
            assert "helpful AI assistant" in content  # Should get project version

        finally:
            # Cleanup user directory
            import shutil

            if user_dir.exists():
                shutil.rmtree(user_dir)

    @pytest.mark.asyncio
    async def test_template_snapshots(self, template_system):
        """Test template snapshot functionality."""
        manager = template_system["manager"]
        template_system["storage"]

        # Get template through manager to trigger snapshot creation
        content = await manager.get_template("system/analyst")

        # Manager should have created snapshots if enabled
        if manager.snapshot_templates:
            assert len(manager.snapshots) > 0

            # Check snapshot for analyst template
            if "system/analyst" in manager.snapshots:
                snapshot = manager.snapshots["system/analyst"]
                assert isinstance(snapshot, TemplateSnapshot)
                assert snapshot.content == content
                assert snapshot.content_hash is not None

    # @pytest.mark.skip(reason="extract_dependencies method not yet implemented")
    # @pytest.mark.asyncio
    # async def test_template_dependencies(self, template_system):
    #     """Test template dependency resolution."""
    #     storage = template_system["storage"]
    #     manager = template_system["manager"]

    #     from good_agent.templating.storage import TemplateValidator
    #     validator = TemplateValidator()

    #     # Get analyst template which has dependencies
    #     content = await storage.get("system/analyst")

    #     # Extract dependencies - NOT IMPLEMENTED YET
    #     # dependencies = validator.extract_dependencies(content)

    #     # Should include extended and included templates
    #     assert "system/base" in dependencies or "'system/base'" in str(dependencies)

    #     # Verify all dependencies exist
    #     for dep in dependencies:
    #         # Clean up quotes if present
    #         dep_clean = dep.strip("'\"")
    #         exists = await storage.exists(dep_clean)
    #         # Some dependencies might have .prompt extension in the template
    #         if not exists:
    #             exists = await storage.exists(dep_clean.replace(".prompt", ""))
    #         assert exists, f"Dependency {dep} not found"

    @pytest.mark.asyncio
    async def test_hot_reload(self, template_system):
        """Test hot reload functionality."""
        project_dir = template_system["project_dir"]
        prompts_dir = project_dir / "prompts"

        # Create manager with hot reload enabled
        storage = FileSystemStorage(prompts_dir)
        manager = FileTemplateManager(storage=storage, enable_hot_reload=True)

        # Load and render template
        await manager.preload_templates(["system/base"])
        initial_render = manager.render(
            "{% include 'system/base' %}", {"domain": "test"}
        )

        # Modify template
        template_path = prompts_dir / "system" / "base.prompt"
        content = template_path.read_text()
        modified = content.replace("helpful", "super helpful")
        template_path.write_text(modified)

        # Clear cache (simulating hot reload)
        manager.file_loader._cache.clear()
        manager._template_cache.clear()

        # Also clear the Jinja2 environment cache if it exists
        if hasattr(manager.env, "cache") and manager.env.cache:
            manager.env.cache.clear()

        # Reload and render again
        await manager.preload_templates(["system/base"])
        new_render = manager.render("{% include 'system/base' %}", {"domain": "test"})

        # Should have the modified content
        assert "super helpful" in new_render
        assert "super helpful" not in initial_render
