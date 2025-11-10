"""Celery task definitions for async job processing."""

import os
import asyncio
from typing import Optional, List, Dict, Any
from celery import Celery
from celery.schedules import crontab
from uuid import UUID

from src.config import settings
from src.adr_generation import ADRGenerationService
from src.logger import get_logger

logger = get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "decision_analyzer",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["src.tasks"]
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
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "periodic-reanalysis": {
        "task": "src.tasks.periodic_reanalysis",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
    },
}


@celery_app.task(bind=True)
def analyze_adr_task(self, adr_id: str, persona: str = None):
    """Celery task for ADR analysis."""
    try:
        self.update_state(state="PROGRESS", meta={"message": "Initializing analysis service"})

        # For demo purposes, simulate analysis without external dependencies
        # In production, this would connect to actual Llama.cpp and LightRAG services
        import asyncio
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
                "overall_assessment": "MODIFY - Solid foundation but needs refinement"
            },
            "score": 7,
            "raw_response": "Simulated analysis response for demo purposes"
        }

        self.update_state(state="PROGRESS", meta={"message": "Analysis completed"})

        return result

    except Exception as e:
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(bind=True)
def generate_adr_task(self, prompt: str, context: str = None, tags: list = None, personas: list = None):
    """Celery task for ADR generation."""
    try:
        import asyncio
        from src.adr_generation import ADRGenerationService
        from src.llama_client import LlamaCppClient
        from src.lightrag_client import LightRAGClient
        from src.persona_manager import PersonaManager
        from src.models import ADRGenerationPrompt, ADR, ADRMetadata, ADRContent, ADRStatus
        from src.adr_file_storage import get_adr_storage
        from datetime import datetime, UTC

        self.update_state(state="PROGRESS", meta={"message": "Initializing ADR generation service"})

        async def _generate():
            # Initialize clients with demo_mode=False to use real LLM
            # Use LlamaCppClientPool for parallel generation if multiple backends are configured
            from src.llama_client import LlamaCppClientPool
            from src.config import get_settings

            settings = get_settings()

            # Use pool if secondary backend is configured, otherwise use single client
            if settings.llama_cpp_url_1 or settings.llama_cpp_url_embedding:
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
                persona_manager=persona_manager
            )

            # Create the generation prompt with required fields
            generation_prompt = ADRGenerationPrompt(
                title=f"ADR: {prompt[:50]}",
                context=context or "No additional context provided",
                problem_statement=prompt,  # The prompt IS the problem statement
                tags=tags or []
            )

            # Default personas if none provided
            if not personas:
                persona_list = ["technical_lead", "architect", "business_analyst"]
            else:
                # Validate persona strings against available personas
                from persona_manager import get_persona_manager

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

            self.update_state(state="PROGRESS", meta={"message": f"Generating ADR with {len(persona_list)} personas"})

            # Create progress callback
            def update_progress(message: str):
                self.update_state(state="PROGRESS", meta={"message": message})

            # Generate the ADR - wrap in async context manager for client pool
            async with llama_client:
                result = await generation_service.generate_adr(
                    generation_prompt,
                    personas=persona_list,
                    progress_callback=update_progress,
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
            from src.models import OptionDetails, ConsequencesStructured

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
                except Exception as e:
                    # If parsing fails, just leave consequences_structured as None
                    pass

            # Create ADR object for storage
            adr = ADR(
                metadata=ADRMetadata(
                    title=result.generated_title,
                    status=ADRStatus.PROPOSED,
                    author="AI Assistant",
                    tags=tags or [],
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
                    referenced_adrs=(
                        result.referenced_adrs if result.referenced_adrs else None
                    ),
                ),
                persona_responses=persona_responses_data,
            )

            # Save to file storage
            storage = get_adr_storage()
            storage.save_adr(adr)

            self.update_state(state="PROGRESS", meta={"message": f"ADR saved with ID {adr.metadata.id}"})

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
                            "type": "adr",
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
            return {
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

        # Run the async generation
        result = asyncio.run(_generate())
        return result

    except Exception as e:
        # Properly handle exceptions for Celery serialization
        error_msg = str(e)
        self.update_state(state="FAILURE", meta={"error": error_msg})
        # Re-raise with a simple exception that can be serialized
        raise Exception(error_msg)


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
        from src.lightrag_client import LightRAGClient
        from src.lightrag_doc_cache import LightRAGDocumentCache
        from src.websocket_broadcaster import get_broadcaster
        import asyncio

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
                        message="Upload monitoring timed out",
                    )

                    return {"status": "timeout", "adr_id": adr_id}

        except Exception as e:
            logger.error(
                "Upload monitoring failed",
                adr_id=adr_id,
                track_id=track_id,
                error=str(e),
            )
            raise

    try:
        result = asyncio.run(_monitor())
        return result
    except Exception as e:
        error_msg = str(e)
        logger.error("Monitor upload status task failed", error=error_msg)
        raise Exception(error_msg)


if __name__ == "__main__":
    celery_app.start()
