# Decision Analyzer - AI Copilot Instructions

## Architecture Overview

This is a **multi-persona ADR (Architectural Decision Record) analysis and generation system** with async task processing. The architecture has 3 main layers:

1. **React/Next.js Frontend** (`frontend/`) - TypeScript UI on port 3000
2. **FastAPI Backend** (`src/api/`) - Python REST API on port 8000
3. **Celery Worker** (`src/celery_app.py`) - Async task processor with Redis queue

**Data Flow**: Frontend → FastAPI routes (`src/api/routes.py`) → Queue Celery tasks → Worker processes using LLM clients → Store results in LightRAG vector DB

## Critical Integration Points

### WebSocket Real-Time Communication (Cross-Process Architecture)

**Multi-Process Challenge**: FastAPI backend and Celery workers run in **separate processes** with separate memory spaces. Direct WebSocket communication from Celery workers is impossible.

**Solution**: Redis Pub/Sub for cross-process messaging

**Architecture**:
```
Celery Worker (process 1)
  ↓
  publish to Redis channel
  ↓
Redis Pub/Sub (websocket:broadcast)
  ↓
FastAPI listener (process 2)
  ↓
WebSocketManager.broadcast_*()
  ↓
Connected WebSocket clients
  ↓
Frontend React components
```

**Key Files**:
- `src/websocket_broadcaster.py` - Redis pub/sub broadcaster
  - `publish_upload_status()` - Celery workers call this to publish messages
  - `publish_cache_status()` - Broadcast cache rebuild status
  - `start_listening()` - FastAPI startup task to listen and forward messages
- `src/websocket_manager.py` - WebSocket connection manager (FastAPI process only)
  - Manages active WebSocket connections
  - `broadcast_upload_status()` - Send to all connected clients
  - `broadcast_cache_status()` - Send cache rebuild notifications
- `src/api/routes.py` - WebSocket endpoint `/ws/cache-status`
  - Clients connect here for real-time updates
  - Sends initial status on connection
  - Keeps connection alive with ping/pong
- `src/api/main.py` - Startup/shutdown lifecycle
  - Starts Redis listener on app startup
  - Cleans up on shutdown

**Pattern in Celery Tasks**:
```python
from src.websocket_broadcaster import get_broadcaster

async def _celery_task():
    broadcaster = get_broadcaster()
    await broadcaster.publish_upload_status(
        adr_id="...",
        status="processing",  # or "completed", "failed"
        message="..."
    )
```

**Frontend WebSocket Hook** (`frontend/src/hooks/useCacheStatusWebSocket.ts`):
- Connects to `ws://HOST:8000/api/v1/adrs/ws/cache-status`
- Sends ping every 30 seconds to keep connection alive
- Receives `cache_status` and `upload_status` messages
- Auto-reconnects with exponential backoff

**Message Types**:
- `cache_status`: `{type: "cache_status", is_rebuilding: bool, last_sync_time: float}`
- `upload_status`: `{type: "upload_status", adr_id: string, status: "processing"|"completed"|"failed", message?: string}`

**CRITICAL**: Never call `get_websocket_manager()` from Celery tasks - it will have `active_connections=0` because connections are in the FastAPI process. Always use `get_broadcaster()` instead.

### Task Queue Visibility (Real-Time Monitoring)

**Purpose**: Real-time WebSocket-based monitoring of Celery task queue with Redis-backed cross-process tracking.

**Architecture**: Replaced slow Celery inspect API (2-8 second blocking calls) with direct Redis queries for <10ms response times.

**Key Components**:
- `src/task_queue_monitor.py` - Redis-based task tracking
  - `get_queue_status()` - Instant queue stats: `redis.llen("celery")` for pending, `redis.hlen("queue:active_tasks")` for active
  - `track_task_started()` - Stores task JSON in Redis hash `"queue:active_tasks"` (async, broadcasts immediately)
  - `track_task_completed()` - Removes from Redis hash (async, broadcasts immediately)
  - `get_all_tasks()` - Returns all active tasks from Redis hash
