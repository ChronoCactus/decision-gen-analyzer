"""Tests for ADR storage abstraction."""

import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime, UTC
from uuid import uuid4

from src.adr_storage import ADRStorageService
from src.models import ADR, ADRMetadata, ADRContent, ADRStatus


class TestADRStorage:
    """Test ADRStorageService class."""

    @pytest.fixture
    def mock_lightrag_client(self):
        """Mock LightRAG client."""
        client = AsyncMock()
        client.store_document.return_value = "doc_id_123"
        client.get_document.return_value = None
        client.delete_document.return_value = True
        client.search.return_value = {"results": []}
        return client

    @pytest.fixture
    def sample_adr(self):
        """Create a sample ADR."""
        return ADR.create(
            title="Test",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )

    @pytest.mark.asyncio
    async def test_save_adr(self, mock_lightrag_client, sample_adr):
        """Test saving an ADR."""
        storage = ADRStorageService(mock_lightrag_client)

        result = await storage.store_adr(sample_adr)

        # Verify store was called
        assert result is not None
        mock_lightrag_client.store_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_adr(self, mock_lightrag_client, sample_adr):
        """Test loading an ADR."""
        storage = ADRStorageService(mock_lightrag_client)

        # This may return None if not found
        adr_id = str(uuid4())
        result = await storage.get_adr(adr_id)

        # Result may be None if not found
        assert result is None or isinstance(result, ADR)
        mock_lightrag_client.get_document.assert_called_once_with(adr_id)

    @pytest.mark.asyncio
    async def test_delete_adr(self, mock_lightrag_client):
        """Test deleting an ADR."""
        storage = ADRStorageService(mock_lightrag_client)

        adr_id = str(uuid4())
        result = await storage.delete_adr(adr_id)

        assert isinstance(result, bool)
        mock_lightrag_client.delete_document.assert_called_once_with(adr_id)

    @pytest.mark.asyncio
    async def test_list_all_adrs(self, mock_lightrag_client):
        """Test listing all ADRs."""
        storage = ADRStorageService(mock_lightrag_client)

        result = await storage.search_adrs("")

        assert isinstance(result, list)
        mock_lightrag_client.retrieve_documents.assert_called_once()
