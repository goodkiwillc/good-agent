import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from good_agent import Agent
from good_agent.extensions.template_manager import TemplateManager


class TestFileTemplateIntegration:
    """Test seamless file template integration with Agent."""

    @pytest_asyncio.fixture
    async def project_with_templates(self):
        """Create a project with template files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project = Path(tmpdir)

            # Create prompts.yaml
            config = {"prompts_dir": "prompts", "default_extension": ".prompt"}
            (project / "prompts.yaml").write_text(yaml.dump(config))

            # Create prompts directory
            prompts = project / "prompts"
            (prompts / "system").mkdir(parents=True)
            (prompts / "user").mkdir(parents=True)

            # Create system templates
            (prompts / "system" / "base.prompt").write_text("""---
version: 1.0.0
description: Base system prompt
---

You are a helpful AI assistant.

{% block instructions %}
Follow these guidelines:
- Be helpful and accurate
- Be concise but complete
{% endblock %}""")

            (prompts / "system" / "specialist.prompt").write_text("""---
version: 1.0.0
description: Specialist assistant
---

{% extends 'system/base' %}

{% block instructions %}
{{ super() }}
Additional guidelines for {{ specialty }}:
- Focus on {{ domain }} best practices
- Provide expert-level insights
{% endblock %}""")

            # Create user template
            (prompts / "user" / "question.prompt").write_text("""---
version: 1.0.0
---
Please help me with {{ topic }}.
{% if details %}
Additional context: {{ details }}
{% endif %}""")

            # Change to project directory
            import os

            original_cwd = os.getcwd()
            os.chdir(project)

            yield project

            # Restore original directory
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_agent_loads_file_templates_automatically(
        self, project_with_templates
    ):
        """Test that Agent automatically loads file templates."""
        # Create agent with file template reference
        # This should work WITHOUT manual rendering
        agent = Agent("{% include 'system/base' %}", model="gpt-4")

        await agent.initialize()

        # Check that system message was rendered from file
        assert len(agent.messages) == 1
        system_msg = agent.messages[0]

        # Should have content from the file template
        rendered_content = str(system_msg.content)
        assert "helpful AI assistant" in rendered_content
        assert "Be helpful and accurate" in rendered_content

    @pytest.mark.asyncio
    async def test_agent_supports_template_inheritance(self, project_with_templates):
        """Test that template inheritance works in Agent."""
        # Use template with inheritance and variables
        agent = Agent(
            "{% include 'system/specialist' %}",
            context={
                "specialty": "Python programming",
                "domain": "software development",
            },
            model="gpt-4",
        )

        await agent.initialize()

        # Check that inheritance and variables worked
        system_msg = agent.messages[0]
        rendered_content = str(system_msg.content)

        # Should have base content
        assert "helpful AI assistant" in rendered_content

        # Should have specialized content with variables
        assert "Python programming" in rendered_content
        assert "software development best practices" in rendered_content

    @pytest.mark.asyncio
    async def test_message_templates_work(self, project_with_templates):
        """Test that file templates work in user messages."""
        agent = Agent("You are a helpful assistant.", model="gpt-4")

        await agent.initialize()

        # Add message using file template
        agent.append(
            "{% include 'user/question' %}",
            context={
                "topic": "async programming in Python",
                "details": "I'm working with asyncio",
            },
        )

        # Check that message was rendered from template
        user_msg = agent.messages[1]
        rendered_content = str(user_msg.content)

        assert "Please help me with async programming in Python" in rendered_content
        assert "Additional context: I'm working with asyncio" in rendered_content

    @pytest.mark.asyncio
    async def test_template_preloading(self, project_with_templates):
        """Test that templates can be preloaded for performance."""
        # Get the template manager from agent
        agent = Agent("Test", model="gpt-4")
        await agent.initialize()

        # The template manager should be enhanced
        template_manager = agent.template
        assert isinstance(template_manager, TemplateManager)

        # Preload templates
        await template_manager.preload_templates(
            ["system/base", "system/specialist", "user/question"]
        )

        # Templates should be cached
        assert "system/base" in template_manager.file_loader._cache
        assert "system/specialist" in template_manager.file_loader._cache
        assert "user/question" in template_manager.file_loader._cache

    @pytest.mark.asyncio
    async def test_mixed_templates(self, project_with_templates):
        """Test mixing file templates with inline templates."""
        agent = Agent(
            """
            {% include 'system/base' %}
            
            Additional instructions:
            - Today's date is {{ current_date }}
            - Focus on {{ focus_area }}
            """,
            context={"current_date": "2025-09-02", "focus_area": "testing"},
            model="gpt-4",
        )

        await agent.initialize()

        system_msg = agent.messages[0]
        rendered_content = str(system_msg.content)

        # Should have file template content
        assert "helpful AI assistant" in rendered_content

        # Should have inline template content
        assert "Today's date is 2025-09-02" in rendered_content
        assert "Focus on testing" in rendered_content

    @pytest.mark.asyncio
    async def test_fallback_to_registry(self, project_with_templates):
        """Test that registry templates still work."""
        agent = Agent("Test", model="gpt-4")
        await agent.initialize()

        # Register a template in the traditional way
        agent.template.add_template(
            "registered_template", "This is registered: {{ value }}"
        )

        # Use both file and registry templates
        agent.append(
            """
            File template: {% include 'system/base' %}
            Registry template: {% include 'registered_template' %}
        """,
            context={"value": "test123"},
        )

        user_msg = agent.messages[1]
        rendered_content = str(user_msg.content)

        # Should have file template
        assert "helpful AI assistant" in rendered_content

        # Should have registry template
        assert "This is registered: test123" in rendered_content

    @pytest.mark.asyncio
    async def test_no_prompts_directory(self):
        """Test that Agent still works when no prompts directory exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import os

            original_cwd = os.getcwd()
            os.chdir(tmpdir)

            try:
                # Create agent without prompts directory
                agent = Agent("Regular system prompt without templates", model="gpt-4")

                await agent.initialize()

                # Should work normally
                assert len(agent.messages) == 1
                assert "Regular system prompt" in str(agent.messages[0].content)

            finally:
                os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_explicit_template_manager(self, project_with_templates):
        """Test providing explicit template manager to Agent."""
        # Create custom template manager with file templates disabled
        custom_manager = TemplateManager(enable_file_templates=False)

        agent = Agent(
            "{% include 'system/base' %}",  # This won't work without file templates
            template_manager=custom_manager,
            model="gpt-4",
        )

        await agent.initialize()

        # Template should not be resolved (no file loading)
        system_msg = agent.messages[0]

        # Accessing content should raise an error since the template can't be found
        with pytest.raises(RuntimeError) as exc_info:
            str(system_msg.content)

        # Verify the error mentions the missing template
        assert "system/base" in str(exc_info.value)
