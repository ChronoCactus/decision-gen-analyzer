"""API routes for Decision Analyzer."""

import asyncio
import io
import json
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.celery_app import analyze_adr_task, generate_adr_task
from src.config import get_settings
from src.lightrag_client import LightRAGClient
from src.logger import get_logger
from src.models import ADR

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
    retrieval_mode: Optional[str] = "naive"  # RAG retrieval mode
    persona_provider_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map of persona name to provider ID override",
    )
    synthesis_provider_id: Optional[str] = Field(
        default=None,
        description="Provider ID for synthesis generation",
    )
    record_type: Optional[str] = "decision"
    mcp_tools: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="List of MCP tools to use: [{server_id, tool_name, arguments?}] (deprecated)",
    )
    use_mcp: Optional[bool] = Field(
        default=False,
        description="Whether to use AI-driven MCP tool orchestration for research",
    )
    status_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter referenced ADRs by status values (e.g., ['accepted', 'proposed']). If None, all statuses are included.",
    )


class PersonaRefinementItem(BaseModel):
    """Individual persona refinement."""

    persona: str
    refinement_prompt: str


class RefinePersonasRequest(BaseModel):
    """Request model for refining personas in an existing ADR."""

    refinements: List[PersonaRefinementItem]
    refinements_to_delete: Optional[Dict[str, List[int]]] = Field(
        default=None,
        description="Map of persona name to list of refinement indices to delete",
    )
    persona_provider_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map of persona name to provider ID override",
    )
    synthesis_provider_id: Optional[str] = Field(
        default=None,
        description="Provider ID to use for synthesis step (separate from persona generation)",
    )


class TaskResponse(BaseModel):
    """Response model for queued tasks."""

    task_id: str
    status: str
    message: str


class ModelConfigInfo(BaseModel):
    """Model configuration information."""

    name: str
    provider: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    num_ctx: Optional[int] = None


class PersonaInfo(BaseModel):
    """Information about an analysis persona."""

    value: str
    label: str
    description: str
    llm_config: Optional[ModelConfigInfo] = None


class DefaultModelConfig(BaseModel):
    """Default model configuration from environment."""

    model: str
    provider: str
    base_url: str
    temperature: float
    num_ctx: int


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
    imported_ids: List[str] = []


# Create routers
adr_router = APIRouter()
analysis_router = APIRouter()
generation_router = APIRouter()
config_router = APIRouter()
queue_router = APIRouter()
provider_router = APIRouter()
mcp_router = APIRouter()
mcp_results_router = APIRouter()


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
    from src.lightrag_doc_cache import LightRAGDocumentCache
    from src.websocket_manager import get_websocket_manager

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
    """Get API configuration including base URL for LAN discovery.

    Returns the API base URL with the following priority:
    1. API_BASE_URL env var (explicit, e.g., https://mysite.com for production)
    2. LAN discovery (http://{HOST_IP}:8000 if ENABLE_LAN_DISCOVERY=true)
    3. Localhost fallback (http://localhost:8000)
    """
    settings = get_settings()

    # Priority 1: Explicit API_BASE_URL (for production behind load balancer)
    if settings.api_base_url:
        api_base_url = settings.api_base_url
    # Priority 2: LAN discovery (for development access from other machines)
    elif settings.enable_lan_discovery and settings.host_ip:
        api_base_url = f"http://{settings.host_ip}:8000"
    # Priority 3: Localhost fallback (local development)
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
        # Convert model_config to API format if present
        llm_config_info = None
        if config.model_config:
            mc = config.model_config
            llm_config_info = ModelConfigInfo(
                name=mc.name,
                provider=mc.provider,
                base_url=mc.base_url,
                temperature=mc.temperature,
                num_ctx=mc.num_ctx,
            )

        personas.append(
            PersonaInfo(
                value=persona_value,
                label=config.name,
                description=config.description,
                llm_config=llm_config_info,
            )
        )

    return {"personas": personas}


@adr_router.get("/config/model")
async def get_default_model_config():
    """Get the default model configuration from environment variables."""
    settings = get_settings()

    return DefaultModelConfig(
        model=settings.llm_model,
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        num_ctx=settings.ollama_num_ctx,
    )


@adr_router.get("/", response_model=ADRListResponse)
async def list_adrs(limit: int = 50, offset: int = 0):
    """List all ADRs."""
    try:
        from src.adr_file_storage import get_adr_storage

        # Get ADRs from file storage (run in thread pool - blocking file I/O)
        storage = get_adr_storage()
        adrs, total = await asyncio.to_thread(storage.list_adrs, limit, offset)

        # If no ADRs in storage, return demo ADRs
        if total == 0:
            from src.models import ADR, ADRContent, ADRMetadata, ADRStatus

            sample_adrs = [
                ADR(
                    metadata=ADRMetadata(
                        title="Database Selection for User Management System",
                        status=ADRStatus.ACCEPTED,
                        author="Architecture Team",
                        tags=["database", "postgresql", "scalability"],
                    ),
                    content=ADRContent(
                        context_and_problem="We need to choose a database technology for our new microservice architecture that handles user management, requiring ACID transactions and complex querying capabilities.",
                        decision_outcome="Adopt PostgreSQL as the primary database technology",
                        consequences="Benefits: ACID compliance, rich querying features, JSON support. Drawbacks: Higher resource usage compared to simpler alternatives.",
                        considered_options=["PostgreSQL", "MySQL", "MongoDB"],
                        decision_drivers=[
                            "ACID requirements",
                            "Complex querying needs",
                            "Team familiarity",
                        ],
                        pros_and_cons={
                            "PostgreSQL": [
                                "Mature ecosystem",
                                "Excellent documentation",
                                "ACID compliance",
                            ],
                            "MySQL": ["Good performance", "Wide adoption"],
                            "MongoDB": [
                                "Flexible schema",
                                "Good for unstructured data",
                            ],
                        },
                        more_information="Migration plan: Phase 1 - Schema design, Phase 2 - Data migration, Phase 3 - Application updates",
                    ),
                ),
                ADR(
                    metadata=ADRMetadata(
                        title="API Gateway Implementation Strategy",
                        status=ADRStatus.PROPOSED,
                        author="DevOps Team",
                        tags=["api", "gateway", "microservices"],
                    ),
                    content=ADRContent(
                        context_and_problem="With our move to microservices, we need a centralized entry point for API management, security, and monitoring.",
                        decision_outcome="Implement Kong API Gateway with custom plugins",
                        consequences="Centralized control over API traffic, improved security, but added complexity in deployment.",
                        considered_options=["Kong", "NGINX", "AWS API Gateway"],
                        decision_drivers=[
                            "Microservices architecture",
                            "Security requirements",
                            "Monitoring needs",
                        ],
                        pros_and_cons={
                            "Kong": [
                                "Highly extensible",
                                "Good performance",
                                "Active community",
                            ],
                            "NGINX": ["High performance", "Mature technology"],
                            "AWS API Gateway": [
                                "Managed service",
                                "Easy integration with AWS",
                            ],
                        },
                        more_information="Plugin development required for custom authentication and rate limiting.",
                    ),
                ),
            ]
            return ADRListResponse(adrs=sample_adrs, total=len(sample_adrs))

        return ADRListResponse(adrs=adrs, total=total)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list ADRs: {str(e)}")


