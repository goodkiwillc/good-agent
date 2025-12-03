from unittest.mock import patch

import pytest
from good_agent.cli.config import GlobalConfig
from good_agent.cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


@pytest.fixture
def mock_config_dir(tmp_path):
    """Mock the configuration directory to use a temporary path."""
    config_dir = tmp_path / ".good-agent"
    config_dir.mkdir()

    # We need to patch where GlobalConfig looks for files
    # Since CONFIG_DIR and CONFIG_FILE are module-level constants in good_agent.cli.config,
    # we need to patch them or the Path.home method if it's used during init.
    # Looking at the implementation, CONFIG_FILE is defined at module level.

    with (
        patch("good_agent.cli.config.CONFIG_FILE", config_dir / "config.toml"),
        patch("good_agent.cli.config.CONFIG_DIR", config_dir),
    ):
        yield config_dir


def test_global_config_basic(mock_config_dir):
    """Test basic set and get operations of GlobalConfig."""
    config = GlobalConfig()
    config.set("openai", "sk-test-key")

    assert config.get("openai") == "sk-test-key"
    # Check alias resolution
    assert config.get("openai_api_key") == "sk-test-key"

    # Check persistence
    config2 = GlobalConfig()
    assert config2.get("openai") == "sk-test-key"


def test_global_config_profiles(mock_config_dir):
    """Test profile support."""
    # Set default
    config = GlobalConfig()
    config.set("model", "gpt-4")

    # Set dev profile
    config.set("model", "gpt-3.5-turbo", profile="dev")

    # Verify default
    assert config.get("model") == "gpt-4"

    # Verify dev profile
    assert config.get("model", profile="dev") == "gpt-3.5-turbo"

    # Verify fallback to default from another profile if not set
    # (Note: The current implementation of get() checks profile THEN default)
    assert config.get("openai", profile="dev") is None  # It wasn't set in default yet

    config.set("openai", "sk-default")
    assert config.get("openai", profile="dev") == "sk-default"


def test_cli_config_set_get(mock_config_dir):
    """Test config set and get CLI commands."""
    result = runner.invoke(app, ["config", "set", "openai", "sk-cli-test"])
    assert result.exit_code == 0
    assert "Set 'openai' in profile 'default'" in result.stdout

    result = runner.invoke(app, ["config", "get", "openai"])
    assert result.exit_code == 0
    assert "sk-cli-test" in result.stdout


def test_cli_config_list(mock_config_dir):
    """Test config list CLI command."""
    runner.invoke(app, ["config", "set", "openai", "sk-secret-key"])
    runner.invoke(app, ["config", "set", "model", "gpt-4o"])

    result = runner.invoke(app, ["config", "list"])
    assert result.exit_code == 0
    # The key is resolved to openai_api_key
    assert (
        "openai_api_key = sk-s...-key" in result.stdout or "openai_api_key = ***" in result.stdout
    )
    assert "model = gpt-4o" in result.stdout

    # Test with --show-secrets
    result = runner.invoke(app, ["config", "list", "--show-secrets"])
    assert result.exit_code == 0
    assert "openai_api_key = sk-secret-key" in result.stdout


def test_cli_profile_flag(mock_config_dir):
    """Test using the --profile flag."""
    # Set value in 'work' profile
    # Note: The main callback handles --profile and injects it into ctx.obj
    # But config subcommands use ctx.obj["profile"]

    # We need to pass --profile to the main app, before the subcommand
    result = runner.invoke(app, ["--profile", "work", "config", "set", "api_key", "12345"])
    assert result.exit_code == 0
    assert "Set 'api_key' in profile 'work'" in result.stdout

    # Verify with get
    result = runner.invoke(app, ["--profile", "work", "config", "get", "api_key"])
    assert result.exit_code == 0
    assert "12345" in result.stdout

    # Verify it's not in default
    result = runner.invoke(app, ["config", "get", "api_key"])
    assert result.exit_code != 0  # Should fail or return empty if using exit(1)
