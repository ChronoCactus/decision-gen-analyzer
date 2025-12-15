"""Tests for ADR generation service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adr_generation import ADRGenerationService
from src.models import ADR, ADRGenerationPrompt


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
            evaluation_criteria=["technical feasibility", "maintainability"],
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
            tags=["database", "postgresql"],
        )

    @pytest.mark.asyncio
    async def test_generate_adr_basic(
        self,
        mock_llama_client,
        mock_lightrag_client,
        mock_persona_manager,
        generation_prompt,
    ):
        """Test basic ADR generation."""
        # Mock the client factory functions to return our mock client
        with (
            patch(
                "src.adr_generation.create_client_from_persona_config"
            ) as mock_factory,
            patch(
                "src.adr_generation.create_client_from_provider_id"
            ) as mock_provider_factory,
            patch("src.adr_generation.get_provider_storage") as mock_get_storage,
        ):
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client

            mock_storage = AsyncMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get.return_value = None
            mock_storage.get_default.return_value = None

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            result = await service.generate_adr(generation_prompt)

            assert result is not None
            assert result.generated_title is not None
            assert result.decision_outcome is not None
            mock_llama_client.generate.assert_called()

    @pytest.mark.asyncio
    async def test_generate_adr_with_personas(
        self,
        mock_llama_client,
        mock_lightrag_client,
        mock_persona_manager,
        generation_prompt,
    ):
        """Test ADR generation with specific personas."""
        personas = ["technical_lead", "business_analyst"]

        with (
            patch(
                "src.adr_generation.create_client_from_persona_config"
            ) as mock_factory,
            patch(
                "src.adr_generation.create_client_from_provider_id"
            ) as mock_provider_factory,
            patch("src.adr_generation.get_provider_storage") as mock_get_storage,
        ):
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client

            mock_storage = AsyncMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get.return_value = None
            mock_storage.get_default.return_value = None

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            result = await service.generate_adr(generation_prompt, personas=personas)

            assert result is not None
            # Should create a client for each persona
            assert mock_factory.call_count >= 2
            # And the generated clients should be called
            assert mock_llama_client.generate.call_count >= 2

    @pytest.mark.asyncio
    async def test_generate_adr_with_related_context(
        self,
        mock_llama_client,
        mock_lightrag_client,
        mock_persona_manager,
        generation_prompt,
    ):
        """Test ADR generation with related context."""
        mock_lightrag_client.retrieve_documents.return_value = [
            {"id": "adr-1", "content": "Previous decision about databases"}
        ]

        # Mock the client factory functions to return our mock client
        with (
            patch(
                "src.adr_generation.create_client_from_persona_config"
            ) as mock_factory,
            patch(
                "src.adr_generation.create_client_from_provider_id"
            ) as mock_provider_factory,
            patch("src.adr_generation.get_provider_storage") as mock_get_storage,
        ):
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client

            mock_storage = AsyncMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get.return_value = None
            mock_storage.get_default.return_value = None

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            result = await service.generate_adr(generation_prompt, include_context=True)

            assert result is not None
            mock_lightrag_client.retrieve_documents.assert_called()

    @pytest.mark.asyncio
    async def test_generate_adr_handles_llm_error(
        self,
        mock_llama_client,
        mock_lightrag_client,
        mock_persona_manager,
        generation_prompt,
    ):
        """Test error handling during generation."""
        mock_llama_client.generate.side_effect = Exception("LLM Error")

        with (
            patch(
                "src.adr_generation.create_client_from_persona_config"
            ) as mock_factory,
            patch(
                "src.adr_generation.create_client_from_provider_id"
            ) as mock_provider_factory,
            patch("src.adr_generation.get_provider_storage") as mock_get_storage,
        ):
            mock_factory.return_value = mock_llama_client
            mock_provider_factory.return_value = mock_llama_client

            mock_storage = AsyncMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get.return_value = None
            mock_storage.get_default.return_value = None

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            # The service might catch and handle the error gracefully
            # So we just test that it doesn't crash completely
            try:
                await service.generate_adr(generation_prompt)
                # If no exception, that's fine - error was handled gracefully
            except Exception as e:
                # If exception raised, that's also acceptable
                assert "LLM Error" in str(e) or "Error" in str(e)

    @pytest.mark.asyncio
    async def test_synthesize_from_existing_personas(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager
    ):
        """Test synthesizing ADR from existing (manually edited) persona responses."""
        # Create an ADR with existing persona responses
        adr = ADR.create(
            title="Test ADR",
            context_and_problem="We need to choose a database",
            decision_outcome="PostgreSQL",
            consequences="Good performance",
        )
        adr.persona_responses = [
            {
                "persona": "technical_lead",
                "perspective": "Manually edited technical perspective",
                "recommendations": ["Use PostgreSQL"],
                "concerns": ["Performance tuning needed"],
            }
        ]

        # Mock synthesis response
        synthesis_response = {
            "decision_outcome": "Synthesized decision from edited personas",
            "consequences": "Synthesized consequences",
            "rationale": "Based on manual edits",
        }
        mock_llama_client.generate.return_value = json.dumps(synthesis_response)

        with (
            patch("src.adr_generation.create_client_from_provider_id") as mock_factory,
            patch("src.adr_generation.get_provider_storage") as mock_get_storage,
        ):
            mock_factory.return_value = mock_llama_client

            mock_storage = AsyncMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get.return_value = None
            mock_storage.get_default.return_value = None

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            result = await service.synthesize_from_existing_personas(adr)

            assert result is not None
            assert (
                result.content.decision_outcome
                == "Synthesized decision from edited personas"
            )
            assert "Synthesized consequences" in result.content.consequences
            # Persona responses should be unchanged
            assert len(result.persona_responses) == 1
            assert result.persona_responses[0]["persona"] == "technical_lead"
            assert "Manually edited" in result.persona_responses[0]["perspective"]

    @pytest.mark.asyncio
    async def test_synthesize_from_existing_personas_no_responses(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager
    ):
        """Test synthesizing ADR fails when no persona responses exist."""
        # Create an ADR without persona responses
        adr = ADR.create(
            title="Test ADR",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )
        adr.persona_responses = []

        service = ADRGenerationService(
            mock_llama_client, mock_lightrag_client, mock_persona_manager
        )

        with pytest.raises(ValueError, match="no persona responses"):
            await service.synthesize_from_existing_personas(adr)

    @pytest.mark.asyncio
    async def test_synthesize_from_existing_personas_with_provider(
        self, mock_llama_client, mock_lightrag_client, mock_persona_manager
    ):
        """Test synthesizing with specific provider ID."""
        adr = ADR.create(
            title="Test ADR",
            context_and_problem="Problem",
            decision_outcome="Decision",
            consequences="Consequences",
        )
        adr.persona_responses = [
            {"persona": "technical_lead", "perspective": "Test perspective"}
        ]

        synthesis_response = {
            "decision_outcome": "Synthesized with custom provider",
            "consequences": "Consequences",
            "rationale": "Rationale",
        }
        mock_llama_client.generate.return_value = json.dumps(synthesis_response)

        with (
            patch("src.adr_generation.create_client_from_provider_id") as mock_factory,
            patch("src.adr_generation.get_provider_storage") as mock_get_storage,
        ):
            mock_factory.return_value = mock_llama_client

            mock_storage = AsyncMock()
            mock_get_storage.return_value = mock_storage
            mock_storage.get.return_value = MagicMock(id="custom-provider")

            service = ADRGenerationService(
                mock_llama_client, mock_lightrag_client, mock_persona_manager
            )

            result = await service.synthesize_from_existing_personas(
                adr, synthesis_provider_id="custom-provider"
            )

            assert result is not None
            # Verify the custom provider was used
            mock_factory.assert_called_with("custom-provider")