@adr_router.get("/{adr_id}")
async def get_adr(adr_id: str):
    """Get a specific ADR by ID."""
    try:
        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        return adr
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ADR {adr_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get ADR: {str(e)}")


@adr_router.delete("/{adr_id}")
async def delete_adr(adr_id: str):
    """Delete an ADR by ID."""
    try:
        from src.adr_file_storage import get_adr_storage
        from src.config import settings
        from src.lightrag_client import LightRAGClient
        from src.lightrag_doc_cache import LightRAGDocumentCache

        storage = get_adr_storage()

        # Delete from file storage (run in thread pool - uses blocking file I/O)
        deleted_from_storage = await asyncio.to_thread(storage.delete_adr, adr_id)

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
                base_url=settings.lightrag_url, demo_mode=False
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


@adr_router.post("/{adr_id}/refine-personas", response_model=TaskResponse)
async def refine_personas(adr_id: str, request: RefinePersonasRequest):
    """Refine specific personas in an existing ADR and re-synthesize."""
    try:
        from src.celery_app import refine_personas_task

        # Convert refinements list to dict
        persona_refinements = {
            item.persona: item.refinement_prompt for item in request.refinements
        }

        # Queue the refinement task
        task = refine_personas_task.delay(
            adr_id=adr_id,
            persona_refinements=persona_refinements,
            refinements_to_delete=request.refinements_to_delete or {},
            persona_provider_overrides=request.persona_provider_overrides or {},
            synthesis_provider_id=request.synthesis_provider_id,
        )

        return TaskResponse(
            task_id=task.id,
            status="queued",
            message=f"Persona refinement queued for {len(persona_refinements)} persona(s)",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to queue persona refinement: {str(e)}"
        )


class RefineOriginalPromptRequest(BaseModel):
    """Request model for refining the original generation prompt."""

    title: Optional[str] = None
    context: Optional[str] = None
    problem_statement: Optional[str] = None
    constraints: Optional[List[str]] = None
    stakeholders: Optional[List[str]] = None
    retrieval_mode: Optional[str] = None
    persona_provider_overrides: Optional[Dict[str, str]] = Field(
        default=None,
        description="Map of persona name to provider ID override",
    )
    synthesis_provider_id: Optional[str] = Field(
        default=None,
        description="Provider ID for synthesis generation",
    )


@adr_router.post("/{adr_id}/refine-original-prompt", response_model=TaskResponse)
async def refine_original_prompt(adr_id: str, request: RefineOriginalPromptRequest):
    """Refine the original generation prompt and regenerate all personas.

    This endpoint allows you to update the original prompt used to generate the ADR.
    All personas will be regenerated with the new prompt, and any existing persona
    refinements will be preserved and re-applied.

    Args:
        adr_id: The ADR ID to refine
        request: The refined prompt fields (only fields you want to update)

    Returns:
        TaskResponse with task_id for tracking the refinement
    """
    try:
        from src.celery_app import refine_original_prompt_task

        # Build dict of refined fields (exclude None values and provider IDs)
        refined_prompt_fields = {}
        if request.title is not None:
            refined_prompt_fields["title"] = request.title
        if request.context is not None:
            refined_prompt_fields["context"] = request.context
        if request.problem_statement is not None:
            refined_prompt_fields["problem_statement"] = request.problem_statement
        if request.constraints is not None:
            refined_prompt_fields["constraints"] = request.constraints
        if request.stakeholders is not None:
            refined_prompt_fields["stakeholders"] = request.stakeholders
        if request.retrieval_mode is not None:
            refined_prompt_fields["retrieval_mode"] = request.retrieval_mode

        if not refined_prompt_fields:
            raise HTTPException(
                status_code=400,
                detail="At least one prompt field must be provided for refinement",
            )

        # Queue the refinement task with per-persona provider overrides
        task = refine_original_prompt_task.delay(
            adr_id=adr_id,
            refined_prompt_fields=refined_prompt_fields,
            persona_provider_overrides=request.persona_provider_overrides or {},
            synthesis_provider_id=request.synthesis_provider_id,
        )

        return TaskResponse(
            task_id=task.id,
            status="queued",
            message=f"Original prompt refinement queued with {len(refined_prompt_fields)} updated field(s)",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue original prompt refinement: {str(e)}",
        )


class ManualPersonaEditsRequest(BaseModel):
    """Request model for manually editing persona responses."""

    persona_responses: List[Dict[str, Any]]
    resynthesize: bool = False
    synthesis_provider_id: Optional[str] = Field(
        default=None,
        description="Provider ID for synthesis generation (if resynthesize=True)",
    )


@adr_router.post("/{adr_id}/manual-persona-edits", response_model=TaskResponse)
async def save_manual_persona_edits(adr_id: str, request: ManualPersonaEditsRequest):
    """Save manually edited persona responses and optionally resynthesize.

    This endpoint allows direct manual editing of persona responses without regenerating them via AI.
    If resynthesize=True, it will synthesize a new final decision record from the edited personas.
    If resynthesize=False, it will just save the manual edits without any AI generation.

    Args:
        adr_id: The ADR ID to update
        request: The manually edited persona responses and resynthesize flag

    Returns:
        TaskResponse with task_id if resynthesizing, or immediate success message
    """
    try:
        from datetime import UTC, datetime

        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Update persona_responses with the manually edited data
        adr.persona_responses = request.persona_responses
        adr.metadata.updated_at = datetime.now(UTC)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        if request.resynthesize:
            # Queue synthesis task using the manually edited personas
            from src.celery_app import resynthesize_from_personas_task

            task = resynthesize_from_personas_task.delay(
                adr_id=adr_id,
                synthesis_provider_id=request.synthesis_provider_id,
            )

            return TaskResponse(
                task_id=task.id,
                status="queued",
                message="Manual edits saved and resynthesis queued",
            )
        else:
            # Just return success without queuing any tasks
            return TaskResponse(
                task_id="",
                status="completed",
                message="Manual edits saved successfully (no resynthesis)",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save manual persona edits: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save manual persona edits: {str(e)}"
        )


class ManualADREditRequest(BaseModel):
    """Request model for manually editing the final ADR content."""

    content: Dict[str, Any]


@adr_router.patch("/{adr_id}/manual-edit")
async def save_manual_adr_edit(adr_id: str, request: ManualADREditRequest):
    """Save manually edited ADR content without any AI regeneration.

    This endpoint allows direct manual editing of the final synthesized ADR content.
    No AI regeneration or synthesis is triggered - this is a pure manual save operation.

    Args:
        adr_id: The ADR ID to update
        request: The manually edited ADR content

    Returns:
        Success message with updated ADR
    """
    try:
        from datetime import UTC, datetime

        from src.adr_file_storage import get_adr_storage
        from src.models import ADRContent

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Update content with manually edited data
        # Use Pydantic to validate the content structure
        try:
            adr.content = ADRContent(**request.content)
        except Exception as validation_error:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid ADR content structure: {str(validation_error)}",
            )

        adr.metadata.updated_at = datetime.now(UTC)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        logger.info(f"Saved manual edit for ADR {adr_id}")

        return {"message": "Manual edit saved successfully", "adr": adr}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save manual ADR edit: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save manual ADR edit: {str(e)}"
        )


