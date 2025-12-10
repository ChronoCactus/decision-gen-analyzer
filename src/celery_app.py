"""Celery task definitions for async job processing."""

import asyncio
import os

from celery import Celery
from celery.schedules import crontab

from src.logger import get_logger

logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "decision_analyzer",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["src.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes
    task_soft_time_limit=480,  # 8 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_disable_rate_limits=False,
    # Fix for slow inspect API - increase broker connection pool
    # See: https://github.com/celery/celery/issues/5139
    broker_pool_limit=100,  # No limit on broker connections
    broker_connection_retry_on_startup=True,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "periodic-reanalysis": {
        "task": "src.tasks.periodic_reanalysis",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
    "refresh-lightrag-cache": {
        "task": "src.celery_app.refresh_lightrag_cache_task",
        "schedule": crontab(hour="*/12"),  # Every 12 hours
    },
}


@celery_app.task(bind=True)
def analyze_adr_task(self, adr_id: str, persona: str = None):
    """Celery task for ADR analysis."""
    try:
        import asyncio

        from src.websocket_broadcaster import get_broadcaster

        # Publish task started status
        async def _publish_status(status: str, message: str):
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="analyze_adr_task",
                status=status,
                position=None,
                message=message,
            )

        asyncio.run(_publish_status("active", f"Analyzing ADR {adr_id}"))

        self.update_state(
            state="PROGRESS", meta={"message": "Initializing analysis service"}
        )

        # For demo purposes, simulate analysis without external dependencies
        # In production, this would connect to actual Llama.cpp and LightRAG services
        import time

        # Simulate processing time
        time.sleep(2)

        self.update_state(state="PROGRESS", meta={"message": "Running analysis"})

        # Simulate analysis result
        result = {
            "adr_id": adr_id,
            "persona": persona or "technical_lead",
            "sections": {
                "strengths": "Good technical foundation and clear requirements",
                "weaknesses": "Missing implementation details and testing strategy",
                "risks": "Potential scalability issues with current architecture",
                "recommendations": "Add comprehensive testing and consider scalability requirements",
                "overall_assessment": "MODIFY - Solid foundation but needs refinement",
            },
            "score": 7,
            "raw_response": "Simulated analysis response for demo purposes",
        }

        self.update_state(state="PROGRESS", meta={"message": "Analysis completed"})

        asyncio.run(
            _publish_status("completed", f"Analysis completed for ADR {adr_id}")
        )

        return result

    except Exception as e:
        import asyncio

        from src.websocket_broadcaster import get_broadcaster

        # Publish task failed status
        async def _publish_failed(e: Exception):
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="analyze_adr_task",
                status="failed",
                position=None,
                message=f"Error: {str(e)}",
            )

        asyncio.run(_publish_failed(e))

        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(bind=True)
