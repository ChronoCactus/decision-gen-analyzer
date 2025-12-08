"""Tests for MCP client manager."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_client import (
    MCPClientManager,
    MCPToolResult,
    StreamableHTTPClient,
)
from src.mcp_config_storage import (
    MCPServerConfig,
    MCPToolConfig,
    MCPTransportType,
)


class TestMCPToolResult:
    """Tests for MCPToolResult class."""

    def test_create_success_result(self):
        """Test creating a successful result."""
        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result={"repos": ["test-repo"]},
        )

        assert result.server_id == "github"
        assert result.success is True
        assert result.error is None

    def test_create_error_result(self):
        """Test creating an error result."""
        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=False,
            error="Connection timeout",
        )

        assert result.success is False
        assert result.error == "Connection timeout"

    def test_to_context_string_success(self):
        """Test formatting successful result as context."""
        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result={"repos": ["test"]},
        )

        context = result.to_context_string()

        assert "GitHub MCP" in context
        assert "search" in context
        assert "repos" in context

    def test_to_context_string_error(self):
        """Test formatting error result as context."""
        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=False,
            error="Connection failed",
        )

        context = result.to_context_string()

        assert "Error" in context
        assert "Connection failed" in context

    def test_format_result_with_fastmcp_content(self):
        """Test formatting FastMCP CallToolResult."""

        class MockTextContent:
            text = "Search results text"

        class MockCallToolResult:
            content = [MockTextContent()]

        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result=MockCallToolResult(),
        )

        context = result.to_context_string()

        assert "Search results text" in context

    def test_format_result_none(self):
        """Test formatting None result."""
        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result=None,
        )

        context = result.to_context_string()

        assert "No result returned" in context

    def test_format_result_list(self):
        """Test formatting list result."""
        result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result=["item1", "item2"],
        )

        context = result.to_context_string()

        assert "item1" in context
        assert "item2" in context


class TestMCPClientManager:
    """Tests for MCPClientManager class."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = AsyncMock()
        storage.get = AsyncMock(return_value=None)
        storage.get_decrypted_auth_token = MagicMock(return_value=None)
        storage.sync_tools = AsyncMock()
        return storage

    @pytest.fixture
    def manager(self, mock_storage):
        """Create manager with mock storage."""
        return MCPClientManager(storage=mock_storage)

    @pytest.mark.asyncio
    async def test_get_client_config_stdio(self, manager, mock_storage):
        """Test building config for STDIO server."""
        server = MCPServerConfig(
            id="github",
            name="GitHub MCP",
            transport_type=MCPTransportType.STDIO,
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_TOKEN": "secret"},
        )

        config = await manager.get_client_config(server)

        assert config["command"] == "npx"
        assert config["args"] == ["-y", "@modelcontextprotocol/server-github"]
        assert config["env"] == {"GITHUB_TOKEN": "secret"}

    @pytest.mark.asyncio
    async def test_get_client_config_stdio_no_command(self, manager):
        """Test STDIO config without command raises error."""
        server = MCPServerConfig(
            id="test",
            name="Test",
            transport_type=MCPTransportType.STDIO,
            command=None,
        )

        with pytest.raises(ValueError, match="requires 'command'"):
            await manager.get_client_config(server)

    @pytest.mark.asyncio
    async def test_get_client_config_http(self, manager):
        """Test building config for HTTP server."""
        server = MCPServerConfig(
            id="custom",
            name="Custom",
            transport_type=MCPTransportType.HTTP,
            url="http://localhost:8080/mcp",
            headers={"X-Custom": "header"},
        )

        config = await manager.get_client_config(server)

        assert config["url"] == "http://localhost:8080/mcp"
        assert config["transport"] == "http"
        assert config["headers"]["X-Custom"] == "header"

    @pytest.mark.asyncio
    async def test_get_client_config_http_no_url(self, manager):
        """Test HTTP config without URL raises error."""
        server = MCPServerConfig(
            id="test",
            name="Test",
            transport_type=MCPTransportType.HTTP,
            url=None,
        )

        with pytest.raises(ValueError, match="requires 'url'"):
            await manager.get_client_config(server)

    @pytest.mark.asyncio
    async def test_get_client_config_with_bearer_auth(self, manager, mock_storage):
        """Test config with bearer token auth."""
        server = MCPServerConfig(
            id="test",
            name="Test",
            transport_type=MCPTransportType.HTTP,
            url="http://localhost:8080/mcp",
            auth_type="bearer",
            auth_token_encrypted="encrypted_token",
        )
        mock_storage.get_decrypted_auth_token.return_value = "secret_token"

        config = await manager.get_client_config(server)

        assert "Authorization" in config["headers"]
        assert config["headers"]["Authorization"] == "Bearer secret_token"

    @pytest.mark.asyncio
    async def test_get_client_config_with_api_key_auth(self, manager, mock_storage):
        """Test config with API key auth."""
        server = MCPServerConfig(
            id="test",
            name="Test",
            transport_type=MCPTransportType.HTTP,
            url="http://localhost:8080/mcp",
            auth_type="api_key",
            auth_token_encrypted="encrypted_key",
        )
        mock_storage.get_decrypted_auth_token.return_value = "api_key_value"

        config = await manager.get_client_config(server)

        assert config["headers"]["X-API-Key"] == "api_key_value"

    @pytest.mark.asyncio
    async def test_call_tool_server_not_found(self, manager, mock_storage):
        """Test calling tool on unknown server."""
        mock_storage.get.return_value = None

        result = await manager.call_tool(
            server_id="unknown",
            tool_name="search",
            arguments={},
        )

        assert result.success is False
        assert "not found" in result.error

    @pytest.mark.asyncio
    async def test_call_tool_http_server(self, manager, mock_storage):
        """Test calling tool on HTTP server."""
        server = MCPServerConfig(
            id="custom",
            name="Custom MCP",
            transport_type=MCPTransportType.HTTP,
            url="http://localhost:8080/mcp",
        )
        mock_storage.get.return_value = server

        # Mock the StreamableHTTPClient
        with patch.object(StreamableHTTPClient, "__aenter__") as mock_enter:
            mock_client = AsyncMock()
            mock_client.call_tool.return_value = {"data": "test"}
            mock_enter.return_value = mock_client

            with patch.object(StreamableHTTPClient, "__aexit__", return_value=None):
                result = await manager.call_tool(
                    server_id="custom",
                    tool_name="search",
                    arguments={"query": "test"},
                )

        assert result.success is True
        assert result.server_name == "Custom MCP"

    @pytest.mark.asyncio
    async def test_call_tool_handles_exception(self, manager, mock_storage):
        """Test that tool call handles exceptions."""
        server = MCPServerConfig(
            id="custom",
            name="Custom MCP",
            transport_type=MCPTransportType.HTTP,
            url="http://localhost:8080/mcp",
        )
        mock_storage.get.return_value = server

        # Mock to raise exception
        with patch.object(StreamableHTTPClient, "__aenter__") as mock_enter:
            mock_enter.side_effect = Exception("Connection refused")

            result = await manager.call_tool(
                server_id="custom",
                tool_name="search",
                arguments={},
            )

        assert result.success is False
        assert "Connection refused" in result.error

    def test_build_tool_arguments_defaults(self, manager):
        """Test building arguments with defaults."""
        tool = MCPToolConfig(
            tool_name="search",
            default_arguments={"limit": 10, "sort": "stars"},
        )

        args = manager._build_tool_arguments(tool, {}, None)

        assert args["limit"] == 10
        assert args["sort"] == "stars"

    def test_build_tool_arguments_context_mapping(self, manager):
        """Test building arguments with context mapping."""
        tool = MCPToolConfig(
            tool_name="search",
            context_argument_mappings={"query": "problem_statement"},
        )
        context = {"problem_statement": "How to cache data?"}

        args = manager._build_tool_arguments(tool, context, None)

        assert args["query"] == "How to cache data?"

    def test_build_tool_arguments_user_override(self, manager):
        """Test that user arguments override defaults."""
        tool = MCPToolConfig(
            tool_name="search",
            default_arguments={"limit": 10},
        )
        user_args = {"limit": 50, "extra": "value"}

        args = manager._build_tool_arguments(tool, {}, user_args)

        assert args["limit"] == 50
        assert args["extra"] == "value"

    def test_build_tool_arguments_combined(self, manager):
        """Test combining defaults, context, and user args."""
        tool = MCPToolConfig(
            tool_name="search",
            default_arguments={"limit": 10},
            context_argument_mappings={"query": "problem"},
        )
        context = {"problem": "caching"}
        user_args = {"extra": "arg"}

        args = manager._build_tool_arguments(tool, context, user_args)

        assert args["limit"] == 10
        assert args["query"] == "caching"
        assert args["extra"] == "arg"