class UpdateStatusRequest(BaseModel):
    """Request model for updating ADR status."""

    status: str


@adr_router.patch("/{adr_id}/status")
async def update_adr_status(adr_id: str, request: UpdateStatusRequest):
    """Update the status of an ADR."""
    try:
        from datetime import UTC, datetime

        from src.adr_file_storage import get_adr_storage
        from src.models import ADRStatus

        # Validate status value
        try:
            new_status = ADRStatus(request.status)
        except ValueError:
            valid_statuses = [status.value for status in ADRStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Update status and updated_at timestamp
        adr.metadata.status = new_status
        adr.metadata.updated_at = datetime.now(UTC)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        logger.info(f"Updated ADR {adr_id} status to {new_status.value}")

        return {"message": f"ADR status updated to {new_status.value}", "adr": adr}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ADR status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update ADR status: {str(e)}"
        )


class UpdateFolderRequest(BaseModel):
    """Request model for updating ADR folder path."""

    folder_path: Optional[str] = Field(
        None, description="Folder path (e.g., '/Architecture/Backend') or null for root"
    )


@adr_router.patch("/{adr_id}/folder")
async def update_adr_folder(adr_id: str, request: UpdateFolderRequest):
    """Update the folder path of an ADR."""
    try:
        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Update folder path using the model method
        adr.set_folder_path(request.folder_path)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        logger.info(f"Updated ADR {adr_id} folder to {adr.metadata.folder_path}")

        return {
            "message": f"ADR folder updated to {adr.metadata.folder_path or 'root'}",
            "adr": adr,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ADR folder: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update ADR folder: {str(e)}"
        )


class UpdateTagsRequest(BaseModel):
    """Request model for updating ADR tags."""

    tags: List[str] = Field(..., description="Complete list of tags for the ADR")


class AddTagRequest(BaseModel):
    """Request model for adding a tag to an ADR."""

    tag: str = Field(..., description="Tag to add")


class RemoveTagRequest(BaseModel):
    """Request model for removing a tag from an ADR."""

    tag: str = Field(..., description="Tag to remove")


@adr_router.patch("/{adr_id}/tags")
async def update_adr_tags(adr_id: str, request: UpdateTagsRequest):
    """Replace all tags on an ADR."""
    try:
        from datetime import UTC, datetime

        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Replace tags
        adr.metadata.tags = request.tags
        adr.metadata.updated_at = datetime.now(UTC)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        logger.info(f"Updated ADR {adr_id} tags to {request.tags}")

        return {"message": "ADR tags updated", "adr": adr}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ADR tags: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update ADR tags: {str(e)}"
        )


@adr_router.post("/{adr_id}/tags")
async def add_adr_tag(adr_id: str, request: AddTagRequest):
    """Add a single tag to an ADR."""
    try:
        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Add tag using model method (handles deduplication)
        adr.add_tag(request.tag)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        logger.info(f"Added tag '{request.tag}' to ADR {adr_id}")

        return {"message": f"Tag '{request.tag}' added", "adr": adr}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add tag to ADR: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add tag: {str(e)}")


