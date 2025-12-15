import pytest
from jinja2 import Environment, TemplateNotFound

from good_agent import Agent
from good_agent.core.templating import (
    TEMPLATE_REGISTRY,
    TemplateRegistry,
    add_named_template,
    get_named_template,
)


@pytest.fixture(autouse=True)
def clear_global_templates():
    """Clear global templates before each test to prevent interference"""
    # Store original templates
    original_templates = dict(TEMPLATE_REGISTRY.templates)

    # Clear for test
    TEMPLATE_REGISTRY._templates.clear()

    yield

    # Restore original templates
    TEMPLATE_REGISTRY._templates.clear()
    TEMPLATE_REGISTRY._templates.update(original_templates)


def test_template_registry_parent_lookup():
    """Test that TemplateRegistry can lookup templates from parent registry"""
    # Add template to global registry
    add_named_template("global_test", "Global: {{ value }}")

    # Create local registry with global as parent
    local_registry = TemplateRegistry(parent=TEMPLATE_REGISTRY)

    # Should find global template
    template = local_registry.get_template("global_test")
    assert template == "Global: {{ value }}"

    # Should also work via get_source (Jinja2 loader interface)
    env = Environment()
    source, _, _ = local_registry.get_source(env, "global_test")
    assert source == "Global: {{ value }}"


def test_template_registry_local_override():
    """Test that local templates take precedence over parent templates"""
    # Add template to global registry
    add_named_template("shared_name", "Global version")

    # Create local registry
    local_registry = TemplateRegistry(parent=TEMPLATE_REGISTRY)

    # Add template with same name locally
    local_registry.add_template("shared_name", "Local version")

    # Should get local version
    template = local_registry.get_template("shared_name")
    assert template == "Local version"

    # Global should still have its version
    global_template = get_named_template("shared_name")
    assert global_template == "Global version"


def test_template_registry_list_templates():
    """Test that list_templates includes both local and parent templates"""
    # Add global templates
    add_named_template("global_1", "Global 1")
    add_named_template("global_2", "Global 2")

    # Create local registry
    local_registry = TemplateRegistry(parent=TEMPLATE_REGISTRY)
    local_registry.add_template("local_1", "Local 1")
    local_registry.add_template("local_2", "Local 2")

    # Should include all templates
    names = local_registry.list_templates()
    assert "global_1" in names
    assert "global_2" in names
    assert "local_1" in names
    assert "local_2" in names
    assert len(names) >= 4


def test_template_registry_get_template_names():
    """Test that get_template_names includes both local and parent templates"""
    # Add global template
    add_named_template("global_template", "Global")

    # Create local registry
    local_registry = TemplateRegistry(parent=TEMPLATE_REGISTRY)
    local_registry.add_template("local_template", "Local")

    # Should include both
    names = local_registry.get_template_names()
    assert "global_template" in names
    assert "local_template" in names


def test_template_registry_getitem_lookup():
    """Test that __getitem__ supports parent lookup"""
    # Add global template
    add_named_template("bracket_test", "Bracket access")

    # Create local registry
    local_registry = TemplateRegistry(parent=TEMPLATE_REGISTRY)

    # Should work with bracket notation
    template = local_registry["bracket_test"]
    assert template == "Bracket access"


def test_template_not_found_with_parent():
    """Test that TemplateNotFound is raised when template not found anywhere"""
    # Create local registry with empty global parent
    local_registry = TemplateRegistry(parent=TEMPLATE_REGISTRY)

    # Should raise TemplateNotFound
    with pytest.raises(TemplateNotFound):
        local_registry.get_template("nonexistent")

    with pytest.raises(TemplateNotFound):
        local_registry["nonexistent"]

    env = Environment()
    with pytest.raises(TemplateNotFound):
        local_registry.get_source(env, "nonexistent")


def test_template_registry_no_parent():
    """Test that registry works without parent (original behavior)"""
    # Create registry with explicit no parent (forces new instance)
    standalone_registry = TemplateRegistry({}, parent=None)
    standalone_registry.add_template("standalone", "Standalone template")

    # Should work normally
    template = standalone_registry.get_template("standalone")
    assert template == "Standalone template"

    # Should not find global templates (since we're not using the global singleton)
    add_named_template("global_only", "Global only")
    with pytest.raises(TemplateNotFound):
        standalone_registry.get_template("global_only")


def test_global_registry_singleton_behavior():
    """Test that global registry maintains singleton behavior"""
    # These should be the same instance
    registry1 = TemplateRegistry()
    registry2 = TemplateRegistry()
    assert registry1 is registry2
    assert registry1 is TEMPLATE_REGISTRY


def test_non_global_registry_instances():
    """Test that registries with parameters create new instances"""
    # These should be different instances
    registry1 = TemplateRegistry(parent=TEMPLATE_REGISTRY)
    registry2 = TemplateRegistry(parent=TEMPLATE_REGISTRY)
    assert registry1 is not registry2
    assert registry1 is not TEMPLATE_REGISTRY
    assert registry2 is not TEMPLATE_REGISTRY


@pytest.mark.asyncio
async def test_agent_template_manager_inheritance():
    """Test that Agent's TemplateManager uses parent registry lookup"""
    # Add global template
    add_named_template("agent_global", "Agent can use global: {{ msg }}")

    # Create agent
    agent = Agent("Test system", context={"msg": "hello"})
    await agent.initialize()

    try:
        # Agent should find global template
        template = agent.template.get_template("agent_global")
        assert template == "Agent can use global: {{ msg }}"

        # Agent should be able to add local templates
        agent.template.add_template("agent_local", "Local template: {{ msg }}")
        local_template = agent.template.get_template("agent_local")
        assert local_template == "Local template: {{ msg }}"

        # Both should be in template names
        names = agent.template._registry.get_template_names()
        assert "agent_global" in names
        assert "agent_local" in names

    finally:
        await agent.events.close()


@pytest.mark.asyncio
async def test_agent_template_rendering_with_inheritance():
    """Test that agent can render templates from both local and global registries"""
    # Add global template
    add_named_template("greeting", "Hello {{ name }}!")

    # Create agent
    agent = Agent("Test system", context={"name": "World"})
    await agent.initialize()

    try:
        # Add message using global template via include
        agent.append("Message: {% include 'greeting' %}")

        # Should render successfully
        rendered = agent.messages[-1].render()
        assert rendered.strip() == "Message: Hello World!"

    finally:
        await agent.events.close()


@pytest.mark.asyncio
async def test_agent_local_template_override():
    """Test that agent's local templates override global ones"""
    # Add global template
    add_named_template("override_test", "Global version: {{ value }}")

    # Create agent
    agent = Agent("Test system", context={"value": "test"})
    await agent.initialize()

    try:
        # Agent should initially get global version
        template = agent.template.get_template("override_test")
        assert template == "Global version: {{ value }}"

        # Add local override
        agent.template.add_template("override_test", "Local version: {{ value }}", replace=True)

        # Should now get local version
        template = agent.template.get_template("override_test")
        assert template == "Local version: {{ value }}"

        # Global should be unchanged
        global_template = get_named_template("override_test")
        assert global_template == "Global version: {{ value }}"

    finally:
        await agent.events.close()
