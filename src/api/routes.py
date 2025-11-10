"""API routes for Decision Analyzer."""

import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List, Optional, Literal
from pydantic import BaseModel
import json
import io

from src.models import ADR
from src.lightrag_client import LightRAGClient
from src.celery_app import analyze_adr_task, generate_adr_task
from src.logger import get_logger
from src.config import get_settings

logger = get_logger(__name__)

# Pydantic models for API requests/responses
class ADRListResponse(BaseModel):
    """Response model for ADR listing."""
    adrs: List[ADR]
    total: int

class AnalyzeADRRequest(BaseModel):
    """Request model for ADR analysis."""
    adr_id: str
    persona: Optional[str] = None

class GenerateADRRequest(BaseModel):
    """Request model for ADR generation."""
    prompt: str
    context: Optional[str] = None
    tags: Optional[List[str]] = None
    personas: Optional[List[str]] = None  # List of persona names

class TaskResponse(BaseModel):
    """Response model for queued tasks."""
    task_id: str
    status: str
    message: str

class PersonaInfo(BaseModel):
    """Information about an analysis persona."""
    value: str
    label: str
    description: str


class ConfigResponse(BaseModel):
    """Response model for API configuration."""

    api_base_url: str
    lan_discovery_enabled: bool


# Export/Import models
class ExportFormat(str):
    """Export format options."""

    VERSIONED_JSON = "versioned_json"
    MARKDOWN = "markdown"
    JSON = "json"
    YAML = "yaml"


class ExportRequest(BaseModel):
    """Request model for bulk export."""

    format: str = "versioned_json"
    adr_ids: Optional[List[str]] = None  # If None, export all
    exported_by: Optional[str] = None


class ExportResponse(BaseModel):
    """Response model for export operations."""

    message: str
    count: int
    format: str
    download_ready: bool = True


class ImportRequest(BaseModel):
    """Request model for bulk import from JSON data."""

    data: dict
    overwrite_existing: bool = False


class ImportResponse(BaseModel):
    """Response model for import operations."""

    message: str
    imported_count: int
    skipped_count: int = 0
    errors: List[str] = []


# Create routers
adr_router = APIRouter()
analysis_router = APIRouter()
generation_router = APIRouter()
config_router = APIRouter()


@adr_router.websocket("/ws/cache-status")
async def websocket_cache_status(websocket: WebSocket):
    """WebSocket endpoint for real-time cache status updates.
    
    Clients connect to this endpoint to receive immediate notifications when:
    - Cache rebuild starts (is_rebuilding: true)
    - Cache rebuild completes (is_rebuilding: false, last_sync_time updated)
    
    Message format:
    {
        "type": "cache_status",
        "is_rebuilding": bool,
        "last_sync_time": float | null  // Unix timestamp in seconds
    }
    """
    from src.websocket_manager import get_websocket_manager
    from src.lightrag_doc_cache import LightRAGDocumentCache

    logger.info(
        "🔌 WebSocket connection attempt",
        client=websocket.client,
        headers=dict(websocket.headers),
    )

    websocket_manager = get_websocket_manager()
    await websocket_manager.connect(websocket)

    logger.info("✅ WebSocket accepted and registered")

    logger.info("✅ WebSocket accepted and registered")

    try:
        # Send initial cache status on connection
        async with LightRAGDocumentCache() as cache:
            is_rebuilding = await cache.is_rebuilding()
            last_sync_time = await cache.get_last_sync_time()

        initial_message = {
            "type": "cache_status",
            "is_rebuilding": is_rebuilding,
            "last_sync_time": last_sync_time,
        }

        logger.info("📤 Sending initial cache status", message=initial_message)
        await websocket.send_json(initial_message)
        logger.info("✅ Initial cache status sent successfully")

        # Keep connection alive and wait for disconnect
        logger.info("👂 Entering message receive loop (keeping connection alive)")
        while True:
            # Wait for any message from client (can be used for ping/pong)
            msg = await websocket.receive_text()
            logger.debug("📩 Received ping from client", message=msg)

    except WebSocketDisconnect:
        logger.info("🔌 WebSocket client disconnected normally")
    except Exception as e:
        logger.error(
            "❌ WebSocket error", error_type=type(e).__name__, error_message=str(e)
        )
    finally:
        logger.info("🧹 Cleaning up WebSocket connection")
        websocket_manager.disconnect(websocket)
        logger.info("✅ WebSocket cleanup complete")


