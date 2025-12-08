"""
MCP (Model Context Protocol) Server Configuration Storage

Manages persistent storage of MCP server configurations and tool settings.
Servers are stored in JSON format in /app/data/mcp_servers.json
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
from pydantic import BaseModel, Field, field_validator

from src.config import get_settings
from src.logger import get_logger

logger = get_logger(__name__)


class MCPTransportType(str, Enum):
    """Transport type for MCP server connection."""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class MCPToolExecutionMode(str, Enum):
    """When to execute the MCP tool during ADR generation.

    - INITIAL_ONLY: Call once before any persona generation, share result with all personas
    - PER_PERSONA: Call separately for each persona generation
    """

    INITIAL_ONLY = "initial_only"
    PER_PERSONA = "per_persona"


class MCPToolConfig(BaseModel):
    """Configuration for an individual MCP tool."""

    tool_name: str = Field(description="Name of the tool as exposed by the MCP server")
    display_name: str = Field(default="", description="Human-readable display name")
    description: Optional[str] = Field(
        default=None, description="Description of what the tool does"
    )
    execution_mode: MCPToolExecutionMode = Field(
        default=MCPToolExecutionMode.INITIAL_ONLY,
        description="When to execute this tool during generation",
    )
    default_enabled: bool = Field(
        default=False, description="Whether this tool is enabled by default"
    )
    # Default arguments to pass to the tool (can be overridden at generation time)
    default_arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Default arguments for tool invocation"
    )
    # Arguments that should be dynamically populated from the generation context
    # e.g., {"query": "problem_statement"} means use the problem_statement as the query arg
    context_argument_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Map tool argument names to generation context fields",
    )

    @field_validator("display_name", mode="before")
    @classmethod
    def set_display_name_default(cls, v: Any) -> str:
        """Convert None to empty string for display_name."""
        if v is None:
            return ""
        return v

    @field_validator("default_enabled", mode="before")
    @classmethod
    def set_default_enabled_default(cls, v: Any) -> bool:
        """Convert None to False for default_enabled."""
        if v is None:
            return False
        return v

    @field_validator("default_arguments", mode="before")
    @classmethod
    def set_default_arguments_default(cls, v: Any) -> Dict[str, Any]:
        """Convert None to empty dict for default_arguments."""
        if v is None:
            return {}
        return v

    @field_validator("context_argument_mappings", mode="before")
    @classmethod
    def set_context_argument_mappings_default(cls, v: Any) -> Dict[str, str]:
        """Convert None to empty dict for context_argument_mappings."""
        if v is None:
            return {}
        return v


class MCPServerConfig(BaseModel):
    """Configuration for an MCP server."""

    id: str = Field(description="Unique identifier for this MCP server")
    name: str = Field(description="Display name for the server")
    description: Optional[str] = Field(
        default=None, description="Description of the server's purpose"
    )
    transport_type: MCPTransportType = Field(
        default=MCPTransportType.STDIO, description="Transport type for connection"
    )
    # For STDIO transport
    command: Optional[str] = Field(
        default=None, description="Command to run (for stdio transport)"
    )
    args: List[str] = Field(
        default_factory=list, description="Arguments for the command"
    )
    env: Dict[str, str] = Field(
        default_factory=dict, description="Environment variables for the server"
    )
    cwd: Optional[str] = Field(
        default=None, description="Working directory for the server"
    )
    # For HTTP/SSE transport
    url: Optional[str] = Field(default=None, description="URL for HTTP/SSE transport")
    headers: Dict[str, str] = Field(
        default_factory=dict, description="Headers for HTTP requests"
    )
    # Authentication
    auth_type: Optional[str] = Field(
        default=None, description="Authentication type: oauth, bearer, api_key"
    )
    auth_token_encrypted: Optional[str] = Field(
        default=None, description="Encrypted auth token/API key"
    )
    # Tool configurations
    tools: List[MCPToolConfig] = Field(
        default_factory=list, description="Configured tools from this server"
    )
    # Status
    is_enabled: bool = Field(default=True, description="Whether the server is enabled")

    # Field validators to handle None values from existing JSON (backward compatibility)
    @field_validator("transport_type", mode="before")
    @classmethod
    def transport_type_validator(cls, v):
        """Convert None to default STDIO transport type."""
        if v is None:
            return MCPTransportType.STDIO
        return v

    @field_validator("args", mode="before")
    @classmethod
    def args_validator(cls, v):
        """Convert None to empty list."""
        if v is None:
            return []
        return v

    @field_validator("env", mode="before")
    @classmethod
    def env_validator(cls, v):
        """Convert None to empty dict."""
        if v is None:
            return {}
        return v

    @field_validator("headers", mode="before")
    @classmethod
    def headers_validator(cls, v):
        """Convert None to empty dict."""
        if v is None:
            return {}
        return v

    @field_validator("tools", mode="before")
    @classmethod
    def tools_validator(cls, v):
        """Convert None to empty list."""
        if v is None:
            return []
        return v

    @field_validator("is_enabled", mode="before")
    @classmethod
    def is_enabled_validator(cls, v):
        """Convert None to True."""
        if v is None:
            return True
        return v

    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CreateMCPServerRequest(BaseModel):
    """Request model for creating a new MCP server."""

    name: str
    description: Optional[str] = None
    transport_type: MCPTransportType = MCPTransportType.STDIO
    command: Optional[str] = None
    args: List[str] = []
    env: Dict[str, str] = {}
    cwd: Optional[str] = None
    url: Optional[str] = None
    headers: Dict[str, str] = {}
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None  # Will be encrypted before storage
    is_enabled: bool = True


class UpdateMCPServerRequest(BaseModel):
    """Request model for updating an MCP server."""

    name: Optional[str] = None
    description: Optional[str] = None
    transport_type: Optional[MCPTransportType] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    is_enabled: Optional[bool] = None


class MCPToolUpdateRequest(BaseModel):
    """Request model for updating tool configuration."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    execution_mode: Optional[MCPToolExecutionMode] = None
    default_enabled: Optional[bool] = None
    default_arguments: Optional[Dict[str, Any]] = None
    context_argument_mappings: Optional[Dict[str, str]] = None