@adr_router.delete("/{adr_id}/tags/{tag}")
async def remove_adr_tag(adr_id: str, tag: str):
    """Remove a tag from an ADR."""
    try:
        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()

        # Get the ADR (run in thread pool - uses blocking file I/O)
        adr = await asyncio.to_thread(storage.get_adr, adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        if tag not in adr.metadata.tags:
            raise HTTPException(
                status_code=404, detail=f"Tag '{tag}' not found on ADR {adr_id}"
            )

        # Remove tag using model method
        adr.remove_tag(tag)

        # Save the updated ADR (run in thread pool - uses blocking file I/O)
        await asyncio.to_thread(storage.save_adr, adr)

        logger.info(f"Removed tag '{tag}' from ADR {adr_id}")

        return {"message": f"Tag '{tag}' removed", "adr": adr}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove tag from ADR: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove tag: {str(e)}")


@adr_router.get("/folders/list")
async def list_folders():
    """Get all unique folder paths used by ADRs."""
    try:
        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()
        adrs = await asyncio.to_thread(storage.get_all_adrs)

        # Collect unique folder paths
        folders = set()
        for adr in adrs:
            if adr.metadata.folder_path:
                # Add the folder and all parent folders
                path = adr.metadata.folder_path
                while path and path != "/":
                    folders.add(path)
                    path = "/".join(path.rsplit("/", 1)[:-1]) or None

        # Sort folders alphabetically
        sorted_folders = sorted(folders) if folders else []

        return {"folders": sorted_folders}
    except Exception as e:
        logger.error(f"Failed to list folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list folders: {str(e)}")


@adr_router.get("/tags/list")
async def list_tags():
    """Get all unique tags used by ADRs with counts."""
    try:
        from src.adr_file_storage import get_adr_storage

        storage = get_adr_storage()
        adrs = await asyncio.to_thread(storage.get_all_adrs)

        # Count tag usage
        tag_counts: Dict[str, int] = {}
        for adr in adrs:
            for tag in adr.metadata.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Sort by count (descending) then alphabetically
        sorted_tags = sorted(
            [{"tag": tag, "count": count} for tag, count in tag_counts.items()],
            key=lambda x: (-x["count"], x["tag"]),
        )

        return {"tags": sorted_tags}
    except Exception as e:
        logger.error(f"Failed to list tags: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tags: {str(e)}")


async def _push_adr_to_rag_internal(adr: "ADR") -> dict:
    """Internal helper to push an ADR to LightRAG for indexing.

    Args:
        adr: The ADR object to push

    Returns:
        dict with result information

    Raises:
        Exception: If push to RAG fails
    """
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
        adr_id = str(adr.metadata.id)

        result = await rag_client.store_document(
            doc_id=adr_id,
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
        logger.info(f"Pushed ADR {adr_id} to LightRAG")

        # Check if we got a track_id for monitoring upload status
        track_id = result.get("track_id")
        result_status = result.get("status", "").lower()

        # Handle empty string track_id as None
        if track_id == "":
            track_id = None

        if track_id:
            # Store upload status and start monitoring task
            from src.celery_app import monitor_upload_status_task
            from src.lightrag_doc_cache import LightRAGDocumentCache

            async with LightRAGDocumentCache() as cache:
                await cache.set_upload_status(
                    adr_id=adr_id,
                    track_id=track_id,
                    status="processing",
                    message="Document uploaded to LightRAG, processing...",
                )

            logger.info(
                f"ADR {adr_id} upload started with tracking",
                extra={"track_id": track_id},
            )

            # Start background task to monitor upload status
            monitor_upload_status_task.delay(adr_id, track_id)
        elif result_status == "duplicated":
            # Document already exists in LightRAG - update cache immediately
            from src.lightrag_doc_cache import LightRAGDocumentCache

            logger.info(
                f"Document {adr_id} already exists in LightRAG (duplicated), updating cache"
            )

            async with LightRAGDocumentCache() as cache:
                # Use adr_id as the doc_id since the document exists
                await cache.set_doc_id(adr_id, adr_id)
                logger.info(
                    "Cache updated for existing document",
                    adr_id=adr_id,
                )
        else:
            # No track_id and not duplicated - document may have been processed immediately
            # Verify document exists in LightRAG and reconcile cache
            from src.lightrag_doc_cache import LightRAGDocumentCache

            try:
                # Check if document actually exists in LightRAG
                existing_doc = await rag_client.get_document(adr_id)

                if existing_doc:
                    # Document exists - update cache to reflect this
                    logger.info(
                        f"Document {adr_id} found in LightRAG, reconciling cache"
                    )

                    async with LightRAGDocumentCache() as cache:
                        # Use the document ID from LightRAG if available, otherwise use adr_id
                        lightrag_doc_id = existing_doc.get("id", adr_id)
                        await cache.set_doc_id(adr_id, lightrag_doc_id)
                        logger.info(
                            "Cache updated with existing document ID",
                            adr_id=adr_id,
                            lightrag_doc_id=lightrag_doc_id,
                        )
                else:
                    # Document doesn't exist yet, trigger background sync
                    logger.info(
                        f"Document {adr_id} uploaded but not immediately available, "
                        "triggering background sync"
                    )
                    from src.lightrag_sync import sync_single_document

                    asyncio.create_task(sync_single_document(adr_id))
            except Exception as sync_error:
                logger.warning(
                    f"Failed to verify document or trigger cache sync for {adr_id}: {sync_error}"
                )
                # Continue anyway - the document was uploaded successfully

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
        except HTTPException:
            # Re-raise HTTP exceptions (like 503 for cache rebuilding)
            raise
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


class BatchRAGStatusRequest(BaseModel):
    """Request model for batch RAG status check."""

    adr_ids: List[str] = Field(..., description="List of ADR IDs to check")


@adr_router.post("/batch/rag-status")
async def get_batch_rag_status(request: BatchRAGStatusRequest):
    """Check RAG status for multiple ADRs in a single request.

    This is much more efficient than individual requests, especially for CORS
    where each request requires an OPTIONS preflight.
    """
    try:
        from src.lightrag_doc_cache import LightRAGDocumentCache

        results = []

        async with LightRAGDocumentCache() as cache:
            # Check cache for all ADR IDs
            for adr_id in request.adr_ids:
                doc_id = await cache.get_doc_id(adr_id)
                exists_in_rag = doc_id is not None
                upload_status = await cache.get_upload_status(adr_id)

                results.append(
                    {
                        "adr_id": adr_id,
                        "exists_in_rag": exists_in_rag,
                        "lightrag_doc_id": doc_id,
                        "upload_status": upload_status,
                    }
                )

        return {"statuses": results}
    except Exception as e:
        logger.error(f"Failed to check batch RAG status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check batch RAG status: {str(e)}"
        )


@adr_router.get("/{adr_id}/rag-status")
async def get_adr_rag_status(adr_id: str):
    """Check if an ADR exists in LightRAG and get upload status if processing."""
    try:
        from src.lightrag_client import LightRAGClient
        from src.lightrag_doc_cache import LightRAGDocumentCache

        async with LightRAGDocumentCache() as cache:
            # Check if document exists in cache
            doc_id = await cache.get_doc_id(adr_id)
            exists_in_rag = doc_id is not None

            # If cache miss, verify with LightRAG directly (fallback mechanism)
            # This makes the system resilient to cache expiration
            if not doc_id:
                logger.debug(
                    "Cache miss for ADR, checking LightRAG directly", adr_id=adr_id
                )
                try:
                    async with LightRAGClient(demo_mode=False) as lightrag:
                        # Try to fetch document by constructing the file path
                        file_path = f"data/adrs/{adr_id}.txt"

                        # Search through all pages until we find the document or exhaust all results
                        page = 1
                        page_size = 50  # Reasonable batch size
                        found = False

                        while not found:
                            result = await lightrag.get_paginated_documents(
                                page=page,
                                page_size=page_size,
                                status_filter="processed",
                            )

                            documents = result.get("documents", [])
                            if not documents:
                                # No more documents to check
                                break

                            # Search for matching document in this page
                            for doc in documents:
                                if doc.get("file_path") == file_path:
                                    doc_id = doc.get("id")
                                    if doc_id:
                                        # Found in LightRAG! Update cache to prevent future misses
                                        await cache.set_doc_id(adr_id, doc_id)
                                        exists_in_rag = True
                                        logger.info(
                                            "Document found in LightRAG via fallback, cache updated",
                                            adr_id=adr_id,
                                            doc_id=doc_id,
                                            page=page,
                                        )
                                        found = True
                                        break

                            # If we got fewer documents than page_size, we've reached the end
                            if len(documents) < page_size:
                                break

                            page += 1

                            # Safety limit: don't search more than 10 pages (500 docs)
                            if page > 10:
                                logger.warning(
                                    "Fallback search exceeded page limit",
                                    adr_id=adr_id,
                                    max_pages=10,
                                )
                                break

                except Exception as fallback_error:
                    # Log but don't fail - just rely on cache result
                    logger.warning(
                        "LightRAG fallback check failed",
                        adr_id=adr_id,
                        error=str(fallback_error),
                    )

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

        return {"is_rebuilding": is_rebuilding, "last_sync_time": last_sync_time}
    except Exception as e:
        logger.error(f"Failed to check cache status: {str(e)}")
        return {"is_rebuilding": False, "last_sync_time": None, "error": str(e)}


@adr_router.post("/cache/refresh")
async def refresh_cache():
    """Manually trigger a cache refresh from LightRAG.

    This endpoint allows administrators to force a cache sync without waiting
    for the scheduled background task. Useful for testing or after bulk operations.
    """
    try:
        from src.lightrag_sync import _sync_lightrag_cache

        logger.info("Manual cache refresh triggered")
        total_synced = await _sync_lightrag_cache(page_size=100)

        return {
            "message": "Cache refresh completed",
            "total_documents": total_synced,
        }
    except Exception as e:
        logger.error(f"Failed to refresh cache: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to refresh cache: {str(e)}"
        )


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
        task = analyze_adr_task.delay(adr_id=request.adr_id, persona=request.persona)

        return TaskResponse(
            task_id=task.id, status="queued", message="ADR analysis queued successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to queue analysis: {str(e)}"
        )


@generation_router.post("/generate", response_model=TaskResponse)
async def generate_adr(request: GenerateADRRequest, background_tasks: BackgroundTasks):
    """Queue ADR generation."""
    try:
        # Queue the generation task
        task = generate_adr_task.delay(
            prompt=request.prompt,
            context=request.context,
            tags=request.tags or [],
            personas=request.personas or [],
            retrieval_mode=request.retrieval_mode or "naive",
            persona_provider_overrides=request.persona_provider_overrides or {},
            synthesis_provider_id=request.synthesis_provider_id,
            record_type=request.record_type,
            mcp_tools=request.mcp_tools or [],
            use_mcp=request.use_mcp or False,
            status_filter=request.status_filter,
        )

        return TaskResponse(
            task_id=task.id,
            status="queued",
            message="ADR generation queued successfully",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to queue generation: {str(e)}"
        )


@analysis_router.get("/task/{task_id}")
async def get_analysis_task_status(task_id: str):
    """Get the status of an analysis task."""
    try:
        from src.celery_app import celery_app

        task_result = celery_app.AsyncResult(task_id)

        if task_result.state == "PENDING":
            response = {"status": "pending", "message": "Task is waiting in queue"}
        elif task_result.state == "PROGRESS":
            response = {
                "status": "progress",
                "message": task_result.info.get("message", "Processing..."),
            }
        elif task_result.state == "SUCCESS":
            response = {
                "status": "completed",
                "message": "Analysis completed successfully",
                "result": task_result.result,
            }
        else:
            response = {
                "status": "failed",
                "message": "Analysis failed",
                "error": str(task_result.info),
            }

        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        )


@generation_router.get("/task/{task_id}")
async def get_generation_task_status(task_id: str):
    """Get the status of a generation task."""
    try:
        from src.celery_app import celery_app
        from src.logger import get_logger

        logger = get_logger(__name__)
        task_result = celery_app.AsyncResult(task_id)

        # Debug logging
        logger.info(f"Task {task_id} state: {task_result.state}")
        logger.info(f"Task {task_id} result: {task_result.result}")
        logger.info(f"Task {task_id} info: {task_result.info}")

        if task_result.state == "PENDING":
            response = {"status": "pending", "message": "Task is waiting in queue"}
        elif task_result.state == "PROGRESS":
            response = {
                "status": "progress",
                "message": task_result.info.get("message", "Generating ADR..."),
            }
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
        elif task_result.state == "FAILURE":
            # Handle actual failures with proper error message
            error_msg = (
                str(task_result.info.get("error", "Unknown error"))
                if isinstance(task_result.info, dict)
                else str(task_result.info)
            )
            response = {
                "status": "failed",
                "message": "Generation failed",
                "error": error_msg,
            }
        elif task_result.state == "REVOKED":
            # Task was cancelled
            response = {
                "status": "revoked",
                "message": "Task was cancelled",
            }
        else:
            # Unknown state - log and return info
            logger.warning(f"Unknown task state {task_result.state} for task {task_id}")
            response = {
                "status": "unknown",
                "message": f"Unknown task state: {task_result.state}",
                "state": task_result.state,
                "info": str(task_result.info),
            }

        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        )


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
        imported_ids = []

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
                imported_ids.append(adr_id)
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
            imported_ids=imported_ids,
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