@config_router.get("/config", response_model=ConfigResponse)
async def get_config():
    """Get API configuration including base URL for LAN discovery."""
    settings = get_settings()

    # Determine the API base URL
    if settings.enable_lan_discovery and settings.host_ip:
        api_base_url = f"http://{settings.host_ip}:8000"
    else:
        api_base_url = "http://localhost:8000"

    return ConfigResponse(
        api_base_url=api_base_url, lan_discovery_enabled=settings.enable_lan_discovery
    )


@adr_router.get("/personas")
async def list_personas():
    """List all available analysis personas dynamically from config files (discovers new personas automatically)."""
    from src.persona_manager import get_persona_manager

    persona_manager = get_persona_manager()
    personas = []

    # Discover all personas from filesystem (includes new JSON files)
    all_personas = persona_manager.discover_all_personas()

    for persona_value, config in all_personas.items():
        personas.append(
            PersonaInfo(
                value=persona_value, label=config.name, description=config.description
            )
        )

    return {"personas": personas}


@adr_router.get("/", response_model=ADRListResponse)
async def list_adrs(limit: int = 50, offset: int = 0):
    """List all ADRs."""
    try:
        from src.adr_file_storage import get_adr_storage
        
        # Get ADRs from file storage
        storage = get_adr_storage()
        adrs, total = storage.list_adrs(limit=limit, offset=offset)
        
        # If no ADRs in storage, return demo ADRs
        if total == 0:
            from src.models import ADR, ADRMetadata, ADRContent, ADRStatus

            sample_adrs = [
                ADR(
                    metadata=ADRMetadata(
                        title="Database Selection for User Management System",
                        status=ADRStatus.ACCEPTED,
                        author="Architecture Team",
                        tags=["database", "postgresql", "scalability"]
                    ),
                    content=ADRContent(
                        context_and_problem="We need to choose a database technology for our new microservice architecture that handles user management, requiring ACID transactions and complex querying capabilities.",
                        decision_outcome="Adopt PostgreSQL as the primary database technology",
                        consequences="Benefits: ACID compliance, rich querying features, JSON support. Drawbacks: Higher resource usage compared to simpler alternatives.",
                        considered_options=["PostgreSQL", "MySQL", "MongoDB"],
                        decision_drivers=["ACID requirements", "Complex querying needs", "Team familiarity"],
                        pros_and_cons={
                            "PostgreSQL": ["Mature ecosystem", "Excellent documentation", "ACID compliance"],
                            "MySQL": ["Good performance", "Wide adoption"],
                            "MongoDB": ["Flexible schema", "Good for unstructured data"]
                        },
                        more_information="Migration plan: Phase 1 - Schema design, Phase 2 - Data migration, Phase 3 - Application updates"
                    )
                ),
                ADR(
                    metadata=ADRMetadata(
                        title="API Gateway Implementation Strategy",
                        status=ADRStatus.PROPOSED,
                        author="DevOps Team",
                        tags=["api", "gateway", "microservices"]
                    ),
                    content=ADRContent(
                        context_and_problem="With our move to microservices, we need a centralized entry point for API management, security, and monitoring.",
                        decision_outcome="Implement Kong API Gateway with custom plugins",
                        consequences="Centralized control over API traffic, improved security, but added complexity in deployment.",
                        considered_options=["Kong", "NGINX", "AWS API Gateway"],
                        decision_drivers=["Microservices architecture", "Security requirements", "Monitoring needs"],
                        pros_and_cons={
                            "Kong": ["Highly extensible", "Good performance", "Active community"],
                            "NGINX": ["High performance", "Mature technology"],
                            "AWS API Gateway": ["Managed service", "Easy integration with AWS"]
                        },
                        more_information="Plugin development required for custom authentication and rate limiting."
                    )
                )
            ]
            return ADRListResponse(adrs=sample_adrs, total=len(sample_adrs))

        return ADRListResponse(adrs=adrs, total=total)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list ADRs: {str(e)}")


