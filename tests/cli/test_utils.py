import sys
from unittest.mock import Mock, patch

import pytest
from good_agent.cli.utils import load_agent_from_path


@pytest.fixture
def mock_importlib():
    with patch("importlib.import_module") as mock:
        yield mock


def test_load_agent_from_path_valid(mock_importlib):
    mock_agent = Mock()
    mock_module = Mock(agent=mock_agent)
    mock_importlib.return_value = mock_module

    agent, config = load_agent_from_path("module:agent")

    assert agent == mock_agent
    assert config == {}
    mock_importlib.assert_called_once_with("module")


def test_load_agent_from_path_invalid_format():
    with pytest.raises(ValueError, match="Invalid agent path format"):
        load_agent_from_path("module")


def test_load_agent_from_path_import_error(mock_importlib):
    mock_importlib.side_effect = ImportError("No module named 'foo'")

    with pytest.raises(ImportError, match="Could not import module 'foo'"):
        load_agent_from_path("foo:bar")


def test_load_agent_from_path_attribute_error(mock_importlib):
    mock_module = Mock(spec=[])  # Empty module
    mock_importlib.return_value = mock_module

    with pytest.raises(AttributeError, match="Module 'foo' has no attribute 'bar'"):
        load_agent_from_path("foo:bar")


def test_load_agent_from_path_adds_cwd_to_sys_path():
    with patch.object(sys, "path", []) as mock_path:
        with patch("importlib.import_module") as mock_import:
            mock_import.return_value = Mock(agent=Mock())
            load_agent_from_path("module:agent")

            # Should have added CWD to sys.path
            assert len(mock_path) > 0


def test_load_agent_from_path_built_in_aliases(mock_importlib):
    mock_agent = Mock()
    # Mock the good_agent.agents.meta module
    mock_meta_module = Mock(agent=mock_agent)

    # Configure importlib to return our mock module when the alias path is imported
    def side_effect(name):
        if name == "good_agent.agents.meta":
            return mock_meta_module
        if name == "good_agent.agents.research":
            return Mock(agent=mock_agent)
        raise ImportError(f"Unknown module {name}")

    mock_importlib.side_effect = side_effect

    # Test good-agent alias
    agent, _ = load_agent_from_path("good-agent")
    assert agent == mock_agent
    mock_importlib.assert_any_call("good_agent.agents.meta")

    # Test good-agent-agent alias
    agent, _ = load_agent_from_path("good-agent-agent")
    assert agent == mock_agent

    # Test research alias
    agent, _ = load_agent_from_path("research")
    assert agent == mock_agent
    mock_importlib.assert_any_call("good_agent.agents.research")