# ==================== Queue Management Endpoints ====================


@queue_router.get("/status")
async def get_queue_status():
    """Get overall queue status including task counts and worker status.

    Now uses fast Redis queries (<10ms) instead of slow Celery inspect API.

    Returns:
        {
            "total_tasks": int,
            "active_tasks": int,
            "pending_tasks": int,
            "reserved_tasks": int,
            "workers_online": int
        }
    """
    try:
        from src.task_queue_monitor import get_task_queue_monitor

        monitor = get_task_queue_monitor()

        # Get queue status (now instant with Redis - no caching needed)
        queue_status = monitor.get_queue_status()

        return {
            "total_tasks": queue_status.total_tasks,
            "active_tasks": queue_status.active_tasks,
            "pending_tasks": queue_status.pending_tasks,
            "reserved_tasks": queue_status.reserved_tasks,
            "workers_online": queue_status.workers_online,
        }
    except Exception as e:
        logger.error(f"Failed to get queue status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get queue status: {str(e)}"
        )


@queue_router.get("/tasks")
async def get_queue_tasks():
    """Get all tasks currently in the queue (active, pending, and scheduled).

    Returns cached data immediately to avoid blocking. The periodic broadcaster
    updates the cache every few seconds.

    Returns:
        {
            "tasks": [
                {
                    "task_id": str,
                    "task_name": str,
                    "status": str,  // "active", "pending", "scheduled"
                    "position": int | null,  // Queue position (null if active)
                    "args": tuple,
                    "kwargs": dict,
                    "worker": str | null
                }
            ]
        }
    """
    try:
        from src.task_queue_monitor import get_task_queue_monitor

        monitor = get_task_queue_monitor()

        # Get all active tasks (now instant - just returns in-memory dict)
        tasks = monitor.get_all_tasks()

        return {
            "tasks": [
                {
                    "task_id": task.task_id,
                    "task_name": task.task_name,
                    "status": task.status,
                    "position": task.position,
                    "args": task.args,
                    "kwargs": task.kwargs,
                    "worker": task.worker,
                    "started_at": task.started_at,
                    "eta": task.eta,
                }
                for task in tasks
            ]
        }
    except Exception as e:
        logger.error(f"Failed to get queue tasks: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get queue tasks: {str(e)}"
        )


@queue_router.get("/task/{task_id}")
async def get_task_info(task_id: str):
    """Get information about a specific task.

    Returns:
        {
            "task_id": str,
            "task_name": str,
            "status": str,
            "position": int | null,
            "args": tuple,
            "kwargs": dict
        }
    """
    try:
        from src.task_queue_monitor import get_task_queue_monitor

        monitor = get_task_queue_monitor()
        # Run blocking Celery inspect call in thread pool to avoid blocking event loop
        task = await asyncio.to_thread(monitor.get_task_info, task_id)

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "status": task.status,
            "position": task.position,
            "args": task.args,
            "kwargs": task.kwargs,
            "worker": task.worker,
            "started_at": task.started_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task info: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get task info: {str(e)}"
        )


@queue_router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str, terminate: bool = False):
    """Cancel a task in the queue.

    Args:
        task_id: The task ID to cancel
        terminate: If True, forcefully terminate the task if it's already running

    Returns:
        {
            "message": str,
            "task_id": str,
            "cancelled": bool
        }
    """
    try:
        from src.task_queue_monitor import get_task_queue_monitor

        monitor = get_task_queue_monitor()
        success = monitor.revoke_task(task_id, terminate=terminate)

        if success:
            return {
                "message": f"Task {task_id} cancelled successfully",
                "task_id": task_id,
                "cancelled": True,
            }
        else:
            raise HTTPException(
                status_code=500, detail=f"Failed to cancel task {task_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


@queue_router.post("/cleanup-orphaned")
async def cleanup_orphaned_tasks():
    """Clean up orphaned task records in Redis.

    Orphaned tasks are those marked as active in Redis but don't have
    corresponding Celery tasks running. This can happen after crashes,
    restarts, or task failures without proper cleanup.

    Returns:
        {
            "message": str,
            "cleaned_count": int,
            "error_count": int,
            "cleaned_tasks": list[dict],
            "errors": list[str]
        }
    """
    try:
        from src.task_queue_monitor import get_task_queue_monitor

        monitor = get_task_queue_monitor()
        result = await monitor.cleanup_orphaned_tasks()

        return {
            "message": f"Cleaned {result['cleaned_count']} orphaned tasks",
            **result,
        }
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned tasks: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup orphaned tasks: {str(e)}"
        )


@queue_router.post("/clear")
async def clear_all_tasks(force: bool = False):
    """Clear all tasks from the queue.

    This will:
    1. Revoke all pending tasks in the Celery queue
    2. Optionally terminate active tasks (if force=True)
    3. Clear all task tracking data from Redis

    WARNING: This is a destructive operation and will cancel all queued work.

    Args:
        force: If True, forcefully terminate running tasks (default: False)

    Returns:
        {
            "message": str,
            "revoked_active": int,
            "purged_pending": int,
            "cleared_redis_records": int,
            "error_count": int,
            "revoked_tasks": list[dict],
            "errors": list[str]
        }
    """
    try:
        from src.task_queue_monitor import get_task_queue_monitor

        monitor = get_task_queue_monitor()
        result = await monitor.clear_all_tasks(force=force)

        total_cleared = result["revoked_active"] + result["purged_pending"]
        return {
            "message": f"Cleared {total_cleared} tasks from queue (active: {result['revoked_active']}, pending: {result['purged_pending']})",
            **result,
        }
    except Exception as e:
        logger.error(f"Failed to clear queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear queue: {str(e)}")


