"""Tests for task queue monitor cleanup and management features."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.task_queue_monitor import TaskInfo, TaskQueueMonitor


class TestTaskQueueMonitorCleanup:
    """Test task queue monitor cleanup and management methods."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis_mock = MagicMock()
        redis_mock.hgetall.return_value = {}
        redis_mock.hlen.return_value = 0
        redis_mock.llen.return_value = 0
        redis_mock.hdel.return_value = 1
        redis_mock.delete.return_value = 1
        return redis_mock

    @pytest.fixture
    def mock_celery_app(self):
        """Create a mock Celery app."""
        celery_mock = MagicMock()
        celery_mock.control.revoke = MagicMock()
        celery_mock.control.purge = MagicMock(return_value=5)
        return celery_mock

    @pytest.fixture
    def monitor(self, mock_celery_app, mock_redis):
        """Create a TaskQueueMonitor with mocked dependencies."""
        monitor = TaskQueueMonitor(mock_celery_app)
        monitor.redis_client = mock_redis
        return monitor

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_tasks_success(self, monitor, mock_redis):
        """Test successful cleanup of orphaned tasks."""
        # Setup: Redis has 2 tasks, one is orphaned (SUCCESS state)
        mock_redis.hgetall.return_value = {
            "task-1": '{"task_id": "task-1", "task_name": "generate_adr", "status": "active", "args": [], "kwargs": {}}',
            "task-2": '{"task_id": "task-2", "task_name": "analyze_adr", "status": "active", "args": [], "kwargs": {}}',
        }

        # Mock AsyncResult to return SUCCESS for task-1 (orphaned), PENDING for task-2 (still running)
        with patch("src.task_queue_monitor.AsyncResult") as mock_async_result:

            def create_result(task_id, **kwargs):
                result = MagicMock()
                result.state = "SUCCESS" if task_id == "task-1" else "PENDING"
                return result

            mock_async_result.side_effect = create_result

            # Mock the broadcast method
            with patch.object(
                monitor, "_broadcast_queue_status", new_callable=AsyncMock
            ) as mock_broadcast:
                result = await monitor.cleanup_orphaned_tasks()

        # Verify
        assert result["cleaned_count"] == 1
        assert result["error_count"] == 0
        assert len(result["cleaned_tasks"]) == 1
        assert result["cleaned_tasks"][0]["task_id"] == "task-1"
        assert result["cleaned_tasks"][0]["state"] == "SUCCESS"

        # Verify Redis hdel was called for orphaned task
        mock_redis.hdel.assert_called_once_with(monitor.ACTIVE_TASKS_KEY, "task-1")

        # Verify broadcast was called
        mock_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_tasks_no_orphans(self, monitor, mock_redis):
        """Test cleanup when no orphaned tasks exist."""
        # Setup: Redis has 1 task that's still running
        mock_redis.hgetall.return_value = {
            "task-1": '{"task_id": "task-1", "task_name": "generate_adr", "status": "active", "args": [], "kwargs": {}}'
        }

        with patch("src.task_queue_monitor.AsyncResult") as mock_async_result:
            result_mock = MagicMock()
            result_mock.state = "PENDING"
            mock_async_result.return_value = result_mock

            with patch.object(
                monitor, "_broadcast_queue_status", new_callable=AsyncMock
            ):
                result = await monitor.cleanup_orphaned_tasks()

        # Verify
        assert result["cleaned_count"] == 0
        assert result["error_count"] == 0
        assert len(result["cleaned_tasks"]) == 0

        # Verify Redis hdel was NOT called
        mock_redis.hdel.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_tasks_multiple_states(self, monitor, mock_redis):
        """Test cleanup identifies all terminal states as orphaned."""
        # Setup: Tasks in various terminal states
        mock_redis.hgetall.return_value = {
            "task-1": '{"task_id": "task-1", "task_name": "task1", "status": "active", "args": [], "kwargs": {}}',
            "task-2": '{"task_id": "task-2", "task_name": "task2", "status": "active", "args": [], "kwargs": {}}',
            "task-3": '{"task_id": "task-3", "task_name": "task3", "status": "active", "args": [], "kwargs": {}}',
            "task-4": '{"task_id": "task-4", "task_name": "task4", "status": "active", "args": [], "kwargs": {}}',
        }

        states = {
            "task-1": "SUCCESS",
            "task-2": "FAILURE",
            "task-3": "REVOKED",
            "task-4": "REJECTED",
        }

        with patch("src.task_queue_monitor.AsyncResult") as mock_async_result:

            def create_result(task_id, **kwargs):
                result = MagicMock()
                result.state = states.get(task_id, "PENDING")
                return result

            mock_async_result.side_effect = create_result

            with patch.object(
                monitor, "_broadcast_queue_status", new_callable=AsyncMock
            ):
                result = await monitor.cleanup_orphaned_tasks()

        # Verify all terminal states were cleaned
        assert result["cleaned_count"] == 4
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_tasks_with_errors(self, monitor, mock_redis):
        """Test cleanup handles errors gracefully."""
        # Setup: Redis has tasks but one throws an error
        mock_redis.hgetall.return_value = {
            "task-1": '{"task_id": "task-1", "task_name": "task1", "status": "active", "args": [], "kwargs": {}}',
            "task-2": '{"task_id": "task-2", "task_name": "task2", "status": "active", "args": [], "kwargs": {}}',
        }

        with patch("src.task_queue_monitor.AsyncResult") as mock_async_result:

            def create_result(task_id, **kwargs):
                if task_id == "task-1":
                    raise Exception("Redis connection error")
                result = MagicMock()
                result.state = "SUCCESS"
                return result

            mock_async_result.side_effect = create_result

            with patch.object(
                monitor, "_broadcast_queue_status", new_callable=AsyncMock
            ):
                result = await monitor.cleanup_orphaned_tasks()

        # Verify: task-2 cleaned, task-1 recorded error
        assert result["cleaned_count"] == 1
        assert result["error_count"] == 1
        assert len(result["errors"]) == 1
        assert "task-1" in result["errors"][0]

    @pytest.mark.asyncio
    async def test_clear_all_tasks_success(self, monitor, mock_redis, mock_celery_app):
        """Test successful clearing of all tasks."""
        # Setup: Monitor has 2 active tasks
        monitor.get_all_tasks = MagicMock(
            return_value=[
                TaskInfo(
                    task_id="task-1",
                    task_name="generate_adr",
                    status="active",
                    args=(),
                    kwargs={},
                ),
                TaskInfo(
                    task_id="task-2",
                    task_name="analyze_adr",
                    status="active",
                    args=(),
                    kwargs={},
                ),
            ]
        )

        mock_celery_app.control.purge.return_value = 3  # 3 pending tasks purged

        with patch.object(
            monitor, "_broadcast_queue_status", new_callable=AsyncMock
        ) as mock_broadcast:
            result = await monitor.clear_all_tasks(force=False)

        # Verify
        assert result["revoked_active"] == 2
        assert result["purged_pending"] == 3
        assert result["cleared_redis_records"] == 1
        assert result["error_count"] == 0
        assert len(result["revoked_tasks"]) == 2

        # Verify Celery control.revoke was called for each task
        assert mock_celery_app.control.revoke.call_count == 2
        mock_celery_app.control.revoke.assert_any_call("task-1", terminate=False)
        mock_celery_app.control.revoke.assert_any_call("task-2", terminate=False)

        # Verify purge was called
        mock_celery_app.control.purge.assert_called_once()

        # Verify Redis delete was called
        mock_redis.delete.assert_called_once_with(monitor.ACTIVE_TASKS_KEY)

        # Verify broadcast was called
        mock_broadcast.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all_tasks_with_force(
        self, monitor, mock_redis, mock_celery_app
    ):
        """Test clearing all tasks with force terminate."""
        monitor.get_all_tasks = MagicMock(
            return_value=[
                TaskInfo(
                    task_id="task-1",
                    task_name="generate_adr",
                    status="active",
                    args=(),
                    kwargs={},
                )
            ]
        )

        with patch.object(monitor, "_broadcast_queue_status", new_callable=AsyncMock):
            await monitor.clear_all_tasks(force=True)

        # Verify terminate=True was passed
        mock_celery_app.control.revoke.assert_called_once_with("task-1", terminate=True)

    @pytest.mark.asyncio
    async def test_clear_all_tasks_empty_queue(
        self, monitor, mock_redis, mock_celery_app
    ):
        """Test clearing when queue is empty."""
        monitor.get_all_tasks = MagicMock(return_value=[])
        mock_celery_app.control.purge.return_value = 0

        with patch.object(monitor, "_broadcast_queue_status", new_callable=AsyncMock):
            result = await monitor.clear_all_tasks(force=False)

        # Verify
        assert result["revoked_active"] == 0
        assert result["purged_pending"] == 0
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_clear_all_tasks_with_errors(
        self, monitor, mock_redis, mock_celery_app
    ):
        """Test clear_all_tasks handles errors gracefully."""
        monitor.get_all_tasks = MagicMock(
            return_value=[
                TaskInfo(
                    task_id="task-1",
                    task_name="task1",
                    status="active",
                    args=(),
                    kwargs={},
                ),
                TaskInfo(
                    task_id="task-2",
                    task_name="task2",
                    status="active",
                    args=(),
                    kwargs={},
                ),
            ]
        )

        # First revoke succeeds, second fails
        def revoke_side_effect(task_id, **kwargs):
            if task_id == "task-2":
                raise Exception("Revoke failed")

        mock_celery_app.control.revoke.side_effect = revoke_side_effect

        with patch.object(monitor, "_broadcast_queue_status", new_callable=AsyncMock):
            result = await monitor.clear_all_tasks(force=False)

        # Verify: one success, one error
        assert result["revoked_active"] == 1
        assert result["error_count"] == 1
        assert "task-2" in result["errors"][0]

    def test_revoke_task_removes_from_redis(self, monitor, mock_redis, mock_celery_app):
        """Test that revoking a task also removes it from Redis tracking."""
        # Mock AsyncResult.revoke() method
        with patch("src.task_queue_monitor.AsyncResult") as mock_async_result:
            mock_result_instance = MagicMock()
            mock_async_result.return_value = mock_result_instance

            success = monitor.revoke_task("task-1", terminate=False)

            assert success is True
            # Verify control.revoke was called (terminates the worker process)
            mock_celery_app.control.revoke.assert_called_once_with(
                "task-1", terminate=False
            )
            # Verify AsyncResult.revoke was called (updates backend state to REVOKED)
            mock_result_instance.revoke.assert_called_once()
            # Verify Redis tracking was removed
            mock_redis.hdel.assert_called_once_with(monitor.ACTIVE_TASKS_KEY, "task-1")

    def test_revoke_task_handles_errors(self, monitor, mock_celery_app):
        """Test revoke_task handles errors gracefully."""
        mock_celery_app.control.revoke.side_effect = Exception("Connection error")

        success = monitor.revoke_task("task-1", terminate=False)

        assert success is False