@adr_router.get("/{adr_id}")
async def get_adr(adr_id: str):
    """Get a specific ADR by ID."""
    try:
        # For now, return not found - we'll implement proper storage later
        raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ADR: {str(e)}")


@adr_router.delete("/{adr_id}")
async def delete_adr(adr_id: str):
    """Delete an ADR by ID."""
    try:
        from src.adr_file_storage import get_adr_storage
        from src.lightrag_client import LightRAGClient
        from src.lightrag_doc_cache import LightRAGDocumentCache
        from src.config import settings

        storage = get_adr_storage()

        # Delete from file storage
        deleted_from_storage = storage.delete_adr(adr_id)

        if not deleted_from_storage:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Try to delete from LightRAG (if it exists there)
        try:
            # First, try to get the LightRAG document ID from cache
            lightrag_doc_id = None
            try:
                async with LightRAGDocumentCache() as cache:
                    lightrag_doc_id = await cache.get_doc_id(adr_id)
                    if lightrag_doc_id:
                        logger.info(
                            f"Found LightRAG doc ID in cache for {adr_id}: {lightrag_doc_id}"
                        )
                        # Remove from cache after getting the ID
                        await cache.delete_doc_id(adr_id)
            except Exception as cache_error:
                logger.warning(f"Failed to get doc ID from cache: {cache_error}")

            # Delete from LightRAG using the cached doc ID if available
            async with LightRAGClient(
                base_url=settings.lightrag_url,
                demo_mode=False
            ) as rag_client:
                deleted = await rag_client.delete_document(adr_id, lightrag_doc_id)
                if deleted:
                    logger.info(f"Deleted ADR {adr_id} from LightRAG")
                else:
                    logger.warning(f"ADR {adr_id} not found in LightRAG")
        except Exception as rag_error:
            # Log but don't fail if RAG deletion fails
            logger.warning(f"Failed to delete from LightRAG: {rag_error}")

        return {"message": f"ADR {adr_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete ADR: {str(e)}")


async def _push_adr_to_rag_internal(adr: "ADR") -> dict:
    """Internal helper to push an ADR to LightRAG for indexing.

    Args:
        adr: The ADR object to push

    Returns:
        dict with result information

    Raises:
        Exception: If push to RAG fails
    """
    from src.lightrag_client import LightRAGClient
    from src.config import settings

    # Format ADR content for LightRAG
    adr_content = f"""Title: {adr.metadata.title}
Status: {adr.metadata.status}
Author: {adr.metadata.author}
Tags: {', '.join(adr.metadata.tags)}

Context & Problem:
{adr.content.context_and_problem}

Decision Outcome:
{adr.content.decision_outcome}

Consequences:
{adr.content.consequences}

Decision Drivers:
{chr(10).join(f"- {driver}" for driver in adr.content.decision_drivers) if adr.content.decision_drivers else "None specified"}

Considered Options:
{chr(10).join(f"- {opt}" for opt in adr.content.considered_options) if adr.content.considered_options else "None specified"}
"""

    # Push to LightRAG
    async with LightRAGClient(
        base_url=settings.lightrag_url, demo_mode=False
    ) as rag_client:
        result = await rag_client.store_document(
            doc_id=str(adr.metadata.id),
            content=adr_content,
            metadata={
                "type": "adr",
                "title": adr.metadata.title,
                "status": adr.metadata.status,
                "author": adr.metadata.author,
                "tags": adr.metadata.tags,
                "created_at": adr.metadata.created_at.isoformat(),
            },
        )
        logger.info(f"Pushed ADR {adr.metadata.id} to LightRAG")

        # Check if we got a track_id for monitoring upload status
        track_id = result.get("track_id")

        if track_id:
            # Store upload status and start monitoring task
            from src.lightrag_doc_cache import LightRAGDocumentCache
            from src.celery_app import monitor_upload_status_task

            async with LightRAGDocumentCache() as cache:
                await cache.set_upload_status(
                    adr_id=str(adr.metadata.id),
                    track_id=track_id,
                    status="processing",
                    message="Document uploaded to LightRAG, processing...",
                )

            logger.info(
                f"ADR {adr.metadata.id} upload started with tracking",
                extra={"track_id": track_id},
            )

            # Start background task to monitor upload status
            monitor_upload_status_task.delay(str(adr.metadata.id), track_id)
        else:
            # No track_id, trigger background sync (old behavior)
            try:
                from src.lightrag_sync import sync_single_document

                asyncio.create_task(sync_single_document(str(adr.metadata.id)))
            except Exception as sync_error:
                logger.warning(f"Failed to trigger cache sync: {sync_error}")

        return result


