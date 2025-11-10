"""FastAPI backend for Decision Analyzer."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.models import ADR
from src.adr_validation import ADRAnalysisService
from src.adr_generation import ADRGenerationService
from src.lightrag_client import LightRAGClient
from src.llama_client import LlamaCppClient
from src.celery_app import celery_app
from src.api.routes import adr_router, analysis_router, generation_router, config_router
from src.logger import get_logger
from src.config import get_settings
from src.lightrag_sync import sync_lightrag_cache_task

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    settings = get_settings()
    logger.info("Starting Decision Analyzer API")

    # Show LAN discovery status
    if settings.enable_lan_discovery and settings.host_ip:
        logger.info(
            "🌐 LAN Discovery ENABLED - Backend accessible at http://%s:8000",
            settings.host_ip,
        )
        logger.info(
            "   Access frontend from any device at http://%s:3003",
            settings.host_ip,
        )
    else:
        logger.info("🔒 LAN Discovery DISABLED - Backend only accessible via localhost")

    # Start WebSocket broadcaster Redis listener
    from src.websocket_broadcaster import get_broadcaster
    from src.websocket_manager import get_websocket_manager

    broadcaster = get_broadcaster()
    ws_manager = get_websocket_manager()
    listener_task = await broadcaster.start_listening(ws_manager)
    logger.info("Started WebSocket broadcaster Redis listener")

    # Start LightRAG cache sync background task
    sync_task = asyncio.create_task(sync_lightrag_cache_task(interval_seconds=300))
    logger.info("Started LightRAG cache sync background task")

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Decision Analyzer API")

    # Cancel broadcaster listener
    if listener_task:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            logger.info("WebSocket broadcaster listener cancelled")

    await broadcaster.disconnect()

    # Cancel sync task
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        logger.info("LightRAG cache sync task cancelled")
    except Exception as e:
        logger.error("Error stopping cache sync task", error=str(e))


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Decision Analyzer API",
        description="AI-powered ADR analysis and generation system",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS based on LAN discovery setting
    settings = get_settings()
    if settings.enable_lan_discovery:
        # Allow all origins when LAN discovery is enabled
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        logger.info(
            "LAN discovery enabled - allowing CORS from all origins",
            host_ip=settings.host_ip,
        )
    else:
        # Restrict to localhost only in normal mode
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:3003",
            ],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include routers
    app.include_router(adr_router, prefix="/api/v1/adrs", tags=["ADRs"])
    app.include_router(analysis_router, prefix="/api/v1/analysis", tags=["Analysis"])
    app.include_router(generation_router, prefix="/api/v1/generation", tags=["Generation"])
    app.include_router(config_router, prefix="/api/v1", tags=["Configuration"])

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy", "service": "decision-analyzer-api"}

    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Decision Analyzer API",
            "docs": "/docs",
            "health": "/health"
        }

    return app


# Create the FastAPI app instance
app = create_application()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
