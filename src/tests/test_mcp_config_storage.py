"""Tests for MCP configuration storage."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_config_storage import (
    CreateMCPServerRequest,
    MCPConfigStorage,
    MCPServerConfig,
    MCPToolConfig,
    MCPToolExecutionMode,
    MCPTransportType,
    UpdateMCPServerRequest,
)


class TestMCPToolConfig:
    """Tests for MCPToolConfig model."""

    def test_create_basic_tool(self):
        """Test creating a basic tool config."""
        tool = MCPToolConfig(
            tool_name="search",
            display_name="Search",
            description="Search for things",
        )

        assert tool.tool_name == "search"
        assert tool.display_name == "Search"
        assert tool.execution_mode == MCPToolExecutionMode.INITIAL_ONLY
        assert tool.default_enabled is False

    def test_create_tool_with_defaults(self):
        """Test tool config with default arguments."""
        tool = MCPToolConfig(
            tool_name="search",
            default_arguments={"limit": 10},
            context_argument_mappings={"query": "problem_statement"},
        )

        assert tool.default_arguments == {"limit": 10}
        assert tool.context_argument_mappings == {"query": "problem_statement"}

    def test_none_values_handled(self):
        """Test that None values are converted to defaults."""
        tool = MCPToolConfig(
            tool_name="test",
            display_name=None,
            default_enabled=None,
            default_arguments=None,
            context_argument_mappings=None,
        )

        assert tool.display_name == ""
        assert tool.default_enabled is False
        assert tool.default_arguments == {}
        assert tool.context_argument_mappings == {}


class TestMCPServerConfig:
    """Tests for MCPServerConfig model."""

    def test_create_stdio_server(self):
        """Test creating a STDIO server config."""
        server = MCPServerConfig(
            id="github",
            name="GitHub MCP",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "secret"},
        )

        assert server.id == "github"
        assert server.name == "GitHub MCP"
        assert server.transport_type == MCPTransportType.STDIO
        assert server.command == "npx"
        assert server.is_enabled is True

    def test_create_http_server(self):
        """Test creating an HTTP server config."""
        server = MCPServerConfig(
            id="custom",
            name="Custom Server",
            transport_type=MCPTransportType.HTTP,
            url="http://localhost:8080/mcp",
            headers={"Authorization": "Bearer token"},
        )

        assert server.transport_type == MCPTransportType.HTTP
        assert server.url == "http://localhost:8080/mcp"
        assert server.headers == {"Authorization": "Bearer token"}

    def test_server_with_tools(self):
        """Test server config with tools."""
        tools = [
            MCPToolConfig(tool_name="search", display_name="Search"),
            MCPToolConfig(tool_name="list", display_name="List"),
        ]
        server = MCPServerConfig(
            id="test",
            name="Test Server",
            tools=tools,
        )

        assert len(server.tools) == 2
        assert server.tools[0].tool_name == "search"

    def test_none_transport_defaults_to_stdio(self):
        """Test that None transport type defaults to STDIO."""
        # Simulate loading from JSON with None transport_type
        server = MCPServerConfig(
            id="test",
            name="Test",
            transport_type=None,
        )

        assert server.transport_type == MCPTransportType.STDIO


class TestMCPConfigStorage:
    """Tests for MCPConfigStorage class."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for storage path."""
        settings = MagicMock()
        settings.adr_storage_path = "/tmp/test/adrs"
        settings.encryption_salt = "test_salt"
        return settings

    @pytest.fixture
    def temp_storage(self, mock_settings):
        """Create storage with temporary directory."""
        with TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "mcp_servers.json"
            with patch(
                "src.mcp_config_storage.get_settings", return_value=mock_settings
            ):
                yield MCPConfigStorage(storage_path=storage_path)

    @pytest.mark.asyncio
    async def test_create_and_get_server(self, temp_storage):
        """Test creating and retrieving a server."""
        request = CreateMCPServerRequest(
            name="GitHub MCP",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
        )

        response = await temp_storage.create(request)

        assert response.name == "GitHub MCP"
        assert response.id is not None

        # Retrieve by ID
        retrieved = await temp_storage.get(response.id)
        assert retrieved is not None
        assert retrieved.name == "GitHub MCP"

    @pytest.mark.asyncio
    async def test_get_nonexistent_server(self, temp_storage):
        """Test getting nonexistent server returns None."""
        result = await temp_storage.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_servers(self, temp_storage):
        """Test listing all servers."""
        await temp_storage.create(CreateMCPServerRequest(name="Server 1"))
        await temp_storage.create(CreateMCPServerRequest(name="Server 2"))

        servers = await temp_storage.list_all()

        assert len(servers) == 2
        names = [s.name for s in servers]
        assert "Server 1" in names
        assert "Server 2" in names

    @pytest.mark.asyncio
    async def test_update_server(self, temp_storage):
        """Test updating a server."""
        response = await temp_storage.create(
            CreateMCPServerRequest(name="Original Name")
        )

        update_request = UpdateMCPServerRequest(name="Updated Name")
        updated = await temp_storage.update(response.id, update_request)

        assert updated is not None
        assert updated.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_server(self, temp_storage):
        """Test deleting a server."""
        response = await temp_storage.create(CreateMCPServerRequest(name="To Delete"))

        deleted = await temp_storage.delete(response.id)
        assert deleted is True

        retrieved = await temp_storage.get(response.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_server(self, temp_storage):
        """Test deleting nonexistent server."""
        deleted = await temp_storage.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_enabled_servers(self, temp_storage):
        """Test listing only enabled servers."""
        await temp_storage.create(
            CreateMCPServerRequest(name="Enabled", is_enabled=True)
        )
        resp = await temp_storage.create(
            CreateMCPServerRequest(name="Disabled", is_enabled=False)
        )

        # Ensure the disabled one is actually disabled
        await temp_storage.update(resp.id, UpdateMCPServerRequest(is_enabled=False))

        servers = await temp_storage.list_enabled()

        assert len(servers) == 1
        assert servers[0].name == "Enabled"
