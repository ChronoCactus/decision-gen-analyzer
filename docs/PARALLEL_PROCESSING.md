# Parallel Processing with Multiple Llama.cpp Backends

## Overview

The Decision Analyzer now supports using multiple llama.cpp backends for parallel processing, significantly improving ADR generation performance.

## Configuration

### Environment Variables

Three environment variables control the backend configuration:

1. **`LLAMA_CPP_URL`** (Required)
   - Primary llama.cpp server URL
   - Default: `http://localhost:11434`
   - Used for: Primary generation requests, synthesis, and polishing

2. **`LLAMA_CPP_URL_1`** (Optional)
   - Secondary llama.cpp server URL for parallel processing
   - Default: Not set (single backend mode)
   - Used for: Parallel persona perspective generation

3. **`LLAMA_CPP_URL_EMBEDDING`** (Optional)
   - Dedicated server for embedding requests
   - Default: Uses `LLAMA_CPP_URL` if not set
   - Used for: All embedding operations (future feature)

### Example Configuration

#### Single Backend (Default)
```bash
LLAMA_CPP_URL=http://192.168.0.118:11434
```

#### Dual Backend (Parallel Generation)
```bash
LLAMA_CPP_URL=http://192.168.0.118:11434
LLAMA_CPP_URL_1=http://192.168.0.119:11434
```

#### Triple Backend (Parallel + Dedicated Embeddings)
```bash
LLAMA_CPP_URL=http://192.168.0.118:11434
LLAMA_CPP_URL_1=http://192.168.0.119:11434
LLAMA_CPP_URL_EMBEDDING=http://192.168.0.120:11434
```

## How It Works

### Architecture

- **Single Client Mode**: When only `LLAMA_CPP_URL` is set, the system uses a single `LlamaCppClient` and processes requests sequentially.

- **Client Pool Mode**: When `LLAMA_CPP_URL_1` or `LLAMA_CPP_URL_EMBEDDING` is set, the system uses `LlamaCppClientPool` which:
  - Initializes multiple client connections
  - Distributes requests across backends in round-robin fashion
  - Executes parallel requests using `asyncio.gather()`

### Performance Benefits

With **N personas** and **2 backends**:

- **Sequential**: N × ~10s = ~30-40s for 3 personas
- **Parallel**: max(N/2) × ~10s = ~15-20s for 3 personas

With **3 polishing steps** and **2 backends**:

- **Sequential**: 3 × ~5s = ~15s
- **Parallel**: ~5s (all three in parallel)

**Total improvement**: ~50% faster ADR generation with dual backends

### Request Distribution

1. **Persona Perspective Generation** (Parallel)
   - Persona 1 → Backend 0 (LLAMA_CPP_URL)
   - Persona 2 → Backend 1 (LLAMA_CPP_URL_1)
   - Persona 3 → Backend 0 (LLAMA_CPP_URL)
   - And so on...

2. **Synthesis** (Single)
   - Always uses primary backend (LLAMA_CPP_URL)
   - Requires all persona perspectives to be complete

3. **Polishing** (Parallel)
   - Section 1 → Backend 0
   - Section 2 → Backend 1
   - Section 3 → Backend 0

4. **Embeddings** (Future)
   - Will use `LLAMA_CPP_URL_EMBEDDING` if set
   - Otherwise uses `LLAMA_CPP_URL`

## Docker Compose Configuration

The environment variables are automatically passed through in `docker-compose.yml`:

```yaml
environment:
  - LLAMA_CPP_URL=${LLAMA_CPP_URL:-http://192.168.0.118:11434}
  - LLAMA_CPP_URL_1=${LLAMA_CPP_URL_1:-}
  - LLAMA_CPP_URL_EMBEDDING=${LLAMA_CPP_URL_EMBEDDING:-}
```

Set them in your `.env` file or export them before running:

```bash
export LLAMA_CPP_URL=http://192.168.0.118:11434
export LLAMA_CPP_URL_1=http://192.168.0.119:11434
docker compose up
```

## Future Enhancements

### Authentication Support

When authentication is needed, the pattern will extend to:

```bash
LLAMA_CPP_URL=http://server1:11434
LLAMA_CPP_URL_AUTH=Bearer token1

LLAMA_CPP_URL_1=http://server2:11434
LLAMA_CPP_URL_1_AUTH=Bearer token2

LLAMA_CPP_URL_EMBEDDING=http://server3:11434
LLAMA_CPP_URL_EMBEDDING_AUTH=Bearer token3
```

This naming convention keeps credentials paired with their corresponding URLs.

### Dynamic Scaling

For more than 2 backends, you could extend the pattern:

```bash
LLAMA_CPP_URL=http://server1:11434
LLAMA_CPP_URL_1=http://server2:11434
LLAMA_CPP_URL_2=http://server3:11434
LLAMA_CPP_URL_3=http://server4:11434
```

However, the current implementation is optimized for 2 generation backends, as most ADR generations use 2-3 personas.

## Monitoring

The system logs which mode is being used:

```
INFO: Using LlamaCppClientPool for parallel generation
INFO: Initialized LlamaCppClientPool generation_backends=2 generation_urls=['http://192.168.0.118:11434', 'http://192.168.0.119:11434']
INFO: Using parallel generation for persona perspectives persona_count=3
```

Or in single client mode:

```
INFO: Using single LlamaCppClient
INFO: Using sequential generation for persona perspectives persona_count=3
```

## Troubleshooting

### Problem: Requests failing intermittently

**Solution**: Check that all backend URLs are accessible and have sufficient resources. Each backend needs to handle full-size model inference.

### Problem: No performance improvement

**Solution**: Verify that `LLAMA_CPP_URL_1` is set and pointing to a different server. Check logs to confirm pool mode is active.

### Problem: Embeddings are slow

**Solution**: Set `LLAMA_CPP_URL_EMBEDDING` to a dedicated backend, potentially running a smaller model optimized for embeddings.

## Implementation Details

- **Client Pool**: `src/llama_client.py` - `LlamaCppClientPool` class
- **Service Integration**: `src/adr_generation.py` - `ADRGenerationService` class
- **Task Runner**: `src/celery_app.py` - `generate_adr_task` function
- **Configuration**: `src/config.py` - `Settings` class