def generate_adr_task(
    self,
    prompt: str,
    context: str = None,
    tags: list = None,
    personas: list = None,
    retrieval_mode: str = "local",
    provider_id: str = None,
    record_type: str = "decision",
    mcp_tools: list = None,
    use_mcp: bool = False,
    status_filter: list = None,
):
    """Celery task for ADR generation."""
    try:
        import asyncio
        from datetime import UTC, datetime

        from src.adr_file_storage import get_adr_storage
        from src.adr_generation import ADRGenerationService
        from src.lightrag_client import LightRAGClient
        from src.llama_client import LlamaCppClient, create_client_from_provider_id
        from src.models import (
            ADR,
            ADRContent,
            ADRGenerationPrompt,
            ADRMetadata,
            ADRStatus,
            RecordType,
        )
        from src.persona_manager import PersonaManager
        from src.websocket_broadcaster import get_broadcaster

        # Publish task started status
        async def _publish_task_started():
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="generate_adr_task",
                status="active",
                position=None,
                message="Starting ADR generation",
            )

            # Track task in monitor for fast queue status
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_started(
                task_id=self.request.id,
                task_name="generate_adr_task",
                args=(prompt,),
                kwargs={
                    "context": context,
                    "personas": personas,
                    "provider_id": provider_id,
                },
            )

        asyncio.run(_publish_task_started())

        self.update_state(
            state="PROGRESS", meta={"message": "Initializing ADR generation service"}
        )

        async def _generate():
            # Initialize clients with demo_mode=False to use real LLM
            from src.config import get_settings
            from src.llama_client import LlamaCppClientPool

            settings = get_settings()

            # If a specific provider_id was requested, use that provider
            if provider_id:
                logger.info(f"Creating LLM client from provider_id: {provider_id}")
                llama_client = await create_client_from_provider_id(provider_id)
            else:
                # Use default behavior: pool if secondary backend configured, otherwise single client
                if settings.llm_base_url_1 or settings.llm_embedding_base_url:
                    logger.info("Using LlamaCppClientPool for parallel generation")
                    llama_client = LlamaCppClientPool(demo_mode=False)
                else:
                    logger.info("Using single LlamaCppClient")
                    llama_client = LlamaCppClient(demo_mode=False)

            lightrag_client = LightRAGClient(demo_mode=False)
            persona_manager = PersonaManager()

            # Initialize the service
            generation_service = ADRGenerationService(
                llama_client=llama_client,
                lightrag_client=lightrag_client,
                persona_manager=persona_manager,
            )

            # Create the generation prompt with required fields
            generation_prompt = ADRGenerationPrompt(
                title=f"{prompt[:50]}",
                context=context or "No additional context provided",
                problem_statement=prompt,  # The prompt IS the problem statement
                tags=tags or [],
                retrieval_mode=retrieval_mode or "naive",
                record_type=RecordType(record_type),
                status_filter=status_filter,
            )

            # Default personas if none provided
            if not personas:
                persona_list = ["technical_lead", "architect", "business_analyst"]
            else:
                # Validate persona strings against available personas
                from src.persona_manager import get_persona_manager

                manager = get_persona_manager()
                available_personas = manager.list_persona_values()

                persona_list = []
                for p in personas:
                    if p in available_personas:
                        persona_list.append(p)
                    else:
                        print(f"Warning: Skipping invalid persona: {p}")

                # If all personas were invalid, use defaults
                if not persona_list:
                    persona_list = ["technical_lead", "architect", "business_analyst"]

            self.update_state(
                state="PROGRESS",
                meta={"message": f"Generating ADR with {len(persona_list)} personas"},
            )

            # Create progress callback
            def update_progress(message: str):
                self.update_state(state="PROGRESS", meta={"message": message})

            # Generate the ADR - wrap in async context manager for client pool
            async with llama_client:
                result = await generation_service.generate_adr(
                    generation_prompt,
                    personas=persona_list,
                    progress_callback=update_progress,
                    provider_id=provider_id,
                    mcp_tools=mcp_tools,
                    use_mcp=use_mcp,
                )

            self.update_state(
                state="PROGRESS",
                meta={"message": f"✓ ADR generated: {result.generated_title}"},
            )

            # Prepare persona responses for storage
            persona_responses_data = None
            if result.persona_responses:
                persona_responses_data = [
                    p.model_dump() for p in result.persona_responses
                ]

            # Convert options to OptionDetails
            from src.models import ConsequencesStructured, OptionDetails

            options_details = None
            if result.considered_options:
                options_details = [
                    OptionDetails(
                        name=opt.option_name,
                        description=opt.description,
                        pros=opt.pros,
                        cons=opt.cons,
                    )
                    for opt in result.considered_options
                ]

            # Convert consequences_structured if available
            consequences_structured = None
            if result.consequences_structured:
                # Use the structured consequences directly from the generation result
                positive_items = result.consequences_structured.get("positive", [])
                negative_items = result.consequences_structured.get("negative", [])

                # Capitalize first letter if needed
                positive_items = [
                    item[0].upper() + item[1:] if item and item[0].islower() else item
                    for item in positive_items
                ]
                negative_items = [
                    item[0].upper() + item[1:] if item and item[0].islower() else item
                    for item in negative_items
                ]

                consequences_structured = ConsequencesStructured(
                    positive=positive_items, negative=negative_items
                )
            else:
                # Fallback: parse from consequences text (for backwards compatibility)
                try:
                    cons_text = result.consequences
                    positive_items = []
                    negative_items = []

                    if "Positive:" in cons_text and "Negative:" in cons_text:
                        parts = cons_text.split("Negative:")
                        positive_text = parts[0].replace("Positive:", "").strip()
                        negative_text = parts[1].strip() if len(parts) > 1 else ""

                        # Parse bullet points from positive section
                        for line in positive_text.split("\n"):
                            line = line.strip()
                            # Remove bullet point markers (-, *, •)
                            if line.startswith("- "):
                                line = line[2:].strip()
                            elif line.startswith("* "):
                                line = line[2:].strip()
                            elif line.startswith("• "):
                                line = line[2:].strip()

                            # Only add if not empty and not just punctuation/whitespace
                            if line and line not in ["-", "•", "*"]:
                                # Capitalize first letter if not already
                                if line and line[0].islower():
                                    line = line[0].upper() + line[1:]
                                positive_items.append(line)

                        # Parse bullet points from negative section
                        for line in negative_text.split("\n"):
                            line = line.strip()
                            # Remove bullet point markers (-, *, •)
                            if line.startswith("- "):
                                line = line[2:].strip()
                            elif line.startswith("* "):
                                line = line[2:].strip()
                            elif line.startswith("• "):
                                line = line[2:].strip()

                            # Only add if not empty and not just punctuation/whitespace
                            if line and line not in ["-", "•", "*"]:
                                # Capitalize first letter if not already
                                if line and line[0].islower():
                                    line = line[0].upper() + line[1:]
                                negative_items.append(line)

                        consequences_structured = ConsequencesStructured(
                            positive=positive_items, negative=negative_items
                        )
                except Exception:
                    # If parsing fails, just leave consequences_structured as None
                    pass

            # Create ADR object for storage
            adr = ADR(
                metadata=ADRMetadata(
                    title=result.generated_title,
                    status=ADRStatus.PROPOSED,
                    author="AI Assistant",
                    tags=tags or [],
                    record_type=RecordType(record_type),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                ),
                content=ADRContent(
                    context_and_problem=result.context_and_problem,
                    decision_outcome=result.decision_outcome,
                    consequences=result.consequences,
                    considered_options=(
                        [opt.option_name for opt in result.considered_options]
                        if result.considered_options
                        else []
                    ),
                    decision_drivers=(
                        result.decision_drivers if result.decision_drivers else []
                    ),
                    options_details=options_details,
                    consequences_structured=consequences_structured,
                    principle_details=result.principle_details,
                    referenced_adrs=(
                        result.referenced_adrs if result.referenced_adrs else None
                    ),
                    original_generation_prompt={
                        "title": generation_prompt.title,
                        "context": generation_prompt.context,
                        "problem_statement": generation_prompt.problem_statement,
                        "constraints": generation_prompt.constraints,
                        "stakeholders": generation_prompt.stakeholders,
                        "tags": generation_prompt.tags,
                        "retrieval_mode": generation_prompt.retrieval_mode,
                    },
                ),
                persona_responses=persona_responses_data,
            )

            # Save to file storage
            storage = get_adr_storage()
            storage.save_adr(adr)

            self.update_state(
                state="PROGRESS",
                meta={"message": f"ADR saved with ID {adr.metadata.id}"},
            )

            # Push to LightRAG for future reference
            try:
                from src.lightrag_doc_cache import LightRAGDocumentCache

                async with LightRAGClient(demo_mode=False) as rag_client:
                    # Format ADR content for storage
                    adr_content = f"""Title: {adr.metadata.title}
Status: {adr.metadata.status}
Tags: {', '.join(adr.metadata.tags)}

Context & Problem:
{adr.content.context_and_problem}

Decision Outcome:
{adr.content.decision_outcome}

Consequences:
{adr.content.consequences}

Decision Drivers:
{chr(10).join(f"- {driver}" for driver in adr.content.decision_drivers)}

Considered Options:
{chr(10).join(f"- {opt}" for opt in adr.content.considered_options)}
"""

                    result = await rag_client.store_document(
                        doc_id=str(adr.metadata.id),
                        content=adr_content,
                        metadata={
                            "record_type": adr.metadata.record_type.value,
                            "title": adr.metadata.title,
                            "status": adr.metadata.status,
                            "tags": adr.metadata.tags,
                            "created_at": adr.metadata.created_at.isoformat(),
                        },
                    )

                    # Check if we got a track_id for monitoring upload status
                    track_id = result.get("track_id")

                    if track_id:
                        # Store upload status and start monitoring task
                        async with LightRAGDocumentCache() as cache:
                            await cache.set_upload_status(
                                adr_id=str(adr.metadata.id),
                                track_id=track_id,
                                status="processing",
                                message="Document uploaded to LightRAG, processing...",
                            )

                        logger.info(
                            "ADR upload started with tracking",
                            adr_id=str(adr.metadata.id),
                            track_id=track_id,
                        )

                        # Start background task to monitor upload status
                        monitor_upload_status_task.delay(str(adr.metadata.id), track_id)

                    else:
                        # No track_id, assume immediate success (old LightRAG behavior)
                        # Update cache immediately so frontend knows ADR is in RAG
                        if result and result.get("status") == "success":
                            lightrag_doc_id = result.get("doc_id", str(adr.metadata.id))
                            async with LightRAGDocumentCache() as cache:
                                await cache.set_doc_id(
                                    str(adr.metadata.id), lightrag_doc_id
                                )
                            logger.info(
                                "ADR pushed to LightRAG and cache updated",
                                adr_id=str(adr.metadata.id),
                                lightrag_doc_id=lightrag_doc_id,
                            )

                    self.update_state(
                        state="PROGRESS", meta={"message": "ADR indexed in LightRAG"}
                    )
            except Exception as e:
                # Log but don't fail if RAG push fails
                logger.warning(f"Failed to push ADR to LightRAG: {e}")

            # Convert ADR to the expected return format
            return_data = {
                "id": str(adr.metadata.id),
                "title": adr.metadata.title,
                "context_and_problem": adr.content.context_and_problem,
                "decision_outcome": adr.content.decision_outcome,
                "consequences": adr.content.consequences,
                "author": adr.metadata.author,
                "tags": adr.metadata.tags or [],
                "status": adr.metadata.status,
                "created_date": adr.metadata.created_at.isoformat(),
                "confidence_score": (
                    result.confidence_score
                    if hasattr(result, "confidence_score")
                    else None
                ),
                "personas_used": (
                    result.personas_used
                    if hasattr(result, "personas_used") and result.personas_used
                    else persona_list
                ),
            }

            # Publish task completed status
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="generate_adr_task",
                status="completed",
                position=None,
                message=f"ADR generated: {adr.metadata.title}",
            )

            # Track task completion in monitor
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_completed(self.request.id)

            return return_data

        # Run the async generation
        result = asyncio.run(_generate())
        return result

    except Exception as e:
        # Publish task failed status
        async def _publish_task_failed(e: Exception):
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="generate_adr_task",
                status="failed",
                position=None,
                message=f"Error: {str(e)}",
            )

        asyncio.run(_publish_task_failed(e))

        # Properly handle exceptions for Celery serialization
        error_msg = str(e)
        self.update_state(state="FAILURE", meta={"error": error_msg})
        # Re-raise with a simple exception that can be serialized
        raise Exception(error_msg)


