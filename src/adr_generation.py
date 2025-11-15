"""ADR Generation Service for creating new ADRs from prompts."""

import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, UTC

from src.models import (
    ADR,
    ADRMetadata,
    ADRContent,
    ADRGenerationPrompt,
    ADRGenerationResult,
    ADRGenerationOptions,
    PersonaSynthesisInput,
)
from src.persona_manager import PersonaManager, PersonaConfig
from src.llama_client import (
    LlamaCppClient,
    LlamaCppClientPool,
    create_client_from_persona_config,
)
from src.lightrag_client import LightRAGClient
from src.logger import get_logger

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
    ) -> ADRGenerationResult:
        """Generate a new ADR from a prompt using multiple personas.

        Args:
            prompt: The generation prompt with context and requirements
            personas: List of persona values (e.g., ['technical_lead', 'architect'])
            include_context: Whether to retrieve related context from vector DB
            progress_callback: Optional callback function for progress updates

        Returns:
            ADRGenerationResult: The generated ADR with all components
        """
        logger.info(
            "Starting ADR generation", title=prompt.title, personas=personas or []
        )

        # Default personas if none specified
        if not personas:
            personas = ["technical_lead", "business_analyst", "architect"]

        # Retrieve related context if requested
        related_context = []
        referenced_adr_info = []
        if include_context:
            if progress_callback:
                progress_callback("Retrieving related context...")
            related_context, referenced_adr_info = await self._get_related_context(
                prompt
            )

        # Generate perspectives from each persona
        synthesis_inputs = await self._generate_persona_perspectives(
            prompt, personas, related_context, progress_callback
        )

        # Synthesize all perspectives into final ADR
        if progress_callback:
            progress_callback("Synthesizing perspectives into final ADR...")
        result = await self._synthesize_adr(
            prompt,
            synthesis_inputs,
            related_context,
            referenced_adr_info,
            progress_callback,
        )

        logger.info(
            "ADR generation completed",
            title=result.generated_title,
            confidence=result.confidence_score,
            personas_used=result.personas_used
        )

        return result

    async def _get_related_context(
        self, prompt: ADRGenerationPrompt
    ) -> tuple[List[str], List[Dict[str, str]]]:
        """Retrieve related ADRs from vector database.

        Args:
            prompt: The generation prompt

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

            related_context.append("**Related Architectural Decision Records (ADRs):**")
            for doc in documents:
                # Extract structured data if available (entities and relationships)
                if "structured_data" in doc:
                    structured = doc["structured_data"]
                    if "entities" in structured:
                        all_entities.extend(structured["entities"])
                    if "relationships" in structured:
                        all_relationships.extend(structured["relationships"])

                # Track the ADR info with ID, title, and summary
                # Skip the generic "context" document from being listed as a referenced ADR
                doc_id = doc.get("id", "unknown")
                if doc_id == "context":
                    # This is the generic query response, not a specific ADR
                    continue

                doc_title = doc.get("title", doc_id)
                doc_content = doc.get("content", "")

                # Add the document content as context
                if doc_content:
                    related_context.append(f"**{doc_title}**:\n{doc_content}")

                # Create a 60-character summary
                summary = doc_content[:60]
                if len(doc_content) > 60:
                    summary += "..."

                referenced_adr_info.append(
                    {"id": doc_id, "title": doc_title, "summary": summary}
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

    async def _generate_persona_perspectives(
        self,
        prompt: ADRGenerationPrompt,
        personas: List[str],
        related_context: List[str],
        progress_callback: Optional[callable] = None,
    ) -> List[PersonaSynthesisInput]:
        """Generate perspectives from each persona.

        Args:
            prompt: The generation prompt
            personas: List of persona values to generate perspectives for
            related_context: Related context from vector DB
            progress_callback: Optional callback for progress updates

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
                    persona_config, prompt, related_context
                )
                persona_prompts.append(system_prompt)

                # Create a client for this persona with its specific model config
                persona_client = create_client_from_persona_config(
                    persona_config, demo_mode=False
                )
                persona_clients.append(persona_client)
            else:
                logger.warning(f"Skipping unknown persona: {persona_value}")

        # Use parallel generation if pool is available or if personas have custom models
        has_custom_models = any(
            config.model_config is not None for _, config in persona_configs
        )

        if self.use_pool or has_custom_models:
            logger.info(
                "Using parallel generation for persona perspectives",
                persona_count=total_personas,
                has_custom_models=has_custom_models,
            )

            # Create tasks with indices for parallel execution with progress tracking
            async def generate_with_index(
                idx: int, prompt_text: str, client: LlamaCppClient
            ) -> tuple[int, str]:
                """Generate response and return with index for ordering."""
                try:
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

        # Parse all responses
        synthesis_inputs = []
        for (persona_value, _), response in zip(persona_configs, responses):
            if not response:
                continue

            try:
                perspective_data = self._parse_persona_response(response)
                if perspective_data:
                    synthesis_input = PersonaSynthesisInput(
                        persona=persona_value, **perspective_data
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
        related_context: List[str]
    ) -> str:
        """Create a generation prompt for a specific persona.

        Args:
            persona_config: Configuration for the persona
            prompt: The generation prompt
            related_context: Related context strings

        Returns:
            Formatted prompt string
        """
        context_str = "\n".join([f"- {ctx}" for ctx in related_context]) if related_context else "No related context available."

        constraints_str = "\n".join([f"- {c}" for c in (prompt.constraints or [])]) if prompt.constraints else "None specified."
        stakeholders_str = "\n".join([f"- {s}" for s in (prompt.stakeholders or [])]) if prompt.stakeholders else "None specified."

        return f"""You are a {persona_config.name} analyzing a decision that needs to be made.

**Your Role**: {persona_config.description}
**Focus Areas**: {', '.join(persona_config.focus_areas)}
**Evaluation Criteria**: {', '.join(persona_config.evaluation_criteria)}

**Decision Context**:
{prompt.context}

**Problem Statement**:
{prompt.problem_statement}

**Constraints**:
{constraints_str}

**Key Stakeholders**:
{stakeholders_str}

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
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            pass

        logger.warning("Failed to parse persona response as JSON", response_preview=response[:200])
        return None

    async def _synthesize_adr(
        self,
        prompt: ADRGenerationPrompt,
        synthesis_inputs: List[PersonaSynthesisInput],
        related_context: List[str],
        referenced_adr_info: List[Dict[str, str]],
        progress_callback: Optional[callable] = None,
    ) -> ADRGenerationResult:
        """Synthesize all persona perspectives into a complete ADR.

        Args:
            prompt: Original generation prompt
            synthesis_inputs: Perspectives from all personas
            related_context: Related context from vector DB
            referenced_adr_info: Info about ADRs referenced during generation (id, title, summary)
            progress_callback: Optional callback for progress updates

        Returns:
            Complete ADR generation result
        """
        # Create synthesis prompt
        synthesis_prompt = self._create_synthesis_prompt(prompt, synthesis_inputs, related_context)

        try:
            # Generate synthesized ADR
            # Use primary client for synthesis
            if self.use_pool:
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
                    confidence_score=synthesis_data.get("confidence_score"),
                    related_context=related_context,
                    referenced_adrs=referenced_adr_info,
                    personas_used=[p.persona for p in synthesis_inputs],
                    persona_responses=synthesis_inputs,
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
        related_context: List[str]
    ) -> str:
        """Create synthesis prompt for combining persona perspectives.

        Args:
            prompt: Original generation prompt
            synthesis_inputs: Perspectives from all personas
            related_context: Related context

        Returns:
            Synthesis prompt string
        """
        perspectives_str = "\n\n".join([
            f"**{p.persona.replace('_', ' ').title()}**:\n"
            f"Perspective: {p.perspective}\n"
            f"Recommended Option: {p.recommended_option or 'None'}\n"
            f"Reasoning: {p.reasoning}\n"
            f"Concerns: {', '.join(p.concerns)}\n"
            f"Requirements: {', '.join(p.requirements)}"
            for p in synthesis_inputs
        ])

        return f"""You are synthesizing multiple expert perspectives into a comprehensive Architectural Decision Record (ADR).

