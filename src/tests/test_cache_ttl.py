"""Test cache TTL handling to verify Redis receives seconds, not timedelta objects."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.lightrag_doc_cache import LightRAGDocumentCache


class TestCacheTTL:
    """Test that cache TTL values are correctly converted to seconds for Redis."""

    @pytest_asyncio.fixture
    async def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.pipeline = MagicMock()

        # Mock pipeline
        pipeline = AsyncMock()
        pipeline.setex = MagicMock()
        pipeline.execute = AsyncMock()
        redis.pipeline.return_value = pipeline

        redis.set = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.delete = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_set_doc_id_uses_seconds_not_timedelta(self, mock_redis):
        """Test that set_doc_id converts timedelta to seconds for Redis setex."""
        cache = LightRAGDocumentCache()
        cache._redis = mock_redis

        # Set a document ID
        await cache.set_doc_id("test_file.json", "test-doc-123")

        # Verify setex was called with integer seconds, not timedelta
        mock_redis.setex.assert_awaited_once()
        call_args = mock_redis.setex.call_args

        # Get the TTL argument (second positional argument)
        ttl_arg = call_args[0][1]

        # Should be an integer (seconds), not timedelta
        assert isinstance(ttl_arg, int), f"Expected int, got {type(ttl_arg)}"

        # Should be 24 hours in seconds (86400)
        expected_seconds = int(timedelta(hours=24).total_seconds())
        assert (
            ttl_arg == expected_seconds
        ), f"Expected {expected_seconds} seconds, got {ttl_arg}"

    @pytest.mark.asyncio
    async def test_set_upload_status_uses_seconds_not_timedelta(self, mock_redis):
        """Test that set_upload_status converts timedelta to seconds for Redis setex."""
        cache = LightRAGDocumentCache()
        cache._redis = mock_redis

        # Set upload status
        await cache.set_upload_status(
            adr_id="test-adr-123",
            track_id="test-track-456",
            status="processing",
            message="Test message",
        )

        # Verify both setex calls used integer seconds
        assert mock_redis.setex.await_count == 2, "Expected 2 setex calls"

        for call_obj in mock_redis.setex.await_args_list:
            ttl_arg = call_obj[0][1]
            assert isinstance(ttl_arg, int), f"Expected int, got {type(ttl_arg)}"

            # Should be 1 hour in seconds (3600)
            expected_seconds = int(timedelta(hours=1).total_seconds())
            assert (
                ttl_arg == expected_seconds
            ), f"Expected {expected_seconds} seconds, got {ttl_arg}"

    @pytest.mark.asyncio
    async def test_update_from_documents_uses_seconds_not_timedelta(self, mock_redis):
        """Test that update_from_documents converts timedelta to seconds for Redis pipeline.setex."""
        cache = LightRAGDocumentCache()
        cache._redis = mock_redis

        # Mock pipeline
        pipeline = mock_redis.pipeline.return_value

        # Update from documents
        documents = [
            {"id": "doc-1", "file_path": "file1.json"},
            {"id": "doc-2", "file_path": "file2.json"},
        ]

        result = await cache.update_from_documents(documents)

        # Verify pipeline.setex was called for each document
        assert pipeline.setex.call_count == 2, "Expected 2 pipeline.setex calls"
        assert result == 2, "Expected 2 documents cached"

        # Verify each call used integer seconds
        for call_obj in pipeline.setex.call_args_list:
            ttl_arg = call_obj[0][1]
            assert isinstance(ttl_arg, int), f"Expected int, got {type(ttl_arg)}"

            # Should be 24 hours in seconds (86400)
            expected_seconds = int(timedelta(hours=24).total_seconds())
            assert (
                ttl_arg == expected_seconds
            ), f"Expected {expected_seconds} seconds, got {ttl_arg}"

    @pytest.mark.asyncio
    async def test_cache_ttl_values(self):
        """Test that TTL constants are set to expected durations."""
        cache = LightRAGDocumentCache()

        # Verify CACHE_TTL is 24 hours
        assert cache.CACHE_TTL == timedelta(hours=24)
        assert int(cache.CACHE_TTL.total_seconds()) == 86400

        # Verify UPLOAD_STATUS_TTL is 1 hour
        assert cache.UPLOAD_STATUS_TTL == timedelta(hours=1)
        assert int(cache.UPLOAD_STATUS_TTL.total_seconds()) == 3600