- `src/queue_status_broadcaster.py` - Periodic background broadcaster (30s interval for supplementary updates)
- API endpoints: `/api/v1/queue/status`, `/api/v1/queue/tasks` (instant <10ms responses)

**Cross-Process Task Tracking**:
```python
# In Celery tasks (src/celery_app.py)
from src.task_queue_monitor import get_task_queue_monitor

async def _task():
    monitor = get_task_queue_monitor()
    
    # When task starts
    await monitor.track_task_started(
        task_id=self.request.id,
        task_name="generate_adr_task",
        args=("context",),
        kwargs={"personas": ["technical_lead"]}
    )
    
    # When task completes
    await monitor.track_task_completed(self.request.id)
```

**Frontend Integration**:
- `useTaskQueueWebSocket` hook - Receives real-time updates, tracks tasks in memory
- `QueueViewerModal` component - Shows all active tasks with elapsed time
- Badge on "View Queue" button updates instantly via WebSocket

**Redis Schema**:
- Queue length: `redis.llen("celery")` - Celery's default queue key
- Active tasks: `redis.hash("queue:active_tasks")` - Custom cross-process tracking
  - Key: task_id
  - Value: JSON with {task_id, task_name, status, args, kwargs, started_at}

**Message Types** (via Redis pub/sub → WebSocket):
- `queue_status`: `{type: "queue_status", total_tasks: int, active_tasks: int, pending_tasks: int, workers_online: int}`
- `task_status`: `{type: "task_status", task_id: str, task_name: str, status: "active"|"completed"|"failed", position: int|null, message: str}`

**Performance**: All queue operations <10ms (was 2000-8000ms with Celery inspect). Tasks broadcast status changes immediately on start/complete, plus periodic broadcaster every 30s for drift correction.

**CRITICAL**: Task tracking methods are **async** - must be awaited in Celery task async functions. Redis hash stores tasks cross-process, enabling FastAPI and Celery worker to share real-time task state.

### External Services (Network Dependencies)

#### LLM Services (LangChain-Based)
The system uses **LangChain's OpenAI-compatible ChatOpenAI** for maximum flexibility across providers:

**Supported Providers**:
- **Ollama** (local) - Default, runs on localhost:11434
- **llama.cpp server** - OpenAI-compatible mode
- **vLLM** - High-performance inference server
- **OpenRouter** - Access to 200+ commercial and open-source models
- **OpenAI** - GPT-4, GPT-3.5, etc.
- Any **OpenAI-compatible** endpoint

**Configuration** (LangChain-based):
- `LLM_BASE_URL` (required) - Primary endpoint (e.g., `http://localhost:11434` for Ollama)
- `LLM_MODEL` (required) - Model name (e.g., `gpt-oss:20b`)
- `LLM_API_KEY` (optional) - API key for cloud providers
- `LLM_BASE_URL_1` (optional) - Secondary endpoint for parallel processing
- `LLM_EMBEDDING_BASE_URL` (optional) - Dedicated endpoint for embeddings
- `LLM_PROVIDER` (optional) - Provider type: ollama, openai, openrouter, vllm, llama_cpp, custom

**Client Classes**:
- `LlamaCppClient` - Single LangChain ChatOllama/ChatOpenAI instance
- `LlamaCppClientPool` - Multiple instances for parallel requests
- Both use LangChain internally for provider-specific optimizations

**Migration Guide**: See `docs/LLM_PROVIDER_MIGRATION.md` for complete details

#### Other External Services
- **LightRAG Server** (`LIGHTRAG_URL`) - Vector database on port 9621, used by `LightRAGClient`
- **Redis** - Task queue and result backend on port 6379 (6380 externally in docker-compose)

**Important**: These services run on external IPs configured in docker-compose environment variables. Always use async context managers (`async with client:` or `async with pool:`) for these clients.

