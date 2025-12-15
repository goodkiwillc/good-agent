import asyncio
import logging
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, create_model

from good_agent.tools import Tool, ToolResponse

logger = logging.getLogger(__name__)

T_Response = TypeVar("T_Response")


class MCPToolSpec(BaseModel):
    """Specification for an MCP tool."""

    name: str
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    examples: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    version: str = "1.0.0"


class MCPToolAdapter(Tool[..., T_Response], Generic[T_Response]):
    """
    Adapts an MCP server tool to the GoodIntel Tool interface.

    This adapter handles:
    - Parameter conversion between MCP and GoodIntel formats
    - Schema validation and type conversion
    - Error handling and retries
    - Result transformation
    """

    def __init__(
        self,
        mcp_client: Any,  # Will be MCPClient from fastmcp
        tool_spec: MCPToolSpec,
        name: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the MCP tool adapter.

        Args:
            mcp_client: The MCP client instance
            tool_spec: The MCP tool specification
            name: Optional override for tool name
            timeout: Timeout for tool execution in seconds
        """
        self.mcp_client = mcp_client
        self.spec = tool_spec
        self.timeout = timeout

        # Build the Pydantic model for input validation if schema provided
        self._input_model = None
        if tool_spec.input_schema:
            self._input_model = self._create_input_model(tool_spec.input_schema)

        # Initialize the base Tool with the MCP tool's metadata
        super().__init__(
            fn=self._execute_mcp_tool,  # type: ignore[arg-type]
            name=name or tool_spec.name,
            description=tool_spec.description or f"MCP tool: {tool_spec.name}",
        )

    def _create_input_model(self, schema: dict[str, Any]) -> type[BaseModel]:
        """
        Create a Pydantic model from an MCP input schema.

        Args:
            schema: JSON schema for the tool's input

        Returns:
            A Pydantic model class for validation
        """
        # Extract properties and required fields from JSON schema
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        # Build field definitions for Pydantic
        fields = {}
        for field_name, field_schema in properties.items():
            field_type = self._json_schema_to_python_type(field_schema)
            field_default = ... if field_name in required else None
            field_description = field_schema.get("description", "")

            fields[field_name] = (
                field_type,
                Field(default=field_default, description=field_description),
            )

        # Create dynamic Pydantic model
        return create_model(  # type: ignore[call-overload]
            f"{self.spec.name}Input",
            __module__=__name__,
            **fields,
        )

    def _json_schema_to_python_type(self, schema: dict[str, Any]) -> type:
        """
        Convert JSON schema type to Python type.

        Args:
            schema: JSON schema definition

        Returns:
            Corresponding Python type
        """
        type_map = {
            "string": str,
            "number": float,
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        json_type = schema.get("type", "string")

        # Handle array types with items
        if json_type == "array":
            items_schema = schema.get("items", {})
            # Recursively get the item type, but use Any for complex nested types
            self._json_schema_to_python_type(items_schema)
            # For typing purposes, we use list[Any] to avoid "not valid as a type" errors
            return list[Any]  # type: ignore[valid-type]

        # Handle union types
        if isinstance(json_type, list):
            # For now, just use Any for union types
            # Could be enhanced to use Union types
            return Any

        return type_map.get(json_type, Any)

    async def _execute_mcp_tool(self, **kwargs: Any) -> ToolResponse[T_Response]:
        """
        Execute the MCP tool via the client.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResponse with the execution result
        """
        try:
            # Validate input if we have a model
            if self._input_model:
                try:
                    validated_input = self._input_model(**kwargs)
                    params = validated_input.model_dump()
                except Exception as e:
                    logger.error(f"Input validation failed for MCP tool {self.spec.name}: {e}")
                    return ToolResponse(
                        tool_name=self.name,
                        response=None,  # type: ignore[arg-type]
                        error=f"Input validation failed: {str(e)}",
                        success=False,
                    )
            else:
                params = kwargs

            # Execute the tool via MCP client with timeout
            logger.debug(f"Executing MCP tool {self.spec.name} with params: {params}")

            try:
                # Call the MCP tool through the client
                result = await asyncio.wait_for(
                    self.mcp_client.call_tool(self.spec.name, params),
                    timeout=self.timeout,
                )

                # Transform the result if needed
                transformed_result = self._transform_result(result)

                return ToolResponse(
                    tool_name=self.name,
                    response=transformed_result,
                    error=None,
                    success=True,
                )

            except TimeoutError:
                logger.error(f"MCP tool {self.spec.name} timed out after {self.timeout}s")
                return ToolResponse(
                    tool_name=self.name,
                    response=None,  # type: ignore[arg-type]
                    error=f"Tool execution timed out after {self.timeout} seconds",
                    success=False,
                )

        except Exception as e:
            logger.error(f"Error executing MCP tool {self.spec.name}: {e}")
            return ToolResponse(
                tool_name=self.name,
                response=None,  # type: ignore[arg-type]
                error=str(e),
                success=False,
            )

    def _transform_result(self, mcp_result: Any) -> Any:
        """
        Transform MCP tool result to GoodIntel format.

        Args:
            mcp_result: Raw result from MCP tool

        Returns:
            Transformed result suitable for GoodIntel
        """
        # If result is already a dict or primitive, return as-is
        if isinstance(mcp_result, (dict, list, str, int, float, bool, type(None))):
            return mcp_result

        # If result has a model_dump method (Pydantic model), use it
        if hasattr(mcp_result, "model_dump"):
            return mcp_result.model_dump()

        # If result has a dict method, use it
        if hasattr(mcp_result, "dict"):
            return mcp_result.dict()

        # If result has a to_dict method, use it
        if hasattr(mcp_result, "to_dict"):
            return mcp_result.to_dict()

        # Otherwise, try to convert to string
        return str(mcp_result)

    def get_schema(self) -> dict[str, Any]:
        """
        Get the tool's schema in OpenAI function calling format.

        Returns:
            Tool schema dictionary
        """
        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
            },
        }

        # Add parameters if we have an input schema
        if self.spec.input_schema:
            schema["function"]["parameters"] = self.spec.input_schema
        else:
            schema["function"]["parameters"] = {
                "type": "object",
                "properties": {},
                "required": [],
            }

        return schema

    def __repr__(self) -> str:
        """String representation of the adapter."""
        return f"MCPToolAdapter(name={self.name}, mcp_tool={self.spec.name}, version={self.spec.version})"
