"""Client for interacting with LLM servers using LangChain.

This module provides a unified interface for connecting to various LLM providers
through LangChain integrations. Supports:
- Ollama (local) - using ChatOllama for full parameter support (num_ctx, num_predict, etc.)
- OpenRouter - using ChatOpenAI
- OpenAI - using ChatOpenAI
- vLLM - using ChatOpenAI
- llama.cpp server - using ChatOpenAI
- Any other OpenAI-compatible endpoint - using ChatOpenAI

The module maintains backward compatibility with the original LlamaCppClient
and LlamaCppClientPool interfaces while using LangChain under the hood.
"""

import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from src.config import get_settings
from src.logger import get_logger

if TYPE_CHECKING:
    from src.persona_manager import PersonaConfig

logger = get_logger(__name__)

DEFAULT_MODEL = "gpt-oss:20b"


class ClientType(Enum):
    """Type of LLM client for different purposes."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EMBEDDING = "embedding"


class LlamaCppClient:
    """Client for LLM interactions using LangChain's ChatOpenAI.

    This client provides a unified interface for interacting with various LLM providers
    that support OpenAI-compatible APIs. It uses LangChain's ChatOpenAI class internally
    for maximum flexibility and compatibility.

    Features:
    - Automatic retry with exponential backoff
    - Demo mode for testing without actual LLM calls
    - Support for multiple providers (Ollama, OpenRouter, OpenAI, vLLM, etc.)
    - Async context manager for proper resource cleanup
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[int] = None,
        temperature: Optional[float] = None,
        provider: Optional[str] = None,
        num_ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        demo_mode: bool = True,  # Enable demo mode by default
    ):
        """Initialize the LLM client.

        Args:
            base_url: Base URL for the OpenAI-compatible API endpoint
            model: Model name to use for generation
            api_key: API key for authentication (optional for local providers)
            timeout: Timeout for LLM requests in seconds
            temperature: Temperature for generation (0.0 to 1.0)
            provider: LLM provider type (ollama, openai, openrouter, vllm, llama_cpp, custom)
            num_ctx: Context window size (Ollama-specific)
            num_predict: Maximum tokens to generate (Ollama-specific)
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            backoff_factor: Multiplier for exponential backoff
            demo_mode: If True, simulate LLM responses without making actual API calls
        """
        settings = get_settings()

        # Use provided values or fall back to settings
        self.base_url = base_url or settings.llm_base_url
        self.model = model or settings.llm_model
        self.api_key = api_key or settings.llm_api_key
        self.timeout = timeout or settings.llm_timeout
        self.temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )
        self.provider = (provider or settings.llm_provider).lower()

        # Ollama-specific parameters
        self.num_ctx = num_ctx if num_ctx is not None else settings.ollama_num_ctx
        self.num_predict = num_predict or settings.ollama_num_predict

        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.demo_mode = demo_mode

        self._llm: Optional[Union[ChatOpenAI, ChatOllama]] = None

    async def __aenter__(self):
        """Async context manager entry."""
        if not self.demo_mode:
            # Initialize provider-specific LangChain client
            if self.provider == "ollama":
                # Use ChatOllama for Ollama provider to preserve num_ctx and other parameters
                # ChatOllama expects the base Ollama URL without /v1 suffix
                base_url = self.base_url
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]  # Remove /v1 suffix

                kwargs = {
                    "model": self.model,
                    "base_url": base_url,
                    "temperature": self.temperature,
                    "num_ctx": self.num_ctx,
                }

                # Add optional Ollama parameters
                if self.num_predict:
                    kwargs["num_predict"] = self.num_predict

                self._llm = ChatOllama(**kwargs)

                logger.info(
                    "Initialized LangChain ChatOllama client",
                    model=self.model,
                    base_url=base_url,
                    temperature=self.temperature,
                    num_ctx=self.num_ctx,
                    num_predict=self.num_predict,
                )
            else:
                # Use ChatOpenAI for other providers (OpenRouter, OpenAI, vLLM, llama.cpp, etc.)
                kwargs = {
                    "model": self.model,
                    "base_url": self.base_url,
                    "timeout": self.timeout,
                    "temperature": self.temperature,
                    "max_retries": self.max_retries,
                }

                # Only include api_key if it's provided
                if self.api_key:
                    kwargs["api_key"] = self.api_key
                else:
                    # Use a dummy key for local providers that don't need auth
                    kwargs["api_key"] = "sk-dummy-key"

                self._llm = ChatOpenAI(**kwargs)

                logger.info(
                    "Initialized LangChain ChatOpenAI client",
                    provider=self.provider,
                    model=self.model,
                    base_url=self.base_url,
                    timeout=self.timeout,
                    temperature=self.temperature,
                )
        else:
            logger.info("LlamaCppClient initialized in demo mode")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # LangChain ChatOpenAI doesn't require explicit cleanup
        self._llm = None

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        num_ctx: Optional[int] = None,
        num_predict: Optional[int] = None,
        stop: Optional[List[str]] = None,
        format: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Generate text using the LLM or demo mode.

        Note: In LangChain, parameters like temperature are set during instantiation.
        If temperature differs from the client's configured value, a temporary client
        will be created for this request.

        Args:
            prompt: The input prompt for generation
            model: Model name (NOTE: not supported for per-request override)
            temperature: Temperature (creates temporary client if different from default)
            num_ctx: Context window size (NOTE: not supported for per-request override)
            num_predict: Maximum tokens to generate (NOTE: not supported for per-request override)
            stop: Stop sequences (passed to invoke)
            format: Response format (e.g., "json")
            **kwargs: Additional provider-specific parameters

        Returns:
            Generated text response
        """
        # Demo mode: simulate LLM response
        if self.demo_mode:
            logger.info("Using demo mode for LLM generation")
            await asyncio.sleep(1.5)  # Simulate processing time

            # Generate a realistic mock response based on the prompt
            if "ADR" in prompt or "decision" in prompt.lower():
                return f"""Based on the prompt "{prompt[:50]}...", I recommend the following architectural decision:

**Decision:** Adopt a microservices architecture with API Gateway pattern.

**Rationale:** This approach provides better scalability, maintainability, and allows independent deployment of services.

**Alternatives Considered:**
- Monolithic architecture (simpler but less scalable)
- Serverless functions (good for event-driven workloads)

**Trade-offs:** Increased complexity vs. better scalability and maintainability."""
            else:
                return f"""This is a simulated LLM response to: "{prompt[:100]}..."

In a real implementation, this would be generated by a large language model like Llama or GPT. The response would be contextually appropriate and based on the actual prompt provided."""

        if not self._llm:
            raise RuntimeError("Client not initialized. Use as async context manager.")

        # Check if we need a different temperature than configured
        needs_temp_client = (
            temperature is not None
            and abs(temperature - self.temperature)
            > 0.001  # Float comparison tolerance
        )

        # Use the existing client or create a temporary one
        llm_to_use = self._llm
        temp_client = None

        if needs_temp_client:
            logger.info(
                "Creating temporary client with different temperature",
                configured_temp=self.temperature,
                requested_temp=temperature,
            )
            # Create a temporary client instance with the requested temperature
            if self.provider == "ollama":
                # ChatOllama expects base URL without /v1 suffix
                base_url = self.base_url
                if base_url.endswith("/v1"):
                    base_url = base_url[:-3]

                temp_client = ChatOllama(
                    model=self.model,
                    base_url=base_url,
                    temperature=temperature,
                    num_ctx=self.num_ctx,
                    num_predict=self.num_predict,
                )
            else:
                kwargs_temp = {
                    "model": self.model,
                    "base_url": self.base_url,
                    "timeout": self.timeout,
                    "temperature": temperature,
                    "max_retries": self.max_retries,
                }
                if self.api_key:
                    kwargs_temp["api_key"] = self.api_key
                else:
                    kwargs_temp["api_key"] = "sk-dummy-key"

                temp_client = ChatOpenAI(**kwargs_temp)

            llm_to_use = temp_client

        # Build kwargs for LangChain invoke
        # Note: Only pass parameters that are valid for invoke(), not instantiation parameters
        invoke_kwargs = {}

        # Stop sequences can be passed to invoke
        if stop:
            invoke_kwargs["stop"] = stop

        # Add any additional kwargs (be careful - most params are instantiation-only)
        # Filter out known instantiation-only parameters
        filtered_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            not in [
                "temperature",
                "model",
                "base_url",
                "api_key",
                "timeout",
                "num_ctx",
                "num_predict",
            ]
        }
        invoke_kwargs.update(filtered_kwargs)

        # Prepare the message
        messages = [HumanMessage(content=prompt)]

        # If format is json, add system message requesting JSON
        if format == "json":
            messages.insert(
                0,
                SystemMessage(
                    content="You are a helpful assistant that responds in valid JSON format."
                ),
            )

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                actual_temp = temperature if needs_temp_client else self.temperature
                logger.info(
                    "Sending generation request",
                    model=self.model,
                    temperature=actual_temp,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1,
                )

                # Use ainvoke for async calls
                response = await llm_to_use.ainvoke(messages, **invoke_kwargs)
                generated_text = response.content

                # Validate response
                if not generated_text.strip():
                    raise ValueError("Empty response from LLM")

                logger.info(
                    "Generation completed successfully",
                    response_length=len(generated_text),
                    attempt=attempt + 1,
                )
                return generated_text

            except Exception as e:
                last_exception = e
                error_type = type(e).__name__

                logger.warning(
                    "Error during generation attempt",
                    attempt=attempt + 1,
                    error_type=error_type,
                    error=str(e),
                )

                # Don't retry on certain errors (e.g., authentication, validation)
                if "authentication" in str(e).lower() or "api key" in str(e).lower():
                    logger.error("Authentication error, not retrying")
                    break

                if attempt < self.max_retries:
                    delay = self.retry_delay * (self.backoff_factor**attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "All generation attempts failed",
            total_attempts=self.max_retries + 1,
            final_error=str(last_exception),
        )
        raise last_exception or RuntimeError("Generation failed after all retries")

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models on the server.

        Note: This makes a direct HTTP call to /v1/models endpoint as LangChain
        doesn't provide a models listing method.
        """
        import httpx

        try:
            # Remove /v1 suffix if present to construct base URL
            base = self.base_url.rstrip("/v1").rstrip("/")
            models_url = f"{base}/v1/models"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(models_url)
                response.raise_for_status()
                return response.json().get("data", [])
        except Exception as e:
            logger.error(
                "Failed to list models", error_type=type(e).__name__, error=str(e)
            )
            raise

    async def health_check(self) -> bool:
        """Check if the LLM server is healthy.

        Returns:
            True if server is accessible, False otherwise
        """
        import httpx

        try:
            # Try to access the models endpoint as a health check
            base = self.base_url.rstrip("/v1").rstrip("/")
            health_url = f"{base}/v1/models"

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(health_url)
                return response.status_code == 200
        except Exception:
            return False