### Multi-Persona System with Parallel Processing
The core feature: analyze ADRs through different "personas" (technical lead, business analyst, security expert, etc.). **Fully config-driven** architecture:

**Persona Configuration**:
- JSON config files define focus areas and evaluation criteria
- **Default Personas**: Shipped in `config/personas/defaults/` directory (10 personas)
- **Custom Personas**: User-defined in `config/personas/` directory (mounted as Docker volume)
- Custom personas with same filename override defaults
- **Hot-Reload**: Personas loaded from filesystem on each API call (no caching)
- **Dynamic Discovery**: New JSON files automatically detected without restart

**Environment Variables**:
- `INCLUDE_DEFAULT_PERSONAS` (default: `true`) - Include shipped defaults
- `PERSONAS_CONFIG_DIR` (optional) - Override default config directory

**PersonaManager API** (`src/persona_manager.py`):
- `get_persona_config(persona_value: str) -> Optional[PersonaConfig]` - Load single persona
- `list_persona_values() -> List[str]` - Get all persona string identifiers
- `discover_all_personas() -> Dict[str, PersonaConfig]` - Scan filesystem for all personas
- **String-Based**: All functions use persona string values (e.g., `"technical_lead"`, `"architect"`)

**Deprecated**: `AnalysisPersona` enum in `src/models.py` is deprecated, maintained only for backwards compatibility with existing tests. Use strings in all new code.

**10 Default Personas**: technical_lead, business_analyst, risk_manager, architect, product_manager, customer_support, security_expert, devops_engineer, qa_engineer, philosopher

**Pattern**: Generate separate perspectives in parallel → synthesize into final ADR with all viewpoints considered. See `ADRGenerationService._generate_persona_perspectives()` in `src/adr_generation.py`.

**Performance**: When `LLAMA_CPP_URL_1` is configured, `LlamaCppClientPool` distributes persona generation requests across multiple backends, reducing generation time by ~50%.

**Customization**: See `config/personas/README.md` for instructions on adding custom personas.

## Critical Developer Workflows

### Starting the Full Stack
```bash
docker compose up --build  # Starts redis, backend API, celery worker, frontend
```

**Port Mapping**: External services use host network IPs (not localhost) in Docker environment. Check `docker-compose.yml` for `LLM_BASE_URL`, `LLM_BASE_URL_1`, `LLM_EMBEDDING_BASE_URL`, and `LIGHTRAG_URL` variables.

### Running Backend Only
```bash
./scripts/run_backend.sh  # Starts uvicorn with correct PYTHONPATH
```

### Testing
```bash
make test                      # Run all tests (backend + frontend)
make test-backend              # Run all backend tests
make test-backend-unit         # Backend unit tests only
make test-backend-integration  # Backend integration tests only
make test-frontend             # Run frontend tests
make test-coverage             # All tests with coverage
```

**Test Structure**: 
- **Backend**: Tests co-located in `src/*/tests/` directories (e.g., `src/tests/test_models.py`)
- **Frontend**: Tests alongside source files with `.test.tsx` extension (e.g., `ADRCard.test.tsx`)
- **Integration**: Tests in `tests/integration/` directory

**Test Patterns**:

*Backend (pytest):*
```python
# src/tests/test_example.py
import pytest
from unittest.mock import AsyncMock

class TestExample:
    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.__aexit__.return_value = None
        return client
    
    @pytest.mark.asyncio
    async def test_method(self, mock_client):
        # Arrange
        mock_client.generate.return_value = '{"data": "test"}'
        
        # Act
        result = await service.method()
        
        # Assert
        assert result is not None
        mock_client.generate.assert_awaited()
```

*Frontend (Vitest + React Testing Library):*
```tsx
// components/Example.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'

describe('Example', () => {
  it('handles interaction', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    
    render(<Example onClick={onClick} />)
    await user.click(screen.getByRole('button'))
    
    expect(onClick).toHaveBeenCalledOnce()
  })
})
```

