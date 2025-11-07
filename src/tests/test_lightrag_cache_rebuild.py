"""Tests for LightRAG document cache rebuild status tracking."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.lightrag_doc_cache import LightRAGDocumentCache


class TestLightRAGDocumentCacheRebuildStatus:
    """Test cache rebuild status tracking."""

    @pytest.mark.asyncio
    async def test_is_rebuilding_returns_false_by_default(self):
        """Test that is_rebuilding returns False when status is not set."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.close = AsyncMock()
            
            # Make from_url return the mock directly (it's a coroutine)
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                result = await cache.is_rebuilding()
                
                assert result is False
                mock_redis.get.assert_called_once_with(
                    LightRAGDocumentCache.CACHE_REBUILD_STATUS_KEY
                )

    @pytest.mark.asyncio
    async def test_is_rebuilding_returns_true_when_set(self):
        """Test that is_rebuilding returns True when status is 'rebuilding'."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.get = AsyncMock(return_value="rebuilding")
            mock_redis.close = AsyncMock()
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                result = await cache.is_rebuilding()
                
                assert result is True

    @pytest.mark.asyncio
    async def test_set_rebuilding_status_true(self):
        """Test setting rebuilding status to True."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.set = AsyncMock()
            mock_redis.close = AsyncMock()
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                await cache.set_rebuilding_status(True)
                
                mock_redis.set.assert_called_once_with(
                    LightRAGDocumentCache.CACHE_REBUILD_STATUS_KEY,
                    "rebuilding"
                )

    @pytest.mark.asyncio
    async def test_set_rebuilding_status_false(self):
        """Test setting rebuilding status to False (deletes key)."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.delete = AsyncMock()
            mock_redis.close = AsyncMock()
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                await cache.set_rebuilding_status(False)
                
                mock_redis.delete.assert_called_once_with(
                    LightRAGDocumentCache.CACHE_REBUILD_STATUS_KEY
                )

    @pytest.mark.asyncio
    async def test_clear_all_removes_doc_keys(self):
        """Test that clear_all removes all document cache keys."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.close = AsyncMock()
            
            # Mock scan to return some keys
            async def mock_scan(cursor=0, match=None, count=100):
                if cursor == 0:
                    return (0, [
                        "lightrag:doc:file1.txt",
                        "lightrag:doc:file2.txt",
                        "lightrag:doc:file3.txt"
                    ])
                return (0, [])
            
            mock_redis.scan = mock_scan
            mock_redis.delete = AsyncMock()
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                await cache.clear_all()
                
                # Verify delete was called with all keys
                mock_redis.delete.assert_called_once()
                call_args = mock_redis.delete.call_args[0]
                assert len(call_args) == 3
                assert "lightrag:doc:file1.txt" in call_args
                assert "lightrag:doc:file2.txt" in call_args
                assert "lightrag:doc:file3.txt" in call_args

    @pytest.mark.asyncio
    async def test_get_last_sync_time_returns_timestamp(self):
        """Test that get_last_sync_time returns the stored timestamp."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_redis.get = AsyncMock(return_value="1699392000.0")
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                result = await cache.get_last_sync_time()
                
                assert result == 1699392000.0
                mock_redis.get.assert_called_once_with(
                    LightRAGDocumentCache.CACHE_LAST_SYNC_KEY
                )

    @pytest.mark.asyncio
    async def test_get_last_sync_time_returns_none_when_not_set(self):
        """Test that get_last_sync_time returns None when no sync has occurred."""
        with patch('redis.asyncio.from_url') as mock_redis_factory:
            mock_redis = AsyncMock()
            mock_redis.close = AsyncMock()
            mock_redis.get = AsyncMock(return_value=None)
            
            async def mock_from_url(*args, **kwargs):
                return mock_redis
            
            mock_redis_factory.side_effect = mock_from_url
            
            async with LightRAGDocumentCache() as cache:
                result = await cache.get_last_sync_time()
                
                assert result is None