@celery_app.task(bind=True)
def refine_personas_task(
    self,
    adr_id: str,
    persona_refinements: dict,  # Dict[str, str] mapping persona name to refinement prompt
    refinements_to_delete: dict = None,  # Dict[str, List[int]] mapping persona name to refinement indices to delete
    provider_id: str = None,
):
    """Celery task for refining persona perspectives in an existing ADR."""
    try:
        import asyncio

        from src.adr_file_storage import get_adr_storage
        from src.adr_generation import ADRGenerationService
        from src.lightrag_client import LightRAGClient
        from src.llama_client import LlamaCppClient, create_client_from_provider_id
        from src.persona_manager import PersonaManager
        from src.websocket_broadcaster import get_broadcaster

        # Publish task started status
        async def _publish_task_started():
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="refine_personas_task",
                status="active",
                position=None,
                message="Starting persona refinement",
            )

            # Track task in monitor for fast queue status
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_started(
                task_id=self.request.id,
                task_name="refine_personas_task",
                args=(adr_id,),
                kwargs={
                    "persona_refinements": persona_refinements,
                    "provider_id": provider_id,
                },
            )

        asyncio.run(_publish_task_started())

        self.update_state(state="PROGRESS", meta={"message": "Loading ADR"})

        async def _refine():
            from src.config import get_settings
            from src.llama_client import LlamaCppClientPool

            settings = get_settings()

            # If a specific provider_id was requested, use that provider
            if provider_id:
                logger.info(f"Creating LLM client from provider_id: {provider_id}")
                llama_client = await create_client_from_provider_id(provider_id)
            else:
                # Use default behavior: pool if secondary backend configured, otherwise single client
                if settings.llm_base_url_1 or settings.llm_embedding_base_url:
                    logger.info("Using LlamaCppClientPool for parallel generation")
                    llama_client = LlamaCppClientPool(demo_mode=False)
                else:
                    logger.info("Using single LlamaCppClient")
                    llama_client = LlamaCppClient(demo_mode=False)

            lightrag_client = LightRAGClient(demo_mode=False)
            persona_manager = PersonaManager()

            # Initialize the service
            generation_service = ADRGenerationService(
                llama_client=llama_client,
                lightrag_client=lightrag_client,
                persona_manager=persona_manager,
            )

            # Load the existing ADR (use asyncio.to_thread for blocking I/O)
            storage = get_adr_storage()
            adr = await asyncio.to_thread(storage.get_adr, adr_id)

            if not adr:
                raise ValueError(f"ADR not found: {adr_id}")

            self.update_state(
                state="PROGRESS",
                meta={"message": f"Refining {len(persona_refinements)} persona(s)"},
            )

            # Create progress callback
            def update_progress(message: str):
                self.update_state(state="PROGRESS", meta={"message": message})

            # Refine the personas - wrap in async context manager for client pool
            async with llama_client:
                refined_adr = await generation_service.refine_personas(
                    adr,
                    persona_refinements,
                    refinements_to_delete=refinements_to_delete or {},
                    progress_callback=update_progress,
                    provider_id=provider_id,
                )

            self.update_state(
                state="PROGRESS",
                meta={"message": "Saving refined ADR"},
            )

            # Save the updated ADR (use asyncio.to_thread for blocking I/O)
            await asyncio.to_thread(storage.save_adr, refined_adr)

            # Broadcast completion
            broadcaster = get_broadcaster()
            await broadcaster.publish_upload_status(
                adr_id=adr_id,
                status="completed",
                message="Persona refinement completed",
            )

            # Track task completion
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_completed(self.request.id)

            return {
                "adr_id": adr_id,
                "title": refined_adr.metadata.title,
                "refined_personas": list(persona_refinements.keys()),
                "updated_at": refined_adr.metadata.updated_at.isoformat(),
            }

        # Run the async refinement
        result = asyncio.run(_refine())
        return result

    except Exception as e:
        # Log the full error for debugging
        import traceback

        logger.error(
            "Error in refine_personas_task",
            adr_id=adr_id,
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )

        # Publish task failed status
        async def _publish_task_failed(error: Exception):
            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="refine_personas_task",
                status="failed",
                position=None,
                message=f"Error: {str(error)}",
            )

            # Track task completion even on failure
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_completed(self.request.id)

        asyncio.run(_publish_task_failed(e))

        # Properly handle exceptions for Celery serialization
        error_msg = str(e)
        self.update_state(state="FAILURE", meta={"error": error_msg})
        # Re-raise the original exception to preserve type info
        raise