**Mocking Strategy**: Mock everything - all external services (LLM, Vector DB, Redis, File I/O, HTTP requests).

**LangChain-Specific Mocking**:
```python
from unittest.mock import AsyncMock
from langchain_core.messages import AIMessage

# Mock LangChain ChatOpenAI responses
async with LlamaCppClient(demo_mode=False) as client:
    mock_response = AIMessage(content="Generated response")
    client._llm.ainvoke = AsyncMock(return_value=mock_response)
    
    result = await client.generate("Test prompt")
    assert result == "Generated response"
```

See `docs/TESTING.md` for comprehensive testing guide.

## Data Models and Conventions

### Core Model Hierarchy
```python
ADR (src/models.py)
├── metadata: ADRMetadata (id, title, status, author, tags)
└── content: ADRContent (context, options, decision, consequences)
    ├── consequences_structured: ConsequencesStructured (positive/negative lists)
    ├── options_details: List[OptionDetails] (name, pros, cons)
    └── referenced_adrs: List[Dict] (ADRs used during generation)
```

### Async Task Pattern (Celery)
```python
# In src/celery_app.py - tasks use nested async functions:
@celery_app.task(bind=True)
def generate_adr_task(self, ...):
    async def _generate():
        async with LlamaCppClient() as llama:
            # async work here
    return asyncio.run(_generate())
```

**Why**: Celery tasks must be sync functions, but our clients are async. Wrap async code in `asyncio.run()`.

### Consequences Parsing (Recent Bug Fix)
The `consequences` field is plain text from LLM with format:
```
Positive:
- item 1
- item 2

Negative:
- item 1
```

**Pattern in `celery_app.py`**: Parse this by splitting on newlines, strip bullet markers (`- `, `* `, `• `), populate `consequences_structured` for frontend rendering. See lines 182-223 for implementation.

## Frontend Conventions

### Component Structure
- `src/components/` - Reusable components (ADRModal, GenerateADRModal, PersonasModal)
- Custom hook: `useEscapeKey` for modal closure
- API client: `src/lib/api.ts` - centralized fetch wrapper

### Type Safety
All API types in `src/types/api.ts` must match backend Pydantic models. When backend models change, update TypeScript interfaces.

### Styling
Tailwind CSS with custom classes. Status colors defined inline (e.g., `getStatusColor()` in ADRModal).

### Dark Mode Support (CRITICAL)
**All new components and UI changes MUST support both light and dark modes.** The app uses Tailwind's `dark:` variant with system preference detection.

**Required Pattern for All Components**:
```tsx
// ✅ CORRECT - Always include dark: variants
<div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100">

// ❌ WRONG - Missing dark mode support
<div className="bg-white text-gray-900">
```

**Dark Mode Checklist for Every Component**:
- [ ] Backgrounds: `bg-white` → `dark:bg-gray-800` (modals/cards) or `bg-gray-50` → `dark:bg-gray-900` (pages)
- [ ] Text: `text-gray-900` → `dark:text-gray-100` (headings), `text-gray-700` → `dark:text-gray-300` (body)
- [ ] Borders: `border-gray-200` → `dark:border-gray-700`
- [ ] Input fields: `bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400`
- [ ] Hover states: Include `dark:hover:` variants for all interactive elements
- [ ] Semi-transparent overlays: `bg-opacity-50 dark:bg-opacity-70`

**Color Patterns**:
- **Status badges**: Use semi-transparent backgrounds (e.g., `bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300`)
- **Colored backgrounds**: Use `/{opacity}` syntax for dark mode (e.g., `dark:bg-blue-900/20`)
- **Gray scale**: Light mode uses 50-900, dark mode inverts (100→900, 900→100)