**Original Request**:
Title: {prompt.title}
Context: {prompt.context}
Problem: {prompt.problem_statement}

**Expert Perspectives**:
{perspectives_str}

>>>>>Related Context>>>>>
{chr(10).join(related_context) if related_context else "None available"}
<<<<<End Related Context<<<<<

Based on these perspectives, create a complete ADR. You must respond with a JSON object containing:

{{
  "title": "Clear, descriptive ADR title",
  "context_and_problem": "Comprehensive context and problem statement",
  "considered_options": [
    {{
      "option_name": "Name of option 1",
      "description": "Description of option 1",
      "pros": ["pro 1", "pro 2", "..."],
      "cons": ["con 1", "con 2", "..."]
    }},
    {{
      "option_name": "Name of option 2",
      "description": "Description of option 2",
      "pros": ["pro 1", "pro 2", "..."],
      "cons": ["con 1", "con 2", "..."]
    }}
  ],
  "decision_outcome": "The chosen option and detailed justification",
  "consequences": {{
    "positive": ["positive point", "positive point", "..."],
    "negative": ["negative point", "negative point", "..."]
  }},
  "decision_drivers": ["driver1", "driver2", "driver3"],
  "confidence_score": 0.85
}}

**CRITICAL FORMATTING RULES**:
1. Each item in "pros", "cons", "positive" and "negative" arrays MUST be a single, brief and to the point complete sentence
2. Each array is not limited to only 2-3 items; include all relevant points - ensure only relevant points are included.
3. Do NOT use bullet points (-, •, *) inside array items
4. Do NOT concatenate multiple items into one string
5. Each item should be a separate string in the array
6. The "consequences" field MUST be an object with "positive" and "negative" arrays

