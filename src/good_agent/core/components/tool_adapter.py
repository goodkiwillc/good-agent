from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Union

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.tools import Tool, ToolResponse, ToolSignature
    from good_agent.tools.bound_tools import BoundTool

# Union type for tools that can be either Tool instances or BoundTool descriptors
ToolLike = Union["Tool", "BoundTool"]

T = TypeVar("T")


class ConflictStrategy(Enum):
    """Strategy for handling conflicts when multiple adapters modify the same tool."""

    CHAIN = "chain"  # Apply adapters in sequence (default)
    MERGE = "merge"  # Merge parameter changes from all adapters
    EXCLUSIVE = "exclusive"  # Only one adapter allowed per parameter
    PRIORITY = "priority"  # Use adapter priority to resolve conflicts


@dataclass
class AdapterMetadata:
    """Metadata about an adapter's transformations."""

    modified_params: set[str]  # Parameters this adapter modifies
    added_params: set[str]  # New parameters added
    removed_params: set[str]  # Parameters removed


class ToolAdapter(ABC, Generic[T]):
    """
    Base class for tool adapters that modify tool behavior.

    Tool adapters allow components to transparently intercept and modify:
    1. Tool signatures sent to the LLM
    2. Parameters from LLM tool calls
    3. Responses from tool execution (optional)

    The adapter maintains any necessary state for the transformations
    and is bound to a specific component instance.
    """

    def __init__(
        self,
        component: T,
        priority: int = 100,
        conflict_strategy: ConflictStrategy = ConflictStrategy.CHAIN,
    ):
        """
        Initialize the adapter with its parent component.

        Args:
            component: The AgentComponent instance that owns this adapter
            priority: Adapter priority (higher = earlier execution)
            conflict_strategy: How to handle conflicts with other adapters
        """
        self.component = component
        self.priority = priority
        self.conflict_strategy = conflict_strategy
        self._adapted_tools: dict[str, Tool] = {}
        self._original_signatures: dict[str, ToolSignature] = {}
        self._metadata_cache: dict[str, AdapterMetadata] = {}

    @abstractmethod
    def should_adapt(self, tool: ToolLike, agent: Agent) -> bool:
        """
        Determine if this adapter should process the given tool.

        Args:
            tool: The tool to check (Tool instance or BoundTool descriptor)
            agent: The agent instance

        Returns:
            True if this adapter should handle the tool
        """
        ...

    @abstractmethod
    def adapt_signature(
        self, tool: ToolLike, signature: ToolSignature, agent: Agent
    ) -> ToolSignature:
        """
        Modify the tool signature that will be sent to the LLM.

        This method is called during the TOOLS_GENERATE_SIGNATURE event
        to transform how the tool appears to the LLM.

        Args:
            tool: The original tool (Tool instance or BoundTool descriptor)
            signature: The original tool signature
            agent: The agent instance

        Returns:
            Modified tool signature for the LLM
        """
        ...

    @abstractmethod
    def adapt_parameters(
        self, tool_name: str, parameters: dict[str, Any], agent: Agent
    ) -> dict[str, Any]:
        """
        Transform parameters from the LLM back to the original tool format.

        This method is called during TOOL_CALL_BEFORE to convert the
        adapted parameters back to what the original tool expects.

        Args:
            tool_name: Name of the tool being called
            parameters: Parameters from the LLM (matching adapted signature)
            agent: The agent instance

        Returns:
            Transformed parameters for the original tool
        """
        ...

    def adapt_response(
        self, tool_name: str, response: ToolResponse, agent: Agent
    ) -> ToolResponse | None:
        """
        Optionally transform the tool response.

        This method is called after tool execution to modify the response
        before it's added to the conversation. Return None to use the
        original response unchanged.

        Args:
            tool_name: Name of the tool that was called
            response: The tool's response
            agent: The agent instance

        Returns:
            Modified response or None to keep original
        """
        return None

    def store_original_signature(self, tool_name: str, signature: ToolSignature):
        """Store the original signature for reference."""
        self._original_signatures[tool_name] = signature

    def get_original_signature(self, tool_name: str) -> ToolSignature | None:
        """Retrieve the original signature."""
        return self._original_signatures.get(tool_name)

    def analyze_transformation(self, tool: ToolLike, signature: ToolSignature) -> AdapterMetadata:
        """
        Analyze what transformations this adapter will perform.

        This method should be overridden by subclasses to provide
        metadata about their transformations for conflict detection.

        Args:
            tool: The tool being adapted (Tool instance or BoundTool descriptor)
            signature: The current signature

        Returns:
            Metadata about the transformations
        """
        # Default implementation - subclasses should override
        return AdapterMetadata(modified_params=set(), added_params=set(), removed_params=set())


