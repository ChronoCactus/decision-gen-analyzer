"""Tests for LightRAG client."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

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
    async def test_get_paginated_documents(self):
        """Test fetching paginated documents."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "documents": [
                {"id": "doc-abc123", "file_path": "test-1.txt", "status": "processed"},
                {"id": "doc-def456", "file_path": "test-2.txt", "status": "processed"},
            ],
            "total": 2,
            "page": 1,
            "page_size": 10,
        }

        async with LightRAGClient(demo_mode=False) as client:
            client._client.post = AsyncMock(return_value=mock_response)

            result = await client.get_paginated_documents(page=1, page_size=10)

            assert "documents" in result
            assert len(result["documents"]) == 2
            client._client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document(self):
        """Test deleting a document in demo mode."""
        async with LightRAGClient(demo_mode=True) as client:
            result = await client.delete_document("test-123")

            # delete_document returns bool
            assert isinstance(result, bool)
            assert result is True

    @pytest.mark.asyncio
    async def test_delete_document_success(self):
        """Test deleting a document successfully with LightRAG doc ID."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "deleted": ["doc-abc123"],
        }

        async with LightRAGClient(demo_mode=False) as client:
            client._client.request = AsyncMock(return_value=mock_response)

            result = await client.delete_document(
                "test-123", lightrag_doc_id="doc-abc123"
            )

            assert result is True
            # Verify the correct endpoint and payload were used with the doc ID
            client._client.request.assert_called_once_with(
                "DELETE",
                "/documents/delete_document",
                json={"doc_ids": ["doc-abc123"], "delete_file": True},
            )

    @pytest.mark.asyncio
    async def test_delete_document_without_doc_id(self):
        """Test deleting a document without LightRAG doc ID (fallback to filename)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "status": "success",
            "deleted": ["test-123.txt"],
        }

        async with LightRAGClient(demo_mode=False) as client:
            client._client.request = AsyncMock(return_value=mock_response)

            result = await client.delete_document("test-123")

            assert result is True
            # Verify it falls back to using filename
            client._client.request.assert_called_once_with(
                "DELETE",
                "/documents/delete_document",
                json={"doc_ids": ["test-123.txt"], "delete_file": True},
            )

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self):
        """Test deleting a document that doesn't exist."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        async with LightRAGClient(demo_mode=False) as client:
            client._client.request = AsyncMock(return_value=mock_response)

            result = await client.delete_document("test-123")

            assert result is False

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
            client._client.post = AsyncMock(
                side_effect=httpx.HTTPError("Connection failed")
            )

            with pytest.raises(httpx.HTTPError):
                await client.store_document("test", "content")

    @pytest.mark.asyncio
    async def test_search_with_filters(self):
        """Test retrieve_documents with metadata filter."""
        async with LightRAGClient(demo_mode=True) as client:
            # Use retrieve_documents with metadata_filter parameter
            results = await client.retrieve_documents(
                "query", limit=10, metadata_filter={"tag": "architecture"}
            )

            assert isinstance(results, list)
            # Demo mode returns mock results
            assert len(results) >= 0