**Common Component Patterns**:
```tsx
// Modal backdrop
<div className="fixed inset-0 bg-black bg-opacity-50 dark:bg-opacity-70">

// Modal/Card container
<div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700">

// Headings
<h2 className="text-gray-900 dark:text-gray-100">

// Body text
<p className="text-gray-700 dark:text-gray-300">

// Muted text
<span className="text-gray-500 dark:text-gray-400">

// Input fields
<input className="bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400" />

// Buttons (neutral)
<button className="bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600">
```

**Testing Dark Mode**: Toggle system dark mode and verify all UI elements are readable and properly styled in both modes.

**Reference Implementation**: See `GenerateADRModal.tsx`, `ADRModal.tsx`, `ADRCard.tsx` for complete dark mode patterns.

## LLM Prompt Engineering Patterns

### Structured JSON Responses
Always request JSON from LLM with explicit schema in prompt. Example from `adr_generation.py`:

```python
prompt = """You must respond with a JSON object containing:
{
  "title": "...",
  "context_and_problem": "...",
  ...
}"""
```

### Parsing Robustness
```python
# Pattern: Extract JSON from markdown code blocks
import re
json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
if json_match:
    data = json.loads(json_match.group(1))
```

See `_parse_synthesis_response()` in `adr_generation.py` for full implementation.

### Text Formatting Polish
After LLM generation, use `_polish_formatting()` and `_apply_formatting_cleanup()` to fix:
- Line breaks in phrases (e.g., "GPU\nRAM" → "GPU, RAM")
- Non-breaking hyphens (‑ → -)
- Bullet point consistency

## Configuration Management

### Settings Pattern
All config via `src/config.py` using `pydantic-settings`:
```python
from src.config import get_settings
settings = get_settings()  # Loads from env vars
```

### Environment Variables
- Development: `.env` (root) and `frontend/.env.local`
- Docker: `docker-compose.yml` environment section
- Required: `LLM_BASE_URL`, `LIGHTRAG_URL`, `REDIS_URL`
- Optional: `LLM_BASE_URL_1` (secondary backend), `LLM_EMBEDDING_BASE_URL` (embedding backend)

## Storage and File Handling

### ADR Storage
ADRs stored as JSON files in `data/adrs/` (volume mounted in Docker). File operations use `aiofiles` for async I/O.

**Pattern**: `ADRFileStorage` class manages CRUD operations. Always use `async with` for file operations.

### LightRAG Vector Storage
Documents stored with `doc_id` as ADR UUID. Content includes:
- Full ADR text
- Metadata for semantic search
- Used by `_get_related_context()` during generation to find relevant past decisions

## Common Pitfalls

1. **Async Context Managers**: Always use `async with client:` or `async with pool:` - clients need proper session cleanup. Works with both `LlamaCppClient` and `LlamaCppClientPool`
2. **PYTHONPATH**: Backend expects `PYTHONPATH=/app/src` in Docker, `./src` locally
3. **Port Conflicts**: Frontend uses 3003 in package.json, docker-compose uses 3000 externally
4. **Celery Tasks**: Must be sync functions wrapping async code with `asyncio.run()`
5. **JSON Parsing**: LLMs sometimes wrap JSON in markdown - always extract with regex first

## Key Files Reference

- `src/models.py` - All Pydantic data models, enums
- `src/adr_generation.py` - Core generation service with persona orchestration and parallel processing
- `src/llama_client.py` - LLM client and client pool for parallel requests
- `src/celery_app.py` - Task definitions, consequences parsing logic, task tracking integration
- `src/api/routes.py` - All REST endpoints including queue management
- `src/task_queue_monitor.py` - Redis-based task queue monitoring (replaces slow Celery inspect)
- `src/websocket_broadcaster.py` - Redis pub/sub for cross-process WebSocket messages
- `src/websocket_manager.py` - WebSocket connection manager (FastAPI process only)
- `config/personas/*.json` - Persona configurations
- `docker-compose.yml` - Service definitions and network config
- `docs/PARALLEL_PROCESSING.md` - Multi-backend configuration guide
- `docs/TASK_QUEUE_VISIBILITY.md` - Task queue monitoring implementation details
