"""Tests for ADR validation service."""

from unittest.mock import AsyncMock

import pytest

from src.adr_validation import ADRAnalysisService
from src.models import ADR


class TestADRAnalysisService:
    """Test ADRAnalysisService class."""

    @pytest.fixture
    def mock_llama_client(self):
        """Mock Llama client."""
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.generate.return_value = '{"analysis": "test analysis", "score": 8}'
        return client

    @pytest.fixture
    def mock_lightrag_client(self):
        """Mock LightRAG client."""
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        return client

    @pytest.fixture
    def sample_adr(self):
        """Create sample ADR."""
        return ADR.create(
            title="Test ADR",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )

    @pytest.mark.asyncio
    async def test_analyze_adr_single_persona(
        self, mock_llama_client, mock_lightrag_client, sample_adr
    ):
        """Test analyzing ADR with single persona."""
        service = ADRAnalysisService(mock_llama_client, mock_lightrag_client)

        result = await service.analyze_adr(sample_adr, persona="technical_lead")

        assert result is not None
        mock_llama_client.generate.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_adr_multiple_personas(
        self, mock_llama_client, mock_lightrag_client, sample_adr
    ):
        """Test analyzing ADR with multiple personas using the multi-persona method."""
        service = ADRAnalysisService(mock_llama_client, mock_lightrag_client)

        # Use the method for multiple personas
        result = await service.analyze_adr_with_multiple_personas(
            sample_adr,
            personas=[
                "technical_lead",
                "business_analyst",
            ],
        )

        assert result is not None
        assert mock_llama_client.generate.call_count >= 2
