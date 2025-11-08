"""Background task for syncing LightRAG document cache."""

import asyncio
from typing import Optional

from src.lightrag_client import LightRAGClient
from src.lightrag_doc_cache import LightRAGDocumentCache
from src.config import get_settings
from src.logger import get_logger

logger = get_logger(__name__)


async def sync_lightrag_cache_task(
    interval_seconds: int = 300,  # Sync every 5 minutes by default
    page_size: int = 100
) -> None:
    """Background task to periodically sync the LightRAG document cache.
    
    This task fetches all documents from LightRAG and updates the Redis cache
    with the mapping between file_path and LightRAG document ID.
    
    Args:
        interval_seconds: How often to sync the cache
        page_size: Number of documents to fetch per page
    """
    settings = get_settings()
    
    logger.info("Starting LightRAG cache sync task", interval=interval_seconds)
    
    while True:
        try:
            await _sync_lightrag_cache(page_size=page_size)
            logger.debug("LightRAG cache sync completed", next_sync_in=interval_seconds)
        except Exception as e:
            logger.error(
                "Error syncing LightRAG cache",
                error_type=type(e).__name__,
                error_message=str(e),
                error_repr=repr(e)
            )
        
        # Wait before next sync
        await asyncio.sleep(interval_seconds)


async def _sync_lightrag_cache(page_size: int = 100) -> int:
    """Internal function to sync the cache.
    
    Args:
        page_size: Number of documents per page
        
    Returns:
        Total number of documents synced
    """
    settings = get_settings()
    total_synced = 0

    try:
        async with LightRAGClient(
            base_url=settings.lightrag_url,
            demo_mode=False
        ) as rag_client:
            async with LightRAGDocumentCache() as cache:
                # Mark cache as rebuilding
                await cache.set_rebuilding_status(True)

                # Clear all existing cache entries before rebuilding
                # This ensures stale entries are removed if documents were deleted from LightRAG
                logger.info("Clearing existing cache before rebuild")
                await cache.clear_all()

                page = 1
                while True:
                    # Fetch a page of documents
                    result = await rag_client.get_paginated_documents(
                        page=page,
                        page_size=page_size,
                        status_filter="processed"  # Only sync processed documents
                    )

                    documents = result.get("documents", [])
                    if not documents:
                        break

                    # Update cache with this batch
                    synced = await cache.update_from_documents(documents)
                    total_synced += synced

                    logger.debug(
                        "Synced batch of documents to cache",
                        page=page,
                        batch_size=len(documents),
                        synced=synced
                    )

                    # Check if there are more pages
                    # If we got fewer documents than page_size, we're done
                    if len(documents) < page_size:
                        break

                    page += 1

                # Mark cache as done rebuilding
                await cache.set_rebuilding_status(False)

                logger.info("LightRAG cache sync completed", total_documents=total_synced)
                return total_synced

    except Exception as e:
        # Make sure to clear rebuilding status on error
        try:
            async with LightRAGDocumentCache() as cache:
                await cache.set_rebuilding_status(False)
        except Exception:
            pass  # Ignore errors when clearing status

        logger.error(
            "Failed to sync LightRAG cache",
            error_type=type(e).__name__,
            error_message=str(e)
        )
        raise


async def sync_single_document(adr_id: str, max_retries: int = 3) -> Optional[str]:
    """Sync a single document to the cache after it's been added to LightRAG.
    
    Since LightRAG doesn't return the doc ID on insert, we need to fetch the
    document list and find it by file_path.
    
    Args:
        adr_id: The ADR ID (used as file_path)
        max_retries: Number of times to retry finding the document
        
    Returns:
        The LightRAG document ID if found, None otherwise
    """
    settings = get_settings()
    filename = f"{adr_id}.txt"
    
    for attempt in range(max_retries):
        try:
            async with LightRAGClient(
                base_url=settings.lightrag_url,
                demo_mode=False
            ) as rag_client:
                # Fetch recent documents (the newly added one should be there)
                result = await rag_client.get_paginated_documents(
                    page=1,
                    page_size=50,
                    sort_field="created_at",
                    sort_direction="desc"
                )
                
                documents = result.get("documents", [])
                
                # Find our document by file_path
                for doc in documents:
                    if doc.get("file_path") == filename:
                        doc_id = doc.get("id")
                        if doc_id:
                            # Cache it
                            async with LightRAGDocumentCache() as cache:
                                await cache.set_doc_id(adr_id, doc_id)
                            
                            logger.info(
                                "Synced single document to cache",
                                adr_id=adr_id,
                                lightrag_doc_id=doc_id
                            )
                            return doc_id
                
                # Document not found yet, maybe it's still being processed
                if attempt < max_retries - 1:
                    logger.debug(
                        "Document not found yet, retrying",
                        adr_id=adr_id,
                        attempt=attempt + 1
                    )
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        except Exception as e:
            logger.warning(
                "Error syncing single document",
                adr_id=adr_id,
                attempt=attempt + 1,
                error=str(e)
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    
    logger.warning("Failed to sync single document after retries", adr_id=adr_id)
    return None
