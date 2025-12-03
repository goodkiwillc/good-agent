import logging
import os
from pathlib import Path
from typing import Any

import tomli_w

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".good-agent"
CONFIG_FILE = CONFIG_DIR / "config.toml"

# Alias mapping for user convenience
KEY_ALIASES = {
    "openai": "openai_api_key",
    "open-ai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "openrouter": "openrouter_api_key",
    "open-router": "openrouter_api_key",
    "gemini": "gemini_api_key",
    "google": "gemini_api_key",
    "cohere": "cohere_api_key",
    "mistral": "mistral_api_key",
}


class GlobalConfig:
    def __init__(self, profile: str | None = None):
        self.profile = profile or os.environ.get("GOOD_AGENT_PROFILE", "default")
        self.config_path = CONFIG_FILE
        self._ensure_config_dir()
        self.data = self._load()

    def _ensure_config_dir(self):
        if not CONFIG_DIR.exists():
            CONFIG_DIR.mkdir(parents=True, mode=0o700)

    def _load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            logger.warning(f"Failed to load global config: {e}")
            return {}

    def save(self):
        # Ensure secure permissions before writing if it doesn't exist
        if not self.config_path.exists():
            self.config_path.touch(mode=0o600)
        else:
            self.config_path.chmod(0o600)

        with open(self.config_path, "wb") as f:
            tomli_w.dump(self.data, f)

    def _resolve_key(self, key: str) -> str:
        return KEY_ALIASES.get(key.lower(), key)

    def get(self, key: str, profile: str | None = None) -> Any:
        """Get a value, checking profile then default."""
        target_profile = profile or self.profile
        resolved_key = self._resolve_key(key)

        # Check specific profile
        if target_profile != "default":
            profile_data = self.data.get("profile", {}).get(target_profile, {})
            if resolved_key in profile_data:
                return profile_data[resolved_key]

        # Check default
        default_data = self.data.get("default", {})
        return default_data.get(resolved_key)

    def set(self, key: str, value: str, profile: str | None = None):
        """Set a value in the specified profile (or default)."""
        target_profile = profile or self.profile
        resolved_key = self._resolve_key(key)

        if target_profile == "default":
            if "default" not in self.data:
                self.data["default"] = {}
            self.data["default"][resolved_key] = value
        else:
            if "profile" not in self.data:
                self.data["profile"] = {}
            if target_profile not in self.data["profile"]:
                self.data["profile"][target_profile] = {}
            self.data["profile"][target_profile][resolved_key] = value

        self.save()

    def list(self, profile: str | None = None) -> dict[str, Any]:
        """List all resolved configuration for a profile."""
        target_profile = profile or self.profile

        # Start with defaults
        result = self.data.get("default", {}).copy()

        # Overlay profile if not default
        if target_profile != "default":
            profile_data = self.data.get("profile", {}).get(target_profile, {})
            result.update(profile_data)

        return result

    def inject_into_environ(self):
        """Inject config values into os.environ if not already set."""
        config_values = self.list()
        for key, value in config_values.items():
            # Convert to upper case for env vars (e.g. openai_api_key -> OPENAI_API_KEY)
            env_key = key.upper()
            if env_key not in os.environ and value is not None:
                os.environ[env_key] = str(value)
