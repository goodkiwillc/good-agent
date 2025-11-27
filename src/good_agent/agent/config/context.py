from typing import Any

from good_agent.agent.config.manager import ConfigStack


class AgentContext(ConfigStack):
    """Runtime context store for agent variables and config overrides.

    Provides a hierarchical dict-like interface for storing and accessing
    runtime context values. Supports scoped overrides via context manager.
    See ``examples/context/thread_context.py`` for usage.
    """

    def __init__(self, agent_config=None, **kwargs):
        """Seed the context with local data plus optional agent_config fallback."""
        super().__init__(**kwargs)
        self._agent_config = agent_config

    def _set_agent_config(self, agent_config):
        """Set or update the backing agent config reference for inheritance."""
        self._agent_config = agent_config

    def _get_config_context(self) -> dict[str, Any]:
        """Get the current context from config manager"""
        if self._agent_config and "context" in self._agent_config._chainmap:
            return dict(self._agent_config._chainmap["context"])
        return {}

    def __getitem__(self, key):
        """Get item with config context inheritance"""
        # First try local context (includes context manager overrides)
        try:
            return self._chainmap[key]
        except KeyError:
            pass

        # Then try config context
        config_context = self._get_config_context()
        if isinstance(config_context, dict) and key in config_context:
            return config_context[key]

        # Key not found
        raise KeyError(key)

    def get(self, key, default=None):
        """Get with config context inheritance"""
        try:
            return self[key]
        except KeyError:
            return default

    def as_dict(self) -> dict[str, Any]:
        """Return current context as a dictionary, merging config and local contexts"""
        # Start with config context
        result = self._get_config_context().copy()
        # Override with local context (including context manager overrides)
        result.update(dict(self._chainmap))
        return result
