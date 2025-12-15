import asyncio
import logging
from typing import Any, TypedDict
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

from good_agent.core.components.component import AgentComponent
from good_agent.mcp.adapter import MCPToolAdapter, MCPToolSpec

logger = logging.getLogger(__name__)


class MCPServerConfig(TypedDict, total=False):
    """Configuration for an MCP server connection."""

    url: str  # Server URL or command
    auth: dict[str, Any] | None  # Authentication config
    timeout: float  # Connection timeout
    auto_reconnect: bool  # Auto-reconnect on disconnect
    namespace: str | None  # Optional namespace for tools


class MCPConnection(BaseModel):
    """Represents a connection to an MCP server."""

    model_config = {"arbitrary_types_allowed": True}

    server_id: str
    config: dict[str, Any]
    session: ClientSession | None = None
    tools: dict[str, MCPToolAdapter] = Field(default_factory=dict)
    resources: dict[str, Any] = Field(default_factory=dict)
    is_connected: bool = False
    error: str | None = None


class MCPClientManager(AgentComponent):
    """
    Manages MCP client connections for an agent.

    This manager handles:
    - Connecting to multiple MCP servers
    - Tool discovery and registration
    - Resource discovery
    - Connection lifecycle management
    - Authentication and security
    """

    def __init__(self):
        """Initialize the MCP client manager."""
        super().__init__()
        self.connections: dict[str, MCPConnection] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self, server_configs: list[str | MCPServerConfig] | None = None):
        """
        Initialize the manager and connect to configured servers.

        Args:
            server_configs: List of server configurations or URLs
        """
        if self._initialized:
            return

        self._initialized = True

        if server_configs:
            await self.connect_servers(server_configs)

    async def connect_servers(self, server_configs: list[str | MCPServerConfig]):
        """
        Connect to multiple MCP servers.

        Args:
            server_configs: List of server configurations
        """
        tasks = []
        for config in server_configs:
            if isinstance(config, str):
                # Simple URL string
                config = {"url": config}
            tasks.append(self.connect(config))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to connect to server {server_configs[i]}: {result}")

    async def connect(self, config: MCPServerConfig) -> MCPConnection:
        """
        Connect to a single MCP server.

        Args:
            config: Server configuration

        Returns:
            MCPConnection object
        """
        server_url = config["url"]
        server_id = self._generate_server_id(server_url)

        async with self._lock:
            # Check if already connected
            if server_id in self.connections:
                connection = self.connections[server_id]
                if connection.is_connected:
                    logger.info(f"Already connected to MCP server: {server_id}")
                    return connection

            # Create new connection
            connection = MCPConnection(
                server_id=server_id,
                config=dict(config),  # Convert TypedDict to dict
            )

            try:
                # Determine connection type based on URL
                session = await self._create_session(config)
                connection.session = session

                # Initialize the session
                await session.initialize()

                # Discover tools and resources
                await self._discover_tools(connection)
                await self._discover_resources(connection)

                connection.is_connected = True
                logger.info(
                    f"Connected to MCP server: {server_id} with {len(connection.tools)} tools"
                )

            except Exception as e:
                logger.error(f"Failed to connect to MCP server {server_id}: {e}")
                connection.error = str(e)
                connection.is_connected = False

            self.connections[server_id] = connection
            return connection

    async def _create_session(self, config: MCPServerConfig) -> ClientSession:
        """
        Create an MCP client session based on the configuration.

        Args:
            config: Server configuration

        Returns:
            ClientSession instance
        """
        url = config["url"]

        # Parse the URL to determine connection type
        parsed = urlparse(url)

        if parsed.scheme in ("http", "https"):
            # SSE-based connection for HTTP(S) servers
            async with sse_client(url) as (read, write):
                return ClientSession(read, write)

        elif parsed.scheme == "stdio" or not parsed.scheme:
            # Stdio-based connection for local commands
            # Treat as a command if no scheme
            command = url.replace("stdio://", "") if url.startswith("stdio://") else url

            # Parse command and arguments
            parts = command.split()
            env_value = config.get("env", None)
            server_params = StdioServerParameters(
                command=parts[0],
                args=parts[1:] if len(parts) > 1 else [],
                env=env_value if isinstance(env_value, dict) else None,  # type: ignore[arg-type]
            )

            async with stdio_client(server_params) as (read, write):
                return ClientSession(read, write)

        else:
            raise ValueError(f"Unsupported MCP server URL scheme: {parsed.scheme}")

    async def _discover_tools(self, connection: MCPConnection):
        """
        Discover available tools from an MCP server.

        Args:
            connection: The MCP connection
        """
        if not connection.session:
            return

        try:
            # List available tools
            tools_response = await connection.session.list_tools()

            for tool_info in tools_response.tools:
                # Create tool spec from MCP tool info
                tool_spec = MCPToolSpec(
                    name=tool_info.name,
                    description=tool_info.description,
                    input_schema=tool_info.inputSchema
                    if hasattr(tool_info, "inputSchema")
                    else None,
                )

                # Create adapter with namespace if configured
                namespace = connection.config.get("namespace")
                tool_name = f"{namespace}:{tool_info.name}" if namespace else tool_info.name

                # Create the adapter
                adapter: MCPToolAdapter[Any] = MCPToolAdapter(
                    mcp_client=connection.session,
                    tool_spec=tool_spec,
                    name=tool_name,
                    timeout=connection.config.get("timeout", 30.0),
                )

                connection.tools[tool_name] = adapter

                # Register with agent's tool manager if attached
                if self.agent and hasattr(self.agent, "tools"):
                    self.agent.tools[tool_name] = adapter

            logger.debug(f"Discovered {len(connection.tools)} tools from {connection.server_id}")

        except Exception as e:
            logger.error(f"Failed to discover tools from {connection.server_id}: {e}")

    async def _discover_resources(self, connection: MCPConnection):
        """
        Discover available resources from an MCP server.

        Args:
            connection: The MCP connection
        """
        if not connection.session:
            return

        try:
            # List available resources
            resources_response = await connection.session.list_resources()

            for resource in resources_response.resources:
                resource_id = str(resource.uri)  # type: ignore[index]
                connection.resources[resource_id] = {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description
                    if hasattr(resource, "description")
                    else None,
                    "mimeType": resource.mimeType if hasattr(resource, "mimeType") else None,
                }

            logger.debug(
                f"Discovered {len(connection.resources)} resources from {connection.server_id}"
            )

        except Exception as e:
            logger.error(f"Failed to discover resources from {connection.server_id}: {e}")

    async def disconnect(self, server_id: str):
        """
        Disconnect from an MCP server.

        Args:
            server_id: The server identifier
        """
        async with self._lock:
            if server_id not in self.connections:
                logger.warning(f"No connection found for server: {server_id}")
                return

            connection = self.connections[server_id]

            try:
                if connection.session:
                    # Close the session
                    await connection.session.__aexit__(None, None, None)

                connection.is_connected = False
                connection.session = None

                # Remove tools from agent's tool manager
                if self.agent and hasattr(self.agent, "tools"):
                    for tool_name in connection.tools:
                        if tool_name in self.agent.tools:
                            del self.agent.tools[tool_name]

                logger.info(f"Disconnected from MCP server: {server_id}")

            except Exception as e:
                logger.error(f"Error disconnecting from {server_id}: {e}")

            finally:
                del self.connections[server_id]

    async def disconnect_all(self):
        """Disconnect from all MCP servers."""
        server_ids = list(self.connections.keys())
        for server_id in server_ids:
            await self.disconnect(server_id)

    def get_tools(self) -> dict[str, MCPToolAdapter]:
        """
        Get all available tools from all connected servers.

        Returns:
            Dictionary of tool name to adapter
        """
        all_tools = {}
        for connection in self.connections.values():
            if connection.is_connected:
                all_tools.update(connection.tools)
        return all_tools

    def get_resources(self) -> dict[str, Any]:
        """
        Get all available resources from all connected servers.

        Returns:
            Dictionary of resource URI to resource info
        """
        all_resources = {}
        for connection in self.connections.values():
            if connection.is_connected:
                all_resources.update(connection.resources)
        return all_resources

    async def read_resource(self, uri: str) -> Any:
        """
        Read a resource from an MCP server.

        Args:
            uri: Resource URI

        Returns:
            Resource content
        """
        # Find the connection that has this resource
        for connection in self.connections.values():
            if uri in connection.resources and connection.session:
                try:
                    response = await connection.session.read_resource(uri)  # type: ignore[arg-type]
                    return response.contents
                except Exception as e:
                    logger.error(f"Failed to read resource {uri}: {e}")
                    raise

        raise ValueError(f"Resource not found: {uri}")

    def _generate_server_id(self, url: str) -> str:
        """
        Generate a unique server ID from a URL.

        Args:
            url: Server URL or command

        Returns:
            Unique server identifier
        """
        # For URLs, use the hostname
        parsed = urlparse(url)
        if parsed.netloc:
            return parsed.netloc

        # For commands, use the command name
        parts = url.split()
        if parts:
            return parts[0].split("/")[-1]  # Get basename

        # Fallback to the full URL
        return url

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect_all()

    def __repr__(self) -> str:
        """String representation."""
        connected = sum(1 for c in self.connections.values() if c.is_connected)
        total = len(self.connections)
        return f"MCPClientManager(connected={connected}/{total})"
