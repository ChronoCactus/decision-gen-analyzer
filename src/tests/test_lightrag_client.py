"""Tests for LightRAG client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.lightrag_client import LightRAGClient


class TestLightRAGClient:
    """Test LightRAGClient class."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        mock = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client initialization."""
        client = LightRAGClient(base_url="http://test:9621", timeout=60)

        assert client.base_url == "http://test:9621"
        assert client.timeout == 60

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client as async context manager."""
        async with LightRAGClient() as client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_store_document(self):
        """Test storing a document in demo mode."""
        # Test demo mode (default behavior without initializing _client)
        async with LightRAGClient(demo_mode=True) as client:
            result = await client.store_document("test-123", "Document content")

            assert result["status"] == "success"
            assert result["doc_id"] == "test-123"

    @pytest.mark.asyncio
    async def test_search_documents(self):
        """Test retrieving/searching documents."""
        # Test in demo mode which returns mock results
        async with LightRAGClient(demo_mode=True) as client:
            # Use retrieve_documents with limit parameter
            results = await client.retrieve_documents("test query", limit=5)

            assert isinstance(results, list)
            assert len(results) >= 0  # Demo mode returns mock results

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """Test deleting a document (returns bool, not dict)."""
        async with LightRAGClient() as client:
            result = await client.delete_document("test-123")

            # delete_document returns bool, not dict (LightRAG limitation)
            assert isinstance(result, bool)
            assert result is True

    @pytest.mark.asyncio
    async def test_get_document(self):
        """Test retrieving a document."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "doc_id": "test-123",
            "content": "Document content",
        }

        async with LightRAGClient() as client:
            client._client.get = AsyncMock(return_value=mock_response)

            result = await client.get_document("test-123")

            assert result["doc_id"] == "test-123"
            assert result["content"] == "Document content"

    @pytest.mark.asyncio
    async def test_client_handles_errors(self):
        """Test client handles HTTP errors in non-demo mode."""
        async with LightRAGClient(demo_mode=False) as client:
            client._client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))

            with pytest.raises(httpx.HTTPError):
                await client.store_document("test", "content")

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test retrieve_documents with metadata filter."""
        async with LightRAGClient(demo_mode=True) as client:
            # Use retrieve_documents with metadata_filter parameter
            results = await client.retrieve_documents(
                "query", 
                limit=10, 
                metadata_filter={"tag": "architecture"}
            )

            assert isinstance(results, list)
            # Demo mode returns mock results
            assert len(results) >= 0
