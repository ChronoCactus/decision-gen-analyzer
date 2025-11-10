"""Cross-process WebSocket broadcaster using Redis pub/sub.

This module enables Celery workers (running in separate processes) to
broadcast WebSocket messages to clients connected to the FastAPI process.
"""

import os
import json
import asyncio
from typing import Optional
import redis.asyncio as redis
from src.logger import get_logger

logger = get_logger(__name__)


class WebSocketBroadcaster:
    """Broadcasts WebSocket messages across processes using Redis pub/sub."""
    
    CHANNEL = "websocket:broadcast"
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.listener_task: Optional[asyncio.Task] = None
        
    async def connect(self):
        """Connect to Redis for pub/sub."""
        if self.redis_client is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True
            )
            logger.info("WebSocket broadcaster connected to Redis", redis_url=redis_url)
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        if self.listener_task:
            self.listener_task.cancel()
        logger.info("WebSocket broadcaster disconnected from Redis")
    
    async def publish_upload_status(self, adr_id: str, status: str, message: str = None):
        """Publish an upload status message to Redis.
        
        This is called by Celery workers to broadcast upload status updates.
        
        Args:
            adr_id: The ADR ID
            status: Upload status: "processing", "completed", "failed"
            message: Optional status message
        """
        await self.connect()
        
        payload = {
            "type": "upload_status",
            "adr_id": adr_id,
            "status": status,
            "message": message
        }
        
        try:
            await self.redis_client.publish(
                self.CHANNEL,
                json.dumps(payload)
            )
            logger.debug(
                "📡 Published upload status to Redis",
                adr_id=adr_id,
                status=status
            )
        except Exception as e:
            logger.error(
                "Failed to publish upload status",
                error=str(e),
                adr_id=adr_id
            )
    
    async def publish_cache_status(self, is_rebuilding: bool, last_sync_time: float = None):
        """Publish a cache status message to Redis.
        
        Args:
            is_rebuilding: Whether the cache is currently rebuilding
            last_sync_time: Unix timestamp of last successful sync
        """
        await self.connect()
        
        payload = {
            "type": "cache_status",
            "is_rebuilding": is_rebuilding,
            "last_sync_time": last_sync_time
        }
        
        try:
            await self.redis_client.publish(
                self.CHANNEL,
                json.dumps(payload)
            )
            logger.debug(
                "📡 Published cache status to Redis",
                is_rebuilding=is_rebuilding
            )
        except Exception as e:
            logger.error(
                "Failed to publish cache status",
                error=str(e)
            )
    
    async def start_listening(self, websocket_manager):
        """Start listening for Redis pub/sub messages and forward to WebSocket clients.
        
        This is called by the FastAPI process on startup.
        
        Args:
            websocket_manager: The WebSocketManager instance to broadcast to
        """
        await self.connect()
        
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe(self.CHANNEL)
        
        logger.info("🎧 Started listening for WebSocket broadcasts on Redis")
        
        async def listen():
            try:
                async for message in self.pubsub.listen():
                    if message["type"] == "message":
                        try:
                            payload = json.loads(message["data"])
                            logger.debug("📩 Received broadcast from Redis", payload=payload)
                            
                            if payload["type"] == "upload_status":
                                await websocket_manager.broadcast_upload_status(
                                    adr_id=payload["adr_id"],
                                    status=payload["status"],
                                    message=payload.get("message")
                                )
                            elif payload["type"] == "cache_status":
                                await websocket_manager.broadcast_cache_status(
                                    is_rebuilding=payload["is_rebuilding"],
                                    last_sync_time=payload.get("last_sync_time")
                                )
                        except Exception as e:
                            logger.error(
                                "Failed to process Redis broadcast",
                                error=str(e),
                                message=message
                            )
            except asyncio.CancelledError:
                logger.info("Redis listener task cancelled")
                raise
            except Exception as e:
                logger.error("Redis listener error", error=str(e))
        
        self.listener_task = asyncio.create_task(listen())
        return self.listener_task


# Global broadcaster instance
_broadcaster: WebSocketBroadcaster = None


def get_broadcaster() -> WebSocketBroadcaster:
    """Get or create the global broadcaster instance."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = WebSocketBroadcaster()
    return _broadcaster
