"""
MCP (Model Context Protocol) Client Manager

Handles connections to MCP servers and tool execution using FastMCP.
Supports both STDIO and Streamable HTTP transports.
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from src.logger import get_logger
from src.mcp_config_storage import (
    MCPConfigStorage,
    MCPServerConfig,
    MCPToolConfig,
    MCPToolExecutionMode,
    MCPTransportType,
    get_mcp_storage,
)

logger = get_logger(__name__)


class StreamableHTTPClient:
    """Client for MCP Streamable HTTP transport.

    Implements the MCP Streamable HTTP protocol which uses:
    - POST /mcp with JSON-RPC messages
    - Mcp-Session-Id header for session management
    """

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize the Streamable HTTP client.

        Args:
            base_url: Base URL of the MCP server (e.g., http://localhost:3001)
            headers: Additional headers to include in requests
        """
        self.base_url = base_url.rstrip("/")
        self.mcp_endpoint = f"{self.base_url}/mcp"
        self.session_id: Optional[str] = None
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **(headers or {}),
        }
        self._client: Optional[httpx.AsyncClient] = None
        self._request_id = 0

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=30.0)
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            # Try to terminate session gracefully
            if self.session_id:
                try:
                    await self._client.delete(
                        self.mcp_endpoint,
                        headers={**self.headers, "mcp-session-id": self.session_id},
                    )
                except Exception:
                    pass
            await self._client.aclose()
            self._client = None

    def _next_request_id(self) -> int:
        """Get next JSON-RPC request ID."""
        self._request_id += 1
        return self._request_id

    async def _initialize(self) -> None:
        """Initialize the MCP session."""
        if not self._client:
            raise RuntimeError("Client not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "decision-analyzer", "version": "1.0.0"},
            },
        }

        response = await self._client.post(
            self.mcp_endpoint, json=request, headers=self.headers
        )
        response.raise_for_status()

        # Extract session ID from response headers
        self.session_id = response.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("Server did not return session ID")

        logger.debug(f"MCP session initialized: {self.session_id}")

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

    def _parse_sse_response(self, text: str) -> Dict[str, Any]:
        """Parse SSE formatted response to extract JSON data."""

        # SSE format: "event: message\ndata: {...json...}\n\n"
        data_line = None
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("data:"):
                data_line = line[5:].strip()
                break

        if not data_line:
            raise RuntimeError(f"No data line found in SSE response: {text[:200]}")

        return json.loads(data_line)

    async def _send_request(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Send a JSON-RPC request and return the result."""
        if not self._client or not self.session_id:
            raise RuntimeError("Client not initialized")

        request = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": method,
        }
        if params:
            request["params"] = params

        response = await self._client.post(
            self.mcp_endpoint,
            json=request,
            headers={**self.headers, "mcp-session-id": self.session_id},
        )
        response.raise_for_status()

        # Handle SSE (text/event-stream) or JSON response
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            data = self._parse_sse_response(response.text)
        else:
            data = response.json()

        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")

        return data.get("result")

    async def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        if not self._client or not self.session_id:
            raise RuntimeError("Client not initialized")

        notification = {"jsonrpc": "2.0", "method": method, "params": params}

        await self._client.post(
            self.mcp_endpoint,
            json=notification,
            headers={**self.headers, "mcp-session-id": self.session_id},
        )

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the server."""
        result = await self._send_request("tools/list")
        return result.get("tools", []) if result else []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with the given arguments."""
        result = await self._send_request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        return result


class MCPToolResult:
    """Result from calling an MCP tool."""

    def __init__(
        self,
        server_id: str,
        server_name: str,
        tool_name: str,
        success: bool,
        result: Any = None,
        error: Optional[str] = None,
    ):
        self.server_id = server_id
        self.server_name = server_name
        self.tool_name = tool_name
        self.success = success
        self.result = result
        self.error = error

    def to_context_string(self) -> str:
        """Format the result as context for the LLM."""
        if not self.success:
            return (
                f"[MCP Tool Error - {self.server_name}/{self.tool_name}]: {self.error}"
            )

        result_str = self._format_result(self.result)
        return f"[MCP Tool Result - {self.server_name}/{self.tool_name}]:\n{result_str}"

    def _format_result(self, result: Any) -> str:
        """Format the result content for display."""
        if result is None:
            return "No result returned"

        # Handle FastMCP CallToolResult
        if hasattr(result, "content"):
            # CallToolResult has a list of content items
            content_parts = []
            for item in result.content:
                if hasattr(item, "text"):
                    content_parts.append(item.text)
                elif hasattr(item, "data"):
                    content_parts.append(str(item.data))
                else:
                    content_parts.append(str(item))
            return "\n".join(content_parts)

        # Handle dict results
        if isinstance(result, dict):
            import json

            return json.dumps(result, indent=2)

        # Handle list results
        if isinstance(result, list):
            import json

            return json.dumps(result, indent=2)

        return str(result)


class MCPClientManager:
    """Manages MCP server connections and tool execution."""

    def __init__(self, storage: Optional[MCPConfigStorage] = None):
        """
        Initialize the MCP client manager.

        Args:
            storage: Storage instance for MCP configurations (default: singleton)
        """
        self.storage = storage or get_mcp_storage()
        self._client_cache: Dict[str, Any] = {}

    async def get_client_config(self, server_config: MCPServerConfig) -> Dict[str, Any]:
        """Build a FastMCP client configuration from server config.

        Args:
            server_config: The MCP server configuration

        Returns:
            Configuration dict suitable for FastMCP Client
        """
        config: Dict[str, Any] = {}

        if server_config.transport_type == MCPTransportType.STDIO:
            if not server_config.command:
                raise ValueError(
                    f"STDIO transport requires 'command' for server {server_config.name}"
                )
            config["command"] = server_config.command
            config["args"] = server_config.args or []
            if server_config.env:
                config["env"] = server_config.env
            if server_config.cwd:
                config["cwd"] = server_config.cwd

        elif server_config.transport_type in (
            MCPTransportType.HTTP,
            MCPTransportType.SSE,
        ):
            if not server_config.url:
                raise ValueError(
                    f"HTTP/SSE transport requires 'url' for server {server_config.name}"
                )
            config["url"] = server_config.url
            config["transport"] = server_config.transport_type.value

            if server_config.headers:
                config["headers"] = server_config.headers.copy()
            else:
                config["headers"] = {}

            # Handle authentication
            if server_config.auth_type and server_config.auth_token_encrypted:
                auth_token = self.storage.get_decrypted_auth_token(server_config)
                if auth_token:
                    if server_config.auth_type == "bearer":
                        config["headers"]["Authorization"] = f"Bearer {auth_token}"
                    elif server_config.auth_type == "api_key":
                        config["headers"]["X-API-Key"] = auth_token
                    elif server_config.auth_type == "oauth":
                        config["auth"] = "oauth"

        return config

    async def discover_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Connect to an MCP server and discover available tools.

        Args:
            server_id: ID of the MCP server to connect to

        Returns:
            List of discovered tools with their schemas
        """
        server_config = await self.storage.get(server_id)
        if not server_config:
            raise ValueError(f"MCP server not found: {server_id}")

        client_config = await self.get_client_config(server_config)
        discovered_tools = []

        try:
            # Use different clients based on transport type
            if server_config.transport_type in (
                MCPTransportType.HTTP,
                MCPTransportType.SSE,
            ):
                # Use StreamableHTTPClient for HTTP/SSE transport
                headers = client_config.get("headers", {})
                async with StreamableHTTPClient(
                    client_config["url"], headers
                ) as client:
                    # __aenter__ already initializes the session
                    tools = await client.list_tools()

                    for tool in tools:
                        tool_info = {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                        }
                        if "inputSchema" in tool:
                            tool_info["input_schema"] = tool["inputSchema"]
                        discovered_tools.append(tool_info)

            else:
                # Use FastMCP Client for STDIO transport
                from fastmcp import Client

                client_source = client_config["command"]
                if client_config.get("args"):
                    # Create full config dict for stdio with args
                    client_source = {
                        "mcpServers": {
                            server_config.name: {
                                "command": client_config["command"],
                                "args": client_config.get("args", []),
                                "env": client_config.get("env", {}),
                            }
                        }
                    }

                async with Client(client_source) as client:
                    tools = await client.list_tools()

                    for tool in tools:
                        tool_info = {
                            "name": tool.name,
                            "description": tool.description,
                        }
                        if hasattr(tool, "inputSchema"):
                            tool_info["input_schema"] = tool.inputSchema
                        discovered_tools.append(tool_info)

            logger.info(
                f"Discovered {len(discovered_tools)} tools from server {server_config.name}"
            )

            # Sync discovered tools to storage
            await self.storage.sync_tools(server_id, discovered_tools)

        except Exception as e:
            logger.error(
                f"Failed to discover tools from server {server_config.name}: {e}"
            )
            raise

        return discovered_tools

    async def call_tool(
        self,
        server_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> MCPToolResult:
        """Call a specific tool on an MCP server.

        Args:
            server_id: ID of the MCP server
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            MCPToolResult with the outcome
        """
        server_config = await self.storage.get(server_id)
        if not server_config:
            return MCPToolResult(
                server_id=server_id,
                server_name="Unknown",
                tool_name=tool_name,
                success=False,
                error=f"MCP server not found: {server_id}",
            )

        client_config = await self.get_client_config(server_config)

        try:
            # Use different clients based on transport type
            if server_config.transport_type in (
                MCPTransportType.HTTP,
                MCPTransportType.SSE,
            ):
                # Use StreamableHTTPClient for HTTP/SSE transport
                headers = client_config.get("headers", {})
                async with StreamableHTTPClient(
                    client_config["url"], headers
                ) as client:
                    # __aenter__ already initializes the session
                    result = await client.call_tool(tool_name, arguments)

                    return MCPToolResult(
                        server_id=server_id,
                        server_name=server_config.name,
                        tool_name=tool_name,
                        success=True,
                        result=result,
                    )

            else:
                # Use FastMCP Client for STDIO transport
                from fastmcp import Client

                client_source = {
                    "mcpServers": {
                        server_config.name: {
                            "command": client_config["command"],
                            "args": client_config.get("args", []),
                            "env": client_config.get("env", {}),
                        }
                    }
                }

                async with Client(client_source) as client:
                    # For multi-server config, tool names are prefixed with server name
                    full_tool_name = f"{server_config.name}_{tool_name}"

                    result = await client.call_tool(full_tool_name, arguments)

                    return MCPToolResult(
                        server_id=server_id,
                        server_name=server_config.name,
                        tool_name=tool_name,
                        success=True,
                        result=result,
                    )

        except Exception as e:
            logger.error(
                f"Failed to call tool {tool_name} on server {server_config.name}: {e}"
            )
            return MCPToolResult(
                server_id=server_id,
                server_name=server_config.name,
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    def _build_tool_arguments(
        self,
        tool_config: MCPToolConfig,
        generation_context: Dict[str, Any],
        user_arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the final arguments for a tool call.

        Args:
            tool_config: Tool configuration with defaults and mappings
            generation_context: Context from the ADR generation (prompt, etc.)
            user_arguments: User-provided argument overrides

        Returns:
            Final arguments dict
        """
        arguments = {}

        # Start with default arguments
        arguments.update(tool_config.default_arguments)

        # Apply context mappings
        for arg_name, context_field in tool_config.context_argument_mappings.items():
            if context_field in generation_context:
                arguments[arg_name] = generation_context[context_field]

        # Apply user overrides
        if user_arguments:
            arguments.update(user_arguments)

        return arguments

    async def execute_tools_for_generation(
        self,
        selected_tools: List[Dict[str, Any]],
        generation_context: Dict[str, Any],
        execution_mode: MCPToolExecutionMode = MCPToolExecutionMode.INITIAL_ONLY,
        persona_name: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> List[MCPToolResult]:
        """Execute MCP tools for ADR generation.

        Args:
            selected_tools: List of tool selections with server_id, tool_name, and optional arguments
            generation_context: Context from the ADR generation prompt
            execution_mode: Filter to only run tools with this execution mode
            persona_name: Optional persona name (for per-persona execution)
            progress_callback: Optional callback for progress updates

        Returns:
            List of tool results
        """
        results = []

        for tool_selection in selected_tools:
            server_id = tool_selection.get("server_id")
            tool_name = tool_selection.get("tool_name")
            user_arguments = tool_selection.get("arguments", {})

            if not server_id or not tool_name:
                logger.warning(f"Invalid tool selection: {tool_selection}")
                continue

            # Get server and tool config
            server_config = await self.storage.get(server_id)
            if not server_config:
                logger.warning(f"Server not found: {server_id}")
                continue

            tool_config = next(
                (t for t in server_config.tools if t.tool_name == tool_name), None
            )

            # If no stored config, create a default one
            if not tool_config:
                tool_config = MCPToolConfig(
                    tool_name=tool_name,
                    display_name=tool_name.replace("_", " ").title(),
                    execution_mode=MCPToolExecutionMode.INITIAL_ONLY,
                )

            # Check if this tool should run in the current mode
            if tool_config.execution_mode != execution_mode:
                continue

            if progress_callback:
                mode_str = f"for {persona_name}" if persona_name else "for all personas"
                progress_callback(
                    f"Calling MCP tool: {server_config.name}/{tool_name} {mode_str}"
                )

            # Build arguments
            arguments = self._build_tool_arguments(
                tool_config, generation_context, user_arguments
            )

            logger.info(
                "MCP tool arguments built",
                tool=tool_name,
                arguments=arguments,
                tool_mappings=tool_config.context_argument_mappings,
                tool_defaults=tool_config.default_arguments,
            )

            # Call the tool
            result = await self.call_tool(server_id, tool_name, arguments)
            results.append(result)

            if not result.success:
                logger.warning(
                    f"Tool {tool_name} failed: {result.error}",
                    server=server_config.name,
                )

        return results

    async def get_all_available_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from enabled servers.

        Returns:
            List of tools with server info
        """
        servers = await self.storage.list_enabled()
        all_tools = []

        for server in servers:
            for tool in server.tools:
                all_tools.append(
                    {
                        "server_id": server.id,
                        "server_name": server.name,
                        "tool_name": tool.tool_name,
                        "display_name": tool.display_name,
                        "description": tool.description,
                        "execution_mode": tool.execution_mode,
                        "default_enabled": tool.default_enabled,
                        "default_arguments": tool.default_arguments,
                        "context_argument_mappings": tool.context_argument_mappings,
                    }
                )

        return all_tools

    async def get_default_enabled_tools(self) -> List[Dict[str, Any]]:
        """Get tools that are enabled by default.

        Returns:
            List of default-enabled tools
        """
        return await self.storage.get_default_enabled_tools()


def format_mcp_results_as_context(
    results: List[MCPToolResult], execution_mode: MCPToolExecutionMode
) -> str:
    """Format MCP tool results as context for LLM prompts.

    Args:
        results: List of tool results
        execution_mode: The execution mode these results came from

    Returns:
        Formatted context string
    """
    if not results:
        return ""

    successful_results = [r for r in results if r.success]
    if not successful_results:
        return ""

    mode_label = (
        "Initial Research Results"
        if execution_mode == MCPToolExecutionMode.INITIAL_ONLY
        else "Persona-Specific Research Results"
    )

    parts = [f"\n**{mode_label} from MCP Tools:**\n"]

    for result in successful_results:
        parts.append(result.to_context_string())
        parts.append("")  # Add blank line between results

    return "\n".join(parts)


# Singleton instance
_mcp_client_manager: Optional[MCPClientManager] = None


def get_mcp_client_manager() -> MCPClientManager:
    """Get the singleton MCP client manager instance."""
    global _mcp_client_manager
    if _mcp_client_manager is None:
        _mcp_client_manager = MCPClientManager()
    return _mcp_client_manager
