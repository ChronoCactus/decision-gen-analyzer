"""Tests for MCP orchestrator."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.mcp_orchestrator import (
    MCPOrchestrator,
    MCPReferenceInfo,
    ToolCall,
    ToolSelectionResult,
)


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_basic(self):
        """Test creating a basic tool call."""
        tc = ToolCall(
            tool_name="search",
            arguments={"query": "test"},
        )

        assert tc.tool_name == "search"
        assert tc.arguments == {"query": "test"}
        assert tc.server_id is None

    def test_create_with_server(self):
        """Test creating tool call with server ID."""
        tc = ToolCall(
            tool_name="search",
            arguments={"query": "test"},
            server_id="github",
        )

        assert tc.server_id == "github"


class TestToolSelectionResult:
    """Tests for ToolSelectionResult dataclass."""

    def test_create_with_tools(self):
        """Test creating with tool calls."""
        result = ToolSelectionResult(
            reasoning="These tools are relevant.",
            tool_calls=[
                ToolCall(tool_name="search", arguments={}),
                ToolCall(tool_name="fetch", arguments={}),
            ],
        )

        assert result.reasoning == "These tools are relevant."
        assert len(result.tool_calls) == 2

    def test_create_empty(self):
        """Test creating with no tools."""
        result = ToolSelectionResult(
            reasoning="No tools needed.",
            tool_calls=[],
        )

        assert len(result.tool_calls) == 0


class TestMCPReferenceInfo:
    """Tests for MCPReferenceInfo dataclass."""

    def test_to_dict(self):
        """Test converting to dict."""
        ref = MCPReferenceInfo(
            id="ref-123",
            title="Web Search",
            summary='Query: "caching strategies"',
            server_name="Brave Search",
        )

        data = ref.to_dict()

        assert data["id"] == "ref-123"
        assert data["title"] == "Web Search"
        assert data["type"] == "mcp"
        assert data["server_name"] == "Brave Search"


class TestMCPOrchestrator:
    """Tests for MCPOrchestrator class."""

    @pytest.fixture
    def mock_client_manager(self):
        """Create mock client manager."""
        manager = AsyncMock()
        manager.discover_tools = AsyncMock(return_value=[])
        manager.call_tool = AsyncMock()
        return manager

    @pytest.fixture
    def mock_storage(self):
        """Create mock config storage."""
        storage = AsyncMock()
        storage.list_enabled = AsyncMock(return_value=[])
        return storage

    @pytest.fixture
    def orchestrator(self, mock_client_manager, mock_storage):
        """Create orchestrator with mocks."""
        with patch("src.mcp_orchestrator.get_mcp_storage", return_value=mock_storage):
            orch = MCPOrchestrator(client_manager=mock_client_manager)
            orch.storage = mock_storage
            return orch

    def test_format_tools_description_empty(self, orchestrator):
        """Test formatting empty tools list."""
        result = orchestrator._format_tools_description([])
        assert result == "No tools available."

    def test_format_tools_with_schemas_empty(self, orchestrator):
        """Test formatting empty schemas list."""
        result = orchestrator._format_tools_with_schemas([])
        assert result == "No tools available."

    def test_format_tools_with_schemas(self, orchestrator):
        """Test formatting tools with schemas."""
        tools = [
            {
                "tool_name": "search",
                "server_name": "GitHub",
                "server_id": "github",
                "description": "Search repositories",
                "input_schema": {
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        }
                    },
                    "required": ["query"],
                },
            }
        ]

        result = orchestrator._format_tools_with_schemas(tools)

        assert "search" in result
        assert "GitHub" in result
        assert "query" in result
        assert "(required)" in result

    def test_parse_tool_selection_response_valid(self, orchestrator):
        """Test parsing valid tool selection response."""
        response = """
        Here's my analysis:
        {
            "reasoning": "The user needs repository search.",
            "tool_calls": [
                {
                    "tool_name": "search_repos",
                    "arguments": {"query": "caching"}
                }
            ]
        }
        """
        available_tools = [
            {"tool_name": "search_repos", "server_id": "github"},
        ]

        result = orchestrator._parse_tool_selection_response(response, available_tools)

        assert result.reasoning == "The user needs repository search."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "search_repos"
        assert result.tool_calls[0].server_id == "github"

    def test_parse_tool_selection_response_no_json(self, orchestrator):
        """Test parsing response with no JSON."""
        response = "I think we should use some tools but I can't format JSON."

        result = orchestrator._parse_tool_selection_response(response, [])

        assert "no JSON found" in result.reasoning
        assert len(result.tool_calls) == 0

    def test_parse_tool_selection_response_unknown_tool(self, orchestrator):
        """Test parsing response with unknown tool."""
        response = """
        {
            "reasoning": "Using tools",
            "tool_calls": [
                {"tool_name": "unknown_tool", "arguments": {}}
            ]
        }
        """
        available_tools = [
            {"tool_name": "search", "server_id": "github"},
        ]

        result = orchestrator._parse_tool_selection_response(response, available_tools)

        # Unknown tool should be skipped
        assert len(result.tool_calls) == 0

    def test_parse_tool_selection_response_invalid_json(self, orchestrator):
        """Test parsing response with invalid JSON."""
        response = '{"reasoning": "test", "tool_calls": [broken'

        result = orchestrator._parse_tool_selection_response(response, [])

        assert "Failed to parse" in result.reasoning
        assert len(result.tool_calls) == 0

    def test_build_reference_summary_with_query(self, orchestrator):
        """Test building summary with query argument."""
        summary = orchestrator._build_reference_summary(
            "search", {"query": "caching strategies"}
        )

        assert 'Query: "caching strategies"' == summary

    def test_build_reference_summary_with_url(self, orchestrator):
        """Test building summary with URL argument."""
        summary = orchestrator._build_reference_summary(
            "fetch", {"url": "https://example.com"}
        )

        assert "URL: https://example.com" == summary

    def test_build_reference_summary_truncates_long_query(self, orchestrator):
        """Test that long queries are truncated."""
        long_query = "a" * 100
        summary = orchestrator._build_reference_summary("search", {"query": long_query})

        assert len(summary) < 100
        assert summary.endswith('..."')

    def test_build_reference_summary_fallback(self, orchestrator):
        """Test fallback when no common args found."""
        summary = orchestrator._build_reference_summary("custom", {"foo": "bar"})

        assert "Args:" in summary

    def test_build_reference_summary_empty_args(self, orchestrator):
        """Test with empty arguments."""
        summary = orchestrator._build_reference_summary("tool", {})

        assert "Tool: tool" == summary

    @pytest.mark.asyncio
    async def test_select_tools_no_tools_available(self, orchestrator, mock_storage):
        """Test tool selection when no tools available."""
        mock_storage.list_enabled.return_value = []

        mock_llm = AsyncMock()

        result = await orchestrator.select_tools(
            title="Test",
            problem_statement="Problem",
            context="Context",
            llm_client=mock_llm,
            available_tools=[],
        )

        assert "No MCP tools" in result.reasoning
        assert len(result.tool_calls) == 0
        # LLM should not be called
        mock_llm.generate.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_execute_tool_calls_empty(self, orchestrator):
        """Test executing empty tool calls list."""
        results = await orchestrator.execute_tool_calls([])

        assert results == []

    @pytest.mark.asyncio
    async def test_execute_tool_calls(self, orchestrator, mock_client_manager):
        """Test executing tool calls."""
        from src.mcp_client import MCPToolResult

        mock_result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result={"data": "test"},
        )
        mock_client_manager.call_tool.return_value = mock_result

        tool_calls = [
            ToolCall(tool_name="search", arguments={"q": "test"}, server_id="github"),
        ]

        results = await orchestrator.execute_tool_calls(tool_calls)

        assert len(results) == 1
        mock_client_manager.call_tool.assert_awaited_once_with(
            server_id="github",
            tool_name="search",
            arguments={"q": "test"},
        )

    def test_format_tool_results_as_context_empty(self, orchestrator):
        """Test formatting empty results."""
        result = orchestrator.format_tool_results_as_context([])

        assert result == ""

    def test_format_tool_results_as_context(self, orchestrator):
        """Test formatting results as context."""
        from src.mcp_client import MCPToolResult

        results = [
            MCPToolResult(
                server_id="github",
                server_name="GitHub MCP",
                tool_name="search",
                success=True,
                result={"repos": ["test-repo"]},
            ),
        ]

        context = orchestrator.format_tool_results_as_context(results)

        assert "Research Results from MCP Tools" in context

    @pytest.mark.asyncio
    async def test_orchestrate_no_tools(self, orchestrator, mock_storage):
        """Test full orchestration with no tools available."""
        mock_storage.list_enabled.return_value = []

        mock_llm = AsyncMock()

        result = await orchestrator.orchestrate(
            title="Test",
            problem_statement="Problem",
            context="Context",
            llm_client=mock_llm,
        )

        assert result.formatted_context == ""
        assert result.tool_results == []

    @pytest.mark.asyncio
    async def test_orchestrate_with_tools(
        self, orchestrator, mock_storage, mock_client_manager
    ):
        """Test full orchestration with tools."""
        from src.mcp_client import MCPToolResult
        from src.mcp_config_storage import MCPServerConfig, MCPToolConfig
        from src.mcp_result_storage import StoredMCPResult

        # Setup mock server with tool
        mock_server = MCPServerConfig(
            id="github",
            name="GitHub MCP",
            tools=[
                MCPToolConfig(
                    tool_name="search",
                    description="Search repos",
                )
            ],
        )
        mock_storage.list_enabled.return_value = [mock_server]

        # Setup mock tool discovery
        mock_client_manager.discover_tools.return_value = [
            {
                "name": "search",
                "description": "Search repos",
                "input_schema": {"properties": {"query": {"type": "string"}}},
            }
        ]

        # Setup mock LLM response
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "reasoning": "User needs to search repos.",
                "tool_calls": [
                    {"tool_name": "search", "arguments": {"query": "caching"}}
                ],
            }
        )

        # Setup mock tool result
        mock_tool_result = MCPToolResult(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            success=True,
            result={"repos": []},
        )
        mock_client_manager.call_tool.return_value = mock_tool_result

        # Mock result storage - patch in mcp_result_storage module
        with patch("src.mcp_result_storage.get_mcp_result_storage") as mock_get_storage:
            mock_result_storage = AsyncMock()
            # save() returns a StoredMCPResult, not just an ID
            mock_stored = StoredMCPResult(
                id="stored-123",
                server_id="github",
                server_name="GitHub MCP",
                tool_name="search",
                arguments={"query": "caching"},
                result={"repos": []},
                success=True,
                error=None,
                created_at="2024-01-15T10:00:00Z",
            )
            mock_result_storage.save.return_value = mock_stored
            mock_get_storage.return_value = mock_result_storage

            result = await orchestrator.orchestrate(
                title="Test",
                problem_statement="Caching decision",
                context="Context",
                llm_client=mock_llm,
                adr_id="adr-123",
            )

        assert result.error is None
        assert result.tool_selection is not None
        assert len(result.tool_selection.tool_calls) == 1
        assert len(result.tool_results) == 1
        assert len(result.references) == 1
        assert result.references[0].id == "stored-123"

    @pytest.mark.asyncio
    async def test_orchestrate_ai_decides_no_tools(
        self, orchestrator, mock_storage, mock_client_manager
    ):
        """Test orchestration when AI decides no tools needed."""
        from src.mcp_config_storage import MCPServerConfig, MCPToolConfig

        mock_server = MCPServerConfig(
            id="github",
            name="GitHub MCP",
            tools=[MCPToolConfig(tool_name="search")],
        )
        mock_storage.list_enabled.return_value = [mock_server]
        mock_client_manager.discover_tools.return_value = [{"name": "search"}]

        # AI decides no tools needed
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = json.dumps(
            {
                "reasoning": "This decision doesn't require external research.",
                "tool_calls": [],
            }
        )

        result = await orchestrator.orchestrate(
            title="Test",
            problem_statement="Simple problem",
            context="Context",
            llm_client=mock_llm,
        )

        assert result.error is None
        assert result.tool_results == []
        assert result.formatted_context == ""
        # Tool should not be called
        mock_client_manager.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_orchestrate_handles_error(self, orchestrator, mock_storage):
        """Test orchestration handles errors gracefully."""
        mock_storage.list_enabled.side_effect = Exception("Connection failed")

        mock_llm = AsyncMock()

        result = await orchestrator.orchestrate(
            title="Test",
            problem_statement="Problem",
            context="Context",
            llm_client=mock_llm,
        )

        assert result.error is not None
        assert "Connection failed" in result.error


class TestGetMcpOrchestrator:
    """Tests for get_mcp_orchestrator singleton."""

    def test_returns_singleton(self):
        """Test that get_mcp_orchestrator returns singleton."""
        from src.mcp_orchestrator import get_mcp_orchestrator

        with patch("src.mcp_orchestrator.get_mcp_client_manager"):
            with patch("src.mcp_orchestrator.get_mcp_storage"):
                # Reset singleton
                import src.mcp_orchestrator

                src.mcp_orchestrator._mcp_orchestrator = None

                orch1 = get_mcp_orchestrator()
                orch2 = get_mcp_orchestrator()

                assert orch1 is orch2
