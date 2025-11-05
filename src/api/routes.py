"""API routes for Decision Analyzer."""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel

from src.models import ADR, AnalysisPersona
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


# Create routers
adr_router = APIRouter()
analysis_router = APIRouter()
generation_router = APIRouter()
config_router = APIRouter()


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
    """List all available analysis personas dynamically from config files."""
    from src.persona_manager import get_persona_manager

    persona_manager = get_persona_manager()
    personas = []

    # Iterate through all defined personas and get their configs
    for persona in AnalysisPersona:
        config = persona_manager.get_persona_config(persona)
        personas.append(
            PersonaInfo(
                value=persona.value, label=config.name, description=config.description
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
        from src.config import settings

        storage = get_adr_storage()

        # Delete from file storage
        deleted_from_storage = storage.delete_adr(adr_id)

        if not deleted_from_storage:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

        # Try to delete from LightRAG (if it exists there)
        try:
            async with LightRAGClient(
                base_url=settings.lightrag_url,
                demo_mode=False
            ) as rag_client:
                await rag_client.delete_document(adr_id)
                logger.info(f"Deleted ADR {adr_id} from LightRAG")
        except Exception as rag_error:
            # Log but don't fail if RAG deletion fails
            logger.warning(f"Failed to delete from LightRAG: {rag_error}")

        return {"message": f"ADR {adr_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete ADR: {str(e)}")


@adr_router.post("/{adr_id}/push-to-rag")
async def push_adr_to_rag(adr_id: str):
    """Push an ADR to LightRAG for indexing."""
    try:
        from src.adr_file_storage import get_adr_storage
        from src.lightrag_client import LightRAGClient
        from src.config import settings

        storage = get_adr_storage()
        adr = storage.get_adr(adr_id)

        if not adr:
            raise HTTPException(status_code=404, detail=f"ADR {adr_id} not found")

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
            logger.info(f"Pushed ADR {adr_id} to LightRAG")

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