@adr_router.post("/{adr_id}/push-to-rag")
async def push_adr_to_rag(adr_id: str):
    """Push an ADR to LightRAG for indexing."""
    try:
        from src.adr_file_storage import get_adr_storage
        from src.lightrag_doc_cache import LightRAGDocumentCache

        # Check if cache is currently rebuilding
        try:
            async with LightRAGDocumentCache() as cache:
                is_rebuilding = await cache.is_rebuilding()
                if is_rebuilding:
                    raise HTTPException(
                        status_code=503,
                        detail="Cache is currently rebuilding. Please try again in a moment.",
                    )
        except Exception as cache_error:
            logger.warning(f"Failed to check cache rebuild status: {cache_error}")
            # Continue anyway if we can't check cache status

        storage = get_adr_storage()
        adr = storage.get_adr(adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        await _push_adr_to_rag_internal(adr)

        return {
            "message": f"ADR {adr_id} pushed to RAG successfully",
            "adr_id": adr_id,
            "title": adr.metadata.title,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to push ADR to RAG: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to push ADR to RAG: {str(e)}"
        )


@adr_router.get("/{adr_id}/rag-status")
async def get_adr_rag_status(adr_id: str):
    """Check if an ADR exists in LightRAG and get upload status if processing."""
    try:
        from src.lightrag_doc_cache import LightRAGDocumentCache

        async with LightRAGDocumentCache() as cache:
            # Check if document exists in cache
            doc_id = await cache.get_doc_id(adr_id)
            exists_in_rag = doc_id is not None

            # Check if there's an active upload being tracked
            upload_status = await cache.get_upload_status(adr_id)

        return {
            "adr_id": adr_id,
            "exists_in_rag": exists_in_rag,
            "lightrag_doc_id": doc_id,
            "upload_status": upload_status,  # Will be None if not being tracked
        }
    except Exception as e:
        logger.error(f"Failed to check RAG status for {adr_id}: {str(e)}")
        # Return unknown status if we can't check
        return {"adr_id": adr_id, "exists_in_rag": None, "error": str(e)}


@adr_router.get("/cache/status")
async def get_cache_status():
    """Get the LightRAG cache status including rebuild state and last sync time."""
    try:
        from src.lightrag_doc_cache import LightRAGDocumentCache

        async with LightRAGDocumentCache() as cache:
            is_rebuilding = await cache.is_rebuilding()
            last_sync_time = await cache.get_last_sync_time()

        return {
            "is_rebuilding": is_rebuilding,
            "last_sync_time": last_sync_time
        }
    except Exception as e:
        logger.error(f"Failed to check cache status: {str(e)}")
        return {
            "is_rebuilding": False,
            "last_sync_time": None,
            "error": str(e)
        }


@adr_router.get("/cache/rebuild-status")
async def get_cache_rebuild_status():
    """Check if the LightRAG cache is currently being rebuilt.
    
    DEPRECATED: Use /cache/status instead for more complete information.
    """
    try:
        from src.lightrag_doc_cache import LightRAGDocumentCache

        async with LightRAGDocumentCache() as cache:
            is_rebuilding = await cache.is_rebuilding()

        return {"is_rebuilding": is_rebuilding}
    except Exception as e:
        logger.error(f"Failed to check cache rebuild status: {str(e)}")
        return {"is_rebuilding": False, "error": str(e)}


@adr_router.post("/cache/rebuild")
async def trigger_cache_rebuild(background_tasks: BackgroundTasks):
    """Manually trigger a cache rebuild.

    This is useful when you've made changes to LightRAG directly (e.g., deleted documents)
    and need to sync the cache immediately rather than waiting for the scheduled sync.
    """
    try:
        from src.lightrag_doc_cache import LightRAGDocumentCache

        # Check if already rebuilding
        async with LightRAGDocumentCache() as cache:
            is_rebuilding = await cache.is_rebuilding()
            if is_rebuilding:
                return {
                    "message": "Cache rebuild is already in progress",
                    "status": "already_running",
                }

        # Trigger rebuild in background
        from src.lightrag_sync import _sync_lightrag_cache

        async def run_rebuild():
            try:
                count = await _sync_lightrag_cache()
                logger.info(f"Manual cache rebuild completed: {count} documents synced")
            except Exception as e:
                logger.error(f"Manual cache rebuild failed: {str(e)}")

        background_tasks.add_task(lambda: asyncio.create_task(run_rebuild()))

        return {"message": "Cache rebuild triggered successfully", "status": "started"}
    except Exception as e:
        logger.error(f"Failed to trigger cache rebuild: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger cache rebuild: {str(e)}"
        )


@analysis_router.post("/analyze", response_model=TaskResponse)
async def analyze_adr(request: AnalyzeADRRequest, background_tasks: BackgroundTasks):
    """Queue an ADR for analysis."""
    try:
        # Queue the analysis task
        task = analyze_adr_task.delay(
            adr_id=request.adr_id,
            persona=request.persona
        )

        return TaskResponse(
            task_id=task.id,
            status="queued",
            message="ADR analysis queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue analysis: {str(e)}")


@generation_router.post("/generate", response_model=TaskResponse)
async def generate_adr(request: GenerateADRRequest, background_tasks: BackgroundTasks):
    """Queue ADR generation."""
    try:
        # Queue the generation task
        task = generate_adr_task.delay(
            prompt=request.prompt,
            context=request.context,
            tags=request.tags or [],
            personas=request.personas or []
        )

        return TaskResponse(
            task_id=task.id,
            status="queued",
            message="ADR generation queued successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue generation: {str(e)}")


@analysis_router.get("/task/{task_id}")
async def get_analysis_task_status(task_id: str):
    """Get the status of an analysis task."""
    try:
        from src.celery_app import celery_app
        task_result = celery_app.AsyncResult(task_id)

        if task_result.state == "PENDING":
            response = {"status": "pending", "message": "Task is waiting in queue"}
        elif task_result.state == "PROGRESS":
            response = {"status": "progress", "message": task_result.info.get("message", "Processing...")}
        elif task_result.state == "SUCCESS":
            response = {"status": "completed", "message": "Analysis completed successfully", "result": task_result.result}
        else:
            response = {"status": "failed", "message": "Analysis failed", "error": str(task_result.info)}

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@generation_router.get("/task/{task_id}")
async def get_generation_task_status(task_id: str):
    """Get the status of a generation task."""
    try:
        from src.celery_app import celery_app
        task_result = celery_app.AsyncResult(task_id)

        if task_result.state == "PENDING":
            response = {"status": "pending", "message": "Task is waiting in queue"}
        elif task_result.state == "PROGRESS":
            response = {"status": "progress", "message": task_result.info.get("message", "Generating ADR...")}
        elif task_result.state == "SUCCESS":
            # Extract title from result for a more informative message
            title = (
                task_result.result.get("title", "ADR")
                if isinstance(task_result.result, dict)
                else "ADR"
            )
            response = {
                "status": "completed",
                "message": f'✓ "{title}" generated successfully',
                "result": task_result.result,
            }
        else:
            response = {"status": "failed", "message": "Generation failed", "error": str(task_result.info)}

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


# ==================== Export/Import Endpoints ====================


@adr_router.post("/export", response_class=StreamingResponse)
async def export_adrs_bulk(request: ExportRequest):
    """Export ADRs in bulk (all or selected) with versioned schema support.

    Returns a downloadable file in the requested format.
    """
    try:
        from src.adr_file_storage import get_adr_storage
        from src.adr_import_export import ADRImportExport

        storage = get_adr_storage()

        # Get ADRs to export
        if request.adr_ids:
            # Export specific ADRs
            adrs = []
            for adr_id in request.adr_ids:
                adr = storage.get_adr(adr_id)
                if adr:
                    adrs.append(adr)
                else:
                    logger.warning(f"ADR {adr_id} not found, skipping")
        else:
            # Export all ADRs
            adrs, _ = storage.list_adrs(limit=10000)  # Get all

        if not adrs:
            raise HTTPException(status_code=404, detail="No ADRs found to export")

        # Generate export based on format
        if request.format == "versioned_json":
            export_data = ADRImportExport.export_bulk_versioned(
                adrs, exported_by=request.exported_by
            )
            content = json.dumps(
                export_data.model_dump(mode="json"), indent=2, ensure_ascii=False
            )
            filename = f"adrs_export_{len(adrs)}_records.json"
            media_type = "application/json"
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported export format: {request.format}"
            )

        # Return as streaming response for download
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export ADRs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export ADRs: {str(e)}")