# ==================== Provider Management Routes ====================


@provider_router.get("")
async def list_providers():
    """List all configured LLM providers.

    Returns:
        {
            "providers": List[ProviderResponse]
        }
    """
    try:
        from src.llm_provider_storage import get_provider_storage

        storage = get_provider_storage()
        await storage.ensure_env_provider()
        providers = await storage.list_all()

        return {"providers": providers}
    except Exception as e:
        logger.error(f"Failed to list providers: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list providers: {str(e)}"
        )


@provider_router.get("/default")
async def get_default_provider():
    """Get the default LLM provider.

    Returns:
        ProviderResponse or null if no default set
    """
    try:
        from src.llm_provider_storage import get_provider_storage

        storage = get_provider_storage()
        await storage.ensure_env_provider()
        provider = await storage.get_default()

        return provider
    except Exception as e:
        logger.error(f"Failed to get default provider: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get default provider: {str(e)}"
        )


@provider_router.get("/{provider_id}")
async def get_provider(provider_id: str):
    """Get a specific provider by ID (without decrypted API key).

    Args:
        provider_id: The provider ID

    Returns:
        ProviderResponse or 404 if not found
    """
    try:
        from src.llm_provider_storage import get_provider_storage

        storage = get_provider_storage()
        provider = await storage.get(provider_id)

        if not provider:
            raise HTTPException(
                status_code=404, detail=f"Provider {provider_id} not found"
            )

        # Convert to response (hide encrypted key)
        from src.llm_provider_storage import ProviderResponse

        return ProviderResponse(
            id=provider.id,
            name=provider.name,
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            model_name=provider.model_name,
            has_api_key=bool(provider.api_key_encrypted),
            temperature=provider.temperature,
            num_ctx=provider.num_ctx,
            num_predict=provider.num_predict,
            is_default=provider.is_default,
            is_env_based=provider.is_env_based,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get provider: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get provider: {str(e)}")


@provider_router.post("")
async def create_provider(request: dict):
    """Create a new LLM provider configuration.

    Request body:
        {
            "name": str,
            "provider_type": str,  # ollama, openai, openrouter, vllm, llama_cpp, custom
            "base_url": str,
            "model_name": str,
            "api_key": str (optional),
            "temperature": float (optional, default 0.7),
            "num_ctx": int (optional),
            "num_predict": int (optional),
            "is_default": bool (optional, default false)
        }

    Returns:
        ProviderResponse
    """
    try:
        from src.llm_provider_storage import CreateProviderRequest, get_provider_storage

        storage = get_provider_storage()
        create_request = CreateProviderRequest(**request)
        provider = await storage.create(create_request)

        return provider
    except Exception as e:
        logger.error(f"Failed to create provider: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create provider: {str(e)}"
        )


@provider_router.put("/{provider_id}")
async def update_provider(provider_id: str, request: dict):
    """Update an existing LLM provider configuration.

    Args:
        provider_id: The provider ID

    Request body (all fields optional):
        {
            "name": str,
            "provider_type": str,
            "base_url": str,
            "model_name": str,
            "api_key": str,
            "temperature": float,
            "num_ctx": int,
            "num_predict": int,
            "is_default": bool
        }

    Returns:
        ProviderResponse or 404 if not found
    """
    try:
        from src.llm_provider_storage import UpdateProviderRequest, get_provider_storage

        storage = get_provider_storage()
        update_request = UpdateProviderRequest(**request)
        provider = await storage.update(provider_id, update_request)

        if not provider:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found or cannot be updated (env-based providers are read-only)",
            )

        return provider
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update provider: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update provider: {str(e)}"
        )


@provider_router.delete("/{provider_id}")
async def delete_provider(provider_id: str):
    """Delete an LLM provider configuration.

    Args:
        provider_id: The provider ID

    Returns:
        {"message": str, "deleted": bool}
    """
    try:
        from src.llm_provider_storage import get_provider_storage

        storage = get_provider_storage()
        success = await storage.delete(provider_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found or cannot be deleted (env-based providers are read-only)",
            )

        return {
            "message": f"Provider {provider_id} deleted successfully",
            "deleted": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete provider: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete provider: {str(e)}"
        )


class PersonaCreateRequest(BaseModel):
    """Request model for creating a new persona."""

    name: str
    description: str
    instructions: str
    focus_areas: List[str]
    evaluation_criteria: List[str]
    llm_config: Optional[ModelConfigInfo] = None


class PersonaUpdateRequest(BaseModel):
    """Request model for updating an existing persona."""

    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    focus_areas: Optional[List[str]] = None
    evaluation_criteria: Optional[List[str]] = None
    llm_config: Optional[ModelConfigInfo] = None


class PersonaGenerateRequest(BaseModel):
    """Request model for generating a persona from a prompt."""

    prompt: str
    provider_id: Optional[str] = None


class PersonaRefineRequest(BaseModel):
    """Request model for refining a persona using LLM."""

    prompt: str
    current_persona: Dict[str, Any]
    provider_id: Optional[str] = None


@adr_router.get("/personas/{name}")
async def get_persona(name: str):
    """Get a specific persona configuration."""
    from src.persona_manager import get_persona_manager

    manager = get_persona_manager()
    config = manager.get_persona_config(name)
    if not config:
        raise HTTPException(status_code=404, detail="Persona not found")

    return config.to_dict()


@adr_router.post("/personas")
async def create_persona(request: PersonaCreateRequest):
    """Create a new persona."""
    from src.persona_manager import ModelConfig, PersonaConfig, get_persona_manager

    manager = get_persona_manager()

    # Check if exists (using name as ID)
    # Note: get_persona_config uses the value/filename, not the display name.
    # We'll assume request.name is the identifier for now.
    # Ideally we should separate ID (filename) from Name (display name).
    # But existing code uses them somewhat interchangeably or uses filename as ID.
    # Let's use a slugified version of name as ID if we want to be safe,
    # but for now let's assume the user provides a valid filename-safe name
    # or we just use it as is.
    if manager.get_persona_config(request.name):
        raise HTTPException(status_code=400, detail="Persona already exists")

    model_config = None
    if request.llm_config:
        model_config = ModelConfig(**request.llm_config.model_dump())

    config = PersonaConfig(
        name=request.name,
        description=request.description,
        instructions=request.instructions,
        focus_areas=request.focus_areas,
        evaluation_criteria=request.evaluation_criteria,
        model_config=model_config,
    )

    manager.save_persona(request.name, config)
    return {"message": "Persona created successfully", "persona": config.to_dict()}