class MCPServerResponse(BaseModel):
    """Response model for MCP server (without encrypted credentials)."""

    id: str
    name: str
    description: Optional[str] = None
    transport_type: MCPTransportType
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    auth_type: Optional[str] = None
    has_auth_token: bool = False
    tools: List[MCPToolConfig] = Field(default_factory=list)
    is_enabled: bool = True
    created_at: str
    updated_at: str


class MCPConfigStorage:
    """Manages persistent storage of MCP server configurations."""

    def __init__(
        self, storage_path: Optional[Path] = None, encryption_salt: Optional[str] = None
    ):
        """
        Initialize MCP storage.

        Args:
            storage_path: Path to JSON storage file (default: /app/data/mcp_servers.json)
            encryption_salt: Salt for credential encryption
        """
        settings = get_settings()
        if storage_path is None:
            data_dir = Path(settings.adr_storage_path).parent
            storage_path = data_dir / "mcp_servers.json"

        self.storage_path = storage_path
        self._encryption_salt = encryption_salt or settings.encryption_salt
        logger.info(f"MCP Config storage initialized at {self.storage_path}")

    def _get_encryption(self):
        """Get encryption instance (lazy load to avoid circular imports)."""
        from src.llm_provider_storage import CredentialEncryption

        return CredentialEncryption(self._encryption_salt)

    async def _ensure_storage_dir(self):
        """Ensure the storage directory exists."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    async def _load_servers(self) -> Dict[str, MCPServerConfig]:
        """Load all servers from storage."""
        await self._ensure_storage_dir()

        if not self.storage_path.exists():
            return {}

        try:
            async with aiofiles.open(self.storage_path, "r") as f:
                content = await f.read()
                data = json.loads(content)
                return {
                    server_id: MCPServerConfig(**config)
                    for server_id, config in data.items()
                }
        except Exception as e:
            logger.error(f"Failed to load MCP servers from {self.storage_path}: {e}")
            return {}

    async def _save_servers(self, servers: Dict[str, MCPServerConfig]):
        """Save all servers to storage."""
        await self._ensure_storage_dir()

        try:
            data = {
                server_id: config.model_dump() for server_id, config in servers.items()
            }
            async with aiofiles.open(self.storage_path, "w") as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save MCP servers to {self.storage_path}: {e}")
            raise

    async def list_all(self) -> List[MCPServerResponse]:
        """List all MCP servers."""
        servers = await self._load_servers()
        return [self._to_response(config) for config in servers.values()]

    async def list_enabled(self) -> List[MCPServerResponse]:
        """List only enabled MCP servers."""
        servers = await self._load_servers()
        return [
            self._to_response(config)
            for config in servers.values()
            if config.is_enabled
        ]

    async def get(self, server_id: str) -> Optional[MCPServerConfig]:
        """Get a specific MCP server configuration by ID."""
        servers = await self._load_servers()
        return servers.get(server_id)

    async def create(self, request: CreateMCPServerRequest) -> MCPServerResponse:
        """Create a new MCP server configuration."""
        import uuid

        servers = await self._load_servers()

        # Generate unique ID
        server_id = str(uuid.uuid4())[:8]
        while server_id in servers:
            server_id = str(uuid.uuid4())[:8]

        # Encrypt auth token if provided
        auth_token_encrypted = None
        if request.auth_token:
            encryption = self._get_encryption()
            auth_token_encrypted = encryption.encrypt(request.auth_token)

        # Create config
        config = MCPServerConfig(
            id=server_id,
            name=request.name,
            description=request.description,
            transport_type=request.transport_type,
            command=request.command,
            args=request.args,
            env=request.env,
            cwd=request.cwd,
            url=request.url,
            headers=request.headers,
            auth_type=request.auth_type,
            auth_token_encrypted=auth_token_encrypted,
            is_enabled=request.is_enabled,
        )

        servers[server_id] = config
        await self._save_servers(servers)

        logger.info(f"Created MCP server: {config.name} (id={server_id})")
        return self._to_response(config)

    async def update(
        self, server_id: str, request: UpdateMCPServerRequest
    ) -> Optional[MCPServerResponse]:
        """Update an existing MCP server configuration."""
        servers = await self._load_servers()

        if server_id not in servers:
            return None

        config = servers[server_id]

        # Get current config as dict
        current_data = config.model_dump()

        # Get update fields (only explicitly set ones)
        update_data = request.model_dump(exclude_unset=True)

        # Handle auth token encryption
        if "auth_token" in update_data:
            auth_token = update_data.pop("auth_token")
            if auth_token:
                encryption = self._get_encryption()
                update_data["auth_token_encrypted"] = encryption.encrypt(auth_token)
            else:
                update_data["auth_token_encrypted"] = None

        # Merge current data with updates
        merged_data = {**current_data, **update_data}
        merged_data["updated_at"] = datetime.utcnow().isoformat()

        # Create new config object with merged data (validators will run)
        updated_config = MCPServerConfig(**merged_data)

        servers[server_id] = updated_config
        await self._save_servers(servers)

        logger.info(f"Updated MCP server: {updated_config.name} (id={server_id})")
        return self._to_response(updated_config)

    async def delete(self, server_id: str) -> bool:
        """Delete an MCP server configuration."""
        servers = await self._load_servers()

        if server_id not in servers:
            return False

        del servers[server_id]
        await self._save_servers(servers)

        logger.info(f"Deleted MCP server: {server_id}")
        return True

    async def update_tool(
        self, server_id: str, tool_name: str, request: MCPToolUpdateRequest
    ) -> Optional[MCPServerResponse]:
        """Update a tool configuration on a server."""
        servers = await self._load_servers()

        if server_id not in servers:
            return None

        config = servers[server_id]

        # Find the tool
        tool_idx = next(
            (i for i, t in enumerate(config.tools) if t.tool_name == tool_name), None
        )

        if tool_idx is None:
            # Tool not found - this might be a newly discovered tool
            logger.warning(f"Tool {tool_name} not found on server {server_id}")
            return None

        # Get current tool data and merge with updates
        current_tool_data = config.tools[tool_idx].model_dump()
        update_data = request.model_dump(exclude_unset=True)
        merged_data = {**current_tool_data, **update_data}

        # Create new tool config with merged data
        config.tools[tool_idx] = MCPToolConfig(**merged_data)

        config.updated_at = datetime.utcnow().isoformat()
        servers[server_id] = config
        await self._save_servers(servers)

        logger.info(f"Updated tool {tool_name} on server {server_id}")
        return self._to_response(config)

    def _infer_context_mappings(self, tool_info: Dict[str, Any]) -> Dict[str, str]:
        """Infer context argument mappings from tool's input schema.

        Maps common tool argument names to generation context fields.

        Args:
            tool_info: Tool discovery info including input_schema

        Returns:
            Dict mapping tool arg names to context field names
        """
        mappings = {}
        input_schema = tool_info.get("input_schema", {})
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        # Common argument name patterns and their context field mappings
        # Format: tool_arg_pattern -> context_field
        arg_patterns = {
            # Search-related
            "query": "query",
            "search_query": "query",
            "search": "query",
            "q": "query",
            # Content-related
            "text": "context",
            "content": "context",
            "input": "context",
            # Title-related
            "title": "title",
            "name": "title",
            # Problem/topic-related
            "topic": "problem_statement",
            "subject": "problem_statement",
            "problem": "problem_statement",
        }

        for arg_name in properties:
            arg_lower = arg_name.lower()

            # Check if this argument matches any known patterns
            for pattern, context_field in arg_patterns.items():
                if arg_lower == pattern or arg_lower.endswith(f"_{pattern}"):
                    mappings[arg_name] = context_field
                    break

            # For required string args without a mapping, try to be helpful
            if arg_name not in mappings and arg_name in required:
                prop = properties[arg_name]
                if prop.get("type") == "string":
                    # If description mentions "search" or "query", map to query
                    desc = prop.get("description", "").lower()
                    if "search" in desc or "query" in desc:
                        mappings[arg_name] = "query"

        return mappings

    async def sync_tools(
        self, server_id: str, discovered_tools: List[Dict[str, Any]]
    ) -> Optional[MCPServerResponse]:
        """Sync discovered tools with stored configuration.

        New tools are added with default settings, existing tools get updated descriptions.
        Removed tools are kept for reference.
        """
        servers = await self._load_servers()

        if server_id not in servers:
            return None

        config = servers[server_id]
        existing_tools = {t.tool_name: t for t in config.tools}

        # Process discovered tools
        for tool_info in discovered_tools:
            tool_name = tool_info.get("name", "")
            if not tool_name:
                continue

            # Auto-detect context argument mappings from input schema
            context_mappings = self._infer_context_mappings(tool_info)

            if tool_name not in existing_tools:
                # Add new tool with auto-detected mappings
                new_tool = MCPToolConfig(
                    tool_name=tool_name,
                    display_name=tool_info.get("name", tool_name)
                    .replace("_", " ")
                    .title(),
                    description=tool_info.get("description"),
                    execution_mode=MCPToolExecutionMode.INITIAL_ONLY,
                    default_enabled=False,
                    context_argument_mappings=context_mappings,
                )
                config.tools.append(new_tool)
                logger.info(
                    f"Added new tool {tool_name} to server {server_id} with mappings: {context_mappings}"
                )
            else:
                # Update existing tool's description and display_name if they're missing
                existing_tool = existing_tools[tool_name]
                tool_idx = next(
                    i for i, t in enumerate(config.tools) if t.tool_name == tool_name
                )

                needs_update = False
                current_data = existing_tool.model_dump()

                # Update display_name if empty
                if not existing_tool.display_name:
                    current_data["display_name"] = (
                        tool_info.get("name", tool_name).replace("_", " ").title()
                    )
                    needs_update = True

                # Update description if missing
                if not existing_tool.description and tool_info.get("description"):
                    current_data["description"] = tool_info.get("description")
                    needs_update = True

                # Update context_argument_mappings if empty (auto-infer from schema)
                if not existing_tool.context_argument_mappings and context_mappings:
                    current_data["context_argument_mappings"] = context_mappings
                    needs_update = True
                    logger.info(
                        f"Auto-configured mappings for {tool_name}: {context_mappings}"
                    )

                if needs_update:
                    config.tools[tool_idx] = MCPToolConfig(**current_data)
                    logger.info(
                        f"Updated tool {tool_name} metadata on server {server_id}"
                    )

        config.updated_at = datetime.utcnow().isoformat()
        servers[server_id] = config
        await self._save_servers(servers)

        return self._to_response(config)

    async def get_default_enabled_tools(self) -> List[Dict[str, Any]]:
        """Get all tools that are marked as default enabled across all servers."""
        servers = await self._load_servers()
        enabled_tools = []

        for config in servers.values():
            if not config.is_enabled:
                continue

            for tool in config.tools:
                if tool.default_enabled:
                    enabled_tools.append(
                        {
                            "server_id": config.id,
                            "server_name": config.name,
                            "tool_name": tool.tool_name,
                            "display_name": tool.display_name,
                            "description": tool.description,
                            "execution_mode": tool.execution_mode,
                            "default_arguments": tool.default_arguments,
                            "context_argument_mappings": tool.context_argument_mappings,
                        }
                    )

        return enabled_tools

    def _to_response(self, config: MCPServerConfig) -> MCPServerResponse:
        """Convert internal config to API response."""
        return MCPServerResponse(
            id=config.id,
            name=config.name,
            description=config.description,
            transport_type=config.transport_type,
            command=config.command,
            args=config.args or [],
            env=config.env or {},
            cwd=config.cwd,
            url=config.url,
            headers=config.headers or {},
            auth_type=config.auth_type,
            has_auth_token=bool(config.auth_token_encrypted),
            tools=config.tools or [],
            is_enabled=config.is_enabled if config.is_enabled is not None else True,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )

    def get_decrypted_auth_token(self, config: MCPServerConfig) -> Optional[str]:
        """Get decrypted auth token for a server config."""
        if not config.auth_token_encrypted:
            return None
        encryption = self._get_encryption()
        return encryption.decrypt(config.auth_token_encrypted)


# Singleton instance
_mcp_storage: Optional[MCPConfigStorage] = None


def get_mcp_storage() -> MCPConfigStorage:
    """Get the singleton MCP storage instance."""
    global _mcp_storage
    if _mcp_storage is None:
        _mcp_storage = MCPConfigStorage()
    return _mcp_storage
