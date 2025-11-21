"""Redis-based cache for LightRAG document ID mappings."""

import os
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

from src.logger import get_logger

logger = get_logger(__name__)


class LightRAGDocumentCache:
    """Cache for mapping file paths to LightRAG document IDs using Redis."""

    CACHE_KEY_PREFIX = "lightrag:doc:"
    CACHE_ALL_DOCS_KEY = "lightrag:all_docs"
    CACHE_LAST_SYNC_KEY = "lightrag:last_sync"
    CACHE_REBUILD_STATUS_KEY = "lightrag:rebuild_status"
    UPLOAD_STATUS_KEY_PREFIX = "lightrag:upload_status:"  # {adr_id} -> track_id
    TRACK_ID_KEY_PREFIX = "lightrag:track_id:"  # {track_id} -> status info
    CACHE_TTL = timedelta(hours=24)  # Cache entries expire after 24 hours
    UPLOAD_STATUS_TTL = timedelta(hours=1)  # Upload status expires after 1 hour

    def __init__(self, redis_url: Optional[str] = None):
        """Initialize the document cache.

        Args:
            redis_url: Redis connection URL. Defaults to REDIS_URL env var.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[aioredis.Redis] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._redis = await aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._redis:
            await self._redis.close()

    async def get_doc_id(self, file_path: str) -> Optional[str]:
        """Get the LightRAG document ID for a given file path.

        Args:
            file_path: The file path (e.g., "adr-123.txt" or just "adr-123")

        Returns:
            The LightRAG document ID (e.g., "doc-abc123...") or None if not found
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        # Normalize file path to ensure .txt extension
        if not file_path.endswith(".txt"):
            file_path = f"{file_path}.txt"

        cache_key = f"{self.CACHE_KEY_PREFIX}{file_path}"
        doc_id = await self._redis.get(cache_key)

        if doc_id:
            logger.debug("Cache hit for file_path", file_path=file_path, doc_id=doc_id)
        else:
            logger.debug("Cache miss for file_path", file_path=file_path)

        return doc_id

    async def set_doc_id(self, file_path: str, doc_id: str) -> None:
        """Set the LightRAG document ID for a given file path.

        Args:
            file_path: The file path (e.g., "adr-123.txt")
            doc_id: The LightRAG document ID (e.g., "doc-abc123...")
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        # Normalize file path to ensure .txt extension
        if not file_path.endswith(".txt"):
            file_path = f"{file_path}.txt"

        cache_key = f"{self.CACHE_KEY_PREFIX}{file_path}"
        await self._redis.setex(cache_key, self.CACHE_TTL, doc_id)
        logger.debug("Cached document ID", file_path=file_path, doc_id=doc_id)

    async def delete_doc_id(self, file_path: str) -> None:
        """Remove a document ID from the cache.

        Args:
            file_path: The file path to remove
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        # Normalize file path to ensure .txt extension
        if not file_path.endswith(".txt"):
            file_path = f"{file_path}.txt"

        cache_key = f"{self.CACHE_KEY_PREFIX}{file_path}"
        await self._redis.delete(cache_key)
        logger.debug("Removed document ID from cache", file_path=file_path)

    async def update_from_documents(self, documents: List[Dict]) -> int:
        """Update cache from a list of document dictionaries.

        Args:
            documents: List of document dicts with 'id' and 'file_path' fields

        Returns:
            Number of documents cached
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        count = 0
        pipeline = self._redis.pipeline()

        for doc in documents:
            doc_id = doc.get("id")
            file_path = doc.get("file_path")

            if doc_id and file_path:
                cache_key = f"{self.CACHE_KEY_PREFIX}{file_path}"
                pipeline.setex(cache_key, self.CACHE_TTL, doc_id)
                count += 1

        await pipeline.execute()

        # Update last sync timestamp (Unix timestamp in seconds)
        await self._redis.set(self.CACHE_LAST_SYNC_KEY, str(time.time()))

        logger.info("Updated document ID cache", count=count)
        return count

    async def clear_all(self) -> None:
        """Clear all cached document IDs."""
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        # Find all keys matching our prefix
        cursor = 0
        keys_to_delete = []

        while True:
            cursor, keys = await self._redis.scan(
                cursor=cursor, match=f"{self.CACHE_KEY_PREFIX}*", count=100
            )
            keys_to_delete.extend(keys)

            if cursor == 0:
                break

        if keys_to_delete:
            await self._redis.delete(*keys_to_delete)
            logger.info("Cleared document ID cache", count=len(keys_to_delete))

    async def is_rebuilding(self) -> bool:
        """Check if the cache is currently being rebuilt.

        Returns:
            True if cache rebuild is in progress, False otherwise
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        status = await self._redis.get(self.CACHE_REBUILD_STATUS_KEY)
        return status == "rebuilding"

    async def set_rebuilding_status(self, is_rebuilding: bool) -> None:
        """Set the cache rebuild status and broadcast to WebSocket clients.

        Args:
            is_rebuilding: True to mark as rebuilding, False to mark as complete
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        if is_rebuilding:
            await self._redis.set(self.CACHE_REBUILD_STATUS_KEY, "rebuilding")
            logger.info("Cache rebuild started")
        else:
            await self._redis.delete(self.CACHE_REBUILD_STATUS_KEY)
            # Update last sync timestamp when rebuild completes (Unix timestamp in seconds)
            await self._redis.set(self.CACHE_LAST_SYNC_KEY, str(time.time()))
            logger.info("Cache rebuild completed")

        # Broadcast status change via WebSocket (cross-process using Redis pub/sub)
        try:
            from src.websocket_broadcaster import get_broadcaster

            broadcaster = get_broadcaster()

            last_sync_time = None
            if not is_rebuilding:
                # Get the sync time we just set
                last_sync_str = await self._redis.get(self.CACHE_LAST_SYNC_KEY)
                if last_sync_str:
                    last_sync_time = float(last_sync_str)

            await broadcaster.publish_cache_status(
                is_rebuilding=is_rebuilding, last_sync_time=last_sync_time
            )
            logger.debug(
                "Broadcasted cache status change",
                is_rebuilding=is_rebuilding,
                last_sync_time=last_sync_time,
            )
        except Exception as e:
            # Don't fail the rebuild if broadcast fails
            logger.warning(
                "Failed to broadcast cache status change",
                error=str(e),
                is_rebuilding=is_rebuilding,
            )

    async def get_last_sync_time(self) -> Optional[float]:
        """Get the timestamp of the last cache sync.

        Returns:
            Unix timestamp of last sync, or None if never synced
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        timestamp_str = await self._redis.get(self.CACHE_LAST_SYNC_KEY)
        if timestamp_str:
            try:
                return float(timestamp_str)
            except ValueError:
                return None
        return None

    async def set_upload_status(
        self, adr_id: str, track_id: str, status: str, message: Optional[str] = None
    ) -> None:
        """Track the upload status of an ADR to LightRAG.

        Args:
            adr_id: The ADR ID
            track_id: The LightRAG tracking ID
            status: Status: "uploading", "processing", "completed", "failed"
            message: Optional status message
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        import json

        status_info = {
            "adr_id": adr_id,
            "track_id": track_id,
            "status": status,
            "message": message,
            "timestamp": time.time(),
        }

        # Store track_id mapping for ADR
        upload_key = f"{self.UPLOAD_STATUS_KEY_PREFIX}{adr_id}"
        await self._redis.setex(upload_key, self.UPLOAD_STATUS_TTL, track_id)

        # Store detailed status info by track_id
        track_key = f"{self.TRACK_ID_KEY_PREFIX}{track_id}"
        await self._redis.setex(
            track_key, self.UPLOAD_STATUS_TTL, json.dumps(status_info)
        )

        logger.debug(
            "Upload status updated", adr_id=adr_id, track_id=track_id, status=status
        )

    async def get_upload_status(self, adr_id: str) -> Optional[Dict[str, Any]]:
        """Get the upload status for an ADR.

        Args:
            adr_id: The ADR ID

        Returns:
            Upload status dict or None if not being tracked
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        import json

        # Get track_id for this ADR
        upload_key = f"{self.UPLOAD_STATUS_KEY_PREFIX}{adr_id}"
        track_id = await self._redis.get(upload_key)

        if not track_id:
            return None

        # Get status info
        track_key = f"{self.TRACK_ID_KEY_PREFIX}{track_id}"
        status_json = await self._redis.get(track_key)

        if not status_json:
            return None

        try:
            return json.loads(status_json)
        except json.JSONDecodeError:
            logger.error("Failed to parse upload status JSON", track_id=track_id)
            return None

    async def clear_upload_status(self, adr_id: str) -> None:
        """Clear the upload status for an ADR.

        Args:
            adr_id: The ADR ID
        """
        if not self._redis:
            raise RuntimeError("Cache not initialized. Use as async context manager.")

        upload_key = f"{self.UPLOAD_STATUS_KEY_PREFIX}{adr_id}"
        track_id = await self._redis.get(upload_key)

        if track_id:
            track_key = f"{self.TRACK_ID_KEY_PREFIX}{track_id}"
            await self._redis.delete(track_key)

        await self._redis.delete(upload_key)
        logger.debug("Upload status cleared", adr_id=adr_id)