@adr_router.put("/personas/{name}")
async def update_persona(name: str, request: PersonaUpdateRequest):
    """Update an existing persona."""
    from src.persona_manager import ModelConfig, PersonaConfig, get_persona_manager

    manager = get_persona_manager()
    existing = manager.get_persona_config(name)
    if not existing:
        raise HTTPException(status_code=404, detail="Persona not found")

    # Update fields
    new_name = request.name or existing.name
    description = request.description or existing.description
    instructions = request.instructions or existing.instructions
    focus_areas = (
        request.focus_areas if request.focus_areas is not None else existing.focus_areas
    )
    evaluation_criteria = (
        request.evaluation_criteria
        if request.evaluation_criteria is not None
        else existing.evaluation_criteria
    )

    model_config = existing.model_config
    if request.llm_config:
        model_config = ModelConfig(**request.llm_config.model_dump())

    config = PersonaConfig(
        name=new_name,
        description=description,
        instructions=instructions,
        focus_areas=focus_areas,
        evaluation_criteria=evaluation_criteria,
        model_config=model_config,
    )

    # If name changed, we treat it as a rename (new file, delete old)
    # Note: 'name' param is the old ID/filename. request.name is the new display name.
    # If we use display name as ID, then ID changes.
    # This is a bit fragile if name != filename.
    # For this implementation, we assume ID == Name.

    if request.name and request.name != name:
        manager.save_persona(request.name, config)
        manager.delete_persona(name)
    else:
        manager.save_persona(name, config)

    return {"message": "Persona updated successfully", "persona": config.to_dict()}


@adr_router.delete("/personas/{name}")
async def delete_persona(name: str):
    """Delete a persona."""
    from src.persona_manager import get_persona_manager

    manager = get_persona_manager()
    if manager.delete_persona(name):
        return {"message": "Persona deleted successfully"}
    else:
        raise HTTPException(
            status_code=404, detail="Persona not found or cannot be deleted"
        )


@adr_router.post("/personas/generate")
async def generate_persona(request: PersonaGenerateRequest):
    """Generate a persona from a prompt."""
    from src.llama_client import create_client_from_provider_id
    from src.prompts import PERSONA_GENERATION_SYSTEM_PROMPT

    # Create client
    client_cm = await create_client_from_provider_id(request.provider_id)
    async with client_cm as client:
        # Construct prompt
        messages = [
            {"role": "system", "content": PERSONA_GENERATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Create a persona based on this description: {request.prompt}",
            },
        ]

        # Call LLM
        response = await client.generate(messages=messages)

        # Parse JSON
        try:
            # Clean up markdown code blocks if present
            content = response.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return data
        except json.JSONDecodeError:
            logger.error(f"Failed to parse generated persona JSON: {response}")
            raise HTTPException(
                status_code=500, detail="Failed to generate valid JSON for persona"
            )


@adr_router.post("/personas/refine")
async def refine_persona(request: PersonaRefineRequest):
    """Refine a persona using LLM."""
    from src.llama_client import create_client_from_provider_id
    from src.prompts import PERSONA_REFINEMENT_SYSTEM_PROMPT

    client_cm = await create_client_from_provider_id(request.provider_id)
    async with client_cm as client:
        messages = [
            {"role": "system", "content": PERSONA_REFINEMENT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Current Persona:\n{json.dumps(request.current_persona, indent=2)}\n\nUser Request: {request.prompt}",
            },
        ]

        response = await client.generate(messages=messages)

        try:
            content = response.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return data
        except json.JSONDecodeError:
            logger.error(f"Failed to parse refined persona JSON: {response}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate valid JSON for persona refinement",
            )


# ==================== MCP Server Management Routes ====================


class MCPServerCreateRequest(BaseModel):
    """Request model for creating an MCP server."""

    name: str
    description: Optional[str] = None
    transport_type: str = "stdio"  # stdio, http, sse
    command: Optional[str] = None
    args: List[str] = []
    env: Dict[str, str] = {}
    cwd: Optional[str] = None
    url: Optional[str] = None
    headers: Dict[str, str] = {}
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    is_enabled: bool = True


class MCPServerUpdateRequest(BaseModel):
    """Request model for updating an MCP server."""

    name: Optional[str] = None
    description: Optional[str] = None
    transport_type: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    auth_type: Optional[str] = None
    auth_token: Optional[str] = None
    is_enabled: Optional[bool] = None


class MCPToolUpdateRequest(BaseModel):
    """Request model for updating MCP tool configuration."""

    display_name: Optional[str] = None
    description: Optional[str] = None
    execution_mode: Optional[str] = None  # initial_only, per_persona
    default_enabled: Optional[bool] = None
    default_arguments: Optional[Dict[str, Any]] = None
    context_argument_mappings: Optional[Dict[str, str]] = None


@mcp_router.get("")
async def list_mcp_servers():
    """List all configured MCP servers.

    Returns:
        {"servers": List[MCPServerResponse]}
    """
    try:
        from src.mcp_config_storage import get_mcp_storage

        storage = get_mcp_storage()
        servers = await storage.list_all()
        return {"servers": servers}
    except Exception as e:
        logger.error(f"Failed to list MCP servers: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list MCP servers: {str(e)}"
        )


@mcp_router.get("/enabled")
async def list_enabled_mcp_servers():
    """List only enabled MCP servers.

    Returns:
        {"servers": List[MCPServerResponse]}
    """
    try:
        from src.mcp_config_storage import get_mcp_storage

        storage = get_mcp_storage()
        servers = await storage.list_enabled()
        return {"servers": servers}
    except Exception as e:
        logger.error(f"Failed to list enabled MCP servers: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list enabled MCP servers: {str(e)}"
        )


@mcp_router.get("/tools")
async def list_all_mcp_tools():
    """List all available MCP tools from enabled servers.

    Returns:
        {"tools": List[ToolInfo]}
    """
    try:
        from src.mcp_client import get_mcp_client_manager

        manager = get_mcp_client_manager()
        tools = await manager.get_all_available_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"Failed to list MCP tools: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list MCP tools: {str(e)}"
        )


@mcp_router.get("/tools/default")
async def list_default_enabled_tools():
    """List MCP tools that are enabled by default.

    Returns:
        {"tools": List[ToolInfo]}
    """
    try:
        from src.mcp_client import get_mcp_client_manager

        manager = get_mcp_client_manager()
        tools = await manager.get_default_enabled_tools()
        return {"tools": tools}
    except Exception as e:
        logger.error(f"Failed to list default enabled tools: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list default enabled tools: {str(e)}"
        )


@mcp_router.get("/{server_id}")
async def get_mcp_server(server_id: str):
    """Get a specific MCP server by ID.

    Args:
        server_id: The server ID

    Returns:
        MCPServerResponse or 404 if not found
    """
    try:
        from src.mcp_config_storage import get_mcp_storage

        storage = get_mcp_storage()
        server = await storage.get(server_id)

        if not server:
            raise HTTPException(
                status_code=404, detail=f"MCP server {server_id} not found"
            )

        return storage._to_response(server)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MCP server: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get MCP server: {str(e)}"
        )


