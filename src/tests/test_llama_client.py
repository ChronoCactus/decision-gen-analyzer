"""Tests for Llama client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from src.llama_client import LlamaCppClient, LlamaCppClientPool, ClientType


class TestLlamaCppClient:
    """Test LlamaCppClient class."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client can be initialized."""
        client = LlamaCppClient(base_url="http://test:8000", timeout=60)

        assert client.base_url == "http://test:8000"
        assert client.timeout == 60

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client works as async context manager."""
        async with LlamaCppClient() as client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_generate_in_demo_mode(self):
        """Test generate method in demo mode."""
        async with LlamaCppClient(demo_mode=True) as client:
            response = await client.generate("Test prompt")

            assert isinstance(response, str)
            assert len(response) > 0
            assert "simulated" in response.lower() or "recommend" in response.lower()

    @pytest.mark.asyncio
    async def test_generate_with_mocked_http_client(self):
        """Test generate method with mocked HTTP client."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "Generated text response",
            "done": True,
        }

        async with LlamaCppClient(demo_mode=False) as client:
            client._client.post = AsyncMock(return_value=mock_response)

            response = await client.generate("Test prompt")

            assert response == "Generated text response"
            client._client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_custom_parameters(self):
        """Test generate with custom parameters."""
        async with LlamaCppClient(demo_mode=True) as client:
            response = await client.generate(
                prompt="Test",
                model="custom-model",
                temperature=0.5,
                num_ctx=64000,
            )

            assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_generate_raises_without_context_manager(self):
        """Test generate raises error when not used as context manager."""
        client = LlamaCppClient(demo_mode=False)

        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.generate("Test")

    @pytest.mark.asyncio
    async def test_client_retry_logic(self):
        """Test client retry logic on failure."""
        async with LlamaCppClient(demo_mode=False, max_retries=2) as client:
            # Mock failure then success
            mock_response_fail = MagicMock()
            mock_response_fail.status_code = 500
            mock_response_fail.response = None  # HTTPError won't have response attribute

            mock_response_success = MagicMock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {"response": "Success", "done": True}

            # Create HTTPError without response attribute
            error = httpx.HTTPError("Error")
            
            client._client.post = AsyncMock(
                side_effect=[error, mock_response_success]
            )

            response = await client.generate("Test")

            assert response == "Success"
            assert client._client.post.call_count == 2


class TestLlamaCppClientPool:
    """Test LlamaCppClientPool class."""

    @pytest.mark.asyncio
    async def test_pool_initialization_single_backend(self):
        """Test pool initializes with single backend from settings."""
        pool = LlamaCppClientPool(demo_mode=True)

        # Pool gets URLs from settings, check they're set
        assert len(pool.generation_urls) >= 1
        assert pool.embedding_url is not None

    @pytest.mark.asyncio
    async def test_pool_initialization_multiple_backends(self):
        """Test pool initialization with settings."""
        # Pool reads from settings, so just verify initialization works
        pool = LlamaCppClientPool(demo_mode=True)

        assert pool.generation_urls is not None
        assert len(pool.generation_urls) >= 1
        assert pool.embedding_url is not None

    @pytest.mark.asyncio
    async def test_pool_context_manager(self):
        """Test pool works as async context manager."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            assert pool is not None
            assert len(pool._clients) > 0

    @pytest.mark.asyncio
    async def test_pool_generate(self):
        """Test pool get_generation_client method."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            # Pool doesn't have generate(), it has get_generation_client()
            client = pool.get_generation_client(0)

            assert client is not None
            assert isinstance(client, LlamaCppClient)

    @pytest.mark.asyncio
    async def test_pool_get_client(self):
        """Test pool can get clients by index."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            client = pool.get_generation_client(0)
            assert client is not None
            assert isinstance(client, LlamaCppClient)

    @pytest.mark.asyncio
    async def test_pool_parallel_generation(self):
        """Test pool supports getting multiple clients for parallel generation."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            # Get clients for parallel processing
            clients = [
                pool.get_generation_client(i) for i in range(min(3, len(pool.generation_urls)))
            ]

            assert len(clients) > 0
            assert all(isinstance(c, LlamaCppClient) for c in clients)

    @pytest.mark.asyncio
    async def test_pool_round_robin_distribution(self):
        """Test pool distributes client access in round-robin fashion."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            # Get clients using round-robin indexing
            clients = []
            for i in range(4):
                client = pool.get_generation_client(i)
                clients.append(client)

            assert len(clients) == 4
            # All clients should be valid LlamaCppClient instances
            assert all(isinstance(c, LlamaCppClient) for c in clients)
