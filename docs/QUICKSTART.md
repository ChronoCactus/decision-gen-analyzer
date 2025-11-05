# Quick Start Guide: Decision Analyzer with Bundled LightRAG

This guide will get you up and running with Decision Analyzer in under 5 minutes.

## Prerequisites

1. **Docker and Docker Compose** installed
2. **Ollama server** running with a model (e.g., `granite4:7b-a1b-h`, `llama3.1:8b`, etc.)
3. Either:
   - Use the bundled LightRAG service (recommended for getting started), or
   - Have an external LightRAG instance running

## Installation

1. **Clone and configure**:
```bash
git clone <repository-url>
cd decision-analyzer
cp .env.example .env
```

2. **Edit `.env`** to point to your Ollama server:
```bash
# Minimal configuration - just set your Ollama URL
LLAMA_CPP_URL=http://192.168.0.121:11434

# Optional: Use multiple Ollama servers for better performance
# LLAMA_CPP_URL_1=http://192.168.0.119:11434
# LLAMA_CPP_URL_EMBEDDING=http://192.168.0.120:11434
```

3. **Start everything with bundled LightRAG**:
```bash
docker compose --profile lightrag up --build
```

Or **start with external LightRAG**:
```bash
# Set LIGHTRAG_URL in .env to your external instance first
docker compose up --build
```

4. **Access the UI**:
```bash
# Local access
http://localhost:3003

# Or from another device on your network (if LAN discovery enabled)
http://192.168.0.XXX:3003
```

## What's Running?

With `docker compose --profile lightrag up`:

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 3003 | React/Next.js web UI |
| Backend API | 8000 | FastAPI REST API |
| Redis | 6380 | Task queue |
| Celery Worker | - | Background processing |
| **LightRAG** | **9621** | **Vector DB & RAG (optional profile)** |

Without `--profile lightrag`, all services except LightRAG will start.

## Quick Configuration Examples

### Minimal Setup (Just Works™)
```bash
# .env file
LLAMA_CPP_URL=http://192.168.0.118:11434
```

That's it! LightRAG will automatically use your Ollama server.

### Performance Tuning
```bash
# Use faster models for LightRAG
LIGHTRAG_LLM_MODEL=llama3.1:8b
LIGHTRAG_EMBEDDING_MODEL=nomic-embed-text

# Tune RAG performance
LIGHTRAG_TOP_K=100
LIGHTRAG_COSINE_THRESHOLD=0.3
LIGHTRAG_CHUNK_SIZE=1500
```

### Using External LightRAG
```bash
# In .env - point to your external instance
LIGHTRAG_URL=http://my-lightrag-server:9621
LIGHTRAG_API_KEY=my-secret-key

# Start without --profile lightrag flag
docker compose up --build
```

### LAN Access (Access from Other Devices)
```bash
# Enable LAN discovery
ENABLE_LAN_DISCOVERY=true
HOST_IP=192.168.0.53

# Now access from any device on your network:
# http://192.168.0.53:3003
```

## Verifying Everything Works

1. **Check all services are running**:
```bash
docker compose ps
```

You should see all services with status `Up` and `healthy`.

2. **Test the API**:
```bash
curl http://localhost:8000/health
# Should return: {"status": "ok"}
```

3. **Access the UI**:
Open `http://localhost:3003` in your browser.

4. **Generate your first ADR**:
- Click "Generate New ADR"
- Enter a prompt like: "Should we use PostgreSQL or MongoDB for our new service?"
- Select personas to analyze from
- Click "Generate"
- Watch the task progress!

## Troubleshooting

### LightRAG Won't Start

**Problem**: `docker compose logs lightrag` shows connection errors

**Solution**: Check that your `LLAMA_CPP_URL` is accessible from Docker:
```bash
# Test from your host
curl http://192.168.0.118:11434/api/tags

# If that works but Docker can't connect, you might need to use your actual IP
# instead of localhost
```

### Backend Can't Connect to LightRAG

**Problem**: Backend logs show LightRAG connection errors

**Solution**: 
1. Verify LightRAG is healthy: `docker compose ps`
2. Check it's using the right URL. When using docker-compose, the backend should use:
   ```bash
   LIGHTRAG_URL=http://lightrag:9621  # Service name, not localhost!
   ```

### Frontend Can't Connect to Backend

**Problem**: UI shows connection errors

**Solution**:
1. Check backend is running: `curl http://localhost:8000/health`
2. Verify frontend can reach it:
   ```bash
   # Check frontend logs
   docker compose logs frontend
   ```

### Out of Memory Errors

**Problem**: Services crash with OOM errors

**Solution**: Reduce context windows in `.env`:
```bash
LIGHTRAG_LLM_NUM_CTX=32000
LIGHTRAG_EMBEDDING_NUM_CTX=2048
```

## Next Steps

- **Read the full docs**: [README.md](../README.md)
- **LightRAG configuration**: [LIGHTRAG_DOCKER_COMPOSE.md](LIGHTRAG_DOCKER_COMPOSE.md)
- **Multi-backend setup**: [PARALLEL_PROCESSING.md](PARALLEL_PROCESSING.md)
- **LAN access**: [LAN_DISCOVERY.md](LAN_DISCOVERY.md)
- **Testing guide**: [TESTING.md](TESTING.md)

## Common Workflows

### Daily Development
```bash
# Start services
docker compose up

# Make changes to code...

# Services auto-reload! Just refresh your browser

# View logs
docker compose logs -f backend
docker compose logs -f celery_worker

# Stop everything
docker compose down
```

### Reset Everything
```bash
# Stop and remove all data
docker compose down -v

# Start fresh
docker compose up --build
```

### Update to Latest
```bash
git pull
docker compose down
docker compose up --build
```

## Performance Tips

1. **Use multiple Ollama servers** for better parallel processing:
   ```bash
   LLAMA_CPP_URL=http://server1:11434
   LLAMA_CPP_URL_1=http://server2:11434
   LLAMA_CPP_URL_EMBEDDING=http://server3:11434
   ```

2. **Use dedicated servers for LightRAG**:
   ```bash
   LIGHTRAG_LLM_HOST=http://fast-server:11434
   LIGHTRAG_EMBEDDING_HOST=http://embedding-server:11434
   ```

3. **Tune chunk sizes** for your use case:
   ```bash
   # Larger chunks = better context, slower processing
   LIGHTRAG_CHUNK_SIZE=2000
   
   # Smaller chunks = faster, might miss context
   LIGHTRAG_CHUNK_SIZE=800
   ```

4. **Adjust retrieval parameters**:
   ```bash
   # More results = better context, slower
   LIGHTRAG_TOP_K=100
   
   # Stricter threshold = fewer results, faster
   LIGHTRAG_COSINE_THRESHOLD=0.4
   ```

## Getting Help

- Check logs: `docker compose logs [service-name]`
- Review documentation in `docs/`
- Check GitHub issues
- Verify your `.env` configuration matches `.env.example`

Happy analyzing! 🚀
