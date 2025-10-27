#!/usr/bin/env python3
"""Simple test script to verify Phase 1 infrastructure works."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import get_settings
from src.models import ADR, ADRStatus
from src.logging import setup_logging, get_logger

async def main():
    """Test the basic infrastructure."""
    # Setup logging
    setup_logging()

    logger = get_logger(__name__)
    logger.info("Starting Phase 1 infrastructure test")

    # Test configuration
    settings = get_settings()
    logger.info("Configuration loaded", llama_url=settings.llama_cpp_url, lightrag_url=settings.lightrag_url)

    # Test ADR creation
    adr = ADR.create(
        title="Test Infrastructure ADR",
        context="Testing the basic infrastructure setup",
        decision="Use Python with async architecture",
        consequences="Good performance and maintainability",
        author="Test Script",
        tags=["infrastructure", "testing"]
    )

    logger.info("ADR created successfully", title=adr.metadata.title, status=adr.metadata.status)

    # Test markdown export
    markdown = adr.to_markdown()
    logger.info("ADR markdown generated", length=len(markdown))

    # Test LightRAG client (without actual server)
    try:
        from lightrag_client import LightRAGClient
        async with LightRAGClient() as client:
            # This will fail since server isn't running, but tests the client setup
            logger.info("LightRAG client initialized successfully")
    except Exception as e:
        logger.warning("LightRAG client test failed (expected without server)", error=str(e))

    # Test Llama client (without actual server)
    try:
        from llama_client import LlamaCppClient
        async with LlamaCppClient() as client:
            # This will fail since server isn't running, but tests the client setup
            logger.info("Llama client initialized successfully")
    except Exception as e:
        logger.warning("Llama client test failed (expected without server)", error=str(e))

    logger.info("Phase 1 infrastructure test completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