@adr_router.get("/{adr_id}/export", response_class=StreamingResponse)
async def export_single_adr(
    adr_id: str, format: str = "versioned_json", exported_by: Optional[str] = None
):
    """Export a single ADR with versioned schema support.

    Returns a downloadable file in the requested format.
    """
    try:
        from src.adr_file_storage import get_adr_storage
        from src.adr_import_export import ADRImportExport

        storage = get_adr_storage()
        adr = storage.get_adr(adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Generate export based on format
        if format == "versioned_json":
            export_data = ADRImportExport.export_single_versioned(
                adr, exported_by=exported_by
            )
            content = json.dumps(
                export_data.model_dump(mode="json"), indent=2, ensure_ascii=False
            )
            filename = f"adr_{adr_id}.json"
            media_type = "application/json"
        elif format == "markdown":
            content = adr.to_markdown()
            filename = f"adr_{adr_id}.md"
            media_type = "text/markdown"
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported export format: {format}"
            )

        # Return as streaming response for download
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export ADR {adr_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export ADR: {str(e)}")


@adr_router.post("/import", response_model=ImportResponse)
async def import_adrs_bulk(request: ImportRequest):
    """Import ADRs in bulk from versioned schema format.

    Accepts JSON data with versioned schema. Supports both single and bulk formats.
    Automatically detects the format based on the presence of 'adr' or 'adrs' field.
    """
    try:
        from src.adr_file_storage import get_adr_storage
        from src.adr_import_export import ADRImportExport

        storage = get_adr_storage()

        # Detect whether this is a single or bulk export format
        # Single exports have 'adr' field, bulk exports have 'adrs' field
        is_single_export = "adr" in request.data and "adrs" not in request.data

        # Import ADRs from versioned schema
        try:
            if is_single_export:
                # Single ADR format - import as a list of one
                adr = ADRImportExport.import_single_versioned(request.data)
                adrs = [adr]
            else:
                # Bulk ADR format
                adrs = ADRImportExport.import_bulk_versioned(request.data)
        except ValueError as ve:
            raise HTTPException(
                status_code=400, detail=f"Invalid import data: {str(ve)}"
            )

        imported_count = 0
        skipped_count = 0
        errors = []

        for adr in adrs:
            adr_id = str(adr.metadata.id)

            # Check if ADR already exists
            existing_adr = storage.get_adr(adr_id)

            if existing_adr and not request.overwrite_existing:
                skipped_count += 1
                errors.append(
                    f"ADR {adr_id} already exists (use overwrite_existing=true to replace)"
                )
                continue

            try:
                # Save ADR
                storage.save_adr(adr)
                imported_count += 1
                logger.info(f"Imported ADR {adr_id}: {adr.metadata.title}")

                # Automatically push to RAG for indexing
                try:
                    await _push_adr_to_rag_internal(adr)
                    logger.info(f"Auto-pushed imported ADR {adr_id} to RAG")
                except Exception as rag_error:
                    # Log the error but don't fail the import
                    logger.warning(
                        f"Failed to push ADR {adr_id} to RAG: {str(rag_error)}"
                    )
                    # Note: We continue with the import even if RAG push fails

            except Exception as e:
                errors.append(f"Failed to import ADR {adr_id}: {str(e)}")
                logger.error(f"Failed to import ADR {adr_id}: {str(e)}")

        return ImportResponse(
            message=f"Import completed: {imported_count} imported, {skipped_count} skipped",
            imported_count=imported_count,
            skipped_count=skipped_count,
            errors=errors,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import ADRs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import ADRs: {str(e)}")


@adr_router.post("/import/file", response_model=ImportResponse)
async def import_adrs_from_file(
    file: UploadFile = File(...), overwrite_existing: bool = False
):
    """Import ADRs from an uploaded file (versioned JSON format).

    Accepts a file upload containing versioned schema data.
    """
    try:
        from src.adr_import_export import ADRImportExport

        # Read file content
        content = await file.read()

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON file")

        # Use the bulk import endpoint logic
        import_request = ImportRequest(data=data, overwrite_existing=overwrite_existing)
        return await import_adrs_bulk(import_request)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import from file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to import from file: {str(e)}"
        )


@adr_router.post("/import/single", response_model=ImportResponse)
async def import_single_adr(request: ImportRequest):
    """Import a single ADR from versioned schema format.

    Accepts JSON data with versioned schema for a single ADR.
    """
    try:
        from src.adr_file_storage import get_adr_storage
        from src.adr_import_export import ADRImportExport

        storage = get_adr_storage()

        # Import single ADR from versioned schema
        try:
            adr = ADRImportExport.import_single_versioned(request.data)
        except ValueError as ve:
            raise HTTPException(
                status_code=400, detail=f"Invalid import data: {str(ve)}"
            )

        adr_id = str(adr.metadata.id)

        # Check if ADR already exists
        existing_adr = storage.get_adr(adr_id)

        if existing_adr and not request.overwrite_existing:
            return ImportResponse(
                message=f"ADR {adr_id} already exists",
                imported_count=0,
                skipped_count=1,
                errors=[
                    f"ADR {adr_id} already exists (use overwrite_existing=true to replace)"
                ],
            )

        # Save ADR
        storage.save_adr(adr)
        logger.info(f"Imported ADR {adr_id}: {adr.metadata.title}")

        # Automatically push to RAG for indexing
        try:
            await _push_adr_to_rag_internal(adr)
            logger.info(f"Auto-pushed imported ADR {adr_id} to RAG")
        except Exception as rag_error:
            # Log the error but don't fail the import
            logger.warning(f"Failed to push ADR {adr_id} to RAG: {str(rag_error)}")

        return ImportResponse(
            message=f"Successfully imported ADR: {adr.metadata.title}",
            imported_count=1,
            skipped_count=0,
            errors=[],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import ADR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import ADR: {str(e)}")
