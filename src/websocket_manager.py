"""WebSocket manager for broadcasting cache status updates."""

from typing import Set
from fastapi import WebSocket
from src.logger import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts cache status updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket client connected", total_connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info("WebSocket client disconnected", total_connections=len(self.active_connections))

    async def broadcast_cache_status(self, is_rebuilding: bool, last_sync_time: float = None):
        """Broadcast cache status to all connected clients.
        
        Args:
            is_rebuilding: Whether the cache is currently rebuilding
            last_sync_time: Unix timestamp of last successful sync (None if never synced)
        """
        message = {
            "type": "cache_status",
            "is_rebuilding": is_rebuilding,
            "last_sync_time": last_sync_time
        }

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(
                    "Failed to send message to WebSocket client",
                    error=str(e),
                    error_type=type(e).__name__
                )
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

        if self.active_connections:
            logger.debug(
                "Broadcasted cache status",
                is_rebuilding=is_rebuilding,
                recipients=len(self.active_connections)
            )

    async def broadcast_upload_status(
        self, adr_id: str, status: str, message: str = None
    ):
        """Broadcast upload status for a specific ADR to all connected clients.

        Args:
            adr_id: The ADR ID
            status: Upload status: "processing", "completed", "failed"
            message: Optional status message
        """
        ws_message = {
            "type": "upload_status",
            "adr_id": adr_id,
            "status": status,
            "message": message,
        }

        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(ws_message)
            except Exception as e:
                logger.warning(
                    "Failed to send upload status to WebSocket client",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

        if self.active_connections:
            logger.debug(
                "Broadcasted upload status",
                adr_id=adr_id,
                status=status,
                recipients=len(self.active_connections),
            )


# Global WebSocket manager instance
_websocket_manager: WebSocketManager = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create the global WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
