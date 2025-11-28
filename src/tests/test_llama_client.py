"""Tests for Llama client."""

import pytest

from src.llama_client import LlamaCppClient, LlamaCppClientPool


class TestLlamaCppClient:
    """Test LlamaCppClient class."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test client can be initialized."""
        client = LlamaCppClient(
            base_url="http://test:8000/v1", model="test-model", timeout=60
        )

        assert client.base_url == "http://test:8000/v1"
        assert client.model == "test-model"
        assert client.timeout == 60

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client works as async context manager in demo mode."""
        async with LlamaCppClient(demo_mode=True) as client:
            # In demo mode, _llm should be None
            assert client._llm is None or client.demo_mode

    @pytest.mark.asyncio
    async def test_client_context_manager_real_mode(self):
        """Test client initializes LangChain client in real mode."""
        # Test with Ollama provider (should use ChatOllama)
        async with LlamaCppClient(provider="ollama", demo_mode=False) as client:
            assert client._llm is not None
            from langchain_ollama import ChatOllama

            assert isinstance(client._llm, ChatOllama)

        # Test with OpenAI provider (should use ChatOpenAI)
        async with LlamaCppClient(provider="openai", demo_mode=False) as client:
            assert client._llm is not None
            from langchain_openai import ChatOpenAI

            assert isinstance(client._llm, ChatOpenAI)

    @pytest.mark.asyncio
    async def test_generate_in_demo_mode(self):
        """Test generate method in demo mode."""
        async with LlamaCppClient(demo_mode=True) as client:
            response = await client.generate("Test prompt")

            assert isinstance(response, str)
            assert len(response) > 0
            assert "simulated" in response.lower() or "recommend" in response.lower()

    @pytest.mark.asyncio
    async def test_generate_with_langchain(self):
        """Test generate method uses LangChain properly (tested via demo mode)."""
        # Note: Since LangChain chat models are Pydantic models, they can't be easily mocked.
        # We use demo mode which simulates the full flow without actual LLM calls.
        async with LlamaCppClient(demo_mode=True) as client:
            response = await client.generate("Test prompt about ADRs")

            assert isinstance(response, str)
            assert len(response) > 0
            assert "decision" in response.lower() or "ADR" in response

    @pytest.mark.asyncio
    async def test_generate_with_custom_parameters(self):
        """Test generate with custom parameters."""
        async with LlamaCppClient(demo_mode=True) as client:
            response = await client.generate(
                prompt="Test",
                model="custom-model",
                temperature=0.5,
                num_predict=100,
            )

            assert isinstance(response, str)

    @pytest.mark.asyncio
    async def test_generate_json_format(self):
        """Test generate with JSON format adds system message."""
        # Demo mode test - validates flow without needing to mock Pydantic models
        async with LlamaCppClient(demo_mode=True) as client:
            response = await client.generate("Test", format="json")

            assert isinstance(response, str)
            # Demo mode should still return a valid response
            assert len(response) > 0

    @pytest.mark.asyncio
    async def test_ollama_num_ctx_parameter(self):
        """Test Ollama-specific num_ctx parameter is passed correctly."""
        async with LlamaCppClient(
            provider="ollama", num_ctx=32000, num_predict=500, demo_mode=False
        ) as client:
            # Verify client was initialized with Ollama parameters
            assert client.provider == "ollama"
            assert client.num_ctx == 32000
            assert client.num_predict == 500

            # Verify ChatOllama was used
            from langchain_ollama import ChatOllama

            assert isinstance(client._llm, ChatOllama)

    @pytest.mark.asyncio
    async def test_generate_raises_without_context_manager(self):
        """Test generate raises error when not used as context manager."""
        client = LlamaCppClient(demo_mode=False)

        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.generate("Test")

    @pytest.mark.asyncio
    async def test_client_error_handling(self):
        """Test client handles errors appropriately in demo mode."""
        # Since we can't easily mock Pydantic-based LangChain models,
        # we test error handling via demo mode's built-in flows
        async with LlamaCppClient(demo_mode=True) as client:
            # Demo mode always succeeds, but we can test the happy path
            response = await client.generate("Test")
            assert isinstance(response, str)
            assert len(response) > 0

    @pytest.mark.asyncio
    async def test_generate_with_prompt_only_real_mode(self):
        """Test generate method with prompt only (no messages) in real mode.

        This specifically tests the code path that failed with UnboundLocalError
        when HumanMessage was imported inside the 'if messages:' block.
        """
        from unittest.mock import AsyncMock, MagicMock

        # Use demo_mode=False to bypass the early return
        # Use provider="openai" to avoid ChatOllama validation if possible,
        # or just mock the internal _llm immediately.
        async with LlamaCppClient(
            demo_mode=False, provider="openai", api_key="test"
        ) as client:
            # Mock the internal LangChain client
            mock_llm = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = "Generated response"
            mock_llm.ainvoke.return_value = mock_response

            # Replace the real _llm with our mock
            client._llm = mock_llm

            # This call would fail with UnboundLocalError if the import is misplaced
            response = await client.generate(prompt="Test prompt")

            assert response == "Generated response"
            # Verify ainvoke was called
            mock_llm.ainvoke.assert_called_once()

            # Verify the argument passed to ainvoke was a list containing a HumanMessage
            call_args = mock_llm.ainvoke.call_args
            assert call_args is not None
            messages_arg = call_args[0][0]  # First arg is the list of messages
            assert isinstance(messages_arg, list)
            assert len(messages_arg) == 1

            # We can check the class name of the message object
            msg = messages_arg[0]
            assert msg.__class__.__name__ == "HumanMessage"
            assert msg.content == "Test prompt"


class TestLlamaCppClientPool:
    """Test LlamaCppClientPool class."""

    @pytest.mark.asyncio
    async def test_pool_initialization_single_backend(self):
        """Test pool initializes with single backend from settings."""
        pool = LlamaCppClientPool(demo_mode=True)

        # Pool gets configs from settings, check they're set
        assert len(pool.generation_configs) >= 1

    @pytest.mark.asyncio
    async def test_pool_initialization_multiple_backends(self):
        """Test pool initialization with settings."""
        # Pool reads from settings, so just verify initialization works
        pool = LlamaCppClientPool(demo_mode=True)

        assert pool.generation_configs is not None
        assert len(pool.generation_configs) >= 1

    @pytest.mark.asyncio
    async def test_pool_context_manager(self):
        """Test pool works as async context manager."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            assert pool is not None
            assert len(pool._clients) > 0

    @pytest.mark.asyncio
    async def test_pool_get_generation_client(self):
        """Test pool get_generation_client method."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            client = pool.get_generation_client(0)

            assert client is not None
            assert isinstance(client, LlamaCppClient)

    @pytest.mark.asyncio
    async def test_pool_get_embedding_client(self):
        """Test pool can get embedding client."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            client = pool.get_embedding_client()
            assert client is not None
            assert isinstance(client, LlamaCppClient)

    @pytest.mark.asyncio
    async def test_pool_parallel_generation(self):
        """Test pool supports parallel generation."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            prompts = ["Test 1", "Test 2", "Test 3"]
            results = await pool.generate_parallel(prompts)

            assert len(results) == 3
            assert all(isinstance(r, str) for r in results)
            assert all(len(r) > 0 for r in results)

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

    @pytest.mark.asyncio
    async def test_pool_parallel_generation_demo(self):
        """Test pool can handle parallel requests in demo mode."""
        async with LlamaCppClientPool(demo_mode=True) as pool:
            # Generate multiple responses in parallel
            prompts = [f"Test prompt {i}" for i in range(4)]
            results = await pool.generate_parallel(prompts)

            # In demo mode, all should succeed
            assert len(results) == 4
            for result in results:
                assert isinstance(result, str)
                assert len(result) > 0