class TestStreamableHTTPClient:
    """Tests for StreamableHTTPClient class."""

    def test_init(self):
        """Test client initialization."""
        client = StreamableHTTPClient("http://localhost:8080")

        assert client.base_url == "http://localhost:8080"
        assert client.mcp_endpoint == "http://localhost:8080/mcp"
        assert client.session_id is None

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from URL."""
        client = StreamableHTTPClient("http://localhost:8080/")

        assert client.base_url == "http://localhost:8080"

    def test_init_with_headers(self):
        """Test initialization with custom headers."""
        client = StreamableHTTPClient(
            "http://localhost:8080",
            headers={"Authorization": "Bearer token"},
        )

        assert "Authorization" in client.headers

    def test_parse_sse_response_valid(self):
        """Test parsing valid SSE response."""
        client = StreamableHTTPClient("http://localhost:8080")
        sse_text = 'event: message\ndata: {"result": "test"}\n\n'

        data = client._parse_sse_response(sse_text)

        assert data == {"result": "test"}

    def test_parse_sse_response_no_data(self):
        """Test parsing SSE response without data line."""
        client = StreamableHTTPClient("http://localhost:8080")
        sse_text = "event: message\n\n"

        with pytest.raises(RuntimeError, match="No data line found"):
            client._parse_sse_response(sse_text)

    def test_next_request_id(self):
        """Test request ID incrementing."""
        client = StreamableHTTPClient("http://localhost:8080")

        id1 = client._next_request_id()
        id2 = client._next_request_id()

        assert id2 == id1 + 1


class TestGetMcpClientManager:
    """Tests for get_mcp_client_manager singleton."""

    def test_returns_singleton(self):
        """Test that get_mcp_client_manager returns singleton."""
        from src.mcp_client import get_mcp_client_manager

        with patch("src.mcp_client.get_mcp_storage"):
            # Reset singleton
            import src.mcp_client

            src.mcp_client._mcp_client_manager = None

            manager1 = get_mcp_client_manager()
            manager2 = get_mcp_client_manager()

            assert manager1 is manager2