class LlamaCppClientPool:
    """Pool of LLM clients for parallel request processing.

    This pool manages multiple LangChain ChatOpenAI clients for parallel generation
    requests. It supports:
    - Multiple generation backends for load balancing
    - Dedicated embedding backend (optional)
    - Round-robin distribution of requests
    """

    def __init__(
        self,
        timeout: Optional[int] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        backoff_factor: float = 2.0,
        demo_mode: bool = True,
    ):
        """Initialize the client pool with URLs from settings.

        Args:
            timeout: Timeout for LLM requests in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries in seconds
            backoff_factor: Multiplier for exponential backoff
            demo_mode: If True, simulate LLM responses without making actual API calls
        """
        settings = get_settings()
        self.timeout = timeout or settings.llm_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.backoff_factor = backoff_factor
        self.demo_mode = demo_mode

        # Build list of available backend configs
        self.generation_configs = [settings.get_llm_config()]

        secondary_config = settings.get_secondary_llm_config()
        if secondary_config:
            self.generation_configs.append(secondary_config)

        self.embedding_config = settings.get_embedding_llm_config()

        logger.info(
            "Initialized LlamaCppClientPool",
            generation_backends=len(self.generation_configs),
            has_dedicated_embedding=self.embedding_config is not None,
        )

        self._clients: Dict[str, LlamaCppClient] = {}

    async def __aenter__(self):
        """Async context manager entry - initialize all clients."""
        # Create clients for each generation config
        for idx, config in enumerate(self.generation_configs):
            client = LlamaCppClient(
                base_url=config["base_url"],
                model=config["model"],
                api_key=config.get("api_key"),
                timeout=self.timeout,
                temperature=config.get("temperature"),
                provider=config.get("provider"),
                num_ctx=config.get("num_ctx"),
                num_predict=config.get("num_predict"),
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                backoff_factor=self.backoff_factor,
                demo_mode=self.demo_mode,
            )
            await client.__aenter__()
            self._clients[f"gen_{idx}"] = client

        # Create dedicated embedding client if configured
        if self.embedding_config:
            embedding_client = LlamaCppClient(
                base_url=self.embedding_config["base_url"],
                model=self.embedding_config["model"],
                api_key=self.embedding_config.get("api_key"),
                timeout=self.timeout,
                provider=self.embedding_config.get("provider"),
                num_ctx=self.embedding_config.get("num_ctx"),
                num_predict=self.embedding_config.get("num_predict"),
                max_retries=self.max_retries,
                retry_delay=self.retry_delay,
                backoff_factor=self.backoff_factor,
                demo_mode=self.demo_mode,
            )
            await embedding_client.__aenter__()
            self._clients["embedding"] = embedding_client

        logger.info("All clients initialized in pool", client_count=len(self._clients))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close all clients."""
        for client in self._clients.values():
            await client.__aexit__(exc_type, exc_val, exc_tb)
        self._clients.clear()

    def get_generation_client(self, index: int = 0) -> LlamaCppClient:
        """Get a generation client by index (round-robin for parallel requests).

        Args:
            index: Index to select which generation backend to use

        Returns:
            LlamaCppClient for generation requests
        """
        client_idx = index % len(self.generation_configs)
        client_key = f"gen_{client_idx}"
        if client_key not in self._clients:
            raise RuntimeError(
                "Client pool not initialized. Use as async context manager."
            )
        return self._clients[client_key]

    def get_embedding_client(self) -> LlamaCppClient:
        """Get the dedicated embedding client, or fallback to primary.

        Returns:
            LlamaCppClient for embedding requests
        """
        if "embedding" in self._clients:
            return self._clients["embedding"]
        # Fallback to primary generation client
        return self.get_generation_client(0)

    async def generate_parallel(
        self,
        prompts: List[str],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> List[str]:
        """Generate responses for multiple prompts in parallel.

        Args:
            prompts: List of prompts to process
            model: Model name to use
            temperature: Temperature for generation
            **kwargs: Additional generation parameters

        Returns:
            List of generated responses in same order as prompts
        """
        if not prompts:
            return []

        logger.info(
            "Starting parallel generation",
            prompt_count=len(prompts),
            backend_count=len(self.generation_configs),
        )

        # Create tasks for each prompt, distributing across available clients
        tasks = []
        for idx, prompt in enumerate(prompts):
            client = self.get_generation_client(idx)
            task = client.generate(
                prompt=prompt, model=model, temperature=temperature, **kwargs
            )
            tasks.append(task)

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for exceptions and log them
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "Parallel generation task failed", task_index=idx, error=str(result)
                )

        # Return results, converting exceptions to empty strings
        return [r if isinstance(r, str) else "" for r in results]


def create_client_from_persona_config(
    persona_config: "PersonaConfig", demo_mode: bool = False
) -> LlamaCppClient:
    """Create a LlamaCppClient instance from a PersonaConfig's model_config.

    Args:
        persona_config: PersonaConfig with optional model_config
        demo_mode: Whether to run in demo mode without actual LLM calls

    Returns:
        LlamaCppClient configured for the persona, or using defaults if no model_config specified
    """

    settings = get_settings()

    # If persona has model_config, use it; otherwise use defaults from settings
    if persona_config.model_config:
        mc = persona_config.model_config
        return LlamaCppClient(
            base_url=mc.base_url if mc.base_url else settings.llm_base_url,
            model=mc.name,
            provider=mc.provider if mc.provider else settings.llm_provider,
            temperature=(
                mc.temperature
                if mc.temperature is not None
                else settings.llm_temperature
            ),
            num_ctx=mc.num_ctx if mc.num_ctx is not None else settings.ollama_num_ctx,
            demo_mode=demo_mode,
        )
    else:
        # Use default settings
        return LlamaCppClient(demo_mode=demo_mode)


async def create_client_from_provider_id(
    provider_id: Optional[str] = None, demo_mode: bool = False
) -> LlamaCppClient:
    """Create a LlamaCppClient instance from a stored provider configuration.

    Args:
        provider_id: ID of the provider to use. If None, uses the default provider.
        demo_mode: Whether to run in demo mode without actual LLM calls

    Returns:
        LlamaCppClient configured for the provider, or using env defaults if provider not found
    """
    from src.llm_provider_storage import get_provider_storage

    storage = get_provider_storage()

    # Ensure env provider exists
    await storage.ensure_env_provider()

    # Get the provider config
    if provider_id:
        provider_config = await storage.get(provider_id)
    else:
        # Get default provider
        default_response = await storage.get_default()
        if default_response:
            provider_config = await storage.get(default_response.id)
        else:
            provider_config = None

    # If no provider found, fall back to env defaults
    if not provider_config:
        logger.warning(f"Provider {provider_id} not found, using environment defaults")
        return LlamaCppClient(demo_mode=demo_mode)

    # Get decrypted API key if present
    api_key = None
    if provider_config.api_key_encrypted:
        api_key = await storage.get_decrypted_api_key(provider_config.id)

    # Create client with provider config
    return LlamaCppClient(
        base_url=provider_config.base_url,
        model=provider_config.model_name,
        provider=provider_config.provider_type,
        api_key=api_key,
        temperature=provider_config.temperature,
        num_ctx=provider_config.num_ctx,
        num_predict=provider_config.num_predict,
        demo_mode=demo_mode,
    )