Ensure the ADR is well-structured, balanced, and considers all perspectives."""

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
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                data = json.loads(json_str)

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
                            options.append(ADRGenerationOptions(
                                option_name=str(opt),
                                description=str(opt),
                                pros=[],
                                cons=[]
                            ))
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

                    data["consequences"] = "\n".join(consequences_parts) if consequences_parts else "No consequences identified."
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

        polish_prompt = f"""Polish the formatting of the following text for an Architectural Decision Record.

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
                options.append(ADRGenerationOptions(
                    option_name=f"Option {i+1}: {opt}",
                    description=f"Recommended by experts: {opt}",
                    pros=["Recommended by domain experts"],
                    cons=["May have unconsidered drawbacks"]
                ))
        else:
            options.append(ADRGenerationOptions(
                option_name="Recommended Approach",
                description="To be determined based on expert analysis",
                pros=["Based on expert input"],
                cons=["Requires further analysis"]
            ))

        # Combine concerns and requirements
        all_concerns = []
        all_requirements = []
        for p in synthesis_inputs:
            all_concerns.extend(p.concerns)
            all_requirements.extend(p.requirements)

        consequences = f"Positive: Addresses key requirements including {', '.join(all_requirements[:3])}\n"
        consequences += f"Negative: Must address concerns including {', '.join(all_concerns[:3])}"

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

    def convert_to_adr(self, generation_result: ADRGenerationResult, author: Optional[str] = None) -> ADR:
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
            tags=generation_result.prompt.tags or []
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
            "strengths": []
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
            validation["strengths"].append("Context and problem statement length is appropriate")
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
            validation["strengths"].append("Multiple personas contributed to the analysis")
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
