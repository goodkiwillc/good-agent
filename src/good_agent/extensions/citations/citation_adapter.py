from __future__ import annotations

import copy
import logging
from typing import TYPE_CHECKING, Any

from good_agent.core.components.tool_adapter import AdapterMetadata, ToolAdapter

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from good_agent import Agent
    from good_agent.extensions.citations.manager import CitationManager
    from good_agent.tools import BoundTool, Tool, ToolSignature

    CitationManagerType = CitationManager
else:
    CitationManagerType = Any


class CitationAdapter(ToolAdapter[CitationManagerType]):
    """
    Tool adapter that transforms URL parameters to citation indices.

    This adapter:
    1. Identifies tools that accept URL parameters
    2. Modifies their signatures to accept citation indices instead
    3. Translates indices back to URLs before tool execution
    4. Maintains the citation-to-URL mapping in the CitationManager

    Example:
        >>> manager = CitationManager()
        >>> adapter = CitationAdapter(manager)
        >>> manager.register_tool_adapter(adapter)

        # Tool signature is transformed:
        # Original: fetch_url(url: str) -> str
        # Adapted:  fetch_url(citation_idx: int) -> str

        # LLM calls with: {"citation_idx": 0}
        # Adapter transforms to: {"url": "https://example.com"}
    """

    def analyze_transformation(
        self, tool: Tool[Any, Any] | BoundTool[Any, Any, Any], signature: ToolSignature
    ) -> AdapterMetadata:
        """
        Analyze the transformations this adapter will perform.

        Returns metadata about which parameters will be modified.
        """
        modified: set[str] = set()
        added = set()
        removed = set()

        # Check which parameters we'll modify
        params: dict[str, Any] = signature["function"]["parameters"].get("properties", {})
        for key, schema in params.items():
            # Single URL parameter
            if key == "url" and schema.get("type") == "string":
                removed.add("url")
                added.add("citation_idx")
            # Multiple URLs parameter
            elif key == "urls" and schema.get("type") == "array":
                items = schema.get("items", {})
                if items.get("type") == "string":
                    removed.add("urls")
                    added.add("citation_idxs")

        return AdapterMetadata(modified_params=modified, added_params=added, removed_params=removed)

    def should_adapt(self, tool: Tool[Any, Any] | BoundTool[Any, Any, Any], agent: Agent) -> bool:
        """
        Check if this tool should be adapted.

        Tools are adapted only if they have specific URL parameters:
        - url: str or url: URL
        - urls: list[str] or urls: list[URL]

        Args:
            tool: The tool to check
            agent: The agent instance

        Returns:
            True if the tool has matching URL parameters
        """
        # Get the tool's model to inspect parameters
        try:
            model = tool.model  # type: ignore[union-attr]
            schema = model.model_json_schema()
            properties = schema.get("properties", {})

            # Check for parameter names containing 'url' and appropriate types
            for param_name, param_schema in properties.items():
                # Check for single URL parameter (exact match or contains 'url')
                if "url" in param_name.lower() and not param_name.lower().endswith("s"):
                    # Check if it's a string type (URL objects appear as strings in JSON schema)
                    if param_schema.get("type") == "string":
                        return True

                # Check for multiple URLs parameter (ends with 'urls' or contains 'urls')
                elif "urls" in param_name.lower() or (
                    "url" in param_name.lower() and param_name.lower().endswith("s")
                ):
                    # Check if it's an array of strings
                    if param_schema.get("type") == "array":
                        items = param_schema.get("items", {})
                        if items.get("type") == "string":
                            return True

            return False
        except Exception:
            return False

    def adapt_signature(
        self,
        tool: Tool[Any, Any] | BoundTool[Any, Any, Any],
        signature: ToolSignature,
        agent: Agent,
    ) -> ToolSignature:
        """
        Transform tool signature to use citation indices.

        Replaces URL string parameters with integer citation indices.

        Args:
            tool: The original tool
            signature: The original tool signature
            agent: The agent instance

        Returns:
            Modified signature with citation index parameters
        """
        # Deep copy the signature to avoid modifying the original
        adapted_sig = copy.deepcopy(signature)

        # Get the function parameters
        params = adapted_sig["function"]["parameters"]
        properties: dict[str, Any] = params.get("properties", {})

        # Track which parameters we're adapting
        adapted_params = []

        # Replace URL parameters with citation indices
        for key, schema in list(properties.items()):
            # Handle single URL parameter (exact match or contains 'url')
            if (
                "url" in key.lower()
                and not key.lower().endswith("s")
                and schema.get("type") == "string"
            ):
                adapted_params.append(key)

                # Generate new parameter name by replacing 'url' with 'citation_idx'
                # Handle different case variations
                if key == "url":
                    new_key = "citation_idx"
                else:
                    # Replace 'url' with 'citation_idx' preserving other parts
                    # e.g., 'url_to_fetch' -> 'citation_idx_to_fetch'
                    new_key = key.replace("url", "citation_idx").replace("URL", "citation_idx")

                # Replace with citation index
                properties[new_key] = {
                    "type": "integer",
                    "description": "Index of the citation to use (0-based)",
                    "minimum": 0,
                }
                del properties[key]

                # Update required list if needed
                if "required" in params and key in params["required"]:
                    idx = params["required"].index(key)
                    params["required"][idx] = new_key

            # Handle multiple URLs parameter
            elif (
                "urls" in key.lower() or ("url" in key.lower() and key.lower().endswith("s"))
            ) and schema.get("type") == "array":
                items = schema.get("items", {})
                if items.get("type") == "string":
                    adapted_params.append(key)

                    # Generate new parameter name
                    if key == "urls":
                        new_key = "citation_idxs"
                    else:
                        # Replace 'urls' with 'citation_idxs' or 'url' with 'citation_idx'
                        new_key = key.replace("urls", "citation_idxs").replace(
                            "URLs", "citation_idxs"
                        )
                        if "urls" not in key.lower():
                            new_key = key.replace("url", "citation_idx").replace(
                                "URL", "citation_idx"
                            )

                    # Replace with citation indices array
                    properties[new_key] = {
                        "type": "array",
                        "items": {"type": "integer", "minimum": 0},
                        "description": "List of citation indices (0-based)",
                    }
                    del properties[key]

                    # Update required list if needed
                    if "required" in params and key in params["required"]:
                        idx = params["required"].index(key)
                        params["required"][idx] = new_key

        # Update function description to mention citations
        if adapted_params:
            orig_desc = adapted_sig["function"].get("description", "")
            adapted_sig["function"]["description"] = (
                f"{orig_desc} [Uses citation indices instead of URLs. "
                f"Reference citations by their 0-based index.]"
            ).strip()

        return adapted_sig

    def adapt_parameters(
        self, tool_name: str, parameters: dict[str, Any], agent: Agent
    ) -> dict[str, Any]:
        """
        Transform citation indices back to URLs.

        Args:
            tool_name: Name of the tool being called
            parameters: Parameters from the LLM (with citation indices)
            agent: The agent instance

        Returns:
            Parameters with URLs restored
        """
        # Copy parameters to avoid modifying original
        adapted_params = dict(parameters)

        # Find any parameters containing 'citation_idx' (including alternate names)
        for key in list(adapted_params.keys()):
            # Handle single citation index (any parameter containing 'citation_idx' but not ending in 's')
            if "citation_idx" in key and not key.endswith("s"):
                idx = adapted_params.pop(key)
                # Generate URL parameter name by reversing the transformation
                url_key = key.replace("citation_idx", "url")

                url = self.component.index.get_url(idx)
                if url:
                    adapted_params[url_key] = url
                else:
                    # Invalid index - keep as is for error handling and emit warning
                    logger.warning("Citation index %s not found in global index.", idx)
                    adapted_params[key] = idx

            # Handle multiple citation indices (parameter containing 'citation_idx' and ending in 's')
            elif "citation_idx" in key and key.endswith("s"):
                idxs = adapted_params.pop(key)
                # Generate URLs parameter name
                urls_key = key.replace("citation_idx", "url")

                urls = []
                for idx in idxs:
                    url = self.component.index.get_url(idx)
                    if url:
                        urls.append(url)
                # Only set urls if we got at least some valid ones
                if urls:
                    adapted_params[urls_key] = urls
                else:
                    # Keep original if all invalid
                    adapted_params[key] = idxs

        return adapted_params
