"""ADR Generation Service for creating new ADRs from prompts."""

import asyncio
import json
from typing import Any, Dict, List, Optional, Union

from src.lightrag_client import LightRAGClient
from src.llama_client import (
    LlamaCppClient,
    LlamaCppClientPool,
    create_client_from_persona_config,
    create_client_from_provider_id,
)
from src.llm_provider_storage import get_provider_storage
from src.logger import get_logger
from src.models import (
    ADR,
    ADRContent,
    ADRGenerationOptions,
    ADRGenerationPrompt,
    ADRGenerationResult,
    ADRMetadata,
    PersonaSynthesisInput,
    RecordType,
)
from src.persona_manager import PersonaConfig, PersonaManager
from src.prompts import (
    ADR_SYNTHESIS_SYSTEM_PROMPT,
    PRINCIPLE_PERSONA_GENERATION_SYSTEM_PROMPT,
    PRINCIPLE_SYNTHESIS_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class ADRGenerationService:
    """Service for generating new ADRs from natural language prompts."""

    def __init__(
        self,
        llama_client: Union[LlamaCppClient, LlamaCppClientPool],
        lightrag_client: LightRAGClient,
        persona_manager: PersonaManager,
    ):
        """Initialize the ADR generation service.

        Args:
            llama_client: Client or client pool for LLM interactions
            lightrag_client: Client for vector database retrieval
            persona_manager: Manager for persona configurations
        """
        self.llama_client = llama_client
        self.lightrag_client = lightrag_client
        self.persona_manager = persona_manager
        self.use_pool = isinstance(llama_client, LlamaCppClientPool)

    async def generate_adr(
        self,
        prompt: ADRGenerationPrompt,
        personas: Optional[List[str]] = None,
        include_context: bool = True,
        progress_callback: Optional[callable] = None,
        persona_provider_overrides: Optional[Dict[str, str]] = None,
        synthesis_provider_id: Optional[str] = None,
        mcp_tools: Optional[List[Dict[str, Any]]] = None,
        use_mcp: bool = False,
    ) -> ADRGenerationResult:
        """Generate a new ADR from a prompt using multiple personas.

        Each persona will use:
        1. Provider from persona_provider_overrides if specified
        2. Otherwise, persona's configured model_config
        3. Otherwise, default provider

        This ensures no data leaks to unexpected providers.

        Args:
            prompt: The generation prompt with context and requirements
            personas: List of persona values (e.g., ['technical_lead', 'architect'])
            include_context: Whether to retrieve related context from vector DB
            progress_callback: Optional callback function for progress updates
            persona_provider_overrides: Optional dict mapping persona names to provider IDs
            synthesis_provider_id: Optional provider ID for synthesis step
            mcp_tools: Optional list of MCP tools (deprecated - use use_mcp instead)
            use_mcp: Whether to use AI-driven MCP tool orchestration

        Returns:
            ADRGenerationResult: The generated ADR with all components
        """
        logger.info(
            "Starting ADR generation", title=prompt.title, personas=personas or []
        )

        # Default personas if none specified
        if not personas:
            personas = ["technical_lead", "business_analyst", "architect"]

        # AI-driven MCP tool orchestration
        tool_output_context = ""
        mcp_refs: List[Dict[str, str]] = []
        if use_mcp:
            tool_output_context, mcp_refs = await self._orchestrate_mcp_tools(
                prompt, progress_callback, synthesis_provider_id
            )

        # Retrieve related context if requested
        related_context = []
        referenced_adr_info = []
        if include_context:
            if progress_callback:
                progress_callback("Retrieving related context...")
            related_context, referenced_adr_info = await self._get_related_context(
                prompt
            )

        # Combine ADR references with MCP references
        all_references = referenced_adr_info + mcp_refs

        # Generate perspectives from each persona
        synthesis_inputs = await self._generate_persona_perspectives(
            prompt,
            personas,
            related_context,
            progress_callback,
            persona_provider_overrides,
            tool_output_context=tool_output_context,
        )

        # Synthesize all perspectives into final ADR
        if progress_callback:
            progress_callback("Synthesizing perspectives into final ADR...")
        result = await self._synthesize_adr(
            prompt,
            synthesis_inputs,
            related_context,
            all_references,
            progress_callback,
            synthesis_provider_id=synthesis_provider_id,
        )

        logger.info(
            "ADR generation completed",
            title=result.generated_title,
            confidence=result.confidence_score,
            personas_used=result.personas_used,
        )

        return result

    async def refine_personas(
        self,
        adr: ADR,
        persona_refinements: Dict[str, str],
        refinements_to_delete: Dict[str, List[int]] = None,
        progress_callback: Optional[callable] = None,
        persona_provider_overrides: Dict[str, str] = None,
        synthesis_provider_id: Optional[str] = None,
    ) -> ADR:
        """Refine specific personas in an existing ADR and re-synthesize.

        Args:
            adr: The existing ADR with persona responses
            persona_refinements: Dict mapping persona names to refinement prompts
            refinements_to_delete: Dict mapping persona names to refinement indices to delete
            progress_callback: Optional callback function for progress updates
            persona_provider_overrides: Dict mapping persona names to provider IDs (overrides persona's default)
            synthesis_provider_id: Optional provider ID to use for synthesis step (separate from persona generation)

        Returns:
            Updated ADR with refined persona perspectives

        Security Note:
            Each persona will use:
            1. Provider from persona_provider_overrides[persona_name] if specified
            2. Otherwise, persona's configured model_config
            3. Otherwise, default llama_client

            This ensures no data leaks to unintended providers.
        """
        logger.info(
            "Starting persona refinement",
            adr_id=str(adr.metadata.id),
            personas_to_refine=list(persona_refinements.keys()),
        )

        if not adr.persona_responses:
            raise ValueError("ADR has no persona responses to refine")

        # Get the original prompt from ADR content
        # Reconstruct the prompt from stored data
        from src.models import ADRGenerationPrompt

        original_prompt = ADRGenerationPrompt(
            title=adr.metadata.title,
            context=(
                adr.content.context_and_problem.split("\n\n")[0]
                if "\n\n" in adr.content.context_and_problem
                else adr.content.context_and_problem
            ),
            problem_statement=(
                adr.content.context_and_problem.split("\n\n")[1]
                if "\n\n" in adr.content.context_and_problem
                else adr.content.context_and_problem
            ),
            tags=adr.metadata.tags,
        )

        # Convert persona_responses to PersonaSynthesisInput objects if they're dicts
        from src.models import PersonaSynthesisInput

        existing_persona_responses = []
        for pr in adr.persona_responses:
            if isinstance(pr, dict):
                existing_persona_responses.append(PersonaSynthesisInput(**pr))
            else:
                existing_persona_responses.append(pr)

        # Process refinement deletions first
        personas_with_deletions = set()
        if refinements_to_delete:
            for persona_name, indices_to_delete in refinements_to_delete.items():
                # Find the persona response
                persona_response = next(
                    (
                        pr
                        for pr in existing_persona_responses
                        if pr.persona == persona_name
                    ),
                    None,
                )
                if persona_response and hasattr(persona_response, "refinement_history"):
                    # Sort indices in reverse order to delete from end to start
                    # This prevents index shifting issues
                    sorted_indices = sorted(indices_to_delete, reverse=True)
                    original_count = len(persona_response.refinement_history)

                    for idx in sorted_indices:
                        if 0 <= idx < len(persona_response.refinement_history):
                            persona_response.refinement_history.pop(idx)

                    deleted_count = original_count - len(
                        persona_response.refinement_history
                    )
                    if deleted_count > 0:
                        personas_with_deletions.add(persona_name)

                    logger.info(
                        f"Deleted {deleted_count} refinement(s) from {persona_name}",
                        persona=persona_name,
                        deleted_count=deleted_count,
                        remaining_count=len(persona_response.refinement_history),
                    )

        # Determine which personas need regeneration
        # This includes both personas with new refinements AND personas with deletions
        personas_to_regenerate = (
            set(persona_refinements.keys()) | personas_with_deletions
        )

        if progress_callback:
            total_count = len(personas_to_regenerate)
            progress_callback(f"Regenerating {total_count} persona perspective(s)...")

        refined_responses = []

        # First, handle personas with new refinements
        for persona_name, refinement_prompt in persona_refinements.items():
            # Find the original persona response
            original_response = next(
                (pr for pr in existing_persona_responses if pr.persona == persona_name),
                None,
            )

            if not original_response:
                logger.warning(
                    f"Cannot refine persona {persona_name}: persona not found in ADR"
                )
                continue

            # If original_prompt_text is missing (old ADR), regenerate it from the persona config
            if not original_response.original_prompt_text:
                logger.info(
                    f"Persona {persona_name} missing original prompt, regenerating from config"
                )
                persona_config = self.persona_manager.get_persona_config(persona_name)
                if not persona_config:
                    logger.warning(
                        f"Cannot refine persona {persona_name}: config not found"
                    )
                    continue

                # Recreate the original prompt
                original_prompt_text = self._create_persona_generation_prompt(
                    persona_config,
                    original_prompt,
                    [],  # No related context for old ADRs
                )
            else:
                original_prompt_text = original_response.original_prompt_text
                persona_config = self.persona_manager.get_persona_config(persona_name)
                if not persona_config:
                    logger.warning(
                        f"Cannot refine persona {persona_name}: config not found"
                    )
                    continue

            # Create refined prompt by appending refinement to original
            refined_prompt_text = (
                original_prompt_text
                + f"\n\n**Additional Refinement Request**:\n{refinement_prompt}"
            )

            if progress_callback:
                progress_callback(
                    f"Regenerating {persona_name.replace('_', ' ').title()}..."
                )

            # Create client for this persona with proper precedence
            # Priority: 1) User override, 2) Persona config, 3) Default
            persona_provider_overrides = persona_provider_overrides or {}
            if persona_name in persona_provider_overrides:
                # User explicitly selected a different provider for this persona
                persona_client = await create_client_from_provider_id(
                    persona_provider_overrides[persona_name], demo_mode=False
                )
                logger.info(
                    f"Using provider override for {persona_name}",
                    provider_id=persona_provider_overrides[persona_name],
                )
            elif persona_config.model_config:
                # Use persona's configured model
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )
                logger.info(
                    f"Using persona-configured model for {persona_name}",
                    model_config=persona_config.model_config,
                )
            else:
                # Fall back to default client (from self.llama_client)
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )
                logger.info(f"Using default client for {persona_name}")

            # Generate refined response
            try:
                async with persona_client:
                    response = await persona_client.generate(
                        prompt=refined_prompt_text, temperature=0.7, num_predict=2000
                    )

                logger.info(
                    "Received response for persona refinement",
                    persona=persona_name,
                    response_length=len(response),
                    response_preview=response[:200],
                )

                # Parse the response
                perspective_data = self._parse_persona_response(response)
                if perspective_data:
                    # Preserve and extend refinement history
                    existing_history = (
                        original_response.refinement_history
                        if hasattr(original_response, "refinement_history")
                        else []
                    )
                    updated_history = existing_history + [refinement_prompt]

                    refined_response = PersonaSynthesisInput(
                        persona=persona_name,
                        original_prompt_text=refined_prompt_text,
                        refinement_history=updated_history,
                        **perspective_data,
                    )
                    refined_responses.append(refined_response)
                    logger.info(
                        "Successfully parsed persona refinement",
                        persona=persona_name,
                        refinement_count=len(updated_history),
                    )
                else:
                    logger.error(
                        "Failed to parse persona refinement response",
                        persona=persona_name,
                        response_preview=response[:500],
                    )
            except Exception as e:
                logger.error(
                    "Exception during persona refinement",
                    persona=persona_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Now handle personas that only had deletions (no new refinements)
        personas_only_deletions = personas_with_deletions - set(
            persona_refinements.keys()
        )

        for persona_name in personas_only_deletions:
            if progress_callback:
                progress_callback(
                    f"Regenerating {persona_name.replace('_', ' ').title()} after refinement deletion..."
                )

            # Find the persona response (with updated refinement_history from deletions)
            persona_response = next(
                (pr for pr in existing_persona_responses if pr.persona == persona_name),
                None,
            )

            if not persona_response:
                logger.warning(
                    f"Cannot regenerate persona {persona_name}: persona not found"
                )
                continue

            persona_config = self.persona_manager.get_persona_config(persona_name)
            if not persona_config:
                logger.warning(
                    f"Cannot regenerate persona {persona_name}: config not found"
                )
                continue

            # Reconstruct the prompt with the current refinement history
            # Start with the original prompt
            if persona_response.original_prompt_text:
                # Extract the base prompt (before any refinements)
                base_prompt = persona_response.original_prompt_text.split(
                    "\n\n**Additional Refinement Request**:"
                )[0]
            else:
                # Recreate base prompt from config
                base_prompt = self._create_persona_generation_prompt(
                    persona_config,
                    original_prompt,
                    [],
                )

            # Now add back the remaining refinements
            current_prompt = base_prompt
            if persona_response.refinement_history:
                for refinement in persona_response.refinement_history:
                    current_prompt += (
                        f"\n\n**Additional Refinement Request**:\n{refinement}"
                    )

            # Create client for this persona with proper precedence
            # Priority: 1) User override, 2) Persona config, 3) Default
            persona_provider_overrides = persona_provider_overrides or {}
            if persona_name in persona_provider_overrides:
                # User explicitly selected a different provider for this persona
                persona_client = await create_client_from_provider_id(
                    persona_provider_overrides[persona_name], demo_mode=False
                )
                logger.info(
                    f"Using provider override for {persona_name} (deletion regeneration)",
                    provider_id=persona_provider_overrides[persona_name],
                )
            elif persona_config.model_config:
                # Use persona's configured model
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )
                logger.info(
                    f"Using persona-configured model for {persona_name} (deletion regeneration)",
                    model_config=persona_config.model_config,
                )
            else:
                # Fall back to default client
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )
                logger.info(
                    f"Using default client for {persona_name} (deletion regeneration)"
                )

            # Regenerate the persona with updated prompt
            try:
                async with persona_client:
                    response = await persona_client.generate(
                        prompt=current_prompt, temperature=0.7, num_predict=2000
                    )

                logger.info(
                    "Received response for persona regeneration after deletion",
                    persona=persona_name,
                    response_length=len(response),
                )

                # Parse the response
                perspective_data = self._parse_persona_response(response)
                if perspective_data:
                    regenerated_response = PersonaSynthesisInput(
                        persona=persona_name,
                        original_prompt_text=current_prompt,
                        refinement_history=persona_response.refinement_history,
                        **perspective_data,
                    )
                    refined_responses.append(regenerated_response)
                    logger.info(
                        "Successfully regenerated persona after deletion",
                        persona=persona_name,
                        remaining_refinements=len(persona_response.refinement_history),
                    )
                else:
                    logger.error(
                        "Failed to parse persona regeneration response",
                        persona=persona_name,
                    )
            except Exception as e:
                logger.error(
                    "Exception during persona regeneration after deletion",
                    persona=persona_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Check if any personas were successfully refined (or had deletions)
        if not refined_responses and not personas_with_deletions:
            error_msg = f"Failed to refine any of the requested personas: {list(persona_refinements.keys())}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        if refined_responses:
            logger.info(
                "Successfully refined personas",
                requested=list(persona_refinements.keys()),
                refined=[pr.persona for pr in refined_responses],
            )

        if personas_with_deletions:
            logger.info(
                "Successfully deleted refinements from personas",
                personas_with_deletions=list(personas_with_deletions),
            )

        # Merge refined responses with existing ones
        updated_responses = []
        refined_persona_names = {pr.persona for pr in refined_responses}

        for original in existing_persona_responses:
            if original.persona in refined_persona_names:
                # Use the refined version
                refined = next(
                    pr for pr in refined_responses if pr.persona == original.persona
                )
                updated_responses.append(refined)
            else:
                # Keep the original (which may have had deletions applied)
                updated_responses.append(original)

        # Re-synthesize the ADR with updated persona responses
        if progress_callback:
            progress_callback("Re-synthesizing ADR with refined perspectives...")

        logger.info(
            "Starting ADR re-synthesis", updated_persona_count=len(updated_responses)
        )

        # Get related context from original ADR
        related_context = []
        referenced_adr_info = adr.content.referenced_adrs or []

        # Synthesize with updated responses
        result = await self._synthesize_adr(
            original_prompt,
            updated_responses,
            related_context,
            referenced_adr_info,
            progress_callback,
            synthesis_provider_id=synthesis_provider_id,
        )

        logger.info("ADR re-synthesis completed successfully")

        # Update the ADR with new content
        adr.content.context_and_problem = result.context_and_problem
        adr.content.decision_outcome = result.decision_outcome
        adr.content.consequences = result.consequences
        adr.content.considered_options = [
            opt.option_name for opt in result.considered_options
        ]
        adr.content.decision_drivers = result.decision_drivers

        # Update persona responses
        adr.persona_responses = [pr.model_dump() for pr in updated_responses]

        # Update timestamp
        from datetime import UTC, datetime

        adr.metadata.updated_at = datetime.now(UTC)

        logger.info(
            "Persona refinement completed",
            adr_id=str(adr.metadata.id),
            personas_refined=list(persona_refinements.keys()),
        )

        return adr

    async def synthesize_from_existing_personas(
        self,
        adr: ADR,
        synthesis_provider_id: Optional[str] = None,
    ) -> ADR:
        """Synthesize a new final decision record from existing (possibly manually edited) persona responses.

        This method takes the existing persona_responses from the ADR and synthesizes them into
        a new final decision record without regenerating the persona perspectives. This is useful
        when persona responses have been manually edited and you want to resynthesize the final ADR
        from those manual edits.

        Args:
            adr: The existing ADR with persona responses
            synthesis_provider_id: Optional provider ID for synthesis step

        Returns:
            Updated ADR with resynthesized content
        """
        logger.info(
            "Starting resynthesis from existing personas",
            adr_id=str(adr.metadata.id),
            num_personas=len(adr.persona_responses) if adr.persona_responses else 0,
        )

        if not adr.persona_responses:
            raise ValueError("ADR has no persona responses to synthesize")

        # Convert persona_responses to PersonaSynthesisInput objects if they're dicts
        from src.models import PersonaSynthesisInput

        existing_persona_responses = []
        for pr in adr.persona_responses:
            if isinstance(pr, dict):
                existing_persona_responses.append(PersonaSynthesisInput(**pr))
            else:
                existing_persona_responses.append(pr)

        # Get the original prompt from ADR content
        # Reconstruct the prompt from stored data
        from src.models import ADRGenerationPrompt

        if adr.content.original_generation_prompt:
            # Use stored prompt if available
            original_prompt = ADRGenerationPrompt(
                **adr.content.original_generation_prompt
            )
        else:
            # Fallback: reconstruct from ADR content
            original_prompt = ADRGenerationPrompt(
                title=adr.metadata.title,
                context=(
                    adr.content.context_and_problem.split("\n\n")[0]
                    if "\n\n" in adr.content.context_and_problem
                    else adr.content.context_and_problem
                ),
                problem_statement=(
                    adr.content.context_and_problem.split("\n\n")[1]
                    if "\n\n" in adr.content.context_and_problem
                    else adr.content.context_and_problem
                ),
                tags=adr.metadata.tags,
            )

        # Get related context (empty list since we're just resynthesizing)
        related_context: List[str] = []

        # Get referenced ADR info from existing content
        referenced_adr_info: List[Dict[str, str]] = []
        if adr.content.referenced_adrs:
            for ref in adr.content.referenced_adrs:
                if isinstance(ref, dict):
                    referenced_adr_info.append(ref)

        # Synthesize the final ADR from existing persona responses
        result = await self._synthesize_adr(
            original_prompt,
            existing_persona_responses,
            related_context,
            referenced_adr_info,
            progress_callback=None,
            synthesis_provider_id=synthesis_provider_id,
        )

        logger.info("ADR resynthesis completed successfully")

        # Update the ADR with new content
        adr.content.context_and_problem = result.context_and_problem
        adr.content.decision_outcome = result.decision_outcome
        adr.content.consequences = result.consequences
        adr.content.considered_options = [
            opt.option_name for opt in result.considered_options
        ]
        adr.content.decision_drivers = result.decision_drivers

        # Preserve the persona_responses (don't update them since they weren't regenerated)
        # They remain as-is from the manual edits

        # Update timestamp
        from datetime import UTC, datetime

        adr.metadata.updated_at = datetime.now(UTC)

        logger.info(
            "Resynthesis from existing personas completed",
            adr_id=str(adr.metadata.id),
        )

        return adr

    async def refine_original_prompt(
        self,
        adr: ADR,
        refined_prompt_fields: Dict[str, Any],
        progress_callback: Optional[callable] = None,
        persona_provider_overrides: Optional[Dict[str, str]] = None,
        synthesis_provider_id: Optional[str] = None,
        exclude_adr_id: Optional[str] = None,
    ) -> ADR:
        """Refine the original generation prompt and regenerate all personas.

        This method takes a refined/updated original prompt and regenerates the entire ADR.
        All personas are re-run with the new prompt, and any existing refinements for each
        persona are preserved and re-applied.

        Each persona will use:
        1. Provider from persona_provider_overrides if specified
        2. Otherwise, persona's configured model_config
        3. Otherwise, default provider

        This ensures no data leaks to unexpected providers.

        Args:
            adr: The existing ADR with original prompt and persona responses
            refined_prompt_fields: Dict with updated prompt fields (title, context, problem_statement, constraints, stakeholders, retrieval_mode)
            progress_callback: Optional callback function for progress updates
            persona_provider_overrides: Optional dict mapping persona names to provider IDs
            synthesis_provider_id: Optional provider ID for synthesis step
            exclude_adr_id: Optional ADR ID to exclude from retrieval (typically the current ADR to prevent self-referencing)

        Returns:
            Updated ADR with regenerated content and persona responses
        """
        logger.info(
            "Starting original prompt refinement",
            adr_id=str(adr.metadata.id),
            refined_fields=list(refined_prompt_fields.keys()),
        )

        if not adr.content.original_generation_prompt:
            raise ValueError(
                "ADR has no original generation prompt stored. This ADR may have been created before prompt storage was implemented."
            )

        if not adr.persona_responses:
            raise ValueError("ADR has no persona responses to regenerate")

        # Merge the refined fields with the original prompt
        original_prompt_data = adr.content.original_generation_prompt.copy()
        original_prompt_data.update(refined_prompt_fields)

        # Create the refined generation prompt
        from src.models import ADRGenerationPrompt

        refined_prompt = ADRGenerationPrompt(
            title=original_prompt_data.get("title", adr.metadata.title),
            context=original_prompt_data.get("context", ""),
            problem_statement=original_prompt_data.get("problem_statement", ""),
            constraints=original_prompt_data.get("constraints"),
            stakeholders=original_prompt_data.get("stakeholders"),
            tags=original_prompt_data.get("tags", adr.metadata.tags),
            retrieval_mode=original_prompt_data.get("retrieval_mode", "naive"),
        )  # Convert persona_responses to PersonaSynthesisInput objects if they're dicts
        from src.models import PersonaSynthesisInput

        existing_persona_responses = []
        for pr in adr.persona_responses:
            if isinstance(pr, dict):
                existing_persona_responses.append(PersonaSynthesisInput(**pr))
            else:
                existing_persona_responses.append(pr)

        # Get the list of personas to regenerate (all existing personas)
        personas_to_regenerate = [pr.persona for pr in existing_persona_responses]

        if progress_callback:
            progress_callback(
                f"Regenerating {len(personas_to_regenerate)} persona perspective(s) with refined original prompt..."
            )

        # Retrieve related context with the refined prompt
        related_context = []
        referenced_adr_info = []
        if refined_prompt.retrieval_mode != "bypass":
            if progress_callback:
                progress_callback("Retrieving related context with refined prompt...")
            related_context, referenced_adr_info = await self._get_related_context(
                refined_prompt, exclude_adr_id=exclude_adr_id
            )

        # Regenerate all personas with the refined original prompt
        regenerated_responses = []

        for persona_response in existing_persona_responses:
            persona_name = persona_response.persona

            if progress_callback:
                progress_callback(
                    f"Regenerating {persona_name.replace('_', ' ').title()}..."
                )

            persona_config = self.persona_manager.get_persona_config(persona_name)
            if not persona_config:
                logger.warning(
                    f"Cannot regenerate persona {persona_name}: config not found"
                )
                continue

            # Create the base prompt with the refined original prompt
            base_prompt_text = self._create_persona_generation_prompt(
                persona_config,
                refined_prompt,
                related_context,
            )

            # Re-apply any existing refinements from the persona's history
            current_prompt = base_prompt_text
            if (
                hasattr(persona_response, "refinement_history")
                and persona_response.refinement_history
            ):
                for refinement in persona_response.refinement_history:
                    current_prompt += (
                        f"\n\n**Additional Refinement Request**:\n{refinement}"
                    )

            # Create client for this persona with three-tier precedence:
            # 1) User override from persona_provider_overrides
            # 2) Persona's configured model_config
            # 3) Default provider
            if (
                persona_provider_overrides
                and persona_name in persona_provider_overrides
            ):
                logger.info(
                    f"Using provider override for {persona_name}: {persona_provider_overrides[persona_name]}"
                )
                persona_client = await create_client_from_provider_id(
                    persona_provider_overrides[persona_name], demo_mode=False
                )
            elif persona_config.model_config:
                logger.info(f"Using persona-configured model for {persona_name}")
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )
            else:
                logger.info(f"Using default client for {persona_name}")
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )

            # Generate response with the refined prompt
            try:
                async with persona_client:
                    response = await persona_client.generate(
                        prompt=current_prompt, temperature=0.7, num_predict=2000
                    )

                logger.info(
                    "Received response for persona with refined original prompt",
                    persona=persona_name,
                    response_length=len(response),
                )

                # Parse the response
                perspective_data = self._parse_persona_response(response)
                if perspective_data:
                    # Preserve the refinement history
                    refinement_history = (
                        persona_response.refinement_history
                        if hasattr(persona_response, "refinement_history")
                        else []
                    )

                    regenerated_response = PersonaSynthesisInput(
                        persona=persona_name,
                        original_prompt_text=base_prompt_text,  # Store the NEW base prompt
                        refinement_history=refinement_history,  # Preserve existing refinements
                        **perspective_data,
                    )
                    regenerated_responses.append(regenerated_response)
                    logger.info(
                        "Successfully regenerated persona with refined original prompt",
                        persona=persona_name,
                        refinement_count=len(refinement_history),
                    )
                else:
                    logger.error(
                        "Failed to parse persona regeneration response",
                        persona=persona_name,
                    )
            except Exception as e:
                logger.error(
                    "Exception during persona regeneration with refined original prompt",
                    persona=persona_name,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Check if any personas were successfully regenerated
        if not regenerated_responses:
            error_msg = "Failed to regenerate any personas with refined original prompt"
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info(
            "Successfully regenerated all personas with refined original prompt",
            regenerated_count=len(regenerated_responses),
        )

        # Re-synthesize the ADR with regenerated persona responses
        if progress_callback:
            record_type_label = (
                "Principle" if adr.metadata.record_type == "principle" else "ADR"
            )
            progress_callback(
                f"Re-synthesizing {record_type_label} with regenerated perspectives..."
            )

        result = await self._synthesize_adr(
            refined_prompt,
            regenerated_responses,
            related_context,
            referenced_adr_info,
            progress_callback,
            synthesis_provider_id=synthesis_provider_id,
        )

        logger.info(
            "ADR re-synthesis with refined original prompt completed successfully"
        )

        # Update the ADR with new content
        adr.metadata.title = result.generated_title  # Update title from synthesis
        adr.content.context_and_problem = result.context_and_problem
        adr.content.decision_outcome = result.decision_outcome
        adr.content.consequences = result.consequences
        adr.content.considered_options = [
            opt.option_name for opt in result.considered_options
        ]
        adr.content.decision_drivers = result.decision_drivers

        # Update options_details with full option objects
        from src.models import OptionDetails

        adr.content.options_details = [
            OptionDetails(
                name=opt.option_name,
                description=opt.description,
                pros=opt.pros,
                cons=opt.cons,
            )
            for opt in result.considered_options
        ]

        # Update consequences_structured
        if result.consequences_structured:
            from src.models import ConsequencesStructured

            adr.content.consequences_structured = ConsequencesStructured(
                positive=result.consequences_structured.get("positive", []),
                negative=result.consequences_structured.get("negative", []),
            )

        # Update the stored original generation prompt
        adr.content.original_generation_prompt = {
            "title": result.generated_title,
            "context": refined_prompt.context,
            "problem_statement": refined_prompt.problem_statement,
            "constraints": refined_prompt.constraints,
            "stakeholders": refined_prompt.stakeholders,
            "tags": refined_prompt.tags,
            "retrieval_mode": refined_prompt.retrieval_mode,
        }

        # Update referenced ADRs
        adr.content.referenced_adrs = (
            referenced_adr_info if referenced_adr_info else None
        )

        # Update persona responses
        adr.persona_responses = [pr.model_dump() for pr in regenerated_responses]

        # Update timestamp
        from datetime import UTC, datetime

        adr.metadata.updated_at = datetime.now(UTC)

        logger.info(
            "Original prompt refinement completed",
            adr_id=str(adr.metadata.id),
            personas_regenerated=len(regenerated_responses),
        )

        return adr

    async def _get_related_context(
        self, prompt: ADRGenerationPrompt, exclude_adr_id: Optional[str] = None
    ) -> tuple[List[str], List[Dict[str, str]]]:
        """Retrieve related ADRs from vector database.

        Args:
            prompt: The generation prompt
            exclude_adr_id: Optional ADR ID to exclude from results (to prevent self-referencing)

        Returns:
            Tuple of (related context strings, referenced ADR info dicts with id, title, summary)
        """
        try:
            # Create search query from prompt
            search_query = f"{prompt.problem_statement} {prompt.context}"
            if prompt.tags:
                search_query += f" {' '.join(prompt.tags)}"

            # Query vector database for related ADRs
            async with self.lightrag_client:
                documents = await self.lightrag_client.retrieve_documents(
                    query=search_query,
                    limit=5,
                    metadata_filter={"type": "adr"},
                    mode=prompt.retrieval_mode,
                )

            # Extract relevant context and ADR info
            related_context = []
            referenced_adr_info = []

            # Track entities and relationships across all documents
            all_entities = []
            all_relationships = []

            # Filter by status if requested
            filtered_documents = []
            if prompt.status_filter:
                # Import here to avoid circular dependency
                from src.adr_file_storage import get_adr_storage

                storage = get_adr_storage()
                for doc in documents:
                    doc_id = doc.get("id", "unknown")

                    # Skip generic context documents
                    if doc_id == "context":
                        continue

                    # Skip excluded ADR to prevent self-referencing
                    if exclude_adr_id and doc_id == exclude_adr_id:
                        continue

                    # Load the ADR to check its status
                    adr = storage.get_adr(doc_id)
                    if adr:
                        adr_status = adr.metadata.status.value
                        if adr_status in prompt.status_filter:
                            filtered_documents.append(doc)
                        else:
                            logger.debug(
                                "Filtering out ADR due to status",
                                adr_id=doc_id,
                                status=adr_status,
                                allowed_statuses=prompt.status_filter,
                            )
                    else:
                        # If we can't load the ADR, include it by default
                        logger.warning(
                            "Could not load ADR for status filtering, including by default",
                            adr_id=doc_id,
                        )
                        filtered_documents.append(doc)
            else:
                # No filtering requested, use all documents
                filtered_documents = documents

            related_context.append("**Related Decision Records:**")
            for doc in filtered_documents:
                # Extract structured data if available (entities and relationships)
                if "structured_data" in doc:
                    structured = doc["structured_data"]
                    if "entities" in structured:
                        all_entities.extend(structured["entities"])
                    if "relationships" in structured:
                        all_relationships.extend(structured["relationships"])

                # Track the ADR info with ID, title, and summary
                doc_id = doc.get("id", "unknown")

                doc_metadata = doc.get("metadata", {})
                doc_title = doc.get("title") or doc_metadata.get("title") or doc_id
                doc_content = doc.get("content", "")

                # Initialize record_type with default from metadata
                record_type = doc_metadata.get("record_type", "decision")

                # Try to extract real title and record type from content if available
                # Content usually starts with "Title: ..." and contains "Record Type: ..."
                if doc_content:
                    # Extract Title
                    if doc_content.startswith("Title: "):
                        first_line = doc_content.split("\n")[0]
                        real_title = first_line[7:].strip()
                        if real_title:
                            doc_title = real_title

                    # Extract Record Type
                    import re

                    type_match = re.search(
                        r"Record Type: (decision|principle)", doc_content, re.IGNORECASE
                    )
                    if type_match:
                        record_type = type_match.group(1).lower()
                    # Fallback: Check if title contains "principle" (case insensitive)
                    elif "principle" in doc_title.lower():
                        record_type = "principle"

                # Add the document content as context
                if doc_content:
                    related_context.append(f"**{doc_title}**:\n{doc_content}")

                # Create a 60-character summary
                summary = doc_content[:60]
                if len(doc_content) > 60:
                    summary += "..."

                referenced_adr_info.append(
                    {
                        "id": doc_id,
                        "title": doc_title,
                        "summary": summary,
                        "type": record_type,
                    }
                )

            # Format entities and relationships as additional context
            if all_entities or all_relationships:
                structured_context = self._format_structured_data(
                    all_entities, all_relationships
                )
                if structured_context:
                    # Add structured data at the beginning for prominence
                    related_context.insert(0, structured_context)

            logger.info(
                "Retrieved related ADRs",
                query_length=len(search_query),
                context_count=len(related_context),
                referenced_adrs=[info["id"] for info in referenced_adr_info],
            )

            return related_context, referenced_adr_info

        except Exception as e:
            logger.warning(
                "Failed to retrieve related context",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e),
            )
            return [], []

    def _format_structured_data(
        self, entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> str:
        """Format entities and relationships from knowledge graph into readable context.

        Args:
            entities: List of entity dictionaries from LightRAG
            relationships: List of relationship dictionaries from LightRAG

        Returns:
            Formatted string describing entities and relationships
        """
        if not entities and not relationships:
            return ""

        parts = []

        # Format entities
        if entities:
            parts.append("**Key Entities and Concepts:**")
            # Deduplicate entities by name and sort by relevance (if weight available)
            seen_entities = {}
            for entity in entities:
                name = entity.get("entity_name", "")
                if name and name not in seen_entities:
                    entity_type = entity.get("entity_type", "")
                    description = entity.get("description", "")

                    entity_str = f"- **{name}**"
                    if entity_type:
                        entity_str += f" ({entity_type})"
                    if description:
                        entity_str += f": {description}"

                    seen_entities[name] = entity_str

            # Add up to 10 most relevant entities
            for entity_str in list(seen_entities.values())[:10]:
                parts.append(entity_str)

        # Format relationships
        if relationships:
            if entities:
                parts.append("")  # Add blank line separator
            parts.append("**Key Relationships:**")

            # Sort by weight (if available) and take top relationships
            sorted_relationships = sorted(
                relationships, key=lambda r: r.get("weight", 0.0), reverse=True
            )

            # Deduplicate and format relationships
            seen_relationships = set()
            relationship_count = 0

            for rel in sorted_relationships:
                if relationship_count >= 10:  # Limit to 10 relationships
                    break

                src = rel.get("src_id", "")
                tgt = rel.get("tgt_id", "")
                desc = rel.get("description", "")
                keywords = rel.get("keywords", "")
                weight = rel.get("weight", 0.0)

                # Create a unique key for deduplication
                rel_key = f"{src}→{tgt}"
                if rel_key in seen_relationships:
                    continue

                seen_relationships.add(rel_key)

                if src and tgt:
                    rel_str = f"- **{src}** → **{tgt}**"
                    if desc:
                        rel_str += f": {desc}"
                    if (
                        keywords and weight > 0.7
                    ):  # Only show keywords for high-confidence relationships
                        rel_str += f" (Keywords: {keywords})"

                    parts.append(rel_str)
                    relationship_count += 1

        return "\n".join(parts) if parts else ""

    async def _orchestrate_mcp_tools(
        self,
        prompt: ADRGenerationPrompt,
        progress_callback: Optional[callable] = None,
        provider_id: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, str]]]:
        """Use AI to select and execute MCP tools for research.

        Args:
            prompt: The generation prompt for context
            progress_callback: Optional callback for progress updates
            provider_id: Optional provider ID for the LLM to use

        Returns:
            Tuple of (formatted context string, list of MCP reference dicts)
        """
        try:
            from src.mcp_orchestrator import get_mcp_orchestrator

            orchestrator = get_mcp_orchestrator()

            # Get or create an LLM client for tool selection
            if provider_id:
                llm_client = await create_client_from_provider_id(
                    provider_id, demo_mode=False
                )
            elif self.use_pool:
                llm_client = self.llama_client.get_generation_client(0)
            else:
                llm_client = self.llama_client

            # Run orchestration
            async with llm_client:
                result = await orchestrator.orchestrate(
                    title=prompt.title,
                    problem_statement=prompt.problem_statement,
                    context=prompt.context or "",
                    llm_client=llm_client,
                    progress_callback=progress_callback,
                )

            if result.error:
                logger.error(f"MCP orchestration error: {result.error}")
                return "", []

            if result.tool_selection:
                logger.info(
                    "MCP orchestration completed",
                    reasoning=result.tool_selection.reasoning[:100],
                    tools_called=len(result.tool_selection.tool_calls),
                    successful_results=sum(1 for r in result.tool_results if r.success),
                )

            # Convert references to dict format for referenced_adrs
            mcp_refs = [ref.to_dict() for ref in result.references]

            return result.formatted_context, mcp_refs

        except ImportError as e:
            logger.warning(f"MCP orchestrator not available: {e}")
            return "", []
        except Exception as e:
            logger.error(f"Error in MCP orchestration: {e}")
            return "", []

    async def _execute_mcp_tools(
        self,
        mcp_tools: List[Dict[str, Any]],
        prompt: ADRGenerationPrompt,
        execution_mode: str,
        progress_callback: Optional[callable] = None,
        persona_name: Optional[str] = None,
    ) -> str:
        """Execute MCP tools and return formatted context.

        Args:
            mcp_tools: List of tool selections with server_id, tool_name, and optional arguments
            prompt: The generation prompt for context
            execution_mode: 'initial_only' or 'per_persona'
            progress_callback: Optional callback for progress updates
            persona_name: Optional persona name (for per-persona execution)

        Returns:
            Formatted context string from tool results
        """
        if not mcp_tools:
            return ""

        try:
            from src.mcp_client import (
                format_mcp_results_as_context,
                get_mcp_client_manager,
            )
            from src.mcp_config_storage import MCPToolExecutionMode

            # Convert string to enum
            mode = MCPToolExecutionMode(execution_mode)

            # Build generation context for argument mapping
            generation_context = {
                "title": prompt.title,
                "context": prompt.context,
                "problem_statement": prompt.problem_statement,
                "constraints": ", ".join(prompt.constraints or []),
                "stakeholders": ", ".join(prompt.stakeholders or []),
                "tags": ", ".join(prompt.tags or []),
                # Full query for search-type tools
                "query": f"{prompt.problem_statement} {prompt.context}",
            }

            manager = get_mcp_client_manager()
            results = await manager.execute_tools_for_generation(
                selected_tools=mcp_tools,
                generation_context=generation_context,
                execution_mode=mode,
                persona_name=persona_name,
                progress_callback=progress_callback,
            )

            # Format results as context
            formatted_context = format_mcp_results_as_context(results, mode)

            logger.info(
                "MCP tools executed",
                mode=execution_mode,
                tool_count=len(mcp_tools),
                results_count=len(results),
                successful_count=sum(1 for r in results if r.success),
            )

            return formatted_context

        except ImportError as e:
            logger.warning(f"MCP client not available: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error executing MCP tools: {e}")
            return ""

    async def _generate_persona_perspectives(
        self,
        prompt: ADRGenerationPrompt,
        personas: List[str],
        related_context: List[str],
        progress_callback: Optional[callable] = None,
        persona_provider_overrides: Optional[Dict[str, str]] = None,
        tool_output_context: str = "",
    ) -> List[PersonaSynthesisInput]:
        """Generate perspectives from each persona.

        Each persona will use:
        1. Provider from persona_provider_overrides if specified
        2. Otherwise, persona's configured model_config
        3. Otherwise, default provider

        This ensures no data leaks to unexpected providers.

        Args:
            prompt: The generation prompt
            personas: List of persona values to generate perspectives for
            related_context: Related context from vector DB
            progress_callback: Optional callback for progress updates
            persona_provider_overrides: Optional dict mapping persona names to provider IDs
            tool_output_context: Formatted output from MCP tools

        Returns:
            List of persona synthesis inputs
        """
        total_personas = len(personas)

        if progress_callback:
            progress_callback(f"Generating perspectives from {total_personas} personas")

        # Build prompts for all personas and create their specific clients
        persona_prompts = []
        persona_configs = []
        persona_clients = []

        for persona_value in personas:
            persona_config = self.persona_manager.get_persona_config(persona_value)
            if persona_config:
                persona_configs.append((persona_value, persona_config))

                system_prompt = self._create_persona_generation_prompt(
                    persona_config, prompt, related_context, tool_output_context
                )
                persona_prompts.append(system_prompt)

                # Create a client for this persona with three-tier precedence:
                # 1) User override from persona_provider_overrides
                # 2) Persona's configured model_config
                # 3) Default provider
                if (
                    persona_provider_overrides
                    and persona_value in persona_provider_overrides
                ):
                    logger.info(
                        f"Using provider override for {persona_value}: {persona_provider_overrides[persona_value]}"
                    )
                    persona_client = await create_client_from_provider_id(
                        persona_provider_overrides[persona_value], demo_mode=False
                    )
                elif persona_config.model_config:
                    logger.info(f"Using persona-configured model for {persona_value}")
                    persona_client = create_client_from_persona_config(
                        persona_config, demo_mode=False
                    )
                else:
                    logger.info(f"Using default client for {persona_value}")
                    persona_client = create_client_from_persona_config(
                        persona_config, demo_mode=False
                    )

                persona_clients.append(persona_client)
            else:
                logger.warning(f"Skipping unknown persona: {persona_value}")

        # Use parallel generation if pool is available or if personas have custom models
        has_custom_models = any(
            config.model_config is not None
            or (persona_provider_overrides and value in persona_provider_overrides)
            for value, config in persona_configs
        )

        # Check default provider parallel settings
        parallel_enabled = False
        max_parallel = 2

        storage = get_provider_storage()
        default_provider = await storage.get_default()
        if default_provider:
            parallel_enabled = default_provider.parallel_requests_enabled
            max_parallel = default_provider.max_parallel_requests

        should_run_parallel = self.use_pool or has_custom_models or parallel_enabled

        if should_run_parallel:
            # Determine concurrency limit
            concurrency_limit = total_personas
            if parallel_enabled and not self.use_pool and not has_custom_models:
                concurrency_limit = max_parallel

            logger.info(
                "Using parallel generation for persona perspectives",
                persona_count=total_personas,
                has_custom_models=has_custom_models,
                provider_parallel_enabled=parallel_enabled,
                concurrency_limit=concurrency_limit,
            )

            semaphore = asyncio.Semaphore(concurrency_limit)

            # Create tasks with indices for parallel execution with progress tracking
            async def generate_with_index(
                idx: int, prompt_text: str, client: LlamaCppClient
            ) -> tuple[int, str]:
                """Generate response and return with index for ordering."""
                try:
                    async with semaphore:
                        async with client:
                            response = await client.generate(
                                prompt=prompt_text, temperature=0.7, num_predict=2000
                            )
                    return (idx, response)
                except Exception as e:
                    logger.warning(
                        "Failed to generate perspective in parallel",
                        persona=personas[idx],
                        error=str(e),
                    )
                    return (idx, "")

            tasks = [
                generate_with_index(idx, prompt_text, client)
                for idx, (prompt_text, client) in enumerate(
                    zip(persona_prompts, persona_clients)
                )
            ]

            # Execute with progress tracking as each completes
            responses = [None] * total_personas
            completed_count = 0

            for coro in asyncio.as_completed(tasks):
                idx, response = await coro
                responses[idx] = response
                completed_count += 1

                if progress_callback:
                    in_progress = total_personas - completed_count
                    persona_name = personas[idx].replace("_", " ").title()

                    if in_progress > 0:
                        progress_callback(
                            f"✓ {persona_name} completed ({completed_count}/{total_personas}), "
                            f"{in_progress} in progress"
                        )
                    else:
                        progress_callback(
                            f"✓ All {total_personas} persona perspectives completed"
                        )
        else:
            # Sequential generation with single client
            logger.info(
                "Using sequential generation for persona perspectives",
                persona_count=total_personas,
            )
            responses = []
            for index, (system_prompt, client) in enumerate(
                zip(persona_prompts, persona_clients), 1
            ):
                try:
                    if progress_callback:
                        progress_callback(
                            f"Generating perspective {index}/{total_personas}: {personas[index-1].replace('_', ' ').title()}"
                        )

                    async with client:
                        response = await client.generate(
                            prompt=system_prompt, temperature=0.7, num_predict=2000
                        )
                    responses.append(response)
                except Exception as e:
                    logger.warning(
                        "Failed to generate perspective for persona",
                        persona=personas[index - 1],
                        error=str(e),
                    )
                    responses.append("")

        # Parse all responses and store original prompt
        synthesis_inputs = []
        for (persona_value, persona_config), response, system_prompt in zip(
            persona_configs, responses, persona_prompts
        ):
            if not response:
                continue

            try:
                perspective_data = self._parse_persona_response(response)
                if perspective_data:
                    synthesis_input = PersonaSynthesisInput(
                        persona=persona_value,
                        original_prompt_text=system_prompt,  # Store the full prompt used
                        **perspective_data,
                    )
                    synthesis_inputs.append(synthesis_input)
            except Exception as e:
                logger.warning(
                    "Failed to parse perspective response",
                    persona=persona_value,
                    error=str(e),
                )

        return synthesis_inputs

    def _create_persona_generation_prompt(
        self,
        persona_config: PersonaConfig,
        prompt: ADRGenerationPrompt,
        related_context: List[str],
        tool_output_context: str = "",
    ) -> str:
        """Create a generation prompt for a specific persona.

        Args:
            persona_config: Configuration for the persona
            prompt: The generation prompt
            related_context: Related context strings
            tool_output_context: Formatted output from MCP tools

        Returns:
            Formatted prompt string
        """
        context_str = (
            "\n".join([f"- {ctx}" for ctx in related_context])
            if related_context
            else "No related context available."
        )

        constraints_str = (
            "\n".join([f"- {c}" for c in (prompt.constraints or [])])
            if prompt.constraints
            else "None specified."
        )
        stakeholders_str = (
            "\n".join([f"- {s}" for s in (prompt.stakeholders or [])])
            if prompt.stakeholders
            else "None specified."
        )

        # Format tool output section
        tool_output_section = ""
        if tool_output_context:
            tool_output_section = f"""**Research from External Tools**:
{tool_output_context}"""

        if prompt.record_type == RecordType.PRINCIPLE:
            return PRINCIPLE_PERSONA_GENERATION_SYSTEM_PROMPT.format(
                persona_name=persona_config.name,
                persona_description=persona_config.description,
                focus_areas=", ".join(persona_config.focus_areas),
                evaluation_criteria=", ".join(persona_config.evaluation_criteria),
                problem_statement=prompt.problem_statement,
                context=prompt.context,
                constraints=constraints_str,
                stakeholders=stakeholders_str,
                related_context=context_str,
                tool_output_section=tool_output_section,
            )

        # Build the prompt with optional tool output section
        tool_section = ""
        if tool_output_context:
            tool_section = f"""
**Research from External Tools**:
{tool_output_context}
"""

        return f"""You are a {persona_config.name} analyzing a decision that needs to be made.

**Your Role**: {persona_config.description}
**Focus Areas**: {', '.join(persona_config.focus_areas)}
**Evaluation Criteria**: {', '.join(persona_config.evaluation_criteria)}

**Problem Statement**:
{prompt.problem_statement}

**Decision Context**:
{prompt.context}

**Constraints**:
{constraints_str}

**Key Stakeholders**:
{stakeholders_str}
{tool_section}
**Related Context from Previous Decisions**:
{context_str}

Based on your expertise, provide your perspective on this decision. You must respond with a JSON object containing:

{{
  "perspective": "Your overall perspective on the decision (2-3 sentences)",
  "recommended_option": "The option you would recommend (or null if you need more information)",
  "reasoning": "Detailed reasoning for your recommendation (3-5 sentences)",
  "concerns": ["List", "of", "key", "concerns", "you", "have"],
  "requirements": ["List", "of", "requirements", "that", "must", "be", "met"]
}}

Ensure your response is practical, considers the constraints, and reflects your area of expertise."""

    def _parse_persona_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from persona generation.

        Args:
            response: Raw response from LLM

        Returns:
            Parsed response data or None if parsing failed
        """
        try:
            # Try to extract JSON from response
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                parsed = json.loads(json_str)

                # Validate required fields
                if "proposed_principle" in parsed:
                    # Principle generation response
                    required_fields = [
                        "perspective",
                        "proposed_principle",
                        "rationale",
                    ]
                else:
                    # Standard ADR generation response
                    required_fields = [
                        "perspective",
                        "reasoning",
                        "concerns",
                        "requirements",
                    ]
                missing_fields = [f for f in required_fields if f not in parsed]

                if missing_fields:
                    logger.warning(
                        "Parsed JSON missing required fields",
                        missing_fields=missing_fields,
                        available_fields=list(parsed.keys()),
                    )
                    return None

                return parsed
        except json.JSONDecodeError as e:
            logger.warning(
                "JSON decode error in persona response",
                error=str(e),
                response_preview=response[:500],
            )
        except (ValueError, TypeError) as e:
            logger.warning(
                "Error parsing persona response",
                error_type=type(e).__name__,
                error=str(e),
                response_preview=response[:200],
            )

        logger.warning(
            "Failed to parse persona response as JSON", response_preview=response[:500]
        )
        return None

    async def _synthesize_adr(
        self,
        prompt: ADRGenerationPrompt,
        synthesis_inputs: List[PersonaSynthesisInput],
        related_context: List[str],
        referenced_adr_info: List[Dict[str, str]],
        progress_callback: Optional[callable] = None,
        tool_output_context: str = "",
        synthesis_provider_id: Optional[str] = None,
    ) -> ADRGenerationResult:
        """Synthesize all persona perspectives into a complete ADR.

        Args:
            prompt: Original generation prompt
            synthesis_inputs: Perspectives from all personas
            related_context: Related context from vector DB
            referenced_adr_info: Info about ADRs referenced during generation (id, title, summary)
            progress_callback: Optional callback for progress updates
            tool_output_context: Formatted output from MCP tools
            synthesis_provider_id: Optional provider ID to use for synthesis (overrides default client)

        Returns:
            Complete ADR generation result
        """
        # Create synthesis prompt
        synthesis_prompt = self._create_synthesis_prompt(
            prompt, synthesis_inputs, related_context, tool_output_context
        )

        try:
            # Generate synthesized ADR
            # Use synthesis_provider_id if provided, otherwise use default client
            if synthesis_provider_id:
                # Create a dedicated client for synthesis
                synthesis_client = await create_client_from_provider_id(
                    synthesis_provider_id
                )
                async with synthesis_client:
                    response = await synthesis_client.generate(
                        prompt=synthesis_prompt,
                        temperature=0.3,  # Lower temperature for more consistent synthesis
                        num_predict=3000,
                    )
            elif self.use_pool:
                client = self.llama_client.get_generation_client(0)
                response = await client.generate(
                    prompt=synthesis_prompt,
                    temperature=0.3,  # Lower temperature for more consistent synthesis
                    num_predict=3000,
                )
            else:
                async with self.llama_client:
                    response = await self.llama_client.generate(
                        prompt=synthesis_prompt,
                        temperature=0.3,  # Lower temperature for more consistent synthesis
                        num_predict=3000,
                    )

            # Parse synthesis response
            synthesis_data = self._parse_synthesis_response(response)

            if synthesis_data:
                # Get title and remove "ADR:" prefix if present
                title = synthesis_data.get("title", prompt.title)
                if title.upper().startswith("ADR:"):
                    title = title[4:].strip()

                # Validate and cleanup the synthesis data
                synthesis_data, sections_to_polish = (
                    self._validate_and_cleanup_synthesis_data(synthesis_data)
                )

                # Extract text fields
                context_and_problem = synthesis_data.get("context_and_problem", "")
                decision_outcome = synthesis_data.get("decision_outcome", "")
                consequences = synthesis_data.get("consequences", "")

                # Only polish sections that need it
                sections_needing_polish = [
                    field
                    for field, needs_polish in sections_to_polish.items()
                    if needs_polish
                ]

                if sections_needing_polish:
                    logger.info(
                        "Formatting issues detected, running polishing step",
                        sections=sections_needing_polish,
                    )

                    # Build list of sections to polish with their display names
                    section_map = {
                        "context_and_problem": (
                            "Context & Problem",
                            context_and_problem,
                        ),
                        "decision_outcome": ("Decision Outcome", decision_outcome),
                        "consequences": ("Consequences", consequences),
                    }

                    sections_to_process = [
                        (section_map[field][0], section_map[field][1], field)
                        for field in sections_needing_polish
                    ]

                    total_sections = len(sections_to_process)

                    if progress_callback:
                        progress_callback(
                            f"Polishing formatting ({total_sections} section{'s' if total_sections > 1 else ''})..."
                        )

                    # Polish sections in parallel if pool is available
                    if self.use_pool and total_sections > 1:
                        # Track completion count for progress updates
                        completed_sections = {"count": 0}

                        # Create polishing tasks with section names for progress tracking
                        async def polish_with_name(
                            section_name: str, text: str, field_name: str
                        ) -> tuple[str, str]:
                            """Polish text and return with field name for mapping."""
                            result = await self._polish_formatting(text)
                            completed_sections["count"] += 1
                            if progress_callback:
                                in_progress = (
                                    total_sections - completed_sections["count"]
                                )
                                if in_progress > 0:
                                    progress_callback(
                                        f"✓ {section_name} completed ({completed_sections['count']}/{total_sections}), "
                                        f"{in_progress} in progress"
                                    )
                                else:
                                    progress_callback(
                                        f"✓ All {total_sections} sections polished"
                                    )
                            return (field_name, result)

                        tasks = [
                            polish_with_name(name, text, field)
                            for name, text, field in sections_to_process
                        ]

                        results = await asyncio.gather(*tasks)

                        # Update the fields that were polished
                        for field_name, polished_text in results:
                            if field_name == "context_and_problem":
                                context_and_problem = polished_text
                            elif field_name == "decision_outcome":
                                decision_outcome = polished_text
                            elif field_name == "consequences":
                                consequences = polished_text
                    else:
                        # Sequential polishing
                        for idx, (section_name, text, field_name) in enumerate(
                            sections_to_process, 1
                        ):
                            if progress_callback:
                                progress_callback(
                                    f"Polishing {section_name} ({idx}/{total_sections})..."
                                )

                            polished_text = await self._polish_formatting(text)

                            if field_name == "context_and_problem":
                                context_and_problem = polished_text
                            elif field_name == "decision_outcome":
                                decision_outcome = polished_text
                            elif field_name == "consequences":
                                consequences = polished_text
                else:
                    logger.info(
                        "Synthesis data is well-formatted, skipping polishing step"
                    )
                    if progress_callback:
                        progress_callback(
                            "✓ Synthesis data is well-formatted, skipping polishing"
                        )

                # Create ADR generation result
                result = ADRGenerationResult(
                    prompt=prompt,
                    generated_title=title,
                    context_and_problem=context_and_problem,
                    considered_options=synthesis_data.get("considered_options", []),
                    decision_outcome=decision_outcome,
                    consequences=consequences,
                    consequences_structured=synthesis_data.get(
                        "consequences_structured"
                    ),
                    decision_drivers=synthesis_data.get("decision_drivers", []),
                    principle_details=synthesis_data.get("principle_details"),
                    confidence_score=synthesis_data.get("confidence_score"),
                    related_context=related_context,
                    referenced_adrs=referenced_adr_info,
                    personas_used=[p.persona for p in synthesis_inputs],
                    persona_responses=synthesis_inputs,
                    original_prompt_text=prompt.problem_statement,  # Store for refinement
                )
                return result
            else:
                # Fallback: create basic ADR from prompt
                return self._create_fallback_adr(
                    prompt, synthesis_inputs, related_context, referenced_adr_info
                )

        except Exception as e:
            logger.error(
                "Failed to synthesize ADR",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e),
            )
            return self._create_fallback_adr(
                prompt, synthesis_inputs, related_context, referenced_adr_info
            )

    def _create_synthesis_prompt(
        self,
        prompt: ADRGenerationPrompt,
        synthesis_inputs: List[PersonaSynthesisInput],
        related_context: List[str],
        tool_output_context: str = "",
    ) -> str:
        """Create synthesis prompt for combining persona perspectives.

        Args:
            prompt: Original generation prompt
            synthesis_inputs: Perspectives from all personas
            related_context: Related context
            tool_output_context: Formatted output from MCP tools

        Returns:
            Synthesis prompt string
        """
        perspectives_str = "\n\n".join(
            [
                f"**{p.persona.replace('_', ' ').title()}**:\n"
                f"Perspective: {p.perspective}\n"
                f"Recommended Option: {p.recommended_option or 'None'}\n"
                f"Reasoning: {p.reasoning}\n"
                f"Concerns: {', '.join(p.concerns)}\n"
                f"Requirements: {', '.join(p.requirements)}"
                for p in synthesis_inputs
            ]
        )

        related_context_str = (
            "\n".join(related_context) if related_context else "None available"
        )

        # Format tool output section
        tool_output_section = ""
        if tool_output_context:
            tool_output_section = f"""**Research from External Tools**:
{tool_output_context}"""

        system_prompt = (
            PRINCIPLE_SYNTHESIS_SYSTEM_PROMPT
            if prompt.record_type == RecordType.PRINCIPLE
            else ADR_SYNTHESIS_SYSTEM_PROMPT
        )

        return system_prompt.format(
            title=prompt.title,
            problem_statement=prompt.problem_statement,
            context=prompt.context,
            perspectives_str=perspectives_str,
            related_context_str=related_context_str,
            tool_output_section=tool_output_section,
        )

    def _clean_list_items(self, items: List[str]) -> List[str]:
        """Clean up list items that may have concatenated bullet points.

        Args:
            items: List of strings that may contain concatenated items

        Returns:
            Cleaned list with split items
        """
        import re

        cleaned = []
        for item in items:
            # Check if item contains bullet markers (-, •, *) that indicate concatenation
            if re.search(r"[-•*]\s+\w+.*[-•*]\s+\w+", item):
                # Split on bullet markers
                parts = re.split(r"\s*[-•*]\s+", item)
                # Filter out empty parts and add non-empty ones
                for part in parts:
                    part = part.strip()
                    if part:
                        cleaned.append(part)
            else:
                # Just clean up the single item
                item = item.strip()
                # Remove leading bullet markers if present
                item = re.sub(r"^[-•*]\s+", "", item)
                # Also remove trailing bullet markers and extra whitespace
                item = item.strip()
                # Skip if empty or only contains bullet markers
                if item and not re.match(r"^[-•*\s]+$", item):
                    cleaned.append(item)

        return cleaned

    def _validate_and_cleanup_synthesis_data(
        self, data: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, bool]]:
        """Validate synthesis data and clean up common formatting issues.

        Args:
            data: Parsed synthesis data

        Returns:
            Tuple of (cleaned data, dict of section names to polish)
            The dict keys are: 'context_and_problem', 'decision_outcome', 'consequences'
        """
        sections_to_polish = {
            "context_and_problem": False,
            "decision_outcome": False,
            "consequences": False,
        }

        # Clean up options pros/cons
        if "considered_options" in data:
            for opt in data["considered_options"]:
                if isinstance(opt, ADRGenerationOptions):
                    # Check if pros/cons have concatenated items
                    original_pros_count = len(opt.pros)
                    original_cons_count = len(opt.cons)

                    opt.pros = self._clean_list_items(opt.pros)
                    opt.cons = self._clean_list_items(opt.cons)

                    # If we split items, log it
                    if (
                        len(opt.pros) != original_pros_count
                        or len(opt.cons) != original_cons_count
                    ):
                        logger.info(
                            "Cleaned up concatenated pros/cons",
                            option=opt.option_name,
                            original_pros=original_pros_count,
                            cleaned_pros=len(opt.pros),
                            original_cons=original_cons_count,
                            cleaned_cons=len(opt.cons),
                        )

        # Check if text fields need polishing (have line breaks in weird places)
        import re

        # Only check text fields that aren't generated from structured data
        # If consequences_structured exists, skip checking consequences text
        fields_to_check = ["context_and_problem", "decision_outcome"]
        if "consequences_structured" not in data:
            fields_to_check.append("consequences")

        for field in fields_to_check:
            if field in data and isinstance(data[field], str):
                text = data[field]
                # Check for common formatting issues:
                # 1. Words split across lines (not after punctuation or bullets)
                # 2. Non-breaking hyphens
                # 3. Multiple consecutive spaces
                if (
                    re.search(r"[a-zA-Z]\n[a-zA-Z]", text)  # Word split across lines
                    or "  " in text  # Multiple spaces
                ):
                    sections_to_polish[field] = True
                    logger.info(
                        "Detected formatting issues in field",
                        field=field,
                        has_line_breaks=bool(re.search(r"[a-zA-Z]\n[a-zA-Z]", text)),
                        has_multiple_spaces=("  " in text),
                    )

        return data, sections_to_polish

    def _parse_synthesis_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse JSON response from ADR synthesis.

        Args:
            response: Raw response from LLM

        Returns:
            Parsed synthesis data or None if parsing failed
        """
        try:
            # Try to extract JSON from response
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)

                # Handle principle details
                if "principle_details" in data:
                    # Ensure lists are cleaned
                    pd = data["principle_details"]
                    if "counter_arguments" in pd and isinstance(
                        pd["counter_arguments"], list
                    ):
                        pd["counter_arguments"] = self._clean_list_items(
                            pd["counter_arguments"]
                        )
                    if "proof_statements" in pd and isinstance(
                        pd["proof_statements"], list
                    ):
                        pd["proof_statements"] = self._clean_list_items(
                            pd["proof_statements"]
                        )
                    if "implications" in pd and isinstance(pd["implications"], list):
                        pd["implications"] = self._clean_list_items(pd["implications"])
                    if "exceptions" in pd and isinstance(pd["exceptions"], list):
                        pd["exceptions"] = self._clean_list_items(pd["exceptions"])

                # Convert options to proper format
                if "considered_options" in data:
                    options = []
                    for opt in data["considered_options"]:
                        if isinstance(opt, dict):
                            # Clean up pros/cons before creating the object
                            if "pros" in opt and isinstance(opt["pros"], list):
                                opt["pros"] = self._clean_list_items(opt["pros"])
                            if "cons" in opt and isinstance(opt["cons"], list):
                                opt["cons"] = self._clean_list_items(opt["cons"])

                            options.append(ADRGenerationOptions(**opt))
                        else:
                            # Handle string options
                            options.append(
                                ADRGenerationOptions(
                                    option_name=str(opt),
                                    description=str(opt),
                                    pros=[],
                                    cons=[],
                                )
                            )
                    data["considered_options"] = options

                # Handle consequences if it's a dict with positive/negative keys
                if "consequences" in data and isinstance(data["consequences"], dict):
                    cons_dict = data["consequences"]
                    positive = cons_dict.get("positive", [])
                    negative = cons_dict.get("negative", [])

                    # Clean the positive/negative lists
                    if isinstance(positive, list):
                        positive = self._clean_list_items(positive)
                    if isinstance(negative, list):
                        negative = self._clean_list_items(negative)

                    # Store the structured version for later use
                    data["consequences_structured"] = {
                        "positive": positive,
                        "negative": negative,
                    }

                    # Also create a text version for backwards compatibility
                    consequences_parts = []
                    if positive:
                        consequences_parts.append("Positive: " + ", ".join(positive))
                    if negative:
                        consequences_parts.append("Negative: " + ", ".join(negative))

                    data["consequences"] = (
                        "\n".join(consequences_parts)
                        if consequences_parts
                        else "No consequences identified."
                    )
                elif "consequences" in data and isinstance(data["consequences"], str):
                    # If it's already a string, keep it as is (fallback for old format)
                    # Don't create consequences_structured in this case
                    pass

                return data
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning(
                "Failed to parse synthesis response",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e),
                response_preview=response[:200],
            )

        return None

    async def _polish_formatting(self, text: str) -> str:
        """Polish the formatting of an ADR section.

        Args:
            text: The text to polish

        Returns:
            Polished text with better formatting
        """
        if not text or len(text.strip()) < 10:
            return text

        polish_prompt = f"""Polish the formatting of the following text for a Decision Record.

**CRITICAL FORMATTING RULES**:
1. Each bullet point should be on its own line starting with "- "
2. Fix line breaks: if words are split across lines (like "GPU\\nRAM"), combine them with proper spacing or punctuation
3. Replace non-breaking hyphens (‑) with regular hyphens (-)
4. Ensure proper spacing after commas and periods
5. Remove excessive whitespace
6. Keep all content EXACTLY the same - only fix formatting issues
7. Do NOT add or remove any information
8. Do NOT change the meaning

**EXAMPLES OF FIXES**:
- Bad: "future GPU\\nRAM\\nor storage" → Good: "future GPU, RAM, or storage"
- Bad: "cooling\\npower delivery\\nand noise" → Good: "cooling, power delivery, and noise"
- Bad: "unsuitable‑for" → Good: "unsuitable for"

**TEXT TO POLISH**:
{text}

**POLISHED TEXT**:"""

        try:
            # Use primary client for polishing
            if self.use_pool:
                client = self.llama_client.get_generation_client(0)
                polished = await client.generate(
                    prompt=polish_prompt,
                    temperature=0.1,  # Very low temperature for consistent formatting
                    num_predict=2000,
                )
            else:
                async with self.llama_client:
                    polished = await self.llama_client.generate(
                        prompt=polish_prompt,
                        temperature=0.1,  # Very low temperature for consistent formatting
                        num_predict=2000,
                    )

            # Clean up the response - remove any markdown formatting or extra whitespace
            polished = polished.strip()

            # If the LLM added any preamble, try to extract just the content
            if polished.startswith("**POLISHED TEXT**:"):
                polished = polished[18:].strip()
            elif polished.startswith("POLISHED TEXT:"):
                polished = polished[14:].strip()

            # Apply programmatic cleanup as a backup
            polished = self._apply_formatting_cleanup(polished)

            # If polishing failed or made it worse, return original
            if len(polished) < len(text) * 0.5 or len(polished) > len(text) * 2:
                logger.warning("Polishing produced unexpected length, using original")
                return self._apply_formatting_cleanup(text)

            return polished

        except Exception as e:
            logger.warning(
                "Failed to polish formatting, using original",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            return self._apply_formatting_cleanup(text)

    def _apply_formatting_cleanup(self, text: str) -> str:
        """Apply programmatic formatting cleanup to text.

        Args:
            text: The text to clean up

        Returns:
            Cleaned up text
        """
        import re

        # Replace non-breaking hyphens with regular hyphens
        text = text.replace("‑", "-")

        # Fix line breaks in the middle of phrases that aren't bullet points
        # Pattern: word\nword (not after punctuation or bullet markers)
        # Replace with word, word or word word depending on context
        lines = text.split("\n")
        cleaned_lines = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            # If this is a bullet line (starts with -)
            if line.startswith("-"):
                # Check if next lines continue this bullet (don't start with -)
                bullet_parts = [line[1:].strip()]  # Remove the leading dash
                i += 1

                while i < len(lines):
                    next_line = lines[i].strip()
                    # If next line doesn't start with -, •, ✓, ✗, or common headers, it's a continuation
                    if next_line and not next_line.startswith(
                        ("-", "•", "✓", "✗", "Positive:", "Negative:")
                    ):
                        bullet_parts.append(next_line)
                        i += 1
                    else:
                        break

                # Join the bullet parts with commas or spaces
                combined = " ".join(bullet_parts)
                cleaned_lines.append(f"- {combined}")
            else:
                cleaned_lines.append(line)
                i += 1

        text = "\n".join(cleaned_lines)

        # Fix multiple spaces
        text = re.sub(r"  +", " ", text)

        # Fix space before punctuation
        text = re.sub(r" +([,.])", r"\1", text)

        # Ensure space after punctuation
        text = re.sub(r"([,.:])([a-zA-Z])", r"\1 \2", text)

        # Clean up extra blank lines (more than 2 consecutive)
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove empty lines
        text = "\n".join(line for line in text.split("\n") if line.strip())

        return text.strip()

    def _create_fallback_adr(
        self,
        prompt: ADRGenerationPrompt,
        synthesis_inputs: List[PersonaSynthesisInput],
        related_context: List[str],
        referenced_adr_info: List[Dict[str, str]],
    ) -> ADRGenerationResult:
        """Create a basic ADR when synthesis fails.

        Args:
            prompt: Original generation prompt
            synthesis_inputs: Perspectives from personas
            related_context: Related context
            referenced_adr_info: Info about ADRs referenced during generation

        Returns:
            Basic ADR generation result
        """
        # Extract recommended options from personas
        recommended_options = []
        for p in synthesis_inputs:
            if p.recommended_option:
                recommended_options.append(p.recommended_option)

        # Create basic options
        options = []
        if recommended_options:
            for i, opt in enumerate(set(recommended_options)):
                options.append(
                    ADRGenerationOptions(
                        option_name=f"Option {i+1}: {opt}",
                        description=f"Recommended by experts: {opt}",
                        pros=["Recommended by domain experts"],
                        cons=["May have unconsidered drawbacks"],
                    )
                )
        else:
            options.append(
                ADRGenerationOptions(
                    option_name="Recommended Approach",
                    description="To be determined based on expert analysis",
                    pros=["Based on expert input"],
                    cons=["Requires further analysis"],
                )
            )

        # Combine concerns and requirements
        all_concerns = []
        all_requirements = []
        for p in synthesis_inputs:
            all_concerns.extend(p.concerns)
            all_requirements.extend(p.requirements)

        consequences = f"Positive: Addresses key requirements including {', '.join(all_requirements[:3])}\n"
        consequences += (
            f"Negative: Must address concerns including {', '.join(all_concerns[:3])}"
        )

        return ADRGenerationResult(
            prompt=prompt,
            generated_title=prompt.title,
            context_and_problem=f"{prompt.context}\n\n{prompt.problem_statement}",
            considered_options=options,
            decision_outcome="Decision to be made based on comprehensive analysis",
            consequences=consequences,
            decision_drivers=list(set(all_requirements)),
            confidence_score=0.5,  # Low confidence for fallback
            related_context=related_context,
            referenced_adrs=referenced_adr_info,
            personas_used=[p.persona for p in synthesis_inputs],
        )

    def convert_to_adr(
        self, generation_result: ADRGenerationResult, author: Optional[str] = None
    ) -> ADR:
        """Convert a generation result to a complete ADR object.

        Args:
            generation_result: The generation result to convert
            author: Author of the ADR

        Returns:
            Complete ADR object
        """
        from src.models import OptionDetails

        # Convert options to string list
        options_list = [opt.option_name for opt in generation_result.considered_options]

        # Convert options to detailed format with pros/cons
        options_details = []
        for opt in generation_result.considered_options:
            options_details.append(
                OptionDetails(
                    name=opt.option_name,
                    description=opt.description,
                    pros=opt.pros,
                    cons=opt.cons,
                )
            )

        # Create ADR content
        content = ADRContent(
            context_and_problem=generation_result.context_and_problem,
            considered_options=options_list,
            decision_outcome=generation_result.decision_outcome,
            consequences=generation_result.consequences,
            decision_drivers=generation_result.decision_drivers,
            options_details=options_details,
            referenced_adrs=generation_result.referenced_adrs,
        )

        # Create ADR metadata
        metadata = ADRMetadata(
            title=generation_result.generated_title,
            author=author,
            tags=generation_result.prompt.tags or [],
            record_type=generation_result.prompt.record_type,
        )

        return ADR(metadata=metadata, content=content)

    def validate_generation_result(self, result: ADRGenerationResult) -> Dict[str, Any]:
        """Validate the quality of a generated ADR result.

        Args:
            result: The generation result to validate

        Returns:
            Validation results with scores and issues
        """
        validation = {
            "overall_score": 0.0,
            "issues": [],
            "warnings": [],
            "strengths": [],
        }

        # Check title quality
        if len(result.generated_title.strip()) < 10:
            validation["issues"].append("Title is too short")
        elif len(result.generated_title.strip()) > 100:
            validation["warnings"].append("Title is very long")
        else:
            validation["strengths"].append("Title length is appropriate")
            validation["overall_score"] += 0.1

        # Check context and problem
        if len(result.context_and_problem.strip()) < 50:
            validation["issues"].append("Context and problem statement is too brief")
        elif len(result.context_and_problem.strip()) > 1000:
            validation["warnings"].append("Context and problem statement is very long")
        else:
            validation["strengths"].append(
                "Context and problem statement length is appropriate"
            )
            validation["overall_score"] += 0.2

        # Check decision outcome
        if len(result.decision_outcome.strip()) < 20:
            validation["issues"].append("Decision outcome is too brief")
        else:
            validation["strengths"].append("Decision outcome is sufficiently detailed")
            validation["overall_score"] += 0.2

        # Check consequences
        if len(result.consequences.strip()) < 20:
            validation["issues"].append("Consequences section is too brief")
        else:
            validation["strengths"].append("Consequences are adequately described")
            validation["overall_score"] += 0.15

        # Check considered options
        if len(result.considered_options) < 2:
            validation["warnings"].append("Few options were considered")
        elif len(result.considered_options) >= 3:
            validation["strengths"].append("Multiple options were properly considered")
            validation["overall_score"] += 0.15

        # Check decision drivers
        if not result.decision_drivers or len(result.decision_drivers) == 0:
            validation["issues"].append("No decision drivers specified")
        elif len(result.decision_drivers) >= 3:
            validation["strengths"].append("Multiple decision drivers identified")
            validation["overall_score"] += 0.1

        # Check personas used
        if not result.personas_used or len(result.personas_used) == 0:
            validation["issues"].append("No personas were involved in generation")
        elif len(result.personas_used) >= 3:
            validation["strengths"].append(
                "Multiple personas contributed to the analysis"
            )
            validation["overall_score"] += 0.1

        # Check confidence score
        if result.confidence_score is None:
            validation["warnings"].append("No confidence score provided")
        elif result.confidence_score < 0.5:
            validation["warnings"].append("Low confidence in generated ADR")
        elif result.confidence_score >= 0.8:
            validation["strengths"].append("High confidence in generated ADR")
            validation["overall_score"] += 0.1

        # Overall assessment
        if validation["overall_score"] >= 0.8:
            validation["assessment"] = "Excellent"
        elif validation["overall_score"] >= 0.6:
            validation["assessment"] = "Good"
        elif validation["overall_score"] >= 0.4:
            validation["assessment"] = "Acceptable"
        else:
            validation["assessment"] = "Needs improvement"

        return validation