@celery_app.task(bind=True)
def refine_original_prompt_task(
    self,
    adr_id: str,
    refined_prompt_fields: dict,
    provider_id: str = None,
):
    """Celery task for refining the original generation prompt.

    This task regenerates all personas with a refined original prompt.
    Any existing persona refinements are preserved and re-applied.

    Args:
        adr_id: ID of the ADR to refine
        refined_prompt_fields: Dict with updated prompt fields (title, context, problem_statement, etc.)
        provider_id: Optional provider ID for LLM selection
    """
    try:
        # Track task start
        async def _publish_task_started():
            from src.websocket_broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="refine_original_prompt_task",
                status="active",
                position=None,
                message=f"Refining original prompt for ADR {adr_id}",
            )

            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_started(
                task_id=self.request.id,
                task_name="refine_original_prompt_task",
                args=(adr_id,),
                kwargs={
                    "refined_prompt_fields": refined_prompt_fields,
                    "provider_id": provider_id,
                },
            )

        asyncio.run(_publish_task_started())

        self.update_state(state="PROGRESS", meta={"message": "Loading ADR"})

        async def _refine():
            from src.adr_file_storage import get_adr_storage
            from src.adr_generation import ADRGenerationService
            from src.config import get_settings
            from src.lightrag_client import LightRAGClient
            from src.llama_client import (
                LlamaCppClient,
                LlamaCppClientPool,
                create_client_from_provider_id,
            )
            from src.persona_manager import PersonaManager
            from src.websocket_broadcaster import get_broadcaster

            settings = get_settings()

            # If a specific provider_id was requested, use that provider
            if provider_id:
                logger.info(f"Creating LLM client from provider_id: {provider_id}")
                llama_client = await create_client_from_provider_id(provider_id)
            else:
                # Use default behavior: pool if secondary backend configured, otherwise single client
                if settings.llm_base_url_1 or settings.llm_embedding_base_url:
                    logger.info("Using LlamaCppClientPool for parallel generation")
                    llama_client = LlamaCppClientPool(demo_mode=False)
                else:
                    logger.info("Using single LlamaCppClient")
                    llama_client = LlamaCppClient(demo_mode=False)

            lightrag_client = LightRAGClient(demo_mode=False)
            persona_manager = PersonaManager()

            # Initialize the service
            generation_service = ADRGenerationService(
                llama_client=llama_client,
                lightrag_client=lightrag_client,
                persona_manager=persona_manager,
            )

            # Load the existing ADR (use asyncio.to_thread for blocking I/O)
            storage = get_adr_storage()
            adr = await asyncio.to_thread(storage.get_adr, adr_id)

            if not adr:
                raise ValueError(f"ADR not found: {adr_id}")

            self.update_state(
                state="PROGRESS",
                meta={
                    "message": "Regenerating all personas with refined original prompt"
                },
            )

            # Create progress callback
            def update_progress(message: str):
                self.update_state(state="PROGRESS", meta={"message": message})

            # Refine the original prompt and regenerate all personas
            # Exclude the current ADR from retrieval to prevent self-referencing
            async with llama_client:
                refined_adr = await generation_service.refine_original_prompt(
                    adr,
                    refined_prompt_fields,
                    progress_callback=update_progress,
                    provider_id=provider_id,
                    exclude_adr_id=adr_id,
                )

            self.update_state(
                state="PROGRESS",
                meta={"message": "Saving refined ADR"},
            )

            # Save the updated ADR (use asyncio.to_thread for blocking I/O)
            await asyncio.to_thread(storage.save_adr, refined_adr)

            # Update the document in LightRAG with the refined content
            self.update_state(
                state="PROGRESS",
                meta={"message": "Updating ADR in LightRAG"},
            )

            try:
                from src.lightrag_doc_cache import LightRAGDocumentCache

                # Format updated ADR content for LightRAG storage
                adr_content = f"""Title: {refined_adr.metadata.title}
Status: {refined_adr.metadata.status}
Tags: {', '.join(refined_adr.metadata.tags)}

Context & Problem:
{refined_adr.content.context_and_problem}

Decision Outcome:
{refined_adr.content.decision_outcome}

Consequences:
{refined_adr.content.consequences}

Decision Drivers:
{chr(10).join(f"- {driver}" for driver in refined_adr.content.decision_drivers)}

Considered Options:
{chr(10).join(f"- {opt}" for opt in refined_adr.content.considered_options)}
"""

                # Update the document in LightRAG
                # LightRAG doesn't have update - must delete then re-insert
                # Use a fresh LightRAG client with its own context manager
                async with LightRAGClient(demo_mode=False) as rag_client:
                    # First, look up the LightRAG document ID from cache
                    refined_adr_id = str(refined_adr.metadata.id)
                    lightrag_doc_id = None

                    try:
                        async with LightRAGDocumentCache() as cache:
                            lightrag_doc_id = await cache.get_doc_id(refined_adr_id)

                        if lightrag_doc_id:
                            logger.info(
                                "Found LightRAG doc ID in cache for deletion",
                                adr_id=refined_adr_id,
                                lightrag_doc_id=lightrag_doc_id,
                            )
                        else:
                            logger.info(
                                "No cached LightRAG doc ID, deletion may fail",
                                adr_id=refined_adr_id,
                            )
                    except Exception as cache_error:
                        logger.warning(
                            "Failed to look up LightRAG doc ID from cache",
                            adr_id=refined_adr_id,
                            error=str(cache_error),
                        )

                    # Try to delete the existing document using the LightRAG doc ID
                    try:
                        await rag_client.delete_document(
                            doc_id=refined_adr_id,
                            lightrag_doc_id=lightrag_doc_id,  # Pass the real doc ID
                        )
                        logger.info(
                            "Deleted existing ADR from LightRAG before re-inserting",
                            adr_id=refined_adr_id,
                            lightrag_doc_id=lightrag_doc_id,
                        )
                        # Wait for deletion to complete (LightRAG processes deletion async)
                        # Give it 2 seconds to process the deletion before re-inserting
                        await asyncio.sleep(2)
                    except Exception as delete_error:
                        # Document might not exist, that's ok
                        logger.info(
                            "Could not delete document (may not exist), proceeding with insert",
                            adr_id=refined_adr_id,
                            error=str(delete_error),
                        )

                    # Now insert the updated document
                    result = await rag_client.store_document(
                        doc_id=refined_adr_id,
                        content=adr_content,
                        metadata={
                            "record_type": refined_adr.metadata.record_type.value,
                            "title": refined_adr.metadata.title,
                            "status": refined_adr.metadata.status,
                            "tags": refined_adr.metadata.tags,
                            "created_at": refined_adr.metadata.created_at.isoformat(),
                            "updated_at": refined_adr.metadata.updated_at.isoformat(),
                        },
                    )

                    # Check if we got a track_id for monitoring upload status
                    track_id = result.get("track_id")

                    if track_id:
                        # Store upload status and start monitoring task
                        async with LightRAGDocumentCache() as cache:
                            await cache.set_upload_status(
                                adr_id=refined_adr_id,
                                track_id=track_id,
                                status="processing",
                                message="Updated ADR document in LightRAG, processing...",
                            )

                        logger.info(
                            "Refined ADR upload started with tracking",
                            adr_id=refined_adr_id,
                            track_id=track_id,
                        )

                        # Start background task to monitor upload status
                        from src.celery_app import monitor_upload_status_task

                        monitor_upload_status_task.delay(refined_adr_id, track_id)
                    else:
                        # No track_id, assume immediate success (old LightRAG behavior)
                        if result and result.get("status") == "success":
                            lightrag_doc_id_result = result.get(
                                "doc_id", refined_adr_id
                            )
                            async with LightRAGDocumentCache() as cache:
                                await cache.set_doc_id(
                                    refined_adr_id, lightrag_doc_id_result
                                )
                            logger.info(
                                "Refined ADR updated in LightRAG and cache updated",
                                adr_id=refined_adr_id,
                                lightrag_doc_id=lightrag_doc_id_result,
                            )

                    self.update_state(
                        state="PROGRESS",
                        meta={"message": "ADR indexed in LightRAG"},
                    )
            except Exception as e:
                # Log but don't fail if RAG update fails
                logger.warning(
                    "Failed to update ADR in LightRAG",
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # Broadcast completion
            # Import already done at top of _refine function
            broadcaster = get_broadcaster()
            await broadcaster.publish_upload_status(
                adr_id=adr_id,
                status="completed",
                message="Original prompt refinement completed",
            )

            # Track task completion
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_completed(self.request.id)

            return {
                "adr_id": adr_id,
                "title": refined_adr.metadata.title,
                "refined_fields": list(refined_prompt_fields.keys()),
                "updated_at": refined_adr.metadata.updated_at.isoformat(),
            }

        # Run the async refinement
        result = asyncio.run(_refine())
        return result

    except Exception as e:
        # Log the full error for debugging
        import traceback

        logger.error(
            "Error in refine_original_prompt_task",
            adr_id=adr_id,
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
        )

        # Publish task failed status
        async def _publish_task_failed(error: Exception):
            from src.websocket_broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            await broadcaster.publish_task_status(
                task_id=self.request.id,
                task_name="refine_original_prompt_task",
                status="failed",
                position=None,
                message=f"Error: {str(error)}",
            )

            # Track task completion even on failure
            from src.task_queue_monitor import get_task_queue_monitor

            monitor = get_task_queue_monitor()
            await monitor.track_task_completed(self.request.id)

        asyncio.run(_publish_task_failed(e))

        # Properly handle exceptions for Celery serialization
        error_msg = str(e)
        self.update_state(state="FAILURE", meta={"error": error_msg})
        # Re-raise the original exception to preserve type info
        raise


@celery_app.task(bind=True, name="monitor_upload_status")
def monitor_upload_status_task(self, adr_id: str, track_id: str):
    """Monitor LightRAG upload status and update cache when complete.

    This task polls the LightRAG track_status endpoint until the upload
    is completed or failed. When complete, it updates the cache and
    broadcasts the status via WebSocket.

    Args:
        adr_id: The ADR ID
        track_id: The LightRAG tracking ID
    """

    async def _monitor():
        import asyncio

        from src.lightrag_client import LightRAGClient
        from src.lightrag_doc_cache import LightRAGDocumentCache
        from src.websocket_broadcaster import get_broadcaster

        max_attempts = 60  # Poll for up to 5 minutes (60 * 5s = 300s)
        attempt = 0

        logger.info(
            "Starting upload status monitoring", adr_id=adr_id, track_id=track_id
        )

        try:
            async with LightRAGClient(demo_mode=False) as rag_client:
                async with LightRAGDocumentCache() as cache:
                    while attempt < max_attempts:
                        attempt += 1

                        try:
                            # Check track status
                            status_result = await rag_client.get_track_status(track_id)

                            # Log full response for debugging
                            logger.debug(
                                "Track status response",
                                adr_id=adr_id,
                                track_id=track_id,
                                response=status_result,
                                attempt=attempt,
                            )

                            # Parse LightRAG track_status response structure
                            # Response format: {track_id, documents: [{status, ...}], status_summary}
                            status = None
                            message = ""
                            doc_id = None

                            # Check if response has documents array
                            documents = status_result.get("documents", [])
                            if documents and len(documents) > 0:
                                # Get status from first document
                                doc = documents[0]
                                doc_status = doc.get("status", "").lower()
                                doc_id = doc.get("id")

                                # Map LightRAG document status to our status
                                if doc_status == "processed":
                                    status = "completed"
                                    message = "Document successfully indexed"
                                elif doc_status == "processing":
                                    status = "processing"
                                    message = "Document being processed..."
                                elif doc_status == "failed" or doc_status == "error":
                                    status = "failed"
                                    message = doc.get("error_msg", "Processing failed")
                                else:
                                    # Unknown status, assume processing
                                    status = "processing"
                                    message = f"Document status: {doc_status}"

                            # Fallback: check top-level status field
                            if status is None:
                                status = (
                                    status_result.get("status")
                                    or status_result.get("state")
                                    or status_result.get("processing_status")
                                )
                                message = (
                                    status_result.get("message")
                                    or status_result.get("msg")
                                    or status_result.get("description")
                                    or ""
                                )

                            logger.debug(
                                "Upload status check",
                                adr_id=adr_id,
                                track_id=track_id,
                                status=status,
                                doc_id=doc_id,
                                attempt=attempt,
                            )

                            if status == "completed":
                                # Upload completed successfully
                                logger.info(
                                    "Upload completed",
                                    adr_id=adr_id,
                                    track_id=track_id,
                                    lightrag_doc_id=doc_id,
                                )

                                # Update cache with LightRAG doc_id (if we have it)
                                # Otherwise use track_id as fallback
                                cache_doc_id = doc_id if doc_id else track_id
                                await cache.set_doc_id(adr_id, cache_doc_id)

                                logger.info(
                                    "Cache updated with document ID",
                                    adr_id=adr_id,
                                    cache_doc_id=cache_doc_id,
                                )

                                # Update upload status
                                await cache.set_upload_status(
                                    adr_id=adr_id,
                                    track_id=track_id,
                                    status="completed",
                                    message="Successfully uploaded to RAG",
                                )

                                # Broadcast via WebSocket (cross-process using Redis)
                                broadcaster = get_broadcaster()
                                logger.info(
                                    "Broadcasting upload completion via Redis pub/sub",
                                    adr_id=adr_id,
                                )
                                await broadcaster.publish_upload_status(
                                    adr_id=adr_id,
                                    status="completed",
                                    message="Successfully uploaded to RAG",
                                )

                                # Clear upload status after 5 seconds
                                await asyncio.sleep(5)
                                await cache.clear_upload_status(adr_id)

                                return {"status": "completed", "adr_id": adr_id}

                            elif status == "failed":
                                # Upload failed
                                logger.error(
                                    "Upload failed",
                                    adr_id=adr_id,
                                    track_id=track_id,
                                    message=message,
                                )

                                # Update upload status
                                await cache.set_upload_status(
                                    adr_id=adr_id,
                                    track_id=track_id,
                                    status="failed",
                                    message=message or "Upload failed",
                                )

                                # Broadcast via WebSocket (cross-process using Redis)
                                broadcaster = get_broadcaster()
                                await broadcaster.publish_upload_status(
                                    adr_id=adr_id,
                                    status="failed",
                                    message=message or "Upload failed",
                                )

                                return {
                                    "status": "failed",
                                    "adr_id": adr_id,
                                    "error": message,
                                }

                            elif status == "processing":
                                # Still processing, update status and wait
                                await cache.set_upload_status(
                                    adr_id=adr_id,
                                    track_id=track_id,
                                    status="processing",
                                    message=message or "Processing...",
                                )

                                # Broadcast via WebSocket (cross-process using Redis)
                                broadcaster = get_broadcaster()
                                logger.debug(
                                    "Broadcasting processing status via Redis pub/sub",
                                    adr_id=adr_id,
                                )
                                await broadcaster.publish_upload_status(
                                    adr_id=adr_id,
                                    status="processing",
                                    message=message or "Processing...",
                                )

                                # Wait before next check
                                await asyncio.sleep(5)

                            else:
                                logger.warning(
                                    "Unknown upload status",
                                    adr_id=adr_id,
                                    track_id=track_id,
                                    status=status,
                                )
                                await asyncio.sleep(5)

                        except Exception as e:
                            logger.error(
                                "Error checking upload status",
                                adr_id=adr_id,
                                track_id=track_id,
                                error=str(e),
                                attempt=attempt,
                            )
                            await asyncio.sleep(5)

                    # Max attempts reached
                    logger.warning(
                        "Upload monitoring timed out",
                        adr_id=adr_id,
                        track_id=track_id,
                        max_attempts=max_attempts,
                    )

                    # Mark as failed due to timeout
                    await cache.set_upload_status(
                        adr_id=adr_id,
                        track_id=track_id,
                        status="failed",
                        message="Upload monitoring timed out after 5 minutes",
                    )

                    # Broadcast timeout via WebSocket
                    broadcaster = get_broadcaster()
                    await broadcaster.publish_upload_status(
                        adr_id=adr_id,
                        status="failed",
                        message="Upload monitoring timed out after 5 minutes",
                    )

                    # Clear upload status after broadcasting
                    await asyncio.sleep(5)
                    await cache.clear_upload_status(adr_id)

                    return {"status": "timeout", "adr_id": adr_id}

        except Exception as e:
            logger.error(
                "Upload monitoring failed",
                adr_id=adr_id,
                track_id=track_id,
                error=str(e),
            )

            # Clean up upload status on error
            try:
                from src.lightrag_doc_cache import LightRAGDocumentCache
                from src.websocket_broadcaster import get_broadcaster

                async with LightRAGDocumentCache() as cache:
                    await cache.set_upload_status(
                        adr_id=adr_id,
                        track_id=track_id,
                        status="failed",
                        message=f"Monitoring error: {str(e)}",
                    )

                    # Broadcast error via WebSocket
                    broadcaster = get_broadcaster()
                    await broadcaster.publish_upload_status(
                        adr_id=adr_id,
                        status="failed",
                        message=f"Monitoring error: {str(e)}",
                    )

                    # Clear status after 5 seconds
                    await asyncio.sleep(5)
                    await cache.clear_upload_status(adr_id)
            except Exception as cleanup_error:
                logger.error(f"Failed to cleanup upload status: {cleanup_error}")

            raise

    try:
        result = asyncio.run(_monitor())
        return result
    except Exception as e:
        error_msg = str(e)
        logger.error("Monitor upload status task failed", error=error_msg)
        raise Exception(error_msg)


@celery_app.task(bind=True, name="refresh_lightrag_cache")
def refresh_lightrag_cache_task(self):
    """Periodic task to refresh LightRAG cache from server.

    This task runs every 12 hours to sync the Redis cache with LightRAG's
    actual document list, preventing cache expiration issues and ensuring
    the "Push to RAG" buttons remain accurate.

    The cache TTL is 24 hours, so refreshing every 12 hours ensures we never
    hit expiration.
    """

    async def _refresh():
        from src.lightrag_sync import _sync_lightrag_cache

        logger.info("Starting periodic LightRAG cache refresh")

        try:
            total_synced = await _sync_lightrag_cache(page_size=100)

            logger.info(
                "Periodic cache refresh completed", total_documents=total_synced
            )

            return {
                "status": "success",
                "total_documents": total_synced,
                "message": "Cache refreshed successfully",
            }
        except Exception as e:
            logger.error(
                "Periodic cache refresh failed",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    try:
        result = asyncio.run(_refresh())
        return result
    except Exception as e:
        error_msg = str(e)
        logger.error("Cache refresh task failed", error=error_msg)
        # Don't raise - we don't want to stop the beat schedule
        # Just log the error and try again next time
        return {
            "status": "error",
            "message": error_msg,
        }


if __name__ == "__main__":
    celery_app.start()