@mcp_router.post("")
async def create_mcp_server(request: MCPServerCreateRequest):
    """Create a new MCP server configuration.

    Args:
        request: Server creation parameters

    Returns:
        MCPServerResponse
    """
    try:
        from src.mcp_config_storage import (
            CreateMCPServerRequest,
            MCPTransportType,
            get_mcp_storage,
        )

        storage = get_mcp_storage()

        # Convert transport type string to enum
        try:
            transport = MCPTransportType(request.transport_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transport_type: {request.transport_type}. Must be one of: stdio, http, sse",
            )

        create_req = CreateMCPServerRequest(
            name=request.name,
            description=request.description,
            transport_type=transport,
            command=request.command,
            args=request.args,
            env=request.env,
            cwd=request.cwd,
            url=request.url,
            headers=request.headers,
            auth_type=request.auth_type,
            auth_token=request.auth_token,
            is_enabled=request.is_enabled,
        )

        server = await storage.create(create_req)
        return server
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create MCP server: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create MCP server: {str(e)}"
        )


@mcp_router.put("/{server_id}")
async def update_mcp_server(server_id: str, request: MCPServerUpdateRequest):
    """Update an existing MCP server configuration.

    Args:
        server_id: The server ID
        request: Update parameters

    Returns:
        MCPServerResponse or 404 if not found
    """
    try:
        from src.mcp_config_storage import (
            MCPTransportType,
            UpdateMCPServerRequest,
            get_mcp_storage,
        )

        storage = get_mcp_storage()

        # Build update request with only fields that were explicitly set
        update_fields = request.model_dump(exclude_unset=True)

        # Convert transport type if provided
        if "transport_type" in update_fields and update_fields["transport_type"]:
            try:
                update_fields["transport_type"] = MCPTransportType(
                    update_fields["transport_type"]
                )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid transport_type: {update_fields['transport_type']}",
                )

        update_req = UpdateMCPServerRequest(**update_fields)

        server = await storage.update(server_id, update_req)

        if not server:
            raise HTTPException(
                status_code=404, detail=f"MCP server {server_id} not found"
            )

        return server
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MCP server: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update MCP server: {str(e)}"
        )


@mcp_router.delete("/{server_id}")
async def delete_mcp_server(server_id: str):
    """Delete an MCP server configuration.

    Args:
        server_id: The server ID

    Returns:
        {"message": str, "deleted": bool}
    """
    try:
        from src.mcp_config_storage import get_mcp_storage

        storage = get_mcp_storage()
        success = await storage.delete(server_id)

        if not success:
            raise HTTPException(
                status_code=404, detail=f"MCP server {server_id} not found"
            )

        return {
            "message": f"MCP server {server_id} deleted successfully",
            "deleted": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete MCP server: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete MCP server: {str(e)}"
        )


@mcp_router.post("/{server_id}/discover-tools")
async def discover_mcp_tools(server_id: str):
    """Connect to an MCP server and discover available tools.

    This endpoint connects to the server, lists all available tools,
    and syncs them with the stored configuration.

    Args:
        server_id: The server ID

    Returns:
        {"tools": List[ToolInfo], "message": str}
    """
    try:
        from src.mcp_client import get_mcp_client_manager

        manager = get_mcp_client_manager()
        tools = await manager.discover_tools(server_id)

        return {
            "tools": tools,
            "message": f"Discovered {len(tools)} tools from server",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to discover tools: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to discover tools: {str(e)}"
        )


@mcp_router.put("/{server_id}/tools/{tool_name}")
async def update_mcp_tool(
    server_id: str, tool_name: str, request: MCPToolUpdateRequest
):
    """Update configuration for a specific tool on an MCP server.

    Args:
        server_id: The server ID
        tool_name: The tool name
        request: Tool update parameters

    Returns:
        MCPServerResponse with updated tool config
    """
    try:
        from src.mcp_config_storage import (
            MCPToolExecutionMode,
        )
        from src.mcp_config_storage import (
            MCPToolUpdateRequest as StorageToolUpdateRequest,
        )
        from src.mcp_config_storage import (
            get_mcp_storage,
        )

        storage = get_mcp_storage()

        # Build update request with only fields that were explicitly set
        update_fields = request.model_dump(exclude_unset=True)

        # Convert execution mode if provided
        if "execution_mode" in update_fields and update_fields["execution_mode"]:
            try:
                update_fields["execution_mode"] = MCPToolExecutionMode(
                    update_fields["execution_mode"]
                )
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid execution_mode: {update_fields['execution_mode']}. Must be one of: initial_only, per_persona",
                )

        update_req = StorageToolUpdateRequest(**update_fields)

        server = await storage.update_tool(server_id, tool_name, update_req)

        if not server:
            raise HTTPException(
                status_code=404,
                detail=f"Server {server_id} or tool {tool_name} not found",
            )

        return server
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update tool: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update tool: {str(e)}")


@mcp_router.post("/{server_id}/tools/{tool_name}/test")
async def test_mcp_tool(server_id: str, tool_name: str, arguments: Dict[str, Any] = {}):
    """Test a specific MCP tool with provided arguments.

    Args:
        server_id: The server ID
        tool_name: The tool name
        arguments: Arguments to pass to the tool

    Returns:
        {"success": bool, "result": Any, "error": Optional[str]}
    """
    try:
        from src.mcp_client import get_mcp_client_manager

        manager = get_mcp_client_manager()
        result = await manager.call_tool(server_id, tool_name, arguments)

        return {
            "success": result.success,
            "result": result.to_context_string() if result.success else None,
            "error": result.error,
        }
    except Exception as e:
        logger.error(f"Failed to test tool: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to test tool: {str(e)}")


# MCP Results endpoints
@mcp_results_router.get("/{result_id}")
async def get_mcp_result(result_id: str):
    """Get a stored MCP tool result by ID.

    This endpoint retrieves the raw JSON output from an MCP tool execution.
    Used for viewing tool results referenced in ADRs.

    Args:
        result_id: The unique ID of the stored result

    Returns:
        Raw JSON data of the tool result
    """
    from src.mcp_result_storage import get_mcp_result_storage

    storage = get_mcp_result_storage()
    result = await storage.get_raw_json(result_id)

    if result is None:
        raise HTTPException(status_code=404, detail="MCP result not found")

    return result


@mcp_results_router.get("")
async def list_mcp_results(adr_id: Optional[str] = None):
    """List stored MCP results, optionally filtered by ADR ID.

    Args:
        adr_id: Optional ADR ID to filter results by

    Returns:
        List of stored result metadata
    """
    from src.mcp_result_storage import get_mcp_result_storage

    storage = get_mcp_result_storage()

    if adr_id:
        results = await storage.list_for_adr(adr_id)
    else:
        # List all results (limited for now)
        results = []
        import os

        for filename in os.listdir(storage.storage_dir):
            if filename.endswith(".json"):
                result_id = filename[:-5]  # Remove .json
                result = await storage.get(result_id)
                if result:
                    results.append(result)

    return {
        "results": [
            {
                "id": r.id,
                "server_name": r.server_name,
                "tool_name": r.tool_name,
                "success": r.success,
                "created_at": r.created_at,
                "adr_id": r.adr_id,
            }
            for r in results
        ]
    }


@mcp_results_router.delete("/{result_id}")
async def delete_mcp_result(result_id: str):
    """Delete a stored MCP result.

    Args:
        result_id: The unique ID of the result to delete

    Returns:
        Success message
    """
    from src.mcp_result_storage import get_mcp_result_storage

    storage = get_mcp_result_storage()
    deleted = await storage.delete(result_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="MCP result not found")

    return {"message": "Result deleted successfully"}
