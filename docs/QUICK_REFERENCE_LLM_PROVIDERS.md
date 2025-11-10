# Quick Reference: LLM Provider Setup

## Installation

```bash
pip install -e .
```

## Provider Quick Setup

### 🏠 Ollama (Local - Default)

```bash
# Start Ollama
ollama serve

# Pull model
ollama pull gpt-oss:20b

# Configure (or use defaults)
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=gpt-oss:20b
```

### ☁️ OpenRouter (Cloud - 200+ Models)

```bash
# Get API key from https://openrouter.ai/
export OPENROUTER_API_KEY=sk-or-v1-...
export LLM_PROVIDER=openrouter
export LLM_BASE_URL=https://openrouter.ai/api/v1
export LLM_MODEL=anthropic/claude-3-5-sonnet
```

### 🤖 OpenAI (Cloud)

```bash
export OPENAI_API_KEY=sk-...
export LLM_PROVIDER=openai
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4
```

### ⚡ vLLM (Local - High Performance)

```bash
# Start vLLM server
vllm serve meta-llama/Llama-2-70b-hf --port 8000

# Configure
export LLM_PROVIDER=vllm
export LLM_BASE_URL=http://localhost:8000/v1
export LLM_MODEL=meta-llama/Llama-2-70b-hf
```

### 🦙 llama.cpp Server (Local)

```bash
# Start llama.cpp with OpenAI compatibility
./server --port 8080 --api

# Configure
export LLM_PROVIDER=llama_cpp
export LLM_BASE_URL=http://localhost:8080/v1
export LLM_MODEL=llama-2-70b
```

## Advanced Setup

### 🔀 Parallel Processing (2x Speed)

```bash
# Two local Ollama instances
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_BASE_URL_1=http://localhost:11435/v1
export LLM_MODEL=gpt-oss:20b
```

### 🎯 Dedicated Embedding Server

```bash
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=gpt-oss:20b
export LLM_EMBEDDING_BASE_URL=http://localhost:11434/v1
export LLM_EMBEDDING_MODEL=nomic-embed-text
```

### 🔄 Hybrid (Local + Cloud)

```bash
# Primary: Fast local
export LLM_BASE_URL=http://localhost:11434/v1
export LLM_MODEL=gpt-oss:20b

# Secondary: High-quality cloud
export LLM_BASE_URL_1=https://openrouter.ai/api/v1
export OPENROUTER_API_KEY=sk-or-...
```

## Docker Configuration

Add to `docker-compose.yml`:

```yaml
services:
  backend:
    environment:
      # For Ollama
      - LLM_BASE_URL=http://host.docker.internal:11434/v1
      - LLM_MODEL=gpt-oss:20b
      
      # For OpenRouter
      - LLM_PROVIDER=openrouter
      - LLM_BASE_URL=https://openrouter.ai/api/v1
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - LLM_MODEL=anthropic/claude-3-5-sonnet
```

## Troubleshooting

### Connection Failed

```bash
# Test endpoint
curl http://localhost:11434/v1/models

# Check Ollama is running
ollama list

# Verify port is correct
netstat -an | grep 11434
```

### Model Not Found

```bash
# Ollama: Pull the model
ollama pull gpt-oss:20b

# Check available models
ollama list
```

### Authentication Error

```bash
# Verify API key
echo $OPENROUTER_API_KEY

# Check key format
# OpenRouter: sk-or-v1-...
# OpenAI: sk-...
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `ollama` | Provider type |
| `LLM_BASE_URL` | Yes | `http://localhost:11434/v1` | API endpoint |
| `LLM_MODEL` | Yes | `gpt-oss:20b` | Model name |
| `LLM_API_KEY` | No* | None | API key (*required for cloud) |
| `LLM_TEMPERATURE` | No | `0.7` | Generation temperature |
| `LLM_TIMEOUT` | No | `300` | Request timeout (seconds) |
| `LLM_BASE_URL_1` | No | None | Secondary endpoint |
| `LLM_EMBEDDING_BASE_URL` | No | None | Embedding endpoint |
| `LLM_EMBEDDING_MODEL` | No | Same as `LLM_MODEL` | Embedding model |

## Common Patterns

### Development (Local)
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=gpt-oss:20b
```

### Production (Cloud)
```bash
LLM_PROVIDER=openrouter
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=anthropic/claude-3-5-sonnet
OPENROUTER_API_KEY=sk-or-v1-...
```

### High Performance (Parallel)
```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_BASE_URL_1=http://localhost:11435/v1
LLM_MODEL=gpt-oss:20b
```

## Cost Comparison

| Provider | Cost | Privacy | Speed | Quality |
|----------|------|---------|-------|---------|
| Ollama | Free | ✅ Private | Fast* | Good |
| vLLM | Free | ✅ Private | Very Fast* | Good |
| llama.cpp | Free | ✅ Private | Fast* | Good |
| OpenRouter | Pay-per-use | ❌ Cloud | Fast | Excellent |
| OpenAI | Pay-per-use | ❌ Cloud | Fast | Excellent |

*Speed depends on hardware

## Next Steps

1. Choose a provider from the list above
2. Set the required environment variables
3. Run `pip install -e .` to install dependencies
4. Test connection: `make test-backend`
5. Start the application: `docker compose up` or `./scripts/run_backend.sh`

## More Information

- Full migration guide: `docs/LLM_PROVIDER_MIGRATION.md`
- Migration summary: `docs/LANGCHAIN_MIGRATION_SUMMARY.md`
- OpenRouter models: https://openrouter.ai/models
- LangChain docs: https://python.langchain.com/docs/integrations/chat/openai
