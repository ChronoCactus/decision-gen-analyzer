"""Tests for MCP result storage."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.mcp_result_storage import MCPResultStorage, StoredMCPResult


class TestStoredMCPResult:
    """Tests for StoredMCPResult dataclass."""

    def test_to_dict_basic(self):
        """Test basic dict conversion."""
        result = StoredMCPResult(
            id="test-id",
            server_id="server1",
            server_name="Test Server",
            tool_name="search",
            arguments={"query": "test"},
            result={"data": "value"},
            success=True,
            error=None,
            created_at="2024-01-15T10:00:00Z",
            adr_id="adr-123",
        )

        data = result.to_dict()

        assert data["id"] == "test-id"
        assert data["server_id"] == "server1"
        assert data["server_name"] == "Test Server"
        assert data["tool_name"] == "search"
        assert data["arguments"] == {"query": "test"}
        assert data["result"] == {"data": "value"}
        assert data["success"] is True
        assert data["error"] is None
        assert data["adr_id"] == "adr-123"

    def test_to_dict_with_error(self):
        """Test dict conversion with error."""
        result = StoredMCPResult(
            id="test-id",
            server_id="server1",
            server_name="Test Server",
            tool_name="search",
            arguments={},
            result=None,
            success=False,
            error="Connection failed",
            created_at="2024-01-15T10:00:00Z",
        )

        data = result.to_dict()

        assert data["success"] is False
        assert data["error"] == "Connection failed"
        assert data["result"] is None

    def test_from_dict(self):
        """Test creating from dict."""
        data = {
            "id": "test-id",
            "server_id": "server1",
            "server_name": "Test Server",
            "tool_name": "search",
            "arguments": {"query": "test"},
            "result": {"data": "value"},
            "success": True,
            "error": None,
            "created_at": "2024-01-15T10:00:00Z",
            "adr_id": "adr-123",
        }

        result = StoredMCPResult.from_dict(data)

        assert result.id == "test-id"
        assert result.server_id == "server1"
        assert result.tool_name == "search"
        assert result.adr_id == "adr-123"

    def test_from_dict_with_defaults(self):
        """Test from_dict handles missing optional fields."""
        data = {
            "id": "test-id",
            "server_id": "server1",
            "server_name": "Test Server",
            "tool_name": "search",
        }

        result = StoredMCPResult.from_dict(data)

        assert result.arguments == {}
        assert result.success is True
        assert result.error is None
        assert result.adr_id is None

    def test_serialize_result_with_fastmcp_content(self):
        """Test serialization of FastMCP CallToolResult."""

        # Mock FastMCP result structure
        class MockTextContent:
            text = "Search results here"

        class MockCallToolResult:
            content = [MockTextContent()]

        result = StoredMCPResult(
            id="test",
            server_id="s1",
            server_name="Server",
            tool_name="tool",
            arguments={},
            result=MockCallToolResult(),
            success=True,
            error=None,
            created_at="2024-01-15T10:00:00Z",
        )

        data = result.to_dict()

        assert data["result"]["content"][0]["type"] == "text"
        assert data["result"]["content"][0]["text"] == "Search results here"


class TestMCPResultStorage:
    """Tests for MCPResultStorage class."""

    @pytest.fixture
    def temp_storage(self):
        """Create storage with temporary directory."""
        with TemporaryDirectory() as tmpdir:
            yield MCPResultStorage(storage_dir=tmpdir)

    @pytest.mark.asyncio
    async def test_save_and_get(self, temp_storage):
        """Test saving and retrieving a result."""
        stored = await temp_storage.save(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search_repositories",
            arguments={"query": "test"},
            result={"repos": [{"name": "test-repo"}]},
            success=True,
            adr_id="adr-123",
        )

        assert stored is not None
        assert stored.id is not None

        retrieved = await temp_storage.get(stored.id)

        assert retrieved is not None
        assert retrieved.server_id == "github"
        assert retrieved.tool_name == "search_repositories"
        assert retrieved.arguments == {"query": "test"}
        assert retrieved.adr_id == "adr-123"

    @pytest.mark.asyncio
    async def test_save_with_error(self, temp_storage):
        """Test saving a failed result."""
        stored = await temp_storage.save(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            arguments={},
            result=None,
            success=False,
            error="Connection timeout",
        )

        retrieved = await temp_storage.get(stored.id)

        assert retrieved.success is False
        assert retrieved.error == "Connection timeout"

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, temp_storage):
        """Test getting nonexistent result returns None."""
        result = await temp_storage.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_raw_json(self, temp_storage):
        """Test getting raw JSON dict."""
        stored = await temp_storage.save(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            arguments={"q": "test"},
            result={"data": "value"},
            success=True,
        )

        raw_data = await temp_storage.get_raw_json(stored.id)

        assert raw_data is not None
        assert isinstance(raw_data, dict)
        assert raw_data["server_id"] == "github"

    @pytest.mark.asyncio
    async def test_get_raw_json_nonexistent(self, temp_storage):
        """Test getting raw JSON for nonexistent result."""
        raw_json = await temp_storage.get_raw_json("nonexistent")
        assert raw_json is None

    @pytest.mark.asyncio
    async def test_list_for_adr(self, temp_storage):
        """Test listing results for a specific ADR."""
        # Save results for different ADRs
        await temp_storage.save(
            server_id="s1",
            server_name="Server 1",
            tool_name="tool1",
            arguments={},
            result={},
            success=True,
            adr_id="adr-123",
        )
        await temp_storage.save(
            server_id="s2",
            server_name="Server 2",
            tool_name="tool2",
            arguments={},
            result={},
            success=True,
            adr_id="adr-123",
        )
        await temp_storage.save(
            server_id="s3",
            server_name="Server 3",
            tool_name="tool3",
            arguments={},
            result={},
            success=True,
            adr_id="adr-456",
        )

        results = await temp_storage.list_for_adr("adr-123")

        assert len(results) == 2
        assert all(r.adr_id == "adr-123" for r in results)

    @pytest.mark.asyncio
    async def test_list_for_adr_empty(self, temp_storage):
        """Test listing results for ADR with no results."""
        results = await temp_storage.list_for_adr("nonexistent-adr")
        assert results == []

    @pytest.mark.asyncio
    async def test_delete(self, temp_storage):
        """Test deleting a result."""
        stored = await temp_storage.save(
            server_id="github",
            server_name="GitHub MCP",
            tool_name="search",
            arguments={},
            result={},
            success=True,
        )

        deleted = await temp_storage.delete(stored.id)
        assert deleted is True

        # Verify it's gone
        result = await temp_storage.get(stored.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, temp_storage):
        """Test deleting nonexistent result."""
        deleted = await temp_storage.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_multiple_saves(self, temp_storage):
        """Test saving multiple results."""
        stored1 = await temp_storage.save(
            server_id="s1",
            server_name="Server 1",
            tool_name="t1",
            arguments={},
            result={},
            success=True,
        )
        stored2 = await temp_storage.save(
            server_id="s2",
            server_name="Server 2",
            tool_name="t2",
            arguments={},
            result={},
            success=True,
        )

        # Verify both can be retrieved
        result1 = await temp_storage.get(stored1.id)
        result2 = await temp_storage.get(stored2.id)

        assert result1 is not None
        assert result2 is not None
        assert result1.server_id == "s1"
        assert result2.server_id == "s2"

    def test_storage_creates_directory(self):
        """Test storage creates directory if not exists."""
        with TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "mcp_results"
            MCPResultStorage(storage_dir=str(storage_path))

            assert storage_path.exists()