class ToolAdapterRegistry:
    """
    Registry for managing tool adapters within a component.

    This class handles the registration and application of multiple
    adapters, supporting adapter chaining when needed.
    """

    def __init__(self, default_strategy: ConflictStrategy = ConflictStrategy.CHAIN):
        """Initialize the adapter registry."""
        self._adapters: list[ToolAdapter] = []
        self._tool_adapter_map: dict[str, list[ToolAdapter]] = {}
        self._default_strategy = default_strategy
        self._conflict_cache: dict[str, list[tuple[str, list[ToolAdapter]]]] = {}

    def register(self, adapter: ToolAdapter):
        """
        Register a tool adapter.

        Args:
            adapter: The adapter to register
        """
        if adapter not in self._adapters:
            self._adapters.append(adapter)
            # Sort by priority (higher priority first)
            self._adapters.sort(key=lambda a: a.priority, reverse=True)
            # Clear caches
            self._tool_adapter_map.clear()
            self._conflict_cache.clear()

    def unregister(self, adapter: ToolAdapter):
        """
        Unregister a tool adapter.

        Args:
            adapter: The adapter to unregister
        """
        if adapter in self._adapters:
            self._adapters.remove(adapter)
            # Clear caches
            self._tool_adapter_map.clear()
            self._conflict_cache.clear()

    def get_adapters_for_tool(self, tool: ToolLike, agent: Agent) -> list[ToolAdapter]:
        """
        Get all adapters that should process the given tool.

        Args:
            tool: The tool to check (Tool instance or BoundTool descriptor)
            agent: The agent instance

        Returns:
            List of applicable adapters (may be empty)
        """
        tool_name = tool.name

        # Check cache first
        if tool_name in self._tool_adapter_map:
            return self._tool_adapter_map[tool_name]

        # Find applicable adapters
        applicable = [adapter for adapter in self._adapters if adapter.should_adapt(tool, agent)]

        # Cache the result
        self._tool_adapter_map[tool_name] = applicable
        return applicable

    def adapt_signature(
        self, tool: ToolLike, signature: ToolSignature, agent: Agent
    ) -> ToolSignature:
        """
        Apply all applicable adapters to transform a tool signature.

        Checks for conflicts and applies resolution strategy.

        Args:
            tool: The original tool (Tool instance or BoundTool descriptor)
            signature: The original signature
            agent: The agent instance

        Returns:
            Transformed signature (or original if no adapters apply)

        Raises:
            ValueError: If conflicts cannot be resolved
        """
        adapters = self.get_adapters_for_tool(tool, agent)

        if not adapters:
            return signature

        # Check for conflicts if not cached
        tool_name = tool.name
        if tool_name not in self._conflict_cache:
            conflicts = self.detect_conflicts(tool, adapters)
            self._conflict_cache[tool_name] = conflicts

            # Resolve or raise based on strategy
            strategy = adapters[0].conflict_strategy if adapters else self._default_strategy
            self.resolve_conflicts(conflicts, strategy)

        # Store original for all adapters so they can be used in reverse
        for adapter in adapters:
            adapter.store_original_signature(tool.name, signature)

        # Apply adapters in sequence (already sorted by priority)
        adapted_signature = signature
        for adapter in adapters:
            adapted_signature = adapter.adapt_signature(tool, adapted_signature, agent)

        return adapted_signature

    def adapt_parameters(
        self, tool_name: str, parameters: dict[str, Any], agent: Agent
    ) -> dict[str, Any]:
        """
        Apply adapters to transform parameters back to original format.

        Args:
            tool_name: Name of the tool being called
            parameters: Parameters from the LLM
            agent: The agent instance

        Returns:
            Transformed parameters (or original if no adapters apply)
        """
        # Find adapters that were applied to this tool
        # We need to apply them in reverse order for parameters
        applicable_adapters = []
        for adapter in self._adapters:
            if tool_name in adapter._original_signatures:
                applicable_adapters.append(adapter)

        if not applicable_adapters:
            return parameters

        # Apply adapters in reverse order for parameters
        adapted_params = parameters
        for adapter in reversed(applicable_adapters):
            adapted_params = adapter.adapt_parameters(tool_name, adapted_params, agent)

        return adapted_params

    def adapt_response(self, tool_name: str, response: ToolResponse, agent: Agent) -> ToolResponse:
        """
        Apply adapters to transform a tool response.

        Args:
            tool_name: Name of the tool that was called
            response: The tool's response
            agent: The agent instance

        Returns:
            Transformed response (or original if no adapters apply)
        """
        # Find adapters that were applied to this tool
        applicable_adapters = []
        for adapter in self._adapters:
            if tool_name in adapter._original_signatures:
                applicable_adapters.append(adapter)

        if not applicable_adapters:
            return response

        # Apply response adapters in forward order
        adapted_response = response
        for adapter in applicable_adapters:
            result = adapter.adapt_response(tool_name, adapted_response, agent)
            if result is not None:
                adapted_response = result

        return adapted_response

    def detect_conflicts(
        self, tool: ToolLike, adapters: list[ToolAdapter]
    ) -> list[tuple[str, list[ToolAdapter]]]:
        """
        Detect parameter conflicts between adapters.

        Args:
            tool: The tool being adapted (Tool instance or BoundTool descriptor)
            adapters: List of applicable adapters

        Returns:
            List of (parameter, [conflicting_adapters]) tuples
        """
        param_adapters: dict[str, list[ToolAdapter]] = {}

        # Analyze each adapter's transformations
        signature = tool.signature
        for adapter in adapters:
            metadata = adapter.analyze_transformation(tool, signature)

            # Track which parameters each adapter touches
            # (modified, removed, or added - all can conflict)
            all_params = metadata.modified_params | metadata.removed_params | metadata.added_params
            for param in all_params:
                if param not in param_adapters:
                    param_adapters[param] = []
                param_adapters[param].append(adapter)

        # Find conflicts (multiple adapters touching same parameter)
        conflicts = []
        for param, adapter_list in param_adapters.items():
            if len(adapter_list) > 1:
                conflicts.append((param, adapter_list))

        return conflicts

    def resolve_conflicts(
        self,
        conflicts: list[tuple[str, list[ToolAdapter]]],
        strategy: ConflictStrategy | None = None,
    ) -> None:
        """
        Resolve or report conflicts between adapters.

        Args:
            conflicts: Detected conflicts
            strategy: Resolution strategy (uses default if None)

        Raises:
            ValueError: If EXCLUSIVE strategy and conflicts exist
        """
        if not conflicts:
            return

        strategy = strategy or self._default_strategy

        if strategy == ConflictStrategy.EXCLUSIVE:
            # Report the conflict details
            conflict_details = []
            for param, adapters in conflicts:
                adapter_names = [type(a).__name__ for a in adapters]
                conflict_details.append(f"{param}: {adapter_names}")

            raise ValueError(
                f"Multiple adapters attempting to modify the same parameters "
                f"(EXCLUSIVE strategy): {', '.join(conflict_details)}"
            )

        # For other strategies, we proceed (CHAIN is default behavior)
        # PRIORITY is handled by sorting adapters by priority
        # MERGE would require custom implementation per adapter type

    def clear(self):
        """Clear all registered adapters."""
        self._adapters.clear()
        self._tool_adapter_map.clear()
        self._conflict_cache.clear()
