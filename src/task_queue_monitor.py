"""Task queue monitoring service using Redis directly (fast).

Instead of using Celery's slow inspect() API, this queries Redis directly
for queue lengths and relies on WebSocket messages for active task tracking.
This provides instant (<10ms) access to queue metrics.
"""

import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import redis
from celery import Celery
from celery.result import AsyncResult

from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TaskInfo:
    """Information about a task in the queue."""

    task_id: str
    task_name: str
    status: str  # pending, active, success, failure
    args: tuple
    kwargs: dict
    position: Optional[int] = None  # Position in queue (0-indexed)
    started_at: Optional[float] = None
    eta: Optional[str] = None
    worker: Optional[str] = None


@dataclass
class QueueStatus:
    """Overall queue status."""

    total_tasks: int
    active_tasks: int
    pending_tasks: int
    reserved_tasks: int
    workers_online: int


class TaskQueueMonitor:
    """Monitor Celery task queue using fast Redis queries."""

    # Redis key for tracking active tasks
    ACTIVE_TASKS_KEY = "queue:active_tasks"

    def __init__(self, celery_app: Optional[Celery] = None):
        """Initialize the task queue monitor.

        Args:
            celery_app: Optional Celery app instance. If None, creates a new one.
        """
        if celery_app is None:
            # Create a new Celery app instance
            self.celery_app = Celery(
                "decision_analyzer",
                broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
                backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            )
        else:
            self.celery_app = celery_app

        # Create Redis client for fast queue queries
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def get_queue_status(self) -> QueueStatus:
        """Get overall queue status using fast Redis queries.

        Returns:
            QueueStatus with counts of tasks in various states
        """
        try:
            start = time.time()

            # Get queue length from Redis (instant - just reads a counter)
            pending_count = self.redis_client.llen("celery")  # Default queue name

            # Active tasks are tracked in Redis hash
            active_count = self.redis_client.hlen(self.ACTIVE_TASKS_KEY)

            # Total tasks = active + pending
            total_tasks = active_count + pending_count

            logger.debug(
                f"⚡ Queue status from Redis: {time.time() - start:.3f}s (active={active_count}, pending={pending_count})"
            )

            return QueueStatus(
                total_tasks=total_tasks,
                active_tasks=active_count,
                pending_tasks=pending_count,
                reserved_tasks=0,  # Not needed
                workers_online=1,  # Assume 1 worker (could query Redis for this too)
            )

        except Exception as e:
            logger.error("Failed to get queue status from Redis", error=str(e))
            return QueueStatus(
                total_tasks=0,
                active_tasks=0,
                pending_tasks=0,
                reserved_tasks=0,
                workers_online=0,
            )

    async def track_task_started(
        self, task_id: str, task_name: str, args: tuple = (), kwargs: dict = None
    ):
        """Track that a task has started (stores in Redis and broadcasts update).

        Args:
            task_id: Celery task ID
            task_name: Task name
            args: Task arguments
            kwargs: Task keyword arguments
        """
        import json

        task_info = TaskInfo(
            task_id=task_id,
            task_name=task_name,
            status="active",
            args=args,
            kwargs=kwargs or {},
            started_at=time.time(),
        )
        # Store as JSON in Redis hash
        self.redis_client.hset(
            self.ACTIVE_TASKS_KEY,
            task_id,
            json.dumps(
                {
                    "task_id": task_id,
                    "task_name": task_name,
                    "status": "active",
                    "args": list(args),
                    "kwargs": kwargs or {},
                    "started_at": task_info.started_at,
                }
            ),
        )
        logger.debug(f"📝 Tracking active task in Redis: {task_id}")

        # Broadcast updated queue status immediately
        await self._broadcast_queue_status()

    async def track_task_completed(self, task_id: str):
        """Track that a task has completed (removes from Redis and broadcasts update).

        Args:
            task_id: Celery task ID
        """
        self.redis_client.hdel(self.ACTIVE_TASKS_KEY, task_id)
        logger.debug(f"✅ Task completed (removed from Redis): {task_id}")

        # Broadcast updated queue status immediately
        await self._broadcast_queue_status()

    async def _broadcast_queue_status(self):
        """Broadcast current queue status via WebSocket."""
        from src.websocket_broadcaster import get_broadcaster

        try:
            queue_status = self.get_queue_status()
            broadcaster = get_broadcaster()
            await broadcaster.publish_queue_status(
                total_tasks=queue_status.total_tasks,
                active_tasks=queue_status.active_tasks,
                pending_tasks=queue_status.pending_tasks,
                workers_online=queue_status.workers_online,
            )
        except Exception as e:
            logger.error("Failed to broadcast queue status", error=str(e))

    def get_all_tasks(self) -> List[TaskInfo]:
        """Get all active tasks (fast - reads from Redis hash).

        Returns:
            List of TaskInfo objects for active tasks only
        """
        import json

        tasks = []
        try:
            task_data = self.redis_client.hgetall(self.ACTIVE_TASKS_KEY)
            for task_id, task_json in task_data.items():
                try:
                    data = json.loads(task_json)
                    tasks.append(
                        TaskInfo(
                            task_id=data["task_id"],
                            task_name=data["task_name"],
                            status=data["status"],
                            args=tuple(data.get("args", [])),
                            kwargs=data.get("kwargs", {}),
                            started_at=data.get("started_at"),
                        )
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"Failed to parse task data for {task_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to get tasks from Redis: {e}")

        return tasks

    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """Get information about a specific task.

        Args:
            task_id: The Celery task ID

        Returns:
            TaskInfo if found, None otherwise
        """
        import json

        # Check active tasks in Redis first
        task_json = self.redis_client.hget(self.ACTIVE_TASKS_KEY, task_id)
        if task_json:
            try:
                data = json.loads(task_json)
                return TaskInfo(
                    task_id=data["task_id"],
                    task_name=data["task_name"],
                    status=data["status"],
                    args=tuple(data.get("args", [])),
                    kwargs=data.get("kwargs", {}),
                    started_at=data.get("started_at"),
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse task data for {task_id}: {e}")

        # Task not active, check AsyncResult for completion status
        result = AsyncResult(task_id, app=self.celery_app)
        if result.state in ["SUCCESS", "FAILURE", "REVOKED"]:
            return TaskInfo(
                task_id=task_id,
                task_name="",
                status=result.state.lower(),
                args=(),
                kwargs={},
            )

        return None

    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke (cancel) a task.

        Args:
            task_id: The Celery task ID
            terminate: If True, terminate the task if it's already running

        Returns:
            True if revoke command was sent successfully
        """
        try:
            # Revoke the task (sends SIGTERM if terminate=True)
            self.celery_app.control.revoke(task_id, terminate=terminate)

            # Update the task state to REVOKED in Celery's result backend
            # This ensures that AsyncResult queries return the correct state
            result = AsyncResult(task_id, app=self.celery_app)
            result.revoke()  # This updates the backend state to REVOKED

            # Remove from Redis tracking if present
            self.redis_client.hdel(self.ACTIVE_TASKS_KEY, task_id)

            logger.info("Task revoked", task_id=task_id, terminate=terminate)
            return True
        except Exception as e:
            logger.error("Failed to revoke task", task_id=task_id, error=str(e))
            return False

    async def cleanup_orphaned_tasks(self) -> Dict[str, Any]:
        """Clean up orphaned task records in Redis.

        Orphaned tasks are those marked as active in Redis but don't have
        corresponding Celery tasks running. This can happen when:
        - Worker crashes or is killed
        - Service restarts
        - Tasks fail without proper cleanup

        Returns:
            Dict with cleanup statistics
        """
        import json

        cleaned = []
        errors = []

        try:
            # Get all active tasks from Redis
            task_data = self.redis_client.hgetall(self.ACTIVE_TASKS_KEY)

            for task_id, task_json in task_data.items():
                try:
                    # Check if task actually exists in Celery
                    result = AsyncResult(task_id, app=self.celery_app)

                    # If task is in terminal state or doesn't exist, it's orphaned
                    if result.state in ["SUCCESS", "FAILURE", "REVOKED", "REJECTED"]:
                        self.redis_client.hdel(self.ACTIVE_TASKS_KEY, task_id)
                        data = json.loads(task_json)
                        cleaned.append(
                            {
                                "task_id": task_id,
                                "task_name": data.get("task_name", "unknown"),
                                "state": result.state,
                            }
                        )
                        logger.info(
                            f"Cleaned orphaned task: {task_id} (state: {result.state})"
                        )

                except Exception as e:
                    errors.append(f"Error checking task {task_id}: {str(e)}")
                    logger.warning(f"Error checking task {task_id}: {e}")

            # Broadcast updated queue status
            await self._broadcast_queue_status()

            return {
                "cleaned_count": len(cleaned),
                "error_count": len(errors),
                "cleaned_tasks": cleaned,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Failed to cleanup orphaned tasks: {e}")
            return {
                "cleaned_count": 0,
                "error_count": 1,
                "cleaned_tasks": [],
                "errors": [str(e)],
            }

    async def clear_all_tasks(self, force: bool = False) -> Dict[str, Any]:
        """Clear all tasks from the queue.

        This will:
        1. Revoke all pending tasks in the Celery queue
        2. Optionally terminate active tasks (if force=True)
        3. Clear all task tracking data from Redis

        Args:
            force: If True, forcefully terminate running tasks

        Returns:
            Dict with clearing statistics
        """
        revoked_active = []
        errors = []

        try:
            # Get all active tasks from Redis
            active_tasks = self.get_all_tasks()

            # Revoke all active tasks
            for task in active_tasks:
                try:
                    self.celery_app.control.revoke(task.task_id, terminate=force)
                    revoked_active.append(
                        {"task_id": task.task_id, "task_name": task.task_name}
                    )
                    logger.info(f"Revoked active task: {task.task_id}")
                except Exception as e:
                    errors.append(f"Error revoking task {task.task_id}: {str(e)}")

            # Clear all active tasks from Redis
            cleared_count = self.redis_client.delete(self.ACTIVE_TASKS_KEY)

            # Purge pending tasks from queue
            try:
                purged = self.celery_app.control.purge()
                logger.info(f"Purged {purged} pending tasks from queue")
            except Exception as e:
                errors.append(f"Error purging queue: {str(e)}")
                purged = 0

            # Broadcast updated queue status
            await self._broadcast_queue_status()

            return {
                "revoked_active": len(revoked_active),
                "purged_pending": purged if isinstance(purged, int) else 0,
                "cleared_redis_records": cleared_count,
                "error_count": len(errors),
                "revoked_tasks": revoked_active,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return {
                "revoked_active": 0,
                "purged_pending": 0,
                "cleared_redis_records": 0,
                "error_count": 1,
                "revoked_tasks": [],
                "errors": [str(e)],
            }


# Singleton instance
_monitor: Optional[TaskQueueMonitor] = None


def get_task_queue_monitor() -> TaskQueueMonitor:
    """Get the singleton TaskQueueMonitor instance.

    Returns:
        TaskQueueMonitor instance
    """
    global _monitor
    if _monitor is None:
        from src.celery_app import celery_app

        _monitor = TaskQueueMonitor(celery_app)
    return _monitor
