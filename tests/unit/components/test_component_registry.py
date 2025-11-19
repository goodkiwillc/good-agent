from unittest.mock import MagicMock, AsyncMock
import pytest

from good_agent import AgentComponent, Agent
from good_agent.agent.components import ComponentRegistry
from good_agent.events import AgentEvents


class ComponentA(AgentComponent):
    name = "component_a"


class ComponentB(AgentComponent):
    name = "component_b"
    __depends__ = {"ComponentA"}


class ComponentC(AgentComponent):
    name = "component_c"
    __depends__ = {"MissingComponent"}


class FailingComponent(AgentComponent):
    name = "failing_component"

    async def install(self, agent):
        raise ValueError("Installation failed")


@pytest.fixture
def mock_agent():
    agent = MagicMock(spec=Agent)
    # Mock events facade
    agent.events = MagicMock()
    agent.events.broadcast_to = MagicMock()
    # Mock do/emit
    agent.do = MagicMock()

    # Mock core properties needed by cloning
    agent.model = MagicMock()
    agent.model.clone.return_value = MagicMock()

    agent.mock = MagicMock()
    agent.mock.clone.return_value = MagicMock()

    agent.tools = MagicMock()
    agent.tools.clone.return_value = MagicMock()

    agent.template = MagicMock()
    agent.template.clone.return_value = MagicMock()

    return agent


class TestComponentRegistry:
    def test_register_extension(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        comp = ComponentA()

        registry.register_extension(comp)

        assert registry.get_extension_by_name("component_a") == comp
        assert registry.get_extension_by_type(ComponentA) == comp

        # Verify agent events broadcasting
        mock_agent.events.broadcast_to.assert_called_with(comp)

        # Verify setup called (ComponentA.setup calls super().setup which sets self.agent)
        assert comp.agent == mock_agent

    def test_extensions_properties(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        comp = ComponentA()
        registry.register_extension(comp)

        # Check extensions property
        exts = registry.extensions
        assert "component_a" in exts
        assert exts["component_a"] == comp

        # Check extensions_by_type property
        exts_type = registry.extensions_by_type
        assert ComponentA in exts_type
        assert exts_type[ComponentA] == comp

        # Ensure they are copies
        exts["new_key"] = "should not affect registry"
        assert "new_key" not in registry.extensions

    def test_dependency_validation_success(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        registry.register_extension(ComponentA())
        registry.register_extension(ComponentB())

        # Should not raise
        registry.validate_component_dependencies()

    def test_dependency_validation_failure(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        registry.register_extension(ComponentC())

        with pytest.raises(ValueError, match="Component dependency validation failed"):
            registry.validate_component_dependencies()

    def test_base_class_registration(self, mock_agent):
        """Test that components are registered under their base classes."""

        class BaseComp(AgentComponent):
            pass

        class ImplComp(BaseComp):
            pass

        registry = ComponentRegistry(mock_agent)
        comp = ImplComp()
        registry.register_extension(comp)

        # Should be registered under ImplComp AND BaseComp
        assert registry.get_extension_by_type(ImplComp) == comp
        assert registry.get_extension_by_type(BaseComp) == comp

    @pytest.mark.asyncio
    async def test_install_components_success(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        comp = ComponentA()
        comp.install = AsyncMock()
        registry.register_extension(comp)

        await registry.install_components()

        # Verify install called
        comp.install.assert_called_once_with(mock_agent)

        # Verify events emitted
        # EXTENSION_INSTALL and EXTENSION_INSTALL_AFTER
        assert mock_agent.do.call_count == 2
        args_list = mock_agent.do.call_args_list
        assert args_list[0][0][0] == AgentEvents.EXTENSION_INSTALL
        assert args_list[1][0][0] == AgentEvents.EXTENSION_INSTALL_AFTER

        # Test idempotency (second call shouldn't do anything)
        mock_agent.do.reset_mock()
        comp.install.reset_mock()
        await registry.install_components()
        comp.install.assert_not_called()
        mock_agent.do.assert_not_called()

    @pytest.mark.asyncio
    async def test_install_components_failure(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        comp = FailingComponent()
        registry.register_extension(comp)

        with pytest.raises(ValueError, match="Installation failed"):
            await registry.install_components()

        # Verify error event emitted
        # EXTENSION_INSTALL should be called first
        # Then EXTENSION_ERROR

        error_calls = [
            call
            for call in mock_agent.do.call_args_list
            if call[0][0] == AgentEvents.EXTENSION_ERROR
        ]
        assert len(error_calls) == 1
        assert error_calls[0][1]["extension"] == comp
        assert isinstance(error_calls[0][1]["error"], ValueError)

    def test_clone_extensions_for_config(self, mock_agent):
        registry = ComponentRegistry(mock_agent)
        comp = ComponentA()
        comp.clone = MagicMock(return_value=ComponentA())
        registry.register_extension(comp)

        target_config = {}
        registry.clone_extensions_for_config(target_config)

        # Verify core components cloned
        assert "language_model" in target_config
        assert "mock" in target_config
        assert "tool_manager" in target_config
        assert "template_manager" in target_config

        # Verify extensions cloned
        assert "extensions" in target_config
        assert len(target_config["extensions"]) == 1
        assert isinstance(target_config["extensions"][0], ComponentA)

        # Verify skip logic
        target_config_skip = {}
        registry.clone_extensions_for_config(
            target_config_skip, skip={"language_model", "extensions"}
        )
        assert "language_model" not in target_config_skip
        assert "extensions" not in target_config_skip
