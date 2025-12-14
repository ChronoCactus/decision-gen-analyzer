"""
Integration tests for per-persona model selection during refinement.

These tests ensure that:
1. Each persona uses its correctly assigned provider
2. No data leaks between providers
3. Provider overrides work as expected
4. Synthesis uses a separate provider when specified
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adr_generation import ADRGenerationService
from src.models import ADR, ADRContent, ADRMetadata, PersonaSynthesisInput


@pytest.mark.asyncio
async def test_persona_respects_provider_override():
    """Test that a persona uses the overridden provider, not its default."""
    # This test verifies the critical security requirement:
    # When a user overrides a persona's provider, that override MUST be used

    with (
        patch(
            "src.adr_generation.create_client_from_provider_id"
        ) as mock_create_provider,
        patch(
            "src.adr_generation.create_client_from_persona_config"
        ) as mock_create_persona,
    ):

        # Setup: persona has default provider A, but user overrides to provider B
        mock_provider_b_client = AsyncMock()
        mock_provider_b_client.__aenter__.return_value = mock_provider_b_client
        mock_provider_b_client.__aexit__.return_value = None
        mock_provider_b_client.generate.return_value = """
        {
            "perspective": "Test perspective",
            "reasoning": "Test reasoning",
            "concerns": ["Test concern"],
            "requirements": ["Test requirement"]
        }
        """
        mock_create_provider.return_value = mock_provider_b_client

        # Create mock ADR with one persona
        adr = ADR(
            metadata=ADRMetadata(
                id=uuid.uuid4(),
                title="Test ADR",
                status="proposed",
                author="test",
                tags=[],
                record_type="decision",
            ),
            content=ADRContent(
                context_and_problem="Test context",
                decision_outcome="Test decision",
                consequences="Test consequences",
            ),
            persona_responses=[
                PersonaSynthesisInput(
                    persona="technical_lead",
                    perspective="Original perspective",
                    reasoning="Original reasoning",
                    original_prompt_text="Original prompt",
                ).model_dump()
            ],
        )

        # Mock the service dependencies
        mock_lightrag = AsyncMock()
        mock_llama = AsyncMock()
        mock_persona_manager = MagicMock()

        # Mock persona config
        mock_persona_config = MagicMock()
        mock_persona_config.model_config = {
            "name": "default-model",
            "provider": "default-provider",
        }
        mock_persona_manager.get_persona_config.return_value = mock_persona_config

        service = ADRGenerationService(
            llama_client=mock_llama,
            lightrag_client=mock_lightrag,
            persona_manager=mock_persona_manager,
        )

        # Execute refinement with provider override
        persona_provider_overrides = {"technical_lead": "provider-b-id"}

        await service.refine_personas(
            adr=adr,
            persona_refinements={"technical_lead": "Make it better"},
            persona_provider_overrides=persona_provider_overrides,
        )

        # Verify: create_client_from_provider_id was called with override provider
        mock_create_provider.assert_called_once_with("provider-b-id", demo_mode=False)

        # Verify: persona's default provider was NOT used
        mock_create_persona.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_personas_different_providers():
    """Test that different personas can use different providers simultaneously."""
    # This verifies no cross-provider data leakage

    with patch(
        "src.adr_generation.create_client_from_provider_id"
    ) as mock_create_provider:

        # Setup: Track which provider is used for which persona
        provider_calls = {}

        def mock_client_factory(provider_id, demo_mode=False):
            client = AsyncMock()
            client.__aenter__.return_value = client
            client.__aexit__.return_value = None
            client.generate.return_value = f"""{{"perspective": "Perspective from {provider_id}", "reasoning": "Reasoning from {provider_id}", "concerns": ["Concern from {provider_id}"], "requirements": ["Requirement from {provider_id}"]}}"""
            provider_calls[provider_id] = client
            return client

        mock_create_provider.side_effect = mock_client_factory

        # Create ADR with 3 personas
        adr = ADR(
            metadata=ADRMetadata(
                id=uuid.uuid4(),
                title="Multi Provider Test",
                status="proposed",
                author="test",
                tags=[],
                record_type="decision",
            ),
            content=ADRContent(
                context_and_problem="Test", decision_outcome="Test", consequences="Test"
            ),
            persona_responses=[
                PersonaSynthesisInput(
                    persona="technical_lead",
                    perspective="P1",
                    reasoning="R1",
                    original_prompt_text="Prompt1",
                ).model_dump(),
                PersonaSynthesisInput(
                    persona="architect",
                    perspective="P2",
                    reasoning="R2",
                    original_prompt_text="Prompt2",
                ).model_dump(),
                PersonaSynthesisInput(
                    persona="business_analyst",
                    perspective="P3",
                    reasoning="R3",
                    original_prompt_text="Prompt3",
                ).model_dump(),
            ],
        )

        # Mock dependencies
        mock_lightrag = AsyncMock()
        mock_llama = AsyncMock()
        mock_persona_manager = MagicMock()

        # Mock persona configs
        def get_persona_config(persona_name):
            config = MagicMock()
            config.model_config = None  # Force use of overrides
            return config

        mock_persona_manager.get_persona_config.side_effect = get_persona_config

        service = ADRGenerationService(
            llama_client=mock_llama,
            lightrag_client=mock_lightrag,
            persona_manager=mock_persona_manager,
        )

        # Refine with different providers for each persona
        persona_provider_overrides = {
            "technical_lead": "provider-a",
            "architect": "provider-b",
            "business_analyst": "provider-c",
        }

        await service.refine_personas(
            adr=adr,
            persona_refinements={
                "technical_lead": "Refine 1",
                "architect": "Refine 2",
                "business_analyst": "Refine 3",
            },
            persona_provider_overrides=persona_provider_overrides,
        )

        # Verify: Each provider was used exactly once
        assert len(provider_calls) == 3
        assert "provider-a" in provider_calls
        assert "provider-b" in provider_calls
        assert "provider-c" in provider_calls

        # Verify: Each provider's client was called with generate()
        for provider_id, client in provider_calls.items():
            client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_synthesis_uses_separate_provider():
    """Test that synthesis uses a different provider than persona generation."""

    with patch(
        "src.adr_generation.create_client_from_provider_id"
    ) as mock_create_provider:

        # Setup synthesis provider
        mock_synthesis_client = AsyncMock()
        mock_synthesis_client.__aenter__.return_value = mock_synthesis_client
        mock_synthesis_client.__aexit__.return_value = None
        mock_synthesis_client.generate.return_value = """
        {
            "title": "Synthesized Title",
            "context_and_problem": "Synthesized context",
            "decision_outcome": "Synthesized decision",
            "consequences": "Synthesized consequences",
            "options_details": []
        }
        """

        # Setup persona provider
        mock_persona_client = AsyncMock()
        mock_persona_client.__aenter__.return_value = mock_persona_client
        mock_persona_client.__aexit__.return_value = None
        mock_persona_client.generate.return_value = '{"perspective": "Refined", "reasoning": "Refined reasoning", "concerns": ["Refined concern"], "requirements": ["Refined requirement"]}'

        call_count = [0]

        def client_factory(provider_id, demo_mode=False):
            call_count[0] += 1
            if "synthesis" in provider_id:
                return mock_synthesis_client
            else:
                return mock_persona_client

        mock_create_provider.side_effect = client_factory

        # Create test ADR
        adr = ADR(
            metadata=ADRMetadata(
                id=uuid.uuid4(),
                title="Synthesis Test",
                status="proposed",
                author="test",
                tags=[],
                record_type="decision",
            ),
            content=ADRContent(
                context_and_problem="Test", decision_outcome="Test", consequences="Test"
            ),
            persona_responses=[
                PersonaSynthesisInput(
                    persona="technical_lead",
                    perspective="Original",
                    reasoning="Original",
                    original_prompt_text="Prompt",
                ).model_dump()
            ],
        )

        # Mock dependencies
        mock_lightrag = AsyncMock()
        mock_llama = AsyncMock()
        mock_persona_manager = MagicMock()
        mock_persona_manager.get_persona_config.return_value = MagicMock(
            model_config=None
        )

        service = ADRGenerationService(
            llama_client=mock_llama,
            lightrag_client=mock_lightrag,
            persona_manager=mock_persona_manager,
        )

        # Refine with separate synthesis provider
        await service.refine_personas(
            adr=adr,
            persona_refinements={"technical_lead": "Refine"},
            persona_provider_overrides={"technical_lead": "persona-provider"},
            synthesis_provider_id="synthesis-provider",
        )

        # Verify: Both providers were called
        assert call_count[0] >= 2  # At least persona and synthesis
        mock_persona_client.generate.assert_called()
        mock_synthesis_client.generate.assert_called()


@pytest.mark.asyncio
async def test_no_override_uses_persona_default():
    """Test that when no override is provided, persona uses its configured model."""

    with patch(
        "src.adr_generation.create_client_from_persona_config"
    ) as mock_create_persona:

        # Setup persona's default client
        mock_persona_client = AsyncMock()
        mock_persona_client.__aenter__.return_value = mock_persona_client
        mock_persona_client.__aexit__.return_value = None
        mock_persona_client.generate.return_value = '{"perspective": "Default perspective", "reasoning": "Default reasoning", "concerns": ["Default concern"], "requirements": ["Default requirement"]}'
        mock_create_persona.return_value = mock_persona_client

        # Create test ADR
        adr = ADR(
            metadata=ADRMetadata(
                id=uuid.uuid4(),
                title="Default Provider Test",
                status="proposed",
                author="test",
                tags=[],
                record_type="decision",
            ),
            content=ADRContent(
                context_and_problem="Test", decision_outcome="Test", consequences="Test"
            ),
            persona_responses=[
                PersonaSynthesisInput(
                    persona="architect",
                    perspective="Original",
                    reasoning="Original",
                    original_prompt_text="Prompt",
                ).model_dump()
            ],
        )

        # Mock dependencies
        mock_lightrag = AsyncMock()
        mock_llama = AsyncMock()
        mock_persona_manager = MagicMock()

        # Persona has a configured model
        mock_persona_config = MagicMock()
        mock_persona_config.model_config = {
            "name": "configured-model",
            "provider": "configured-provider",
        }
        mock_persona_manager.get_persona_config.return_value = mock_persona_config

        service = ADRGenerationService(
            llama_client=mock_llama,
            lightrag_client=mock_lightrag,
            persona_manager=mock_persona_manager,
        )

        # Refine WITHOUT provider override
        await service.refine_personas(
            adr=adr,
            persona_refinements={"architect": "Refine"},
            persona_provider_overrides={},  # Empty - no overrides
        )

        # Verify: Persona's configured model was used
        mock_create_persona.assert_called()
        # Verify it was called with the persona config
        call_args = mock_create_persona.call_args
        assert call_args[0][0] == mock_persona_config
