# Parallel Processing Configuration

## Overview

The Decision Analyzer supports parallel processing to significantly improve ADR generation performance. This can be achieved in two ways:

1. **Provider-Based Parallelism**: Enabling parallel requests for a single provider (e.g., sending multiple requests to OpenAI or a robust local server concurrently).
2. **Multi-Backend Parallelism**: Using multiple distinct backend URLs (legacy method for local llama.cpp instances).

## 1. Provider-Based Parallelism (Recommended)

This method allows you to send multiple requests in parallel to a single provider. This is ideal for cloud providers (OpenAI, OpenRouter) or high-performance local servers (vLLM, Ollama with concurrency enabled).

### Configuration

You can configure parallel processing settings per provider.

#### Environment Variables (Default Provider)

For the default provider configured via environment variables, use:

- **`LLM_PARALLEL_REQUESTS_ENABLED`** (Default: `false`)
  - Set to `true` to enable parallel execution.
- **`LLM_MAX_PARALLEL_REQUESTS`** (Default: `2`)
  - Maximum number of concurrent requests to send to the provider.

**Example `.env`:**
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
LLM_PARALLEL_REQUESTS_ENABLED=true
LLM_MAX_PARALLEL_REQUESTS=5
```

#### Custom Providers

When adding or editing providers via the UI/API, you can toggle "Enable Parallel Requests" and set the "Max Parallel Requests" value for each provider independently.

### How It Works

When generating an ADR with multiple personas (e.g., Technical Lead, Architect, Business Analyst):
1. The system checks if the active provider has parallel requests enabled.
2. If enabled, it launches generation tasks for all personas simultaneously.
3. A semaphore limits the number of concurrent requests to `LLM_MAX_PARALLEL_REQUESTS`.
4. As tasks complete, new ones are started until all personas are generated.

## 2. Multi-Backend Parallelism (Legacy)

This method is designed for local setups where a single GPU/server cannot handle concurrent requests efficiently, so you run multiple instances of llama.cpp on different ports/machines.

### Configuration

- **`LLAMA_CPP_URL`** (Required): Primary backend.
- **`LLAMA_CPP_URL_1`** (Optional): Secondary backend.
- **`LLAMA_CPP_URL_EMBEDDING`** (Optional): Dedicated embedding backend.

### How It Works

The system uses a `LlamaCppClientPool` to distribute requests round-robin across the configured backends.

## Performance Benefits

With **N personas** and parallel processing enabled:

- **Sequential**: N × ~10s = ~30-40s for 3 personas
- **Parallel (2 concurrent)**: max(N/2) × ~10s = ~15-20s for 3 personas
- **Parallel (N concurrent)**: ~10s (all in parallel)

**Total improvement**: 50-70% faster ADR generation depending on concurrency limits.

## Implementation Details

- **Client Pool**: `src/llama_client.py` - `LlamaCppClientPool` class
- **Service Integration**: `src/adr_generation.py` - `ADRGenerationService` class
- **Task Runner**: `src/celery_app.py` - `generate_adr_task` function
- **Configuration**: `src/config.py` - `Settings` class
