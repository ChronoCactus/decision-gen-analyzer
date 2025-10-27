# Quick Reference: Multi-Backend Configuration

## TL;DR

Set `LLAMA_CPP_URL_1` to enable parallel processing → ~50% faster ADR generation.

## Environment Variables

```bash
# Required - Primary backend
LLAMA_CPP_URL=http://192.168.0.118:11434

# Optional - Secondary backend for parallel processing
LLAMA_CPP_URL_1=http://192.168.0.119:11434

# Optional - Dedicated embedding server (future use)
LLAMA_CPP_URL_EMBEDDING=http://192.168.0.120:11434
```

## How It Works

```
Single Backend:
Persona 1 → Backend → 10s
Persona 2 → Backend → 10s  } Sequential
Persona 3 → Backend → 10s
Total: 30s

Dual Backend:
Persona 1 → Backend 0 ┐
Persona 2 → Backend 1 ├─ Parallel (10s)
Persona 3 → Backend 0 ┘
Total: ~15s
```

## Code Usage

### Service Initialization
```python
from src.llama_client import LlamaCppClient, LlamaCppClientPool
from src.config import get_settings

settings = get_settings()

# Automatic selection based on config
if settings.llama_cpp_url_1 or settings.llama_cpp_url_embedding:
    client = LlamaCppClientPool(demo_mode=False)
else:
    client = LlamaCppClient(demo_mode=False)

# Use with context manager
async with client:
    service = ADRGenerationService(client, lightrag, personas)
    result = await service.generate_adr(prompt)
```

### Direct Parallel Generation
```python
async with LlamaCppClientPool(demo_mode=False) as pool:
    prompts = ["prompt1", "prompt2", "prompt3"]
    responses = await pool.generate_parallel(
        prompts=prompts,
        temperature=0.7,
        num_predict=2000
    )
```

### Client Selection
```python
# When using pool directly
client_0 = pool.get_generation_client(0)  # Primary
client_1 = pool.get_generation_client(1)  # Secondary
embedding = pool.get_embedding_client()    # Dedicated or fallback to primary

# Service handles this automatically
service = ADRGenerationService(pool, lightrag, personas)
```

## Check Logs

```bash
# Look for this line to confirm pool mode
INFO: Using LlamaCppClientPool for parallel generation
INFO: Initialized LlamaCppClientPool generation_backends=2
```

## Docker Setup

```bash
# Add to .env file
LLAMA_CPP_URL=http://192.168.0.118:11434
LLAMA_CPP_URL_1=http://192.168.0.119:11434

# Start services
docker compose up --build
```

## Troubleshooting

**Problem**: No performance improvement
```bash
# Check if variable is set
docker compose exec backend env | grep LLAMA_CPP_URL

# Check logs for pool initialization
docker compose logs backend | grep -i pool
```

**Problem**: Connection errors
```bash
# Test each backend
curl http://192.168.0.118:11434/v1/models
curl http://192.168.0.119:11434/v1/models
```

## Key Files

- `src/llama_client.py` - Client pool implementation
- `src/adr_generation.py` - Parallel generation logic
- `src/config.py` - Environment variable definitions
- `docs/PARALLEL_PROCESSING.md` - Full documentation
