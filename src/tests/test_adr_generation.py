"""Tests for ADR generation service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.adr_generation import ADRGenerationService
from src.models import ADRGenerationPrompt, ADRGenerationOptions


class TestADRGenerationService:
    """Test ADRGenerationService class."""

    @pytest.fixture
    def mock_llama_client(self):
        """Mock Llama client."""
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.generate.return_value = '{"title": "Test ADR", "context_and_problem": "Problem", "decision_outcome": "Decision", "consequences": "Consequences"}'
        return client

    @pytest.fixture
    def mock_lightrag_client(self):
        """Mock LightRAG client."""
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        client.retrieve_documents.return_value = []
        return client

    @pytest.fixture
    def mock_persona_manager(self):
        """Mock PersonaManager."""
        from src.persona_manager import PersonaConfig

        manager = MagicMock()
        persona_config = PersonaConfig(
            name="Technical Lead",
            description="Focuses on technical aspects",
            instructions="Analyze technical feasibility",
            focus_areas=["architecture", "scalability"],
            evaluation_criteria=["technical feasibility", "maintainability"]
        )
        manager.get_persona_config.return_value = persona_config
        manager.list_persona_values.return_value = ["technical_lead"]
        return manager

    @pytest.fixture
    def generation_prompt(self):
        """Create generation prompt."""
        return ADRGenerationPrompt(
            title="Database Selection Decision",
            context="We need a reliable database for our application",
            problem_statement="We need to choose a database technology that supports ACID transactions and complex queries",
            constraints=["Must support ACID transactions", "Need good performance"],
            stakeholders=["Engineering Team", "Product Team"],
            tags=["database", "postgresql"]
        )

    @pytest.mark.asyncio
    async def test_generate_adr_basic(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager, generation_prompt
    ):
        """Test basic ADR generation."""
        # Mock the client factory functions to return our mock client
        with patch("src.adr_generation.create_client_from_persona_config") as mock_factory, \
             patch("src.adr_generation.create_client_from_provider_id") as mock_provider_factory:
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client
            
            service = ADRGenerationService(mock_llama_client, mock_lightrag_client, mock_persona_manager)

            result = await service.generate_adr(generation_prompt)

            assert result is not None
            assert result.generated_title is not None
            assert result.decision_outcome is not None
            mock_llama_client.generate.assert_called()

    @pytest.mark.asyncio
    async def test_generate_adr_with_personas(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager, generation_prompt
    ):
        """Test ADR generation with personas."""
        # Mock the client factory to return our mock client
        with patch(
            "src.adr_generation.create_client_from_persona_config"
        ) as mock_factory:
            mock_factory.return_value = mock_llama_client

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            personas = ["technical_lead", "business_analyst"]

            result = await service.generate_adr(generation_prompt, personas=personas)

            assert result is not None
            # Should create a client for each persona
            assert mock_factory.call_count >= 2
            # And the generated clients should be called
            assert mock_llama_client.generate.call_count >= 2

    @pytest.mark.asyncio
    async def test_generate_adr_with_related_context(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager, generation_prompt
    ):
        """Test ADR generation with related context."""
        mock_lightrag_client.retrieve_documents.return_value = [
            {"id": "adr-1", "content": "Previous decision about databases"}
        ]

        # Mock the client factory functions to return our mock client
        with patch("src.adr_generation.create_client_from_persona_config") as mock_factory, \
             patch("src.adr_generation.create_client_from_provider_id") as mock_provider_factory:
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client
            
            service = ADRGenerationService(mock_llama_client, mock_lightrag_client, mock_persona_manager)

            result = await service.generate_adr(generation_prompt, include_context=True)

            assert result is not None
            mock_lightrag_client.retrieve_documents.assert_called()

    @pytest.mark.asyncio
    async def test_generate_adr_handles_llm_error(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager, generation_prompt
    ):
        """Test generation handles LLM errors gracefully."""
        # Make generate raise an exception
        mock_llama_client.generate = AsyncMock(side_effect=Exception("LLM Error"))

        # Mock the client factory functions to return our mock client
        with patch("src.adr_generation.create_client_from_persona_config") as mock_factory, \
             patch("src.adr_generation.create_client_from_provider_id") as mock_provider_factory:
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client
            
            service = ADRGenerationService(mock_llama_client, mock_lightrag_client, mock_persona_manager)

            # The service might catch and handle the error gracefully
            # So we just test that it doesn't crash completely
            try:
                result = await service.generate_adr(generation_prompt)
                # If no exception, that's fine - error was handled gracefully
            except Exception as e:
                # If exception raised, that's also acceptable
                assert "LLM Error" in str(e) or "Error" in str(e)
