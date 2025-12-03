"""Component Registry - Manages component lifecycle and dependencies."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from good_agent.core.components import AgentComponent
from good_agent.events import AgentEvents
from good_agent.extensions.template_manager import TemplateManager
from good_agent.model.llm import LanguageModel
from good_agent.tools import ToolManager

if TYPE_CHECKING:
    from good_agent.agent import Agent

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """Manages component lifecycle and dependencies.

    This manager handles all component-related operations including:
    - Component registration (by type and name)
    - Dependency validation
    - Async component installation
    - Component task tracking
    - Extension cloning for forked contexts
    """

    def __init__(self, agent: Agent) -> None:
        """Initialize component registry.

        Args:
            agent: Parent Agent instance
        """
        self.agent = agent

        # Initialize extension storage
        self._extensions: dict[type[AgentComponent], AgentComponent] = {}
        self._extension_names: dict[str, AgentComponent] = {}

        # Track component initialization tasks
        self._component_tasks: list[asyncio.Task] = []

        # Track if components have been installed to prevent duplicate installation
        self._components_installed = False

    @property
    def extensions(self) -> dict[str, AgentComponent]:
        """Access extensions by name.

        Returns:
            Copy of extension name-to-component mapping
        """
        return self._extension_names.copy()

    @property
    def extensions_by_type(self) -> dict[type[AgentComponent], AgentComponent]:
        """Access extensions by type.

        Returns:
            Copy of extension type-to-component mapping
        """
        return self._extensions.copy()

    def register_extension(self, extension: AgentComponent) -> None:
        """Register an extension component (without installing it).

        Args:
            extension: Component to register
        """
        # Store by type for type-based access
        ext_type = type(extension)
        self._extensions[ext_type] = extension

        # Also register under base classes for compatibility
        # This allows agent[TemplateManager] to find TemplateManager
        for base in ext_type.__bases__:
            # Don't overwrite if a more specific implementation exists
            if (
                issubclass(base, AgentComponent)
                and base != AgentComponent
                and base not in self._extensions
            ):
                self._extensions[base] = extension

        # Store by name if available
        if hasattr(extension, "name"):
            self._extension_names[extension.name] = extension
        else:
            # Use class name as fallback
            self._extension_names[ext_type.__name__] = extension

        # Subscribe to agent events (so handlers are ready even before async install)
        self.agent.events.broadcast_to(extension)

        # Call synchronous setup which sets the agent reference and allows early event handler registration
        extension.setup(self.agent)

    async def install_components(self) -> None:
        """Install all registered components asynchronously.

        This is called during AGENT_INIT_AFTER event, after all components
        have been registered and dependencies validated.
        """
        # Skip if components have already been installed
        if self._components_installed:
            return

        # Mark as installed to prevent duplicate calls
        self._components_installed = True

        # Get unique extensions (avoid installing the same instance twice)
        installed = set()

        for extension in self._extensions.values():
            # Skip if already installed (handles duplicates from base class registration)
            if id(extension) in installed:
                continue
            installed.add(id(extension))

            # Get extension name for debugging
            extension_name = (
                extension.name if hasattr(extension, "name") else extension.__class__.__name__
            )

            # Emit extension:install event with extension name
            self.agent.do(
                AgentEvents.EXTENSION_INSTALL,
                extension=extension,
                extension_name=extension_name,
                agent=self.agent,
            )

            # Call the extension's async install method
            try:
                await extension.install(self.agent)

                # Emit successful installation event with extension name
                self.agent.do(
                    AgentEvents.EXTENSION_INSTALL_AFTER,
                    extension=extension,
                    extension_name=extension_name,
                    agent=self.agent,
                )
            except Exception as e:
                # Emit extension:error event
                self.agent.do(
                    AgentEvents.EXTENSION_ERROR,
                    extension=extension,
                    error=e,
                    context="install",
                    agent=self.agent,
                )
                raise

    def validate_component_dependencies(self) -> None:
        """Validate that all component dependencies are satisfied.

        Raises:
            ValueError: If any component's dependencies are not met
        """
        # Build set of available component class names from self._extensions
        available = {ext.__class__.__name__ for ext in self._extensions.values()}

        # Also include base class names for polymorphic dependencies
        for ext in self._extensions.values():
            for base in ext.__class__.__bases__:
                if issubclass(base, AgentComponent) and base != AgentComponent:
                    available.add(base.__name__)

        # Check each component's dependencies
        missing = []
        for ext in self._extensions.values():
            if hasattr(ext, "__depends__") and ext.__depends__:
                for dep in ext.__depends__:
                    if dep not in available:
                        missing.append(f"  - {ext.__class__.__name__} requires {dep}")

        if missing:
            raise ValueError(
                "Component dependency validation failed:\n"
                + "\n".join(missing)
                + f"\nAvailable components: {', '.join(sorted(available))}"
            )

    def clone_extensions_for_config(
        self, target_config: dict[str, Any], skip: set[str] | None = None
    ) -> None:
        """Clone extensions for a forked agent configuration.

        Args:
            target_config: Configuration dict to populate with cloned extensions
            skip: Optional set of extension keys to skip cloning
        """
        skip = skip or set()
        unique_extensions = list({id(ext): ext for ext in self._extensions.values()}.values())

        # Import here to avoid circular dependency
        from good_agent.mock import AgentMockInterface

        core_types = (LanguageModel, AgentMockInterface, ToolManager, TemplateManager)

        if "language_model" not in skip:
            target_config["language_model"] = self.agent.model.clone()
        if "mock" not in skip:
            target_config["mock"] = self.agent.mock.clone()
        if "tool_manager" not in skip:
            target_config["tool_manager"] = self.agent.tools.clone()
        if "template_manager" not in skip:
            target_config["template_manager"] = self.agent.template.clone()

        if "extensions" in skip:
            return

        additional_extensions = [
            ext.clone() for ext in unique_extensions if not isinstance(ext, core_types)
        ]
        target_config["extensions"] = additional_extensions

    def track_component_task(self, _component: AgentComponent, task: asyncio.Task) -> None:
        """Track a component initialization task.

        Args:
            _component: Component that owns the task (unused, for future use)
            task: Async task to track
        """
        self._component_tasks.append(task)

    def get_extension_by_type(self, ext_type: type[AgentComponent]) -> AgentComponent | None:
        """Get extension by type.

        Args:
            ext_type: Type of extension to retrieve

        Returns:
            Extension instance or None if not found
        """
        return self._extensions.get(ext_type)

    def get_extension_by_name(self, name: str) -> AgentComponent | None:
        """Get extension by name.

        Args:
            name: Name of extension to retrieve

        Returns:
            Extension instance or None if not found
        """
        return self._extension_names.get(name)
