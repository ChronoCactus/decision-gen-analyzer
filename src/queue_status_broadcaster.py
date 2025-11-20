"""Background task to periodically broadcast queue status via WebSocket.

This task runs continuously and broadcasts queue status updates every
few seconds, so clients don't need to poll the inspect API directly.
"""

import asyncio

from src.logger import get_logger
from src.task_queue_monitor import get_task_queue_monitor
from src.websocket_broadcaster import get_broadcaster

logger = get_logger(__name__)


async def broadcast_queue_status_periodically(interval_seconds: int = 5):
    """Periodically broadcast queue status to all WebSocket clients.

    This task runs in the background and sends queue status updates
    via WebSocket every few seconds, providing real-time visibility
    to connected clients without them needing to poll.

    Args:
        interval_seconds: How often to broadcast updates (default: 5 seconds)
    """
    broadcaster = get_broadcaster()
    monitor = get_task_queue_monitor()

    logger.info(
        "Starting periodic queue status broadcaster", interval_seconds=interval_seconds
    )

    try:
        while True:
            try:
                # Get current queue status (now fast with Redis - no need for thread pool)
                queue_status = monitor.get_queue_status()

                # Broadcast to all connected WebSocket clients
                await broadcaster.publish_queue_status(
                    total_tasks=queue_status.total_tasks,
                    active_tasks=queue_status.active_tasks,
                    pending_tasks=queue_status.pending_tasks,
                    workers_online=queue_status.workers_online,
                )

                logger.debug(
                    "📡 Broadcasted queue status",
                    total_tasks=queue_status.total_tasks,
                    active_tasks=queue_status.active_tasks,
                    pending_tasks=queue_status.pending_tasks,
                )

            except Exception as e:
                logger.error(
                    "Failed to broadcast queue status",
                    error=str(e),
                    error_type=type(e).__name__,
                )

            # Wait before next broadcast
            await asyncio.sleep(interval_seconds)

    except asyncio.CancelledError:
        logger.info("Queue status broadcaster cancelled")
        raise
    except Exception as e:
        logger.error(
            "Queue status broadcaster error", error=str(e), error_type=type(e).__name__
        )
