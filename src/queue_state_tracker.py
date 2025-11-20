"""Fast queue state tracking using Redis.

Instead of using Celery's slow inspect() API, we maintain queue state
directly in Redis and update it as tasks start/complete. This provides
instant access to queue metrics without the 2+ second inspect delay.
"""

import json
from typing import Dict

import redis.asyncio as redis

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class QueueStateTracker:
    """Track queue state in Redis for fast access."""

    # Redis keys
    QUEUE_STATS_KEY = "queue:stats"
    ACTIVE_TASKS_KEY = "queue:active_tasks"

    def __init__(self):
        self.redis_client: redis.Redis = None

    async def connect(self):
        """Connect to Redis."""
        if self.redis_client is None:
            self.redis_client = redis.from_url(
                settings.redis_url, decode_responses=True
            )

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis_client:
            await self.redis_client.close()

    async def task_started(
        self, task_id: str, task_name: str, args: tuple, kwargs: dict
    ):
        """Record that a task has started.

        Args:
            task_id: Celery task ID
            task_name: Task name
            args: Task arguments
            kwargs: Task keyword arguments
        """
        await self.connect()

        # Store task info
        task_info = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "active",
            "args": list(args),
            "kwargs": kwargs,
            "started_at": None,  # Could add timestamp
        }

        # Add to active tasks set
        await self.redis_client.hset(
            self.ACTIVE_TASKS_KEY, task_id, json.dumps(task_info)
        )

        # Increment active count
        await self.redis_client.hincrby(self.QUEUE_STATS_KEY, "active_tasks", 1)

        logger.debug(f"📝 Tracked task start: {task_id}")

    async def task_completed(self, task_id: str):
        """Record that a task has completed.

        Args:
            task_id: Celery task ID
        """
        await self.connect()

        # Remove from active tasks
        await self.redis_client.hdel(self.ACTIVE_TASKS_KEY, task_id)

        # Decrement active count
        await self.redis_client.hincrby(self.QUEUE_STATS_KEY, "active_tasks", -1)

        logger.debug(f"✅ Tracked task completion: {task_id}")

    async def get_queue_stats(self) -> Dict[str, int]:
        """Get current queue statistics.

        Returns:
            Dict with active_tasks count
        """
        await self.connect()

        stats = await self.redis_client.hgetall(self.QUEUE_STATS_KEY)

        return {
            "active_tasks": int(stats.get("active_tasks", 0)),
            "workers_online": 1,  # Could track this too
        }

    async def get_active_tasks(self) -> list:
        """Get all active tasks.

        Returns:
            List of task info dicts
        """
        await self.connect()

        tasks_data = await self.redis_client.hgetall(self.ACTIVE_TASKS_KEY)

        tasks = []
        for task_id, task_json in tasks_data.items():
            try:
                task_info = json.loads(task_json)
                tasks.append(task_info)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse task info for {task_id}")

        return tasks


# Singleton instance
_tracker: QueueStateTracker = None


def get_queue_state_tracker() -> QueueStateTracker:
    """Get the global queue state tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = QueueStateTracker()
    return _tracker
